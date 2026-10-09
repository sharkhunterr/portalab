"""Activity ingestion (027, Telemetra-style): the raw play/read history of every service, kept row by row.

* services providing ``media.activity_history`` are read page by page: first the whole history
  (*backfill*, oldest first, resumable from its cursor), then *incrementally* from the latest play seen
  (with an overlap, rows are upserted so a replay changes nothing);
* services without a history (Jellyfin…) contribute their ended live sessions;
* each row keeps the source's account id; it is *attributed* to a member through the verified account
  links — now, and again whenever an administrator links the account later;
* each row is tied to the catalog (the item, and its *work*: the film, the series of an episode, the
  album of a track) by source item, then by strong ids;
* sources reporting the same plays (Plex and Tautulli: family ``plex``) are de-duplicated: from the first
  play the richest source recorded, the other source's rows stop being ``counted``;
* every changed day is marked for the daily aggregates.
"""

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from portalab.capabilities.media import ACTIVITY_HISTORY, ACTIVITY_KINDS, ActivityPage, SourceActivity, unwrap
from portalab.capabilities.record_sink import Report, ServiceRef, SinkResult
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.logging import redact_text
from portalab.core.time import Clock, utc_now
from portalab.modules.media.common import strong_ids
from portalab.modules.media.insights.progress import Progress, history_task
from portalab.modules.media.models import (
    Activity,
    ActivityCursor,
    ActivityDirtyDay,
    ExternalId,
    MediaObject,
    MediaRequest,
    PlaybackSession,
    SourceItem,
    UserLink,
)
from portalab.modules.media.observability import log, metrics

JOB = "media.activity_sync"
PAGE_TIMEOUT = 60
BACKFILL_PAGES = 40  # per run and service: a large history is caught up over a few runs
INCREMENTAL_PAGES = 10
MAX_DRIVEN_RUNS = 100  # « sync now »: up to 4,000 pages of history in one go
OVERLAP = timedelta(hours=6)
WORKS = frozenset({"movie", "series", "album", "book", "audiobook", "game"})


def day_of(at: datetime) -> datetime:
    at = at.astimezone(UTC)
    return datetime(at.year, at.month, at.day, tzinfo=UTC)


async def mark_days(session: AsyncSession, days: Iterable[datetime]) -> None:
    values = [{"day": d} for d in {day_of(d) for d in days}]
    if values:
        await session.execute(insert(ActivityDirtyDay).values(values).on_conflict_do_nothing())


async def attribute(session: AsyncSession, service_id: UUID, external_user_id: str, user: UUID | None) -> int:
    """(Re-)attribute an account's plays — and the requests it made, 027 — on one service to a member
    (``None`` detaches them). Requests made from the portal keep their member; only synchronised ones move."""
    await session.execute(
        update(MediaRequest)
        .where(
            MediaRequest.service_id == service_id,
            MediaRequest.external_ref["requester"].astext == external_user_id,
            MediaRequest.counted == "none",
            MediaRequest.requester_user_id.is_distinct_from(user),
        )
        .values(requester_user_id=user)
    )
    rows = (
        await session.execute(
            update(Activity)
            .where(
                Activity.service_id == service_id,
                Activity.external_user_id == external_user_id,
                Activity.user_id.is_distinct_from(user),
            )
            .values(user_id=user)
            .returning(Activity.started_at)
        )
    ).all()
    await mark_days(session, (r[0] for r in rows))
    return len(rows)


SAME_PLAY_BEFORE = timedelta(hours=12)  # a richer row starts at most this long before the same play's row
BEHIND_AFTER = timedelta(hours=6)  # a richest source this far behind its family no longer receives plays


