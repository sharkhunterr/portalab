"""#4: administrators approve or decline members' requests from the portal.

The queue is the requests the portal knows (made here or synchronised from the request service), the
pending ones first, each with who asked (administrators see it), the seasons and 4K asked for, and its
poster. A decision goes to the request service (Seerr sends an approved request to Radarr or Sonarr); the
portal keeps it with the reason given, gives back a unit bought in the shop when a request is declined,
and tells the member (« media.request_updated »).
"""

import asyncio
from contextlib import suppress
from typing import Any
from uuid import UUID

from sqlalchemy import case, select

from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.media import unwrap
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.core.errors import ValidationFailed
from portalab.core.time import utc_now
from portalab.modules.media.identity.resolver import MediaNotFound
from portalab.modules.media.models import MediaRequest
from portalab.modules.media.observability import log
from portalab.modules.media.requests.insights import kind_of, lookup_of
from portalab.modules.media.requests.service import Requests, RequestServiceUnavailable

OPEN = ("pending", "approved", "processing")
FILTERS = {"pending": ("pending",), "open": OPEN, "all": None}


class RequestModeration:
    def __init__(self, requests: Requests) -> None:
        self.requests = requests

    async def queue(
        self, state: str = "pending", limit: int = 200, user: UUID | None = None
    ) -> list[dict[str, Any]]:
        wanted = FILTERS.get(state, ("pending",))
        query = select(MediaRequest)
        if wanted is not None:
            query = query.where(MediaRequest.state.in_(wanted))
        if user is not None:  # one member's only (their admin card)
            query = query.where(MediaRequest.requester_user_id == user)
        pending_first = case((MediaRequest.state == "pending", 0), else_=1)
        async with self.requests.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        query.order_by(pending_first, MediaRequest.requested_at.desc()).limit(limit)
                    )
                ).scalars()
            )
        names = await self._names({r.requester_user_id for r in rows if r.requester_user_id})
        out = []
        for row in rows:
            ref = row.external_ref or {}
            decision = ref.get("decision") or None
            out.append(
                {
                    "id": str(row.id),
                    "object_id": str(row.object_id) if row.object_id else None,
                    "title": str(ref.get("title") or "?"),
                    "kind": kind_of(row),
                    "state": row.state,
                    "requested_at": row.requested_at.isoformat(),
                    "updated_at": row.updated_at.isoformat(),
                    "seasons": ref.get("seasons"),
                    "is4k": bool(ref.get("is4k")),
                    "requester": {
                        "id": str(row.requester_user_id),
                        "name": names.get(row.requester_user_id),
                    }
                    if row.requester_user_id
                    else None,
                    "decidable": bool(row.external_request_id) and row.state == "pending",
                    "decision": decision,
                    "_lookup": lookup_of(row),
                }
            )
        return out

    async def _names(self, users: set[UUID]) -> dict[UUID, str | None]:
        out: dict[UUID, str | None] = {}
        with suppress(Exception):
            directory = self.requests.capabilities.system_providers(DIRECTORY)[0].provider
            for user in users:
                with suppress(Exception):
                    found = await directory.get_user_summary(user)
                    out[user] = found.display_name if found else None
        return out

    async def decide(self, request_id: UUID, approve: bool, reason: str | None, actor: UUID | None) -> str:
        """Approve or decline a pending request: on the request service first, then here."""
        async with self.requests.database.session() as session:
            row = await session.get(MediaRequest, request_id)
            if row is None:
                raise MediaNotFound("This request does not exist.")
            if row.state != "pending":
                raise ValidationFailed(
                    "This request is no longer waiting for a decision.", code="media.invalid"
                )
            if not row.external_request_id:
                raise ValidationFailed(
                    "This request never reached the request service.", code="media.invalid"
                )
            service, external = row.service_id, row.external_request_id
        provider = dict(self.requests._providers()).get(service)
        decide = getattr(provider, "decide", None)
        if decide is None:
            raise RequestServiceUnavailable("The request service cannot take decisions from the portal.")
        try:
            answer = unwrap(await asyncio.wait_for(decide(external, approve), timeout=15))
        except Exception as exc:
            log.info("request decision not taken", extra={"reason": type(exc).__name__})
            raise RequestServiceUnavailable("The request service did not take the decision.") from exc
        now = utc_now(self.requests.clock)
        async with self.requests.database.unit_of_work() as uow:
            row = await uow.session.get(MediaRequest, request_id, with_for_update=True)
            assert row is not None
            state = answer.state if approve else "declined"
            if state == "pending":  # the service answered with the request as it was: the decision stands
                state = "approved"
            if not approve and row.requester_user_id is not None:
                # declined: a unit bought in the shop comes back (the service never counted it)
                await self.requests.quota.give_back(
                    uow.session, row.requester_user_id, str(row.id), row.counted
                )
                row.counted = "none"
            row.state, row.source_state, row.updated_at = state, answer.source_state[:60], now
            row.external_ref = {
                **(row.external_ref or {}),
                "decision": {
                    "approved": approve,
                    "reason": (reason or "").strip()[:500] or None,
                    "by": str(actor) if actor else None,
                    "at": now.isoformat(),
                },
            }
            await self.requests.publish(uow.session, row, "media.request_updated")
            requester, title = row.requester_user_id, str((row.external_ref or {}).get("title") or "?")
        if requester is not None:
            await self._tell(requester, request_id, title, approve, reason)
        self.requests.service_quotas.forget(requester)
        return state

    async def _tell(
        self, user: UUID, request_id: UUID, title: str, approve: bool, reason: str | None
    ) -> None:
        with suppress(Exception):
            providers = self.requests.capabilities.system_providers(NOTIFY)
            if not providers:
                return
            outcome = "approved" if approve else "declined"
            await providers[0].provider.send(
                CommunicationRequest(
                    category="media.request_updated",
                    template_key=f"media:notify.request.{outcome}",
                    audience=Users((user,)),
                    dedup_key=f"media-request:{request_id}:{outcome}",
                    params={"title": title[:200], "reason": (reason or "").strip()[:300]},
                    subject_ref=f"media-request:{request_id}",
                    action_url="/media/requests?tab=list",
                )
            )
