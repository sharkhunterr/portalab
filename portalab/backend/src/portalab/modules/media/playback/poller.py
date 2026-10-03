"""``PlaybackPoller`` (T022; R6, FR-013..016): polls every ``media.playback`` provider (one per service),
normalizes sessions into ``media.playback_sessions`` and publishes throttled playback events.

* cadence adapts: every ``pollActiveSeconds`` while something plays, else every ``pollIdleSeconds``;
* a session missing from the next answer (or reported ``stopped``) ends: ``finished`` when the furthest
  position reached the kind's threshold, else ``abandoned`` — ``finished`` once per session;
* a source that stops answering marks its sessions ``stale``; after ``staleTimeoutSeconds`` they are
  ``interrupted`` with ``media.playback_error`` (never ``finished``);
* activity of accounts without a verified link is stored as unlinked and never attributed or published;
* events carry ids and counters, the linked user as private subject, dedup ``(session, state_seq)``.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.media import PLAYBACK, SourceHistoryItem, SourcePlayback, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.media.common import strong_ids
from portalab.modules.media.links.service import UserLinkService
from portalab.modules.media.models import ExternalId, PlaybackSession, SourceItem
from portalab.modules.media.observability import log, metrics
from portalab.modules.media.playback.normalizer import ACTIVE, on_end, on_update, percent
from portalab.modules.media.settings import MediaConfig

JOB = "media.playback_poll"


class PlaybackPoller:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        links: UserLinkService,
        config: Callable[[], MediaConfig],
        threshold: Callable[[str], float | None],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.links = links
        self.config = config
        self.threshold = threshold
        self.clock = clock
        self.last_poll: dict[str, datetime] = {}
        self.history_since: dict[str, datetime] = {}

    def providers(self) -> list[tuple[UUID, Any]]:
        try:
            registrations = self.capabilities.system_providers(PLAYBACK)
        except Exception:
            return []
        out = []
        for registration in registrations:
            try:
                out.append((UUID(registration.instance_ref), registration.provider))
            except ValueError:
                continue
        return out

    async def tick(self) -> int:
        """One scheduler tick: poll services that are due (active cadence or idle cadence)."""
        now = utc_now(self.clock)
        config = self.config()
        polled = 0
        for service_id, provider in self.providers():
            key = str(service_id)
            active = await self._has_active(service_id)
            every = config.poll_active_seconds if active else config.poll_idle_seconds
            last = self.last_poll.get(key)
            if last is not None and now - last < timedelta(seconds=max(1, every) - 1):
                continue
            await self.poll(service_id, provider)
            polled += 1
        return polled

    async def _has_active(self, service_id: UUID) -> bool:
        async with self.database.session() as session:
            found = await session.scalar(
                select(PlaybackSession.session_key)
                .where(PlaybackSession.service_id == service_id, PlaybackSession.ended.is_(False))
                .limit(1)
            )
        return found is not None

    async def poll(self, service_id: UUID, provider: Any) -> None:
        now = utc_now(self.clock)
        self.last_poll[str(service_id)] = now
        try:
            reports = list(unwrap(await asyncio.wait_for(provider.now_playing(), timeout=15)))
        except Exception as exc:
            metrics.increment("media.playback.poll_failures")
            log.info("playback poll failed", extra={"reason": type(exc).__name__})
            await self._source_lost(service_id, now)
            return
        seen: set[str] = set()
        for report in reports:
            session_key = f"{service_id}:{report.session_key}"[:300]
            seen.add(session_key)
            try:
                await self._report(service_id, session_key, report, now)
            except Exception:
                log.warning("playback session not recorded")
        await self._end_missing(service_id, seen, now)
        await self._recent(service_id, provider, now)

    async def _resolve_object(
        self, session: AsyncSession, service_id: UUID, item: str | None, ids: Any
    ) -> UUID | None:
        if item:
            found = (
                await session.execute(
                    select(SourceItem.object_id).where(
                        SourceItem.service_id == service_id, SourceItem.external_id == item
                    )
                )
            ).scalar_one_or_none()
            if found is not None:
                return found
        for scheme, value in strong_ids(ids or {}).items():
            owner: UUID | None = await session.scalar(
                select(ExternalId.object_id).where(ExternalId.scheme == scheme, ExternalId.value == value)
            )
            if owner is not None:
                return owner
        return None

    async def _publish(self, session: AsyncSession, row: PlaybackSession, name: str, now: datetime) -> None:
        if row.user_id is None:
            metrics.increment("media.playback.unlinked")
            return  # unlinked activity is never attributed
        payload = {
            "object": str(row.object_id) if row.object_id else None,
            "kind": row.kind,
            "service": str(row.service_id),
            "session": row.session_key,
            "state_seq": row.state_seq,
            "position_s": round(row.position_s, 1),
            "duration_s": row.duration_s,
            "percent": percent(row.max_position_s, row.duration_s),
            "occurred_at": now.isoformat(),
        }
        dedup = (
            f"media.playback_finished:{row.session_key}"
            if name == "media.playback_finished"
            else f"media.playback:{row.session_key}:{row.state_seq}"
        )
        await self.events.publish(
            session,
            name,
            payload,
            occurred_at=now,
            subject=SubjectRef("user", str(row.user_id)),
            source="media",
            dedup_key=dedup,
        )
        metrics.increment(f"media.playback.{name.split('_', 1)[1]}")

    async def _report(
        self, service_id: UUID, session_key: str, report: SourcePlayback, now: datetime
    ) -> None:
        user = await self.links.resolve(service_id, report.external_user_id)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            row = await session.get(PlaybackSession, session_key, with_for_update=True)
            if row is not None and row.ended:
                return
            position = max(0.0, float(report.position_s))
            if row is None:
                if report.state == "stopped":
                    return
                row = PlaybackSession(
                    session_key=session_key,
                    service_id=service_id,
                    user_id=user,
                    external_user_id=report.external_user_id,
                    object_id=await self._resolve_object(
                        session, service_id, report.item_external_id, report.ids
                    ),
                    kind=report.kind,
                    state=report.state,
                    position_s=position,
                    max_position_s=position,
                    duration_s=report.duration_s,
                    device=(report.device or None) and report.device[:120],
                    started_at=now,
                    updated_at=now,
                    as_of=now,
                    last_event_at=now,
                    state_seq=1,
                    ended=False,
                )
                session.add(row)
                await session.flush()
                await self._publish(session, row, "media.playback_started", now)
                return
            decision = on_update(
                row.state, row.last_event_at, now, report, self.config().progress_event_seconds
            )
            row.position_s, row.max_position_s = position, max(row.max_position_s, position)
            row.duration_s = report.duration_s or row.duration_s
            row.updated_at = row.as_of = now
            if decision.state == "stopped":
                await self._finish(session, row, now)
                return
            row.state = decision.state
            if decision.event is not None:
                row.state_seq += 1
                row.last_event_at = now
                await self._publish(session, row, decision.event, now)

    async def _finish(self, session: AsyncSession, row: PlaybackSession, now: datetime) -> None:
        name = on_end(row.max_position_s, row.duration_s, self.threshold(row.kind))
        row.state, row.ended, row.state_seq, row.last_event_at = "stopped", True, row.state_seq + 1, now
        await self._publish(session, row, name, now)

    async def _end_missing(self, service_id: UUID, seen: set[str], now: datetime) -> None:
        async with self.database.unit_of_work() as uow:
            rows = (
                (
                    await uow.session.execute(
                        select(PlaybackSession)
                        .where(PlaybackSession.service_id == service_id, PlaybackSession.ended.is_(False))
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                if row.session_key not in seen:
                    await self._finish(uow.session, row, now)

    async def _source_lost(self, service_id: UUID, now: datetime) -> None:
        timeout = timedelta(seconds=self.config().stale_timeout_seconds)
        async with self.database.unit_of_work() as uow:
            rows = (
                (
                    await uow.session.execute(
                        select(PlaybackSession)
                        .where(PlaybackSession.service_id == service_id, PlaybackSession.ended.is_(False))
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                if now - row.as_of >= timeout:
                    row.state, row.ended, row.state_seq = "interrupted", True, row.state_seq + 1
                    row.updated_at = now
                    await self._publish(uow.session, row, "media.playback_error", now)
                elif row.state in ACTIVE:
                    row.state, row.updated_at = "stale", now

    async def _recent(self, service_id: UUID, provider: Any, now: datetime) -> None:
        """Completed plays reported after the fact (sources without live sessions, offline devices)."""
        fetch = getattr(provider, "recent_history", None)
        if fetch is None:
            return
        since = self.history_since.get(str(service_id), now - timedelta(hours=1))
        try:
            items: list[SourceHistoryItem] = list(unwrap(await asyncio.wait_for(fetch(since), timeout=15)))
        except Exception:
            return
        self.history_since[str(service_id)] = now
        for item in items:
            user = await self.links.resolve(service_id, item.external_user_id)
            if user is None:
                metrics.increment("media.playback.unlinked")
                continue
            async with self.database.unit_of_work() as uow:
                object_id = await self._resolve_object(
                    uow.session, service_id, item.item_external_id, item.ids
                )
                ref = item.item_external_id or item.title[:40]
                key = f"{service_id}:history:{ref}:{item.occurred_at.isoformat()}"
                if await uow.session.get(PlaybackSession, key[:300]) is not None:
                    continue
                row = PlaybackSession(
                    session_key=key[:300],
                    service_id=service_id,
                    user_id=user,
                    external_user_id=item.external_user_id,
                    object_id=object_id,
                    kind=item.kind,
                    state="stopped",
                    position_s=item.position_s,
                    max_position_s=item.position_s,
                    duration_s=item.duration_s,
                    device=None,
                    started_at=item.occurred_at,
                    updated_at=now,
                    as_of=now,
                    last_event_at=now,
                    state_seq=1,
                    ended=True,
                )
                uow.session.add(row)
                await uow.session.flush()
                name = on_end(item.position_s, item.duration_s, self.threshold(item.kind))
                if name == "media.playback_abandoned":
                    name = "media.playback_progressed"
                await self._publish(uow.session, row, name, item.occurred_at)

    async def now_playing(self, user: UUID) -> list[PlaybackSession]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(PlaybackSession)
                        .where(PlaybackSession.user_id == user, PlaybackSession.ended.is_(False))
                        .order_by(PlaybackSession.updated_at.desc())
                    )
                )
                .scalars()
                .all()
            )
