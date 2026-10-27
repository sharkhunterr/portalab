"""Notifications API (T012, T016, T024, T026, T027): the user's notification center and preferences, the
category list, and administration (broadcast, e-mail transport, category policy, delivery metadata)."""

import html
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, delete, func, select, update

from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.notifications import AllAuthenticated, CommunicationRequest, EmailMessage
from portalab.capabilities.search.fts import decode_cursor, encode_cursor
from portalab.core.audit_port import AuditRecord
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import NotFound, Unavailable, ValidationFailed
from portalab.core.time import utc_now
from portalab.modules.notifications.fanout.merge import rewards_of
from portalab.modules.notifications.models import Announcement, Communication, Delivery, Notification
from portalab.modules.notifications.module import NotificationsModule
from portalab.modules.notifications.permissions import NOTIFICATIONS_BROADCAST, NOTIFICATIONS_MANAGE, SELF
from portalab.modules.notifications.preferences.resolver import MandatoryChannel, decide, validate_update
from portalab.modules.notifications.settings import (
    CATEGORY_POLICY,
    DIGEST,
    PREFERENCES,
    SETTINGS,
    SMTP_PASSWORD,
)

router = APIRouter(prefix="/api/v1", tags=["notifications"])
PAGE = 30


def notifications_module(request: Request) -> NotificationsModule:
    module = getattr(request.app.state, "notifications_module", None)
    if not isinstance(module, NotificationsModule):
        raise Unavailable("Notifications are not available.", code="notifications.unavailable")
    return module


Module = Annotated[NotificationsModule, Depends(notifications_module)]
User = Annotated[Principal, require(SELF)]
Manager = Annotated[Principal, require(NOTIFICATIONS_MANAGE)]
Broadcaster = Annotated[Principal, require(NOTIFICATIONS_BROADCAST)]


class NotificationRewardOut(BaseModel):
    value: str  # xp | coins | contribution
    amount: int


class NotificationOut(BaseModel):
    id: UUID
    kind: Literal["notification", "alert"]
    category: str
    priority: Literal["low", "normal", "high", "critical"]
    title: str
    body: str
    count: int
    action_url: str | None
    read: bool
    archived: bool
    created_at: str
    updated_at: str
    # issue 186: what the notification is about (a quest, an achievement, why a gain) and what it brought,
    # apart from its title — shown as a subtitle and as badges
    subtitle: str | None = None
    rewards: list[NotificationRewardOut] = Field(default_factory=list)
    boost: str | None = None


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    next_cursor: str | None
    unread: int


class ChannelStateOut(BaseModel):
    enabled: bool
    mandatory: bool
    locked: bool


class CategoryPreferenceOut(BaseModel):
    key: str
    label_key: str
    user_mutable: bool
    channels: dict[str, ChannelStateOut]


class NotificationPreferencesOut(BaseModel):
    categories: list[CategoryPreferenceOut]
    digest: Literal["off", "daily", "weekly"]


class NotificationPreferencesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferences: dict[str, dict[str, bool]] = Field(default_factory=dict)
    digest: Literal["off", "daily", "weekly"] | None = None


Channel = Literal["notification", "email", "banner"]
DEFAULT_CHANNELS: tuple[Channel, ...] = ("notification",)


class BroadcastIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(default="", max_length=2000)
    priority: Literal["low", "normal", "high", "critical"] = "normal"
    kind: Literal["notification", "alert"] = "notification"
    dedup_key: str = Field(min_length=3, max_length=120)
    action_url: str | None = Field(default=None, max_length=256, pattern=r"^/[A-Za-z0-9/_:.\-?=&]*$")
    # 027: where it goes — any of a notification, an e-mail, a banner across the portal (until a date)
    channels: list[Channel] = Field(
        default_factory=lambda: list(DEFAULT_CHANNELS), min_length=1, max_length=3
    )
    banner_until: datetime | None = None
    banner_dismissible: bool = True  # whether each member may close the banner
    tone: Literal["info", "success", "warning", "critical"] = "info"


class AnnouncementOut(BaseModel):
    id: UUID
    title: str
    body: str
    link: str | None
    tone: str
    channels: list[str]
    banner: bool
    banner_until: datetime | None
    dismissible: bool
    recipients: int
    created_at: datetime
    ended_at: datetime | None


