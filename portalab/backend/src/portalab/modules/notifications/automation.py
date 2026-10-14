"""``communication.produce`` (T024; R1): the Automations (019) action that produces a communication through
the same producer — under the **author's** authority (the automation principal acts for its author), with
the trigger's dedup key. 010 contains no rule engine."""

from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update

from portalab.capabilities.automation_actions import ActionRegistry, ActionType, default_actions
from portalab.capabilities.notifications import (
    AllAuthenticated,
    AudienceSpec,
    CommunicationRef,
    CommunicationRequest,
    Role,
    Users,
    WithPermission,
)
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.notifications.models import Announcement
from portalab.modules.notifications.permissions import NOTIFICATIONS_BROADCAST, SEND_TO_AUDIENCE

KEY = "communication.produce"
Send = Callable[[CommunicationRequest, Principal | None], Awaitable[CommunicationRef]]


def parse_audience(raw: Mapping[str, Any]) -> AudienceSpec:
    kind = raw.get("type")
    if kind == "users":
        return Users(tuple(UUID(str(u)) for u in raw.get("ids", [])))
    if kind == "permission":
        return WithPermission(str(raw["permission"]))
    if kind == "role":
        return Role(str(raw["role"]))
    if kind == "all":
        return AllAuthenticated()
    raise ValidationFailed("Unknown audience.", code="notifications.invalid")


def register_action(send: Send, registry: ActionRegistry = default_actions) -> None:
    async def run(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        ref = await send(
            CommunicationRequest(
                category=str(params["category"]),
                template_key=str(params["template_key"]),
                audience=parse_audience(params["audience"]),
                dedup_key=str(params["dedup_key"]),
                kind=params.get("kind", "notification"),
                priority=params.get("priority", "normal"),
                params=dict(params.get("params") or {}),
                source="automation",
                source_ref=str(params.get("rule", "")) or None,
                action_url=params.get("action_url"),
            ),
            principal,
        )
        return {"communication": str(ref.id), "created": ref.created, "recipients": ref.recipients}

    if registry.get(KEY) is None:
        registry.register(
            ActionType(
                key=KEY,
                description="Send a notification or alert to an audience",
                permission=SEND_TO_AUDIENCE,
                idempotency="dedup_key from the trigger: one communication per (source, dedup_key)",
                run=run,
                owner="module:notifications",
                required=("category", "template_key", "audience", "dedup_key"),
                ai_output_allowed=True,
                params_schema={
                    "category": "string",
                    "template_key": "string",
                    "audience": "object {type: users|permission|role|all, …}",
                    "dedup_key": "string",
                    "kind": "notification|alert",
                    "priority": "low|normal|high|critical",
                    "params": "object? (template values)",
                    "action_url": "string? (in-portal route)",
                    "rule": "string? (source reference)",
                },
            )
        )


BANNER_SHOW = "announcement.banner"
BANNER_END = "announcement.end"
TONES = ("info", "success", "warning", "critical")


def register_banner_actions(database: Database, clock: Clock | None, registry: ActionRegistry) -> None:
    """Issue 122: an automation shows a banner across the portal under a ``tag`` — once: a banner with
    that tag still up is updated, not doubled — and takes it down when the thing is over."""

    async def show(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        tag = str(params["tag"])[:64]
        tone = str(params.get("tone") or "info")
        if tone not in TONES:
            raise ValidationFailed("Unknown tone.", code="notifications.invalid")
        now = utc_now(clock)
        minutes = params.get("minutes")
        until = now + timedelta(minutes=int(minutes)) if minutes else None
        async with database.unit_of_work() as uow:
            row = await uow.session.scalar(
                select(Announcement)
                .where(
                    Announcement.tag == tag, Announcement.banner.is_(True), Announcement.ended_at.is_(None)
                )
                .order_by(Announcement.created_at.desc())
                .limit(1)
                .with_for_update()
            )
            if row is None:
                row = Announcement(
                    tag=tag, channels=["banner"], banner=True, recipients=0, created_at=now, created_by=None
                )
                uow.session.add(row)
            row.title = str(params["title"])[:200]
            row.body = str(params.get("body") or "")[:2000]
            row.link = str(params["link"])[:256] if params.get("link") else None
            row.tone, row.banner_until = tone, until
            await uow.session.flush()
            return {"announcement": str(row.id), "tag": tag}

    async def end(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        tag = str(params["tag"])[:64]
        async with database.unit_of_work() as uow:
            result = await uow.session.execute(
                update(Announcement)
                .where(Announcement.tag == tag, Announcement.ended_at.is_(None))
                .values(ended_at=utc_now(clock))
            )
        return {"ended": int(getattr(result, "rowcount", 0) or 0), "tag": tag}

    if registry.get(BANNER_SHOW) is None:
        registry.register(
            ActionType(
                key=BANNER_SHOW,
                description="Show a banner across the portal (one per tag: shown again, it is updated)",
                permission=NOTIFICATIONS_BROADCAST,
                idempotency="one banner up per tag: a second one updates it",
                run=show,
                owner="module:notifications",
                required=("tag", "title"),
                ai_output_allowed=True,
                params_schema={
                    "tag": "string (names the banner, to end it)",
                    "title": "string",
                    "body": "string?",
                    "tone": "info|success|warning|critical",
                    "link": "string? (in-portal route)",
                    "minutes": "integer? (ends by itself after)",
                },
                summarize=lambda p: f"Banner « {p.get('title', '')} »"[:300],
            )
        )
    if registry.get(BANNER_END) is None:
        registry.register(
            ActionType(
                key=BANNER_END,
                description="Take down the banner shown under a tag",
                permission=NOTIFICATIONS_BROADCAST,
                idempotency="ending an ended banner does nothing",
                run=end,
                owner="module:notifications",
                required=("tag",),
                params_schema={"tag": "string"},
            )
        )
