"""Ports Media provides: ``media.history`` (privacy-bounded history/progress for other modules) and
``activity.attributes`` for media events (T037; used by 014 campaign and 019 automation conditions)."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.activity import ActivityAttributes
from portalab.capabilities.media_core import HistoryItem, Progress
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.visibility_port import OwnerOnlyVisibility, Redacted, VisibilityFilter
from portalab.modules.media.models import HistoryEntry, MediaObject, UserProgress
from portalab.modules.media.sections.service import HISTORY_CLASS


class HistoryReader:
    def __init__(self, database: Database, visibility: VisibilityFilter | None = None) -> None:
        self.database = database
        self.visibility: VisibilityFilter = visibility or OwnerOnlyVisibility()

    async def _visible(self, user: UUID, viewer: Principal) -> bool:
        if (viewer.acting_for or viewer.user_id) == user or viewer.channel == "system":
            return True
        return not isinstance(await self.visibility.filter(viewer, user, HISTORY_CLASS, None, True), Redacted)

    async def for_user(
        self, user: UUID, viewer: Principal, *, limit: int = 50, kind: str | None = None
    ) -> Sequence[HistoryItem]:
        if not await self._visible(user, viewer):
            return []
        stmt = (
            select(HistoryEntry, MediaObject)
            .join(MediaObject, MediaObject.id == HistoryEntry.object_id)
            .where(HistoryEntry.user_id == user, HistoryEntry.kind != "progress")
            .order_by(HistoryEntry.occurred_at.desc())
            .limit(max(1, min(limit, 500)))
        )
        if kind:
            stmt = stmt.where(MediaObject.kind == kind)
        async with self.database.session() as session:
            rows = (await session.execute(stmt)).all()
        return [
            HistoryItem(o.id, o.kind, o.title, h.occurred_at, h.completed, h.position_to_s) for h, o in rows
        ]

    async def progress(self, user: UUID, viewer: Principal, object_id: UUID) -> Progress | None:
        if not await self._visible(user, viewer):
            return None
        async with self.database.session() as session:
            row = await session.get(UserProgress, (user, object_id))
        if row is None:
            return None
        return Progress(row.object_id, row.percent, row.resume_position_s, row.state, row.last_occurred_at)  # type: ignore[arg-type]


class MediaActivityAttributes:
    """Media kind, canonical genres and titles of the object a media event is about."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def handles(self, event_type: str) -> bool:
        return event_type.startswith("media.")

    async def attributes(self, event_type: str, payload: dict[str, Any]) -> ActivityAttributes | None:
        raw = payload.get("object")
        if not raw:
            return None
        try:
            object_id = UUID(str(raw))
        except ValueError:
            return None
        async with self.database.session() as session:
            row = await session.get(MediaObject, object_id)
            if row is None:
                return None
            effective = row.effective or {}
            genres = effective.get("genres") or ()
            parent_id, hops = row.parent_id, 0
            # 027: an episode or a season carries no genres of its own — its series does
            while not genres and parent_id is not None and hops < 3:
                parent = await session.get(MediaObject, parent_id)
                if parent is None:
                    break
                genres = (parent.effective or {}).get("genres") or ()
                parent_id, hops = parent.parent_id, hops + 1
        return ActivityAttributes(
            media_kind=row.kind,
            genres=tuple(sorted({str(g).strip().casefold() for g in genres})),
            title=row.title,
            original_title=effective.get("original_title"),
        )