def _announcement_out(row: Announcement) -> AnnouncementOut:
    return AnnouncementOut(
        id=row.id,
        title=row.title,
        body=row.body,
        link=row.link,
        tone=row.tone,
        channels=list(row.channels or []),
        banner=row.banner,
        banner_until=row.banner_until,
        dismissible=row.dismissible,
        recipients=row.recipients,
        created_at=row.created_at,
        ended_at=row.ended_at,
    )


def _email_of(body: BroadcastIn) -> dict[str, str]:
    text = body.body + (f"\n\n{body.action_url}" if body.action_url else "")
    paragraphs = "".join(f"<p>{html.escape(p)}</p>" for p in body.body.split("\n\n") if p.strip())
    return {
        "subject": body.title,
        "text": text,
        "html": f"<h1>{html.escape(body.title)}</h1>{paragraphs}",
    }


class EmailConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    sender: str = Field(min_length=3, max_length=200)
    host: str = Field(min_length=1, max_length=200)
    port: int = Field(ge=1, le=65535)
    tls: bool = False
    username: str = Field(default="", max_length=200)
    password: str | None = Field(default=None, max_length=500)  # write-only; None keeps the stored one
    # 027: the portal's public address, for the links of e-mails (newsletters…); None keeps the stored one
    portal_url: str | None = Field(default=None, max_length=300, pattern=r"^(https?://[^\s]+)?$")


class CategoryPolicyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mandatory_channels: list[Literal["portal", "email"]] = Field(default_factory=list)
    disabled_channels: list[Literal["portal", "email"]] = Field(default_factory=list)
    locked: bool = False


SUBJECTS = ("quest", "achievement", "product", "item", "reason")


def _details(params: Mapping[str, Any] | None) -> dict[str, Any]:
    """Issue 186: the subtitle, the rewards and a boost, read from the communication's parameters."""
    if not params:
        return {}
    subtitle = next(
        (
            str(params[key]).strip()[:160]
            for key in SUBJECTS
            if isinstance(params.get(key), str) and params[key].strip() and params[key] != "none"
        ),
        None,
    )
    rewards = [
        NotificationRewardOut(value=value, amount=int(amount))
        for value, amount in rewards_of(params).items()
        if amount > 0
    ]
    boost = params.get("boost")
    return {
        "subtitle": subtitle,
        "rewards": rewards,
        "boost": str(boost)
        if isinstance(boost, str | int | float) and str(boost) not in ("", "none")
        else None,
    }


def _out(
    row: Notification, params: Mapping[str, Any] | None = None, text: tuple[str, str] | None = None
) -> NotificationOut:
    title, body = text or (row.title, row.body)
    return NotificationOut(
        **_details(params),
        id=row.id,
        kind=row.kind,
        category=row.category,
        priority=row.priority,
        title=title,
        body=body,
        count=row.count,
        action_url=row.action_url,
        read=row.read_at is not None,
        archived=row.archived_at is not None,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


async def _texts(
    module: NotificationsModule, user: UUID, lang: str | None, sources: Sequence[tuple[UUID, str, Any]]
) -> dict[UUID, tuple[str, str]]:
    """Issue 242: a notification's title and text in the reader's language of now — written once at its
    delivery, they stayed in the language of then (or the portal's default, English, for everyone)."""
    if not sources:
        return {}
    ctx = await module.fanout.locale(user)
    if lang:  # the interface's language, when it is not the account's (the guide's screenshots)
        ctx = replace(ctx, language=lang)
    texts: dict[UUID, tuple[str, str]] = {}
    for ident, template, params in sources:
        title, body = module.fanout.render(template, params or {}, ctx)
        if title and title != template.partition(":")[2]:  # rendered (else the stored text stays)
            texts[ident] = (title, body)
    return texts


async def _unread(module: NotificationsModule, user: UUID) -> int:
    async with module.database.session() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.user_id == user,
                    Notification.read_at.is_(None),
                    Notification.archived_at.is_(None),
                )
            )
            or 0
        )


