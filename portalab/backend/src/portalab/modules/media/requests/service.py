"""``RequestService`` (T026; R12, FR-021..023): requests go to a ``request.service`` provider after a quota
check, are mirrored with a normalized state machine, and follow the source of truth through sync records
(``RequestSink``). Idempotent per ``idempotency_key``; a failed submission gives the quota back; no paid
priority exists anywhere in the flow."""

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.media import REQUESTS, RequestPayload, SourceUnavailable, unwrap
from portalab.capabilities.record_sink import ServiceRef, SinkResult
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.errors import Unavailable, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.media.common import strong_ids
from portalab.modules.media.identity.resolver import MediaNotFound, live_object
from portalab.modules.media.links.service import UserLinkService
from portalab.modules.media.models import ExternalId, MediaRequest, UserLink
from portalab.modules.media.observability import metrics
from portalab.modules.media.requests.quota import RequestQuota

CANCELLABLE = ("pending", "approved")


class RequestServiceUnavailable(Unavailable):
    default_code = "media.service_unavailable"
    default_title = "No request service is available"


class Requests:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        quota: RequestQuota,
        links: UserLinkService,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.quota = quota
        self.links = links
        self.clock = clock

    def _providers(self) -> list[tuple[UUID, Any]]:
        try:
            registrations = self.capabilities.system_providers(REQUESTS)
        except Exception:
            return []
        out = []
        for registration in registrations:
            try:
                out.append((UUID(registration.instance_ref), registration.provider))
            except ValueError:
                continue
        return out

    async def publish(self, session: AsyncSession, row: MediaRequest, name: str) -> None:
        if row.requester_user_id is None:
            return
        await self.events.publish(
            session,
            name,
            {
                "request": str(row.id),
                "object": str(row.object_id) if row.object_id else None,
                "kind": str(row.external_ref.get("kind", "")),
                "state": row.state,
            },
            occurred_at=utc_now(self.clock),
            subject=SubjectRef("user", str(row.requester_user_id)),
            source="media",
            dedup_key=f"media.request:{row.id}:{row.state}:{name}",
        )

    async def _target(
        self, session: AsyncSession, object_id: UUID | None, ref: Mapping[str, Any] | None
    ) -> tuple[UUID | None, dict[str, Any]]:
        if object_id is not None:
            row = await live_object(session, object_id)
            if row is None or row.status != "active":
                raise MediaNotFound("This object does not exist.")
            ids = {
                scheme: value
                for scheme, value in await session.execute(
                    select(ExternalId.scheme, ExternalId.value).where(ExternalId.object_id == row.id)
                )
            }
            return row.id, {"ids": ids, "kind": row.kind, "title": row.title}
        ids = strong_ids((ref or {}).get("ids") or {})
        title = str((ref or {}).get("title") or "").strip()[:500]
        kind = str((ref or {}).get("kind") or "").strip()[:40]
        if not ids or not title or not kind:
            raise ValidationFailed("Give the media's ids, kind and title.", code="media.invalid")
        for scheme, value in ids.items():
            found = await session.scalar(
                select(ExternalId.object_id).where(ExternalId.scheme == scheme, ExternalId.value == value)
            )
            if found is not None:
                return found, {"ids": ids, "kind": kind, "title": title}
        return None, {"ids": ids, "kind": kind, "title": title}

    async def submit(
        self,
        user: UUID,
        *,
        object_id: UUID | None,
        ref: Mapping[str, Any] | None,
        service_id: UUID | None,
        idempotency_key: str | None,
    ) -> MediaRequest:
        providers = self._providers()
        chosen = next(((s, p) for s, p in providers if service_id is None or s == service_id), None)
        if chosen is None:
            raise RequestServiceUnavailable("No request service is configured.")
        service, provider = chosen
        key = f"{user}:{idempotency_key}"[:200] if idempotency_key else None
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            if key is not None:
                existing = (
                    await session.execute(select(MediaRequest).where(MediaRequest.idempotency_key == key))
                ).scalar_one_or_none()
                if existing is not None:
                    return existing
            target, external_ref = await self._target(session, object_id, ref)
            row = MediaRequest(
                object_id=target,
                external_ref=external_ref,
                requester_user_id=user,
                service_id=service,
                state="pending",
                source_state="",
                idempotency_key=key,
                counted="none",
                requested_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            row.counted = await self.quota.consume(session, user, str(row.id))
            request_id = row.id
        requester = await self._external_user(user, service)
        try:
            answer = unwrap(
                await asyncio.wait_for(
                    provider.submit(
                        external_ref["ids"], external_ref["kind"], external_ref["title"], requester
                    ),
                    timeout=20,
                )
            )
        except (SourceUnavailable, TimeoutError, ConnectionError, OSError) as exc:
            metrics.increment("media.requests.failed")
            async with self.database.unit_of_work() as uow:
                failed = await uow.session.get(MediaRequest, request_id, with_for_update=True)
                assert failed is not None
                row = failed
                await self.quota.give_back(uow.session, user, str(row.id), row.counted)
                row.state, row.counted, row.source_state, row.updated_at = (
                    "failed",
                    "none",
                    "",
                    utc_now(self.clock),
                )
                await self.publish(uow.session, row, "media.request_created")
            raise RequestServiceUnavailable("The request service did not answer; nothing was used.") from exc
        async with self.database.unit_of_work() as uow:
            done = await uow.session.get(MediaRequest, request_id, with_for_update=True)
            assert done is not None
            row = done
            row.external_request_id = answer.external_request_id[:200]
            row.state, row.source_state = answer.state, answer.source_state[:60]
            row.updated_at = utc_now(self.clock)
            await self.publish(uow.session, row, "media.request_created")
            if row.state == "available":
                await self.publish(uow.session, row, "media.request_available")
            return row

    async def _external_user(self, user: UUID, service: UUID) -> str | None:
        async with self.database.session() as session:
            return (
                await session.execute(
                    select(UserLink.external_user_id).where(
                        UserLink.user_id == user, UserLink.service_id == service, UserLink.verified.is_(True)
                    )
                )
            ).scalar_one_or_none()

    async def cancel(self, user: UUID, request_id: UUID) -> MediaRequest:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(MediaRequest, request_id, with_for_update=True)
            if row is None or row.requester_user_id != user:
                raise MediaNotFound("This request does not exist.")
            if row.state not in CANCELLABLE:
                raise ValidationFailed("This request can no longer be cancelled.", code="media.invalid")
            row.state, row.updated_at = "cancelled", utc_now(self.clock)
            await self.publish(uow.session, row, "media.request_updated")
            providers = dict(self._providers())
        cancel = getattr(providers.get(row.service_id), "cancel", None)
        if cancel is not None and row.external_request_id:
            try:
                await asyncio.wait_for(cancel(row.external_request_id), timeout=10)
            except Exception:
                metrics.increment("media.requests.cancel_not_propagated")
        return row

    async def mine(self, user: UUID, *, limit: int = 100) -> list[MediaRequest]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(MediaRequest)
                        .where(MediaRequest.requester_user_id == user)
                        .order_by(MediaRequest.requested_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )


class RequestSink:
    """``RecordSink`` for ``request.service`` sync records: the source is the truth for request state."""

    def __init__(self, requests: Requests) -> None:
        self.requests = requests

    async def upsert(self, records: Sequence[SourceRecord], service: ServiceRef) -> SinkResult:
        added = modified = ignored = errored = 0
        now = utc_now(self.requests.clock)
        async with self.requests.database.unit_of_work() as uow:
            session = uow.session
            for record in records:
                if record.removed:
                    ignored += 1
                    continue
                try:
                    payload = RequestPayload.model_validate(dict(record.payload))
                except ValidationError:
                    errored += 1
                    continue
                row = (
                    await session.execute(
                        select(MediaRequest)
                        .where(
                            MediaRequest.service_id == service.service_id,
                            MediaRequest.external_request_id == record.external_id,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if row is None:
                    requester = await self.requests.links.resolve(service.service_id, payload.requester)
                    target, ref = (
                        await self.requests._target(
                            session, None, {"ids": payload.ids, "kind": payload.kind, "title": payload.title}
                        )
                        if strong_ids(payload.ids)
                        else (None, {"ids": {}, "kind": payload.kind, "title": payload.title})
                    )
                    if payload.requester:  # kept so a later account link attributes the request (027)
                        ref = {**ref, "requester": payload.requester}
                    row = MediaRequest(
                        object_id=target,
                        external_ref=ref,
                        requester_user_id=requester,
                        service_id=service.service_id,
                        external_request_id=record.external_id[:200],
                        state=payload.state,
                        source_state=payload.source_state,
                        idempotency_key=None,
                        counted="none",
                        requested_at=record.observed_at,
                        updated_at=now,
                    )
                    session.add(row)
                    await session.flush()
                    await self.requests.publish(session, row, "media.request_created")
                    added += 1
                    continue
                attributed = await self._attribution(row, payload.requester, service)
                if row.state == payload.state and row.source_state == payload.source_state:
                    if attributed:  # who asked changed: no notification, nothing else moved
                        row.updated_at = now
                        modified += 1
                    else:
                        ignored += 1
                    continue
                became_available = payload.state == "available" and row.state != "available"
                row.state, row.source_state, row.updated_at = payload.state, payload.source_state, now
                await self.requests.publish(session, row, "media.request_updated")
                if became_available:
                    await self.requests.publish(session, row, "media.request_available")
                modified += 1
        return SinkResult(added=added, modified=modified, ignored=ignored, errored=errored)

    async def _attribution(self, row: MediaRequest, requester: str | None, service: ServiceRef) -> bool:
        """027: remember who asked on the service, and attribute the request once the account is linked."""
        changed = False
        if requester and (row.external_ref or {}).get("requester") != requester:
            row.external_ref = {**(row.external_ref or {}), "requester": requester}
            changed = True
        if requester and row.requester_user_id is None:
            member = await self.requests.links.resolve(service.service_id, requester)
            if member is not None:
                row.requester_user_id = member
                changed = True
        return changed

    async def deactivate(self, external_ids: Sequence[str], service: ServiceRef) -> int:
        return 0  # a request vanishing from the source keeps its last known state

    async def active_ids(self, service: ServiceRef) -> set[str]:
        async with self.requests.database.session() as session:
            rows = await session.execute(
                select(MediaRequest.external_request_id).where(
                    MediaRequest.service_id == service.service_id,
                    MediaRequest.external_request_id.is_not(None),
                )
            )
            return {str(r[0]) for r in rows}

    async def purge(self, service: ServiceRef) -> int:
        async with self.requests.database.unit_of_work() as uow:
            result = await uow.session.execute(
                delete(MediaRequest).where(MediaRequest.service_id == service.service_id)
            )
            return int(getattr(result, "rowcount", 0) or 0)