class _Resolver:
    """Item → (object, work), cached for the run."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cache: dict[tuple[str, str], tuple[UUID | None, UUID | None]] = {}
        self.families: dict[str, list[UUID]] = {}
        self.durations: dict[UUID, float | None] = {}

    async def duration(self, object_id: UUID | None) -> float | None:
        """The item's length from the catalog, for sources that do not give it (Plex's history)."""
        if object_id is None:
            return None
        if object_id not in self.durations:
            value = await self.session.scalar(
                select(SourceItem.payload["duration_s"].as_float())
                .where(SourceItem.object_id == object_id, SourceItem.payload.has_key("duration_s"))
                .limit(1)
            )
            self.durations[object_id] = float(value) if value else None
        return self.durations[object_id]

    async def _follow(self, object_id: UUID | None) -> MediaObject | None:
        for _ in range(5):
            if object_id is None:
                return None
            obj = await self.session.get(MediaObject, object_id)
            if obj is None or obj.status != "merged" or obj.merged_into is None:
                return obj
            object_id = obj.merged_into
        return None

    async def _work(self, obj: MediaObject | None) -> UUID | None:
        if obj is None:
            return None
        current = obj
        for _ in range(3):
            if current.kind in WORKS or current.parent_id is None:
                return current.id
            parent = await self._follow(current.parent_id)
            if parent is None:
                return current.id
            current = parent
        return current.id

    async def _family_services(self, family: str) -> list[UUID]:
        if family not in self.families:
            self.families[family] = list(
                (
                    await self.session.execute(
                        select(SourceItem.service_id)
                        .where(SourceItem.source_system.like(f"{family}:%"))
                        .group_by(SourceItem.service_id)
                    )
                ).scalars()
            )
        return self.families[family]

    async def resolve(self, service_id: UUID, item: SourceActivity) -> tuple[UUID | None, UUID | None]:
        key = (str(service_id), item.item_external_id or f"ids:{sorted(item.ids.items())}")
        if key in self.cache:
            return self.cache[key]
        found: UUID | None = None
        if item.item_external_id:
            services = [service_id]
            if item.family:
                services += await self._family_services(item.family)
            found = (
                await self.session.execute(
                    select(SourceItem.object_id)
                    .where(
                        SourceItem.service_id.in_(services),
                        SourceItem.external_id == item.item_external_id,
                        SourceItem.object_id.is_not(None),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
        if found is None and item.kind not in ("episode", "track"):  # episode ids are not reliable
            for scheme, value in strong_ids(item.ids).items():
                found = await self.session.scalar(
                    select(ExternalId.object_id).where(ExternalId.scheme == scheme, ExternalId.value == value)
                )
                if found is not None:
                    break
        obj = await self._follow(found)
        result = (obj.id if obj else None, await self._work(obj))
        self.cache[key] = result
        return result


class ActivityIngestor:
    def __init__(self, database: Database, capabilities: CapabilityRegistry, *, clock: Clock | None = None):
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self.progress = Progress(database)
        self._locks: dict[UUID, asyncio.Lock] = {}

    def providers(self) -> list[tuple[UUID, Any]]:
        try:
            registrations = self.capabilities.system_providers(ACTIVITY_HISTORY)
        except Exception:
            return []
        out = []
        for registration in registrations:
            try:
                out.append((UUID(registration.instance_ref), registration.provider))
            except ValueError:
                continue
        return out

    async def run(self) -> int:
        """One sweep: every history service, then the live sessions of the others. Returns rows stored."""
        stored = 0
        with_history: set[UUID] = set()
        for service_id, provider in self.providers():
            with_history.add(service_id)
            if self._lock(service_id).locked():
                continue  # « sync now » is reading this history right now
            try:
                async with self._lock(service_id):
                    stored += await self._history(service_id, provider)
            except Exception as exc:  # one failing service never stops the others
                await self._failed(service_id, "history", exc)
        stored += await self._sessions(with_history)
        families = await self._families_touched()
        for family in families:
            await self.dedup(family)
        metrics.increment("media.activity.stored", stored)
        return stored

    def _lock(self, service_id: UUID) -> asyncio.Lock:
        return self._locks.setdefault(service_id, asyncio.Lock())

    async def drive(self, service: ServiceRef, kind: str, report: Report) -> SinkResult:
        """027: « sync now » (and the scheduled sync) of a history service, from the services page: the
        whole history is read — the backfill to its end, then what is new — with its progress; a full
        resync starts the history over."""
        provider = dict(self.providers()).get(service.service_id)
        if provider is None:
            return SinkResult()
        stored = 0
        async with self._lock(service.service_id):
            if kind == "resync_full":
                await self.reset(service.service_id)
            try:
                for _ in range(MAX_DRIVEN_RUNS):
                    stored += await self._history(service.service_id, provider, report)
                    async with self.database.session() as session:
                        state = await session.get(ActivityCursor, service.service_id)
                    if state is None or state.mode != "backfill":
                        break
            except Exception as exc:
                await self._failed(service.service_id, "history", exc)
                raise
        for family in await self._families_touched():
            await self.dedup(family)
        metrics.increment("media.activity.stored", stored)
        return SinkResult(added=stored)

    # --- history providers -----------------------------------------------------------------------------
    async def _cursor(self, session: AsyncSession, service_id: UUID, source: str) -> ActivityCursor:
        row = await session.get(ActivityCursor, service_id, with_for_update=True)
        if row is None:
            row = ActivityCursor(service_id=service_id, source=source, mode="backfill", items=0)
            session.add(row)
            await session.flush()
        return row

    async def _history(self, service_id: UUID, provider: Any, report: Report | None = None) -> int:
        async with self.database.unit_of_work() as uow:
            state = await self._cursor(uow.session, service_id, "history")
            mode, cursor, watermark = state.mode, state.cursor, state.watermark
        since = None if mode == "backfill" else (watermark - OVERLAP if watermark else None)
        pages = BACKFILL_PAGES if mode == "backfill" else INCREMENTAL_PAGES
        stored, latest = 0, watermark
        if mode == "incremental":
            cursor = None
        finished = False
        task = history_task(service_id)
        await self.progress.set(task, utc_now(self.clock), running=True)
        for _ in range(pages):
            page: ActivityPage = unwrap(
                await asyncio.wait_for(provider.history(since=since, cursor=cursor), timeout=PAGE_TIMEOUT)
            )
            stored += await self.store(service_id, page.items)
            await self.progress.set(
                task, utc_now(self.clock), running=True, done=page.position, total=page.total
            )
            if report is not None:
                await report(page.position if page.position is not None else stored, page.total)
            for item in page.items:
                if latest is None or item.started_at > latest:
                    latest = item.started_at
            cursor = page.cursor
            if mode == "backfill":  # resumable: the cursor is saved after every page
                async with self.database.unit_of_work() as uow:
                    state = await self._cursor(uow.session, service_id, "history")
                    state.cursor, state.watermark = cursor, latest
                    state.items += len(page.items)
            if cursor is None:
                finished = True
                break
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            state = await self._cursor(uow.session, service_id, "history")
            state.last_run_at, state.last_error, state.watermark = now, None, latest
            if mode == "incremental":
                state.items += stored
            if mode == "backfill" and finished:
                state.mode, state.cursor, state.backfilled_at = "incremental", None, now
                state.watermark = latest or now
        await self.progress.set(task, now, running=False)
        return stored

    async def store(self, service_id: UUID, items: Iterable[SourceActivity]) -> int:
        rows = [i for i in items if i.kind in ACTIVITY_KINDS and i.ref and i.external_user_id]
        if not rows:
            return 0
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            links = {
                link.external_user_id: link.user_id
                for link in (
                    await session.execute(
                        select(UserLink).where(UserLink.service_id == service_id, UserLink.verified.is_(True))
                    )
                ).scalars()
            }
            resolver = _Resolver(session)
            values = []
            for item in rows:
                object_id, work_id = await resolver.resolve(service_id, item)
                duration = item.duration_s or await resolver.duration(object_id)
                watched = float(item.watched_s or 0)
                if watched <= 0 and duration:  # the source only says it was played: use what was reached
                    watched = duration * (item.progress if item.progress is not None else 1.0)
                values.append(
                    {
                        "service_id": service_id,
                        "ref": item.ref[:200],
                        "family": item.family,
                        "priority": item.priority,
                        "counted": True,
                        "external_user_id": item.external_user_id[:200],
                        "user_id": links.get(item.external_user_id),
                        "kind": item.kind,
                        "title": item.title[:500] or "?",
                        "parent_title": (item.parent_title or None) and item.parent_title[:500],
                        "object_id": object_id,
                        "work_id": work_id,
                        "item_external_id": (item.item_external_id or None) and item.item_external_id[:200],
                        "ids": strong_ids(item.ids),
                        "year": item.year,
                        "started_at": item.started_at,
                        "stopped_at": item.stopped_at,
                        "watched_s": watched,
                        "duration_s": duration,
                        "progress": item.progress,
                        "device": (item.device or None) and item.device[:120],
                        "platform": (item.platform or None) and item.platform[:60],
                        "stream": (item.stream or None) and item.stream[:12],
                        "quality": (item.quality or None) and item.quality[:12],
                        "received_at": now,
                    }
                )
            for chunk in range(0, len(values), 500):
                statement = insert(Activity).values(values[chunk : chunk + 500])
                await session.execute(
                    statement.on_conflict_do_update(
                        constraint="uq_activity_service_ref",
                        set_={
                            "stopped_at": statement.excluded.stopped_at,
                            "watched_s": statement.excluded.watched_s,
                            "duration_s": statement.excluded.duration_s,
                            "progress": statement.excluded.progress,
                            # 027: a connector learning more (live TV's show) completes stored plays
                            "parent_title": func.coalesce(
                                statement.excluded.parent_title, Activity.parent_title
                            ),
                            "user_id": statement.excluded.user_id,
                            "object_id": func.coalesce(statement.excluded.object_id, Activity.object_id),
                            "work_id": func.coalesce(statement.excluded.work_id, Activity.work_id),
                            "stream": func.coalesce(statement.excluded.stream, Activity.stream),
                            "quality": func.coalesce(statement.excluded.quality, Activity.quality),
                        },
                    )
                )
            await mark_days(session, (i.started_at for i in rows))
        return len(rows)

    # --- live sessions of services without a history -------------------------------------------------
    async def _sessions(self, with_history: set[UUID]) -> int:
        async with self.database.session() as session:
            services = [
                s
                for s in (
                    await session.execute(
                        select(PlaybackSession.service_id)
                        .where(PlaybackSession.ended.is_(True))
                        .group_by(PlaybackSession.service_id)
                    )
                ).scalars()
                if s not in with_history
            ]
        stored = 0
        for service_id in services:
            try:
                stored += await self._service_sessions(service_id)
            except Exception as exc:
                await self._failed(service_id, "sessions", exc)
        return stored

    async def _service_sessions(self, service_id: UUID) -> int:
        async with self.database.unit_of_work() as uow:
            state = await self._cursor(uow.session, service_id, "sessions")
            watermark = state.watermark
        async with self.database.session() as session:
            query = select(PlaybackSession).where(
                PlaybackSession.service_id == service_id, PlaybackSession.ended.is_(True)
            )
            if watermark is not None:
                query = query.where(PlaybackSession.updated_at > watermark)
            ended = list(
                (await session.execute(query.order_by(PlaybackSession.updated_at).limit(2000))).scalars()
            )
            object_ids = {r.object_id for r in ended if r.object_id}
            titles: dict[UUID, str] = {}
            if object_ids:
                rows = await session.execute(
                    select(MediaObject.id, MediaObject.title).where(MediaObject.id.in_(object_ids))
                )
                titles = {object_id: title for object_id, title in rows.all()}
        items = []
        for row in ended:
            if not row.external_user_id:
                continue
            spent = (row.updated_at - row.started_at).total_seconds()
            items.append(
                SourceActivity(
                    ref=row.session_key[-200:],
                    external_user_id=row.external_user_id,
                    kind=row.kind if row.kind in ACTIVITY_KINDS else "other",
                    title=titles.get(row.object_id, "?") if row.object_id else "?",
                    started_at=row.started_at,
                    stopped_at=row.updated_at,
                    watched_s=spent if spent > 0 else row.max_position_s,
                    duration_s=row.duration_s,
                    progress=min(1.0, row.max_position_s / row.duration_s) if row.duration_s else None,
                    device=row.device,
                )
            )
        stored = await self.store(service_id, items)
        if ended:
            async with self.database.unit_of_work() as uow:
                # the poller already tied each session to the catalog: keep its object
                for row in ended:
                    if row.object_id:
                        await uow.session.execute(
                            update(Activity)
                            .where(Activity.service_id == service_id, Activity.ref == row.session_key[-200:])
                            .values(
                                object_id=row.object_id,
                                work_id=func.coalesce(Activity.work_id, row.object_id),
                            )
                        )
                state = await self._cursor(uow.session, service_id, "sessions")
                state.watermark = max(r.updated_at for r in ended)
                state.mode, state.items = "incremental", state.items + stored
                state.last_run_at, state.last_error = utc_now(self.clock), None
        return stored

    # --- de-duplication ----------------------------------------------------------------------------------
    async def _families_touched(self) -> list[str]:
        async with self.database.session() as session:
            return [
                f
                for f in (
                    await session.execute(
                        select(Activity.family).where(Activity.family.is_not(None)).group_by(Activity.family)
                    )
                ).scalars()
                if f
            ]

    async def dedup(self, family: str) -> None:
        """Within a family, a row is set aside only when a richer source recorded **the same play** (#24):
        the same item (its id, the catalog object, or its title within its series), the same member when
        both rows are attributed, and a start within the richer row's session (an hour before it, up to
        three hours after it ended — Plex dates a play when it is marked watched). A play the richer source
        missed (Tautulli down, not running yet) keeps counting."""
        richer = aliased(Activity)
        same_play = (
            select(literal(1))
            .where(
                richer.family == Activity.family,
                richer.priority > Activity.priority,
                richer.started_at.between(
                    Activity.started_at - SAME_PLAY_BEFORE, Activity.started_at + timedelta(hours=1)
                ),
                or_(
                    richer.item_external_id == Activity.item_external_id,
                    and_(richer.object_id.is_not(None), richer.object_id == Activity.object_id),
                    and_(
                        richer.title == Activity.title,
                        func.coalesce(richer.parent_title, "") == func.coalesce(Activity.parent_title, ""),
                    ),
                ),
                or_(richer.user_id.is_(None), Activity.user_id.is_(None), richer.user_id == Activity.user_id),
                Activity.started_at
                <= func.coalesce(richer.stopped_at, richer.started_at) + timedelta(hours=3),
            )
            .exists()
        )
        async with self.database.unit_of_work() as uow:
            session = uow.session
            changed = (
                await session.execute(
                    update(Activity)
                    .where(
                        Activity.family == family,
                        or_(
                            and_(same_play, Activity.counted.is_(True)),
                            and_(~same_play, Activity.counted.is_(False)),
                        ),
                    )
                    .values(counted=~same_play)
                    .returning(Activity.started_at)
                    .execution_options(synchronize_session=False)
                )
            ).all()
            await mark_days(session, (r[0] for r in changed))

    async def behind(self) -> dict[UUID, datetime]:
        """#24: the richest source of a family that stopped receiving plays while another one goes on
        (Tautulli no longer told by Plex): the date of its latest play, by service."""
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(
                        Activity.service_id, Activity.family, Activity.priority, func.max(Activity.started_at)
                    )
                    .where(Activity.family.is_not(None))
                    .group_by(Activity.service_id, Activity.family, Activity.priority)
                )
            ).all()
        out: dict[UUID, datetime] = {}
        for family in {r[1] for r in rows}:
            members = [r for r in rows if r[1] == family]
            if len(members) < 2:
                continue
            newest = max(r[3] for r in members)
            best = max(r[2] for r in members)
            for service_id, _, priority, latest in members:
                if priority == best and newest - latest > BEHIND_AFTER:
                    out[service_id] = latest
        return out

    async def _failed(self, service_id: UUID, source: str, exc: Exception) -> None:
        await self.progress.set(history_task(service_id), utc_now(self.clock), running=False)
        log.warning("media activity ingestion failed for %s: %s", service_id, type(exc).__name__)
        async with self.database.unit_of_work() as uow:
            state = await self._cursor(uow.session, service_id, source)
            state.last_run_at = utc_now(self.clock)
            state.last_error = redact_text(f"{type(exc).__name__}: {exc}")[:300]

    async def reset(self, service_id: UUID) -> None:
        """Start the history of one service over (a full backfill at the next run)."""
        async with self.database.unit_of_work() as uow:
            state = await self._cursor(uow.session, service_id, "history")
            state.mode, state.cursor, state.watermark, state.items = "backfill", None, None, 0
            state.backfilled_at, state.last_error = None, None
        await self.progress.set(history_task(service_id), utc_now(self.clock), running=False, done=0)