@router.get("/me/notifications", response_model=NotificationPage)
async def my_notifications(
    principal: User,
    module: Module,
    cursor: Annotated[str | None, Query(max_length=128)] = None,
    category: Annotated[str | None, Query(max_length=96)] = None,
    kind: Annotated[Literal["notification", "alert"] | None, Query()] = None,
    unread: bool = False,
    archived: bool = False,
    lang: Annotated[str | None, Query(max_length=35)] = None,
) -> NotificationPage:
    assert principal.user_id is not None
    user = principal.user_id
    offset = decode_cursor(cursor)
    stmt = select(Notification).where(
        Notification.user_id == user,
        Notification.archived_at.is_not(None) if archived else Notification.archived_at.is_(None),
    )
    if category:
        stmt = stmt.where(Notification.category == category)
    if kind:
        stmt = stmt.where(Notification.kind == kind)
    if unread:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = (
        stmt.order_by(
            (Notification.read_at.is_(None)).desc(),
            Notification.priority_rank.desc(),
            Notification.updated_at.desc(),
        )
        .offset(offset)
        .limit(PAGE + 1)
    )
    async with module.database.session() as session:
        rows = (await session.execute(stmt)).scalars().all()
        sources = {r.communication_id for r in rows[:PAGE]}
        found: list[tuple[UUID, str, Any]] = []
        if sources:
            found = [
                (ident, template, values)
                for ident, template, values in (
                    await session.execute(
                        select(Communication.id, Communication.template_key, Communication.params).where(
                            Communication.id.in_(sources)
                        )
                    )
                ).all()
            ]
    sent = {ident: (template, values) for ident, template, values in found}
    # issue 258: a series merged into one item says what it brought in all (its merged parameters)
    shown: list[tuple[UUID, str, Any]] = []
    for r in rows[:PAGE]:
        if r.communication_id in sent:
            template, values = sent[r.communication_id]
            shown.append((r.id, template, r.params if r.params is not None else values))
    params: dict[UUID, Mapping[str, Any]] = {ident: values for ident, _, values in shown}
    texts = await _texts(module, user, lang, shown)
    return NotificationPage(
        items=[_out(r, params.get(r.id), texts.get(r.id)) for r in rows[:PAGE]],
        next_cursor=encode_cursor(offset + PAGE) if len(rows) > PAGE else None,
        unread=await _unread(module, user),
    )


@router.get("/me/notifications/unread-count")
async def unread_count(principal: User, module: Module) -> dict[str, int]:
    assert principal.user_id is not None
    return {"unread": await _unread(module, principal.user_id)}


async def _own(module: NotificationsModule, user: UUID, notification_id: UUID) -> Notification:
    async with module.database.session() as session:
        row = await session.get(Notification, notification_id)
    if row is None or row.user_id != user:
        raise NotFound("This notification does not exist.", code="notifications.not_found")
    return row


@router.post("/me/notifications/read-all")
async def read_all(principal: User, module: Module) -> dict[str, int]:
    assert principal.user_id is not None
    return {"read": await module.fanout.mark_read(principal.user_id, None)}


class BulkIn(BaseModel):
    """#112: one action on several of my notifications at once (the panel's selection)."""

    model_config = ConfigDict(extra="forbid")
    ids: list[UUID] = Field(min_length=1, max_length=500)
    action: Literal["read", "archive", "unarchive", "delete"]


@router.post("/me/notifications/bulk")
async def bulk(principal: User, body: BulkIn, module: Module) -> dict[str, int]:
    """#112: mark read, archive, bring back from the archive or delete several notifications — mine only
    (another member's ids are ignored); how many changed."""
    assert principal.user_id is not None
    user = principal.user_id
    if body.action == "read":
        return {"done": await module.fanout.mark_read(user, body.ids)}
    mine = and_(Notification.user_id == user, Notification.id.in_(body.ids))
    now = utc_now(module.clock)
    async with module.database.unit_of_work() as uow:
        if body.action == "delete":
            result = await uow.session.execute(delete(Notification).where(mine))
        elif body.action == "archive":
            result = await uow.session.execute(
                update(Notification)
                .where(mine, Notification.archived_at.is_(None))
                .values(archived_at=now, read_at=func.coalesce(Notification.read_at, now))
            )
        else:
            result = await uow.session.execute(
                update(Notification)
                .where(mine, Notification.archived_at.is_not(None))
                .values(archived_at=None)
            )
    return {"done": int(getattr(result, "rowcount", 0) or 0)}


