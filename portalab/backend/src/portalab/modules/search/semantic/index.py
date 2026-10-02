"""Semantic index (T016; R3, R4): ``search.embeddings`` holds **ids and vectors only**, filled by the
``search.index`` job from providers implementing ``Indexable`` through the optional ``EmbeddingProvider``
port (content-hash skip). Queries over-fetch ANN candidates, which the coordinator re-hydrates and
re-authorizes through the owning provider — the index is never authoritative for permissions.

Everything here tolerates absence: no pgvector, no table or no embedding provider ⇒ ``available()`` is
false and semantic mode is reported ``unavailable`` (never silently pretended)."""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import EMBEDDING, Indexable, ParsedQuery, SearchRegistry
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.search.models import IndexState
from portalab.modules.search.observability import log, metrics

OVER_FETCH = 3
BATCH = 32


def _vector(values: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


class SemanticIndex:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        registry: SearchRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.registry = registry
        self.clock = clock
        self._table: bool | None = None

    def embedder(self) -> Any | None:
        providers = self.capabilities.system_providers(EMBEDDING)
        return providers[0].provider if providers else None

    async def table_exists(self) -> bool:
        if self._table is None:
            try:
                async with self.database.session() as session:
                    found = await session.scalar(text("SELECT to_regclass('search.embeddings') IS NOT NULL"))
                self._table = bool(found)
            except Exception:
                return False
        return self._table

    async def available(self) -> bool:
        return self.embedder() is not None and await self.table_exists()

    async def candidates(
        self, query: ParsedQuery, kinds: Sequence[str], top_k: int
    ) -> Mapping[str, Sequence[str]] | None:
        embedder = self.embedder()
        if embedder is None or not kinds or not await self.table_exists():
            return None
        [vector] = await embedder.embed([query.text], query.language)
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT kind, id FROM search.embeddings WHERE kind = ANY(:kinds) "
                        "ORDER BY embedding <=> CAST(:vector AS vector) LIMIT :limit"
                    ),
                    {"kinds": list(kinds), "vector": _vector(vector), "limit": max(1, top_k) * OVER_FETCH},
                )
            ).all()
        found: dict[str, list[str]] = {}
        for kind, item_id in rows:
            found.setdefault(kind, []).append(item_id)
        return found

    async def index(self, kind: str, *, full: bool = False) -> int:
        """Embed new or changed documents of ``kind``; returns how many were (re)embedded."""
        provider = self.registry.provider(kind)
        embedder = self.embedder()
        if provider is None or not isinstance(provider, Indexable):
            return 0
        if embedder is None or not await self.table_exists():
            await self._state(kind, error="semantic index unavailable (no embedding provider or pgvector)")
            return 0
        async with self.database.session() as session:
            state = await session.get(IndexState, kind)
            since = None if full or state is None else state.last_indexed_at
            rows = await session.execute(
                text("SELECT id || ':' || language, content_hash FROM search.embeddings WHERE kind = :k"),
                {"k": kind},
            )
            known = {str(ref): str(content_hash) for ref, content_hash in rows.all()}
        pending = [
            document
            async for document in provider.documents(since)
            if known.get(f"{document.id}:{document.language or ''}") != document.content_hash
        ]
        done = 0
        try:
            for start in range(0, len(pending), BATCH):
                batch = pending[start : start + BATCH]
                vectors = await embedder.embed([d.text for d in batch], batch[0].language if batch else None)
                async with self.database.unit_of_work() as uow:
                    for document, vector in zip(batch, vectors, strict=True):
                        await uow.session.execute(
                            text(
                                "INSERT INTO search.embeddings (kind, id, language, embedding, content_hash, "
                                "model_id, indexed_at) VALUES (:kind, :id, :language, "
                                "CAST(:vector AS vector), "
                                ":hash, :model, :now) ON CONFLICT (kind, id, language) DO UPDATE SET "
                                "embedding = EXCLUDED.embedding, content_hash = EXCLUDED.content_hash, "
                                "model_id = EXCLUDED.model_id, indexed_at = EXCLUDED.indexed_at"
                            ),
                            {
                                "kind": kind,
                                "id": document.id,
                                "language": document.language or "",
                                "vector": _vector(vector),
                                "hash": document.content_hash,
                                "model": embedder.model_id,
                                "now": utc_now(self.clock),
                            },
                        )
                done += len(batch)
        except Exception as exc:
            log.warning("semantic indexing failed", extra={"kind": kind})
            metrics.increment("search.index.failures")
            await self._state(kind, error=type(exc).__name__)
            return done
        await self._state(kind, full=full, model=embedder.model_id)
        return done

    async def forget(self, kind: str, ids: Sequence[str]) -> None:
        """Drop vectors of deleted objects (the owner calls this from its own change handling)."""
        if ids and await self.table_exists():
            async with self.database.unit_of_work() as uow:
                await uow.session.execute(
                    text("DELETE FROM search.embeddings WHERE kind = :k AND id = ANY(:ids)"),
                    {"k": kind, "ids": list(ids)},
                )

    async def _state(
        self, kind: str, *, full: bool = False, model: str | None = None, error: str | None = None
    ) -> None:
        now = utc_now(self.clock)
        values: dict[str, Any] = {"kind": kind, "pending_count": 0, "updated_at": now, "last_error": error}
        if error is None:
            values["last_indexed_at"] = now
            values["embedding_model"] = model
            if full:
                values["last_full_reindex_at"] = now
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(IndexState)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=["kind"], set_={k: v for k, v in values.items() if k != "kind"}
                )
            )

    async def status(self) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            rows = (await session.execute(select(IndexState).order_by(IndexState.kind))).scalars().all()
        return [
            {
                "kind": row.kind,
                "last_full_reindex_at": row.last_full_reindex_at.isoformat()
                if row.last_full_reindex_at
                else None,
                "last_indexed_at": row.last_indexed_at.isoformat() if row.last_indexed_at else None,
                "pending_count": row.pending_count,
                "last_error": row.last_error,
                "embedding_model": row.embedding_model,
            }
            for row in rows
        ]
