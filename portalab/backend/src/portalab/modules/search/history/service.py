"""Search history (T026; R8, FR-019..021): personal data (class ``activity``), private to its owner — every
read and delete is keyed by the caller's own user id, so no cross-user path exists. Upsert per normalized
query, capped (last N) and retention-limited, clearable, disabled by ``search.historyEnabled``, exported and
erased with the account (privacy participants)."""

from collections.abc import Callable, Sequence
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import ParsedQuery
from portalab.core.db import Database
from portalab.core.errors import NotFound
from portalab.core.time import Clock, utc_now
from portalab.modules.search.models import SearchHistory
from portalab.modules.search.settings import HISTORY_ENABLED, SearchConfig


class HistoryService:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        config: Callable[[], SearchConfig],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.config = config
        self.clock = clock

    async def enabled_for(self, user_id: UUID) -> bool:
        providers = self.capabilities.system_providers(CONFIG)
        if not providers:
            return True
        try:
            return bool((await providers[0].provider.get(HISTORY_ENABLED, user_id=user_id)).value)
        except Exception:
            return False  # unknown preference: do not record personal data

    async def record(self, user_id: UUID, query: ParsedQuery, raw: str) -> bool:
        text = " ".join(raw.split())[:512]
        if not query.normalized or not text or not await self.enabled_for(user_id):
            return False
        now = utc_now(self.clock)
        filters: dict[str, Any] = {name: list(values) for name, values in query.filters.items()}
        if query.kinds:
            filters["type"] = list(query.kinds)
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(SearchHistory)
                .values(
                    user_id=user_id,
                    query_text=text,
                    normalized_query=query.normalized[:512],
                    mode=query.mode,
                    filters=filters,
                    count=1,
                    performed_at=now,
                    created_at=now,
                )
                .on_conflict_do_update(
                    constraint="uq_history_user_query",
                    set_={
                        "query_text": text,
                        "mode": query.mode,
                        "filters": filters,
                        "count": SearchHistory.count + 1,
                        "performed_at": now,
                    },
                )
            )
            keep = max(1, self.config().history_max_entries)
            stale = (
                select(SearchHistory.id)
                .where(SearchHistory.user_id == user_id)
                .order_by(SearchHistory.performed_at.desc(), SearchHistory.id.desc())
                .offset(keep)
            )
            await uow.session.execute(delete(SearchHistory).where(SearchHistory.id.in_(stale)))
        return True

    async def list(self, user_id: UUID) -> Sequence[SearchHistory]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(SearchHistory)
                .where(SearchHistory.user_id == user_id)
                .order_by(SearchHistory.performed_at.desc(), SearchHistory.id.desc())
                .limit(max(1, self.config().history_max_entries))
            )
            return list(rows.scalars())

    async def delete(self, user_id: UUID, entry_id: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            result = await uow.session.execute(
                delete(SearchHistory).where(SearchHistory.id == entry_id, SearchHistory.user_id == user_id)
            )
            if not getattr(result, "rowcount", 0):
                raise NotFound("This history entry does not exist.", code="search.history_not_found")

    async def clear(self, user_id: UUID) -> int:
        async with self.database.unit_of_work() as uow:
            result = await uow.session.execute(delete(SearchHistory).where(SearchHistory.user_id == user_id))
            return int(getattr(result, "rowcount", 0) or 0)

    async def purge_expired(self) -> int:
        cutoff = utc_now(self.clock) - timedelta(days=max(1, self.config().history_retention_days))
        async with self.database.unit_of_work() as uow:
            result = await uow.session.execute(
                delete(SearchHistory).where(SearchHistory.performed_at < cutoff)
            )
            return int(getattr(result, "rowcount", 0) or 0)

    async def count(self, user_id: UUID) -> int:
        async with self.database.session() as session:
            return int(
                await session.scalar(
                    select(func.count()).select_from(SearchHistory).where(SearchHistory.user_id == user_id)
                )
                or 0
            )


class HistoryParticipant:
    """Export and final erasure of a user's search history (021 participants; idempotent)."""

    def __init__(self, history: HistoryService) -> None:
        self.history = history

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        return [
            ExportRecord(
                "search.history",
                {
                    "query": row.query_text,
                    "mode": row.mode,
                    "filters": row.filters,
                    "count": row.count,
                    "performed_at": row.performed_at.isoformat(),
                },
            )
            for row in await self.history.list(user_id)
        ]

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        await self.history.clear(user_id)