@router.post("/me/notifications/{notification_id}/read", response_model=NotificationOut)
async def read_one(principal: User, notification_id: UUID, module: Module) -> NotificationOut:
    assert principal.user_id is not None
    row = await _own(module, principal.user_id, notification_id)
    if row.read_at is None:
        await module.fanout.mark_read(principal.user_id, [notification_id])
        now = utc_now(module.clock)
        async with module.database.unit_of_work() as uow:
            await module.events.publish(
                uow.session,
                "notification.read",
                {"notification": str(notification_id)},
                occurred_at=now,
                actor=principal,
                source="notifications",
                dedup_key=f"notification.read:{notification_id}",
            )
    return _out(await _own(module, principal.user_id, notification_id))


@router.post("/me/notifications/{notification_id}/archive", response_model=NotificationOut)
async def archive(principal: User, notification_id: UUID, module: Module) -> NotificationOut:
    assert principal.user_id is not None
    await _own(module, principal.user_id, notification_id)
    now = utc_now(module.clock)
    async with module.database.unit_of_work() as uow:
        await uow.session.execute(
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == principal.user_id)
            .values(archived_at=now, read_at=func.coalesce(Notification.read_at, now))
        )
    return _out(await _own(module, principal.user_id, notification_id))


@router.delete("/me/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_one(principal: User, notification_id: UUID, module: Module) -> Response:
    assert principal.user_id is not None
    await _own(module, principal.user_id, notification_id)
    async with module.database.unit_of_work() as uow:
        await uow.session.execute(
            delete(Notification).where(
                and_(Notification.id == notification_id, Notification.user_id == principal.user_id)
            )
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _setting(module: NotificationsModule, key: str, user: UUID | None, default: Any) -> Any:
    providers = module.capabilities.system_providers(CONFIG)
    if not providers:
        return default
    try:
        return (await providers[0].provider.get(key, user_id=user)).value
    except Exception:
        return default


@router.get("/me/notification-preferences", response_model=NotificationPreferencesOut)
async def get_preferences(principal: User, module: Module) -> NotificationPreferencesOut:
    assert principal.user_id is not None
    preferences = await _setting(module, PREFERENCES, principal.user_id, {})
    digest = await _setting(module, DIGEST, principal.user_id, "off")
    policies = module.config.category_policy or {}
    categories = []
    for category in module.categories.all():
        decisions = decide(category, preferences or {}, policies.get(category.key, {}))
        categories.append(
            CategoryPreferenceOut(
                key=category.key,
                label_key=category.label_key,
                user_mutable=category.user_mutable,
                channels={
                    name: ChannelStateOut(enabled=d.enabled, mandatory=d.mandatory, locked=d.locked)
                    for name, d in decisions.items()
                },
            )
        )
    return NotificationPreferencesOut(
        categories=categories, digest=digest if digest in ("off", "daily", "weekly") else "off"
    )


@router.put("/me/notification-preferences", response_model=NotificationPreferencesOut)
async def put_preferences(
    principal: User, body: NotificationPreferencesIn, module: Module
) -> NotificationPreferencesOut:
    try:
        validate_update(
            {c.key: c for c in module.categories.all()}, module.config.category_policy or {}, body.preferences
        )
    except MandatoryChannel as exc:
        raise ValidationFailed(str(exc), code="notifications.mandatory_channel") from exc
    providers = module.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
    if not providers:
        raise Unavailable("Preferences are not available.", code="admin.unavailable")
    writer = providers[0].provider
    current = await _setting(module, PREFERENCES, principal.user_id, {}) or {}
    merged = {
        **current,
        **{key: {**current.get(key, {}), **channels} for key, channels in body.preferences.items()},
    }
    await writer.set_user(principal, PREFERENCES, merged)
    if body.digest is not None:
        await writer.set_user(principal, DIGEST, body.digest)
    return await get_preferences(principal, module)


@router.get("/notifications/categories")
async def categories(_: User, module: Module) -> list[dict[str, Any]]:
    policies = module.config.category_policy or {}
    return [
        {
            "key": c.key,
            "label_key": c.label_key,
            "default_priority": c.default_priority,
            "default_channels": list(c.default_channels),
            "mandatory_channels": sorted(
                set(c.mandatory_channels) | set((policies.get(c.key) or {}).get("mandatory_channels") or ())
            ),
            "user_mutable": c.user_mutable and not (policies.get(c.key) or {}).get("locked"),
        }
        for c in module.categories.all()
    ]


async def _audit(
    module: NotificationsModule, principal: Principal, action: str, resource: str, context: dict[str, Any]
) -> None:
    async with module.database.unit_of_work() as uow:
        await module.audit.record(
            uow.session,
            AuditRecord(
                action=action,
                actor=principal,
                resource=ResourceRef("notifications", resource),
                decision="allow",
                result="success",
                context=context,
                sensitive=True,
            ),
        )


@router.post("/admin/notifications/broadcast")
async def broadcast(principal: Broadcaster, body: BroadcastIn, module: Module) -> dict[str, Any]:
    if body.kind == "alert" and body.priority not in ("high", "critical"):
        raise ValidationFailed("An alert has priority high or critical.", code="notifications.invalid")
    now = utc_now(module.clock)
    if "banner" in body.channels and body.banner_until is not None and body.banner_until <= now:
        raise ValidationFailed("A banner ends in the future.", code="notifications.invalid")
    channels = list(dict.fromkeys(body.channels))
    recipients, created, reference = 0, True, None
    if "notification" in channels:
        ref = await module.send(
            CommunicationRequest(
                category="communications.broadcast",
                template_key="notifications:broadcast.message",
                audience=AllAuthenticated(),
                dedup_key=body.dedup_key,
                kind=body.kind,
                priority=body.priority,
                params={"title": body.title, "body": body.body},
                source="admin_rule",
                action_url=body.action_url,
            ),
            caller=principal,
        )
        recipients, created, reference = ref.recipients, ref.created, ref.id
    if "email" in channels:
        mail = await module.send(
            CommunicationRequest(
                category="communications.announcement_email",
                template_key="notifications:broadcast.message",
                audience=AllAuthenticated(),
                dedup_key=f"{body.dedup_key}:email",
                priority=body.priority,
                params={"title": body.title, "body": body.body},
                source="admin_rule",
                action_url=body.action_url,
                email_body=_email_of(body),
            ),
            caller=principal,
        )
        recipients = max(recipients, mail.recipients)
        reference = reference or mail.id
    async with module.database.unit_of_work() as uow:
        row = Announcement(
            title=body.title,
            body=body.body,
            link=body.action_url,
            tone=body.tone,
            channels=channels,
            banner="banner" in channels,
            banner_until=body.banner_until if "banner" in channels else None,
            dismissible=body.banner_dismissible,
            recipients=recipients,
            created_by=principal.acting_for or principal.user_id,
            created_at=now,
        )
        uow.session.add(row)
        await uow.session.flush()
        announcement = row.id
    await _audit(
        module,
        principal,
        "notifications.broadcast",
        str(reference or announcement),
        {"recipients": recipients, "created": created, "channels": channels},
    )
    return {
        "communication": str(reference) if reference else None,
        "announcement": str(announcement),
        "created": created,
        "recipients": recipients,
    }


@router.get("/admin/announcements", response_model=list[AnnouncementOut])
async def announcements(_: Broadcaster, module: Module) -> list[AnnouncementOut]:
    """027: the latest announcements and how they went out."""
    async with module.database.session() as session:
        rows = (
            await session.execute(
                select(Announcement)
                .order_by(Announcement.created_at.desc(), Announcement.id.desc())
                .limit(50)
            )
        ).scalars()
        return [_announcement_out(r) for r in rows]


@router.post("/admin/announcements/{announcement_id}/end", response_model=AnnouncementOut)
async def end_announcement(principal: Broadcaster, announcement_id: UUID, module: Module) -> AnnouncementOut:
    """027: take a banner down now."""
    async with module.database.unit_of_work() as uow:
        row = await uow.session.get(Announcement, announcement_id, with_for_update=True)
        if row is None:
            raise NotFound("This announcement does not exist.", code="notifications.not_found")
        if row.ended_at is None:
            row.ended_at = utc_now(module.clock)
        return _announcement_out(row)


@router.get("/announcements/banners", response_model=list[AnnouncementOut])
async def banners(_: User, module: Module) -> list[AnnouncementOut]:
    """027: announcements shown as a banner right now."""
    now = utc_now(module.clock)
    async with module.database.session() as session:
        rows = (
            await session.execute(
                select(Announcement)
                .where(
                    Announcement.banner.is_(True),
                    Announcement.ended_at.is_(None),
                    (Announcement.banner_until.is_(None)) | (Announcement.banner_until > now),
                )
                .order_by(Announcement.created_at.desc())
                .limit(5)
            )
        ).scalars()
        return [_announcement_out(r) for r in rows]


@router.get("/admin/notifications/status")
async def admin_status(_: Manager, module: Module) -> dict[str, Any]:
    return await module.status()


@router.get("/admin/notifications/deliveries")
async def deliveries(
    _: Manager,
    module: Module,
    status_filter: Annotated[str | None, Query(alias="status", max_length=12)] = None,
) -> list[dict[str, Any]]:
    stmt = select(Delivery).order_by(Delivery.created_at.desc()).limit(200)
    if status_filter:
        stmt = stmt.where(Delivery.status == status_filter)
    async with module.database.session() as session:
        rows = (await session.execute(stmt)).scalars().all()
    return [  # metadata only: never titles, bodies or addresses
        {
            "id": str(r.id),
            "communication": str(r.communication_id),
            "channel": r.channel,
            "status": r.status,
            "reason": r.suppress_reason,
            "attempts": r.attempts,
            "error": r.last_error,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.put("/admin/notifications/email")
async def put_email(principal: Manager, body: EmailConfigIn, module: Module) -> dict[str, Any]:
    providers = module.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
    if not providers:
        raise Unavailable("Configuration is not available.", code="admin.unavailable")
    writer = providers[0].provider
    for field, value in (
        ("email_enabled", body.enabled),
        ("email_from", body.sender),
        ("smtp_host", body.host),
        ("smtp_port", body.port),
        ("smtp_tls", body.tls),
        ("smtp_username", body.username),
    ):
        await writer.set_global(principal, SETTINGS[field], value, reason="e-mail transport")
    if body.password is not None:
        await writer.set_global(principal, SMTP_PASSWORD, body.password, reason="e-mail transport")
    if body.portal_url is not None:
        await writer.set_global(
            principal, SETTINGS["portal_url"], body.portal_url.rstrip("/"), reason="e-mail links"
        )
    await module.refresh_config()
    return {"enabled": module.config.email_enabled, "host": module.config.smtp_host, "password": "********"}


@router.post("/admin/notifications/email/test")
async def email_test(principal: Manager, module: Module) -> dict[str, str]:
    assert principal.user_id is not None
    address = await module.email.address(principal.user_id)
    if not address:
        raise ValidationFailed("Your account has no e-mail address.", code="notifications.no_address")
    try:
        await module.email.transport.send(
            EmailMessage(address, "Portalab e-mail test", "E-mail delivery works.")
        )
        outcome = "sent"
    except Exception as exc:
        outcome = f"failed:{type(exc).__name__}"
    await _audit(module, principal, "notifications.email_test", "email", {"outcome": outcome})
    return {"outcome": outcome}


@router.put("/admin/notifications/categories/{key}")
async def put_category_policy(
    principal: Manager, key: str, body: CategoryPolicyIn, module: Module
) -> dict[str, Any]:
    if module.categories.get(key) is None:
        raise NotFound("Unknown category.", code="notifications.category_unknown")
    providers = module.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
    if not providers:
        raise Unavailable("Configuration is not available.", code="admin.unavailable")
    policies = dict(module.config.category_policy or {})
    policies[key] = body.model_dump()
    await providers[0].provider.set_global(
        principal, CATEGORY_POLICY, policies, reason="notification category policy"
    )
    await module.refresh_config()
    return {"key": key, **policies[key]}
