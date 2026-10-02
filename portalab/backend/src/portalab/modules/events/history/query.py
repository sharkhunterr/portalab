"""History queries (T021; FR-015..020, R1): history *is* the event store, read through permissions and
privacy. A user sees their own history; anyone else sees only event types whose visibility class is public
or community **and** that the privacy engine lets through for the ``history`` datum class (owner-only by
default, CD-016). Pagination is newest first on ``(occurred_at, event_id)``."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, or_, select

from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.capabilities.visibility import register_datum_class
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import BadRequest
from portalab.core.visibility_port import Redacted, VisibilityFilter
from portalab.modules.events.models import Event

HISTORY = "history"
MAX_PAGE = 100

register_datum_class(
    HISTORY,
    owner="module:events",
    default_level="private",
    classification="history",
    description="Activity history (events attributable to you)",
    user_choosable=False,
)


@dataclass(frozen=True, slots=True)
class HistoryItem:
    event_id: UUID
    type: str
    occurred_at: datetime
    source_system: str
    actor_kind: str
    subject_type: str | None
    subject_id: str | None
    payload: dict[str, Any]


def _cursor(statement: Select[tuple[Event]], cursor: str | None) -> Select[tuple[Event]]:
    if not cursor:
        return statement
    try:
        stamp, event_id = cursor.split("|", 1)
        when, ident = datetime.fromisoformat(stamp), UUID(event_id)
    except ValueError as exc:
        raise BadRequest("Invalid cursor.", code="pagination.invalid_cursor") from exc
    return statement.where(
        or_(Event.occurred_at < when, and_(Event.occurred_at == when, Event.event_id < ident))
    )


class HistoryQuery:
    def __init__(
        self,
        database: Database,
        visibility: VisibilityFilter | None,
        *,
        event_types: EventTypeRegistry = default_event_types,
    ) -> None:
        self.database = database
        self.visibility = visibility
        self.event_types = event_types

    async def _page(
        self, statement: Select[tuple[Event]], cursor: str | None, limit: int
    ) -> tuple[list[Event], str | None]:
        limit = max(1, min(limit, MAX_PAGE))
        statement = (
            _cursor(statement, cursor)
            .order_by(Event.occurred_at.desc(), Event.event_id.desc())
            .limit(limit + 1)
        )
        async with self.database.session() as session:
            rows = list((await session.execute(statement)).scalars())
        page = rows[:limit]
        next_cursor = f"{page[-1].occurred_at.isoformat()}|{page[-1].event_id}" if len(rows) > limit else None
        return page, next_cursor

    def _shareable_types(self) -> list[str]:
        return [t.name for t in self.event_types.all() if t.visibility_class in ("public", "community")]

    async def for_user(
        self, viewer: Principal, user_id: UUID, *, cursor: str | None = None, limit: int = 50
    ) -> tuple[list[HistoryItem], str | None]:
        mine = or_(
            Event.actor_user_id == user_id,
            and_(Event.subject_type == "user", Event.subject_id == str(user_id)),
        )
        statement = select(Event).where(mine)
        owner = (viewer.acting_for or viewer.user_id) == user_id
        if not owner:
            statement = statement.where(Event.type.in_(self._shareable_types()))
        rows, next_cursor = await self._page(statement, cursor, limit)
        items = []
        for row in rows:
            if not owner and self.visibility is not None:
                shown = await self.visibility.filter(viewer, user_id, HISTORY, row.type, row.payload)
                if isinstance(shown, Redacted):
                    continue
            elif not owner:
                continue  # no privacy engine: owner-only (CD-016)
            items.append(_item(row))
        return items, next_cursor

    async def for_subject(
        self,
        viewer: Principal,
        subject_type: str,
        subject_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[HistoryItem], str | None]:
        if subject_type == "user":
            return await self.for_user(viewer, UUID(subject_id), cursor=cursor, limit=limit)
        statement = select(Event).where(
            Event.subject_type == subject_type,
            Event.subject_id == subject_id,
            Event.visibility_class.in_(["public", "community"]),
        )
        rows, next_cursor = await self._page(statement, cursor, limit)
        return [_item(row) for row in rows], next_cursor


def _item(row: Event) -> HistoryItem:
    return HistoryItem(
        row.event_id,
        row.type,
        row.occurred_at,
        row.source_system,
        row.actor_kind,
        row.subject_type,
        row.subject_id,
        dict(row.payload),
    )
