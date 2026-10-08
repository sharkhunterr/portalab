"""Detail sections (T020; FR-009..012): every section of the detail page loads and fails on its own and
answers ``{state, as_of, data}`` — one failing source degrades only its section. Personal sections
(``history``, ``progress``, ``requests``) show the viewer's own data; other users appear in "concerned
users" only when their ``media_history`` visibility allows the viewer (021). Plugin blocks come from the
detail-block registry, each gated by its permission and isolated."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.media_core import DetailBlockRegistry
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.visibility import register_datum_class
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.core.visibility_port import OwnerOnlyVisibility, Redacted, VisibilityFilter
from portalab.modules.media.availability.service import AvailabilityService
from portalab.modules.media.catalog import CatalogQuery
from portalab.modules.media.models import (
    HistoryEntry,
    MediaObject,
    MediaRequest,
    MergeLog,
    ObjectTag,
    UserProgress,
)
from portalab.modules.media.observability import log
from portalab.modules.media.permissions import MEDIA_MANAGE, MEDIA_REQUEST

HISTORY_CLASS = "media_history"
REQUEST_CLASS = "media_request"
SECTIONS = (
    "info",
    "sources",
    "history",
    "progress",
    "requests",
    "people",
    "statistics",
    "events",
    "actions",
    "links",
    "blocks",
)
COHORT = 5
LINKS = {
    "tmdb": ("TMDB", "https://www.themoviedb.org/{kind}/{value}"),
    "imdb": ("IMDb", "https://www.imdb.com/title/{value}/"),
    "tvdb": ("TheTVDB", "https://thetvdb.com/dereferrer/series/{value}"),
    "igdb": ("IGDB", "https://www.igdb.com/games/{value}"),
    "musicbrainz": ("MusicBrainz", "https://musicbrainz.org/release/{value}"),
    "openlibrary": ("Open Library", "https://openlibrary.org/works/{value}"),
}

for key, description in (
    (HISTORY_CLASS, "What I watched, read, played or listened to (media history)"),
    (REQUEST_CLASS, "My media requests"),
):
    register_datum_class(
        key, owner="module:media", default_level="private", classification="activity", description=description
    )


@dataclass
class Section:
    state: str  # available | partial | stale | unavailable | insufficient_data | no-data
    as_of: datetime
    data: dict[str, Any] = field(default_factory=dict)


class Sections:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        catalog: CatalogQuery,
        availability: AvailabilityService,
        blocks: DetailBlockRegistry,
        *,
        visibility: VisibilityFilter | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.catalog = catalog
        self.availability = availability
        self.blocks = blocks
        self.visibility: VisibilityFilter = visibility or OwnerOnlyVisibility()
        self.clock = clock

    async def load(self, name: str, object_id: UUID, viewer: Principal) -> Section:
        view = await self.catalog.get(viewer, object_id)  # 404 for unknown/hidden objects
        loader = getattr(self, f"_{name}")
        try:
            return await asyncio.wait_for(loader(view.id, view, viewer), timeout=10)
        except Exception as exc:
            log.info("media section unavailable", extra={"section": name, "reason": type(exc).__name__})
            return Section("unavailable", utc_now(self.clock))

    def _user(self, viewer: Principal) -> UUID | None:
        return viewer.acting_for or viewer.user_id

    async def _info(self, object_id: UUID, view: Any, viewer: Principal) -> Section:
        keep = (
            "title",
            "original_title",
            "overview",
            "year",
            "genres",
            "language",
            "duration_s",
            "pages",
            # 027: what a book or an audiobook's page tells (Grimmory): authors and narrator, series,
            # publisher, publication date
            "people",
            "series",
            "series_position",
            "publisher",
            "released",
            "tags",
            "platform",  # 027: a game's console (RomM)
        )
        data = {k: view.effective.get(k) for k in keep if view.effective.get(k) not in (None, "", [])}
        if view.ids.get("isbn"):
            data["isbn"] = view.ids["isbn"]
        data.update(
            kind=view.kind,
            parent_id=str(view.parent_id) if view.parent_id else None,
            position=view.position,
            children=view.children,
            image_id=str(view.image_id) if view.image_id else None,
        )
        return Section("available", view.first_seen_at or utc_now(self.clock), data)

    async def _sources(self, object_id: UUID, view: Any, viewer: Principal) -> Section:
        available, sources, as_of = await self.availability.sources(object_id)
        degraded = [s for s in sources if s.service_state in ("unavailable", "maintenance")]
        state = "available"
        if sources and len(degraded) == len(sources):
            state = "stale"
        elif degraded:
            state = "partial"
        return Section(
            state,
            as_of,
            {
                "available": available,
                "sources": [
                    {
                        "service_id": s.service_id,
                        "service_name": s.service_name,
                        "connector": s.connector,
                        "variant": s.variant,
                        "present": s.present,
                        "availability": s.availability,
                        "last_seen_at": s.last_seen_at.isoformat(),
                        "service_state": s.service_state,
                        "service_state_as_of": s.service_state_as_of.isoformat()
                        if s.service_state_as_of
                        else None,
                        "sync_status": s.sync_status,
                        "last_sync_success_at": s.last_sync_success_at.isoformat()
                        if s.last_sync_success_at
                        else None,
                        # 027: failing now — an error after the last success — not an old error
                        "sync_error": bool(s.last_sync_error)
                        and (
                            s.sync_status == "failed"
                            or s.last_sync_success_at is None
                            or (
                                s.last_sync_attempt_at is not None
                                and s.last_sync_attempt_at > s.last_sync_success_at
                            )
                        ),
                        "sync_failed_at": s.last_sync_attempt_at.isoformat()
                        if s.last_sync_attempt_at
                        else None,
                        # 027: only the title's own page in a library (Plex, Jellyfin, Grimmory…) — never
                        # a download manager's or a service's home
                        "link": s.item_link,
                        "item_link": s.item_link,
                    }
                    for s in sources
                ],
            },
        )

    async def _concerned(self, viewer: Principal, users: list[UUID]) -> list[dict[str, Any]]:
        directory = None
        try:
            providers = self.capabilities.system_providers(DIRECTORY)
            directory = providers[0].provider if providers else None
        except Exception:
            directory = None
        out = []
        for user in users:
            if user == self._user(viewer):
                continue
            shown = await self.visibility.filter(viewer, user, HISTORY_CLASS, None, True)
            if isinstance(shown, Redacted):
                continue
            summary = await directory.get_user_summary(user) if directory is not None else None
            if summary is None or summary.anonymized or not summary.is_active:
                continue
            out.append({"user_id": str(user), "display_name": summary.display_name})
        return out[:20]

    async def _history(self, object_id: UUID, view: Any, viewer: Principal) -> Section:
        user = self._user(viewer)
        async with self.database.session() as session:
            mine = (
                (
                    await session.execute(
                        select(HistoryEntry)
                        .where(
                            HistoryEntry.object_id == object_id,
                            HistoryEntry.user_id == user,
                            HistoryEntry.kind != "progress",
                        )
                        .order_by(HistoryEntry.occurred_at.desc())
                        .limit(50)
                    )
                )
                .scalars()
                .all()
            )
            others = [
                r[0]
                for r in await session.execute(
                    select(HistoryEntry.user_id)
                    .where(HistoryEntry.object_id == object_id, HistoryEntry.completed.is_(True))
                    .group_by(HistoryEntry.user_id)
                    .order_by(func.max(HistoryEntry.occurred_at).desc())
                    .limit(100)
                )
            ]
        data = {
            "mine": [
                {
                    "occurred_at": h.occurred_at.isoformat(),
                    "completed": h.completed,
                    "position_s": h.position_to_s,
                }
                for h in mine
            ],
            "concerned_users": await self._concerned(viewer, others),
        }
        return Section(
            "available" if mine or data["concerned_users"] else "no-data", utc_now(self.clock), data
        )

    async def _progress(self, object_id: UUID, view: Any, viewer: Principal) -> Section:
        user = self._user(viewer)
        async with self.database.session() as session:
            row = await session.get(UserProgress, (user, object_id)) if user else None
        if row is None:
            return Section("no-data", utc_now(self.clock))
        return Section(
            "available",
            row.last_occurred_at,
            {"state": row.state, "percent": row.percent, "resume_position_s": row.resume_position_s},
        )

    async def _requests(self, object_id: UUID, view: Any, viewer: Principal) -> Section:
        user = self._user(viewer)
        async with self.database.session() as session:
            mine = (
                (
                    await session.execute(
                        select(MediaRequest)
                        .where(MediaRequest.object_id == object_id, MediaRequest.requester_user_id == user)
                        .order_by(MediaRequest.requested_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            total = await session.scalar(
                select(func.count()).where(
                    MediaRequest.object_id == object_id,
                    MediaRequest.state.in_(("pending", "approved", "processing")),
                )
            )
        return Section(
            "available",
            utc_now(self.clock),
            {
                "mine": [
                    {"id": str(r.id), "state": r.state, "requested_at": r.requested_at.isoformat()}
                    for r in mine
                ],
                "open_total": int(total or 0),
            },
        )

    async def _people(self, object_id: UUID, view: Any, viewer: Principal) -> Section:
        async with self.database.session() as session:
            people = [
                r[0]
                for r in await session.execute(
                    select(ObjectTag.value).where(
                        ObjectTag.object_id == object_id, ObjectTag.tag_kind == "person"
                    )
                )
            ]
        return Section("available" if people else "no-data", utc_now(self.clock), {"people": people})

    async def _statistics(self, object_id: UUID, view: Any, viewer: Principal) -> Section:
        async with self.database.session() as session:
            finishers = await session.scalar(
                select(func.count(func.distinct(HistoryEntry.user_id))).where(
                    HistoryEntry.object_id == object_id, HistoryEntry.completed.is_(True)
                )
            )
        count = int(finishers or 0)
        if count < COHORT:
            return Section("insufficient_data", utc_now(self.clock), {"min_cohort_size": COHORT})
        return Section("available", utc_now(self.clock), {"finished_by": count})

    async def _events(self, object_id: UUID, view: Any, viewer: Principal) -> Section:
        async with self.database.session() as session:
            row = await session.get(MediaObject, object_id)
            merges = (
                (
                    await session.execute(
                        select(MergeLog)
                        .where(MergeLog.object_id == object_id)
                        .order_by(MergeLog.created_at.desc())
                        .limit(20)
                    )
                )
                .scalars()
                .all()
            )
        timeline = [{"type": "media.added", "at": row.first_seen_at.isoformat()}] if row is not None else []
        timeline += [
            {
                "type": f"media.{m.action}d" if m.action == "merge" else "media.split",
                "at": m.created_at.isoformat(),
            }
            for m in merges
        ]
        return Section(
            "available",
            utc_now(self.clock),
            {"events": sorted(timeline, key=lambda e: e["at"], reverse=True)},
        )

    async def _actions(self, object_id: UUID, view: Any, viewer: Principal) -> Section:
        actions = [{"id": "media.open", "route": f"/media/{object_id}"}]
        if not view.available and await self._allowed(viewer, MEDIA_REQUEST):
            actions.append({"id": "media.request", "route": f"/media/{object_id}?request=1"})
        if await self._allowed(viewer, MEDIA_MANAGE):
            actions.append({"id": "media.manage", "route": f"/admin/media?object={object_id}"})
        return Section("available", utc_now(self.clock), {"actions": actions})

    async def _links(self, object_id: UUID, view: Any, viewer: Principal) -> Section:
        links = []
        for scheme, value in sorted(view.ids.items()):
            if scheme in LINKS:
                label, template = LINKS[scheme]
                kind = "tv" if view.kind in ("series", "season", "episode") else "movie"
                links.append({"label": label, "url": template.format(kind=kind, value=value)})
        return Section("available" if links else "no-data", utc_now(self.clock), {"links": links})

    async def _blocks(self, object_id: UUID, view: Any, viewer: Principal) -> Section:
        out = []
        for block in self.blocks.for_kind(view.kind):
            if block.required_permission and not await self._allowed(viewer, block.required_permission):
                continue
            try:
                data = await asyncio.wait_for(block.load(object_id, viewer), timeout=5)
                out.append(
                    {
                        "key": block.key,
                        "title_key": block.title_key,
                        "template": block.template,
                        "state": "available",
                        "data": data,
                    }
                )
            except Exception:
                out.append(
                    {
                        "key": block.key,
                        "title_key": block.title_key,
                        "template": block.template,
                        "state": "unavailable",
                        "data": {},
                    }
                )
        return Section("available" if out else "no-data", utc_now(self.clock), {"blocks": out})

    async def _allowed(self, viewer: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(viewer, permission)
        except Exception:
            return False
