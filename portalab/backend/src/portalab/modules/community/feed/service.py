"""Feed reads (T010; US2): entries newest first, each re-checked **at read time** against the actor's
current ``community_activity`` visibility — an actor turning Private disappears at once. Keyset cursor
over ``(occurred_at, id)``; retention purge and erasure with the actor."""

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, or_, select

from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.core.visibility_port import VisibilityFilter
from portalab.modules.community.models import FeedEntry
from portalab.modules.community.preferences import ACTIVITY, shown

MAX_SCANS = 6


@dataclass(frozen=True, slots=True)
class FeedItem:
    id: UUID
    actor_id: UUID
    actor_name: str | None
    kind: str
    text_key: str
    params: dict[str, Any]
    subject_ref: str | None
    source_event_id: UUID
    occurred_at: datetime


def encode(at: datetime, entry: UUID) -> str:
    raw = json.dumps({"t": at.isoformat(), "i": str(entry)}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode(cursor: str | None) -> tuple[datetime, UUID] | None:
    if not cursor:
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode((cursor + "=" * (-len(cursor) % 4)).encode()))
        return datetime.fromisoformat(data["t"]), UUID(data["i"])
    except (ValueError, KeyError, TypeError):
        return None


class FeedService:
    def __init__(
        self,
        database: Database,
        visibility: VisibilityFilter,
        names: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.visibility = visibility
        self.names = names  # async (UUID) -> str | None
        self.clock = clock

    async def page(
        self,
        viewer: Principal,
        *,
        cursor: str | None = None,
        limit: int = 20,
        actor: UUID | None = None,
        kinds: tuple[str, ...] | None = None,
        exclude: tuple[str, ...] = (),
    ) -> tuple[list[FeedItem], str | None]:
        limit = max(1, min(limit, 50))
        position = decode(cursor)
        allowed: dict[UUID, bool] = {}
        items: list[FeedItem] = []
        for _ in range(MAX_SCANS):
            statement = select(FeedEntry).order_by(FeedEntry.occurred_at.desc(), FeedEntry.id.desc())
            if position is not None:
                at, last = position
                statement = statement.where(
                    or_(
                        FeedEntry.occurred_at < at,
                        and_(FeedEntry.occurred_at == at, FeedEntry.id < last),
                    )
                )
            if actor is not None:
                statement = statement.where(FeedEntry.actor_user_id == actor)
            if kinds:
                statement = statement.where(FeedEntry.kind.in_(kinds))
            if exclude:
                statement = statement.where(FeedEntry.kind.not_in(exclude))
            async with self.database.session() as session:
                rows = list((await session.execute(statement.limit(limit * 2))).scalars())
            for row in rows:
                position = (row.occurred_at, row.id)
                if row.actor_user_id not in allowed:
                    allowed[row.actor_user_id] = await shown(
                        self.visibility, viewer, row.actor_user_id, ACTIVITY, True
                    )
                if not allowed[row.actor_user_id]:
                    continue
                items.append(
                    FeedItem(
                        row.id,
                        row.actor_user_id,
                        await self.names(row.actor_user_id),
                        row.kind,
                        row.text_key,
                        dict(row.params),
                        row.subject_ref,
                        row.source_event_id,
                        row.occurred_at,
                    )
                )
                if len(items) == limit:
                    return items, encode(*position)
            if len(rows) < limit * 2:
                return items, None
        return items, encode(*position) if position else None

    async def purge(self, days: int) -> int:
        cutoff = utc_now(self.clock) - timedelta(days=max(1, days))
        async with self.database.unit_of_work() as uow:
            result = await uow.session.execute(delete(FeedEntry).where(FeedEntry.occurred_at < cutoff))
        return int(getattr(result, "rowcount", 0) or 0)
