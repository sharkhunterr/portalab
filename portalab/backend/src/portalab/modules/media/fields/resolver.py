"""``FieldResolver`` (T013; R3, CD-026): every source's value is kept per field (``field_candidates``);
the effective value follows ``media.fieldPriority.<kind>.<field>`` (first listed source with a value wins,
then active sources before inactive ones, then name order), an Admin override (pseudo-source ``admin``)
beats every source, and the winner of each field is recorded as provenance. Deterministic: the same
candidates and priorities always give the same object."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.record_sink import reconcile
from portalab.modules.media.common import sort_title
from portalab.modules.media.models import FieldCandidate, MediaObject, ObjectTag, SourceItem

FIELDS = (
    "title",
    "original_title",
    "overview",
    "year",
    "genres",
    "people",
    "authors",  # #92: books — who wrote it, who reads it; films — who directed it
    "narrators",
    "directors",
    "language",
    "duration_s",
    "pages",
    "image",
    "series",  # 027: books (Grimmory)
    "series_position",
    "publisher",
    "released",
    "tags",
    "platform",  # 027: a game's console or system (RomM)
    "resolution",  # 027: the video file's resolution (statistics)
)
ADMIN = "admin"
Priorities = Callable[[str], Awaitable[Mapping[str, Sequence[str]]]]


class FieldResolver:
    def __init__(self, priorities: Priorities) -> None:
        self.priorities = priorities

    async def store_candidates(self, session: AsyncSession, item: SourceItem) -> None:
        if item.object_id is None:
            return
        for name in FIELDS:
            value = item.payload.get(name)
            if value in (None, "", []):
                await session.execute(
                    delete(FieldCandidate).where(
                        FieldCandidate.object_id == item.object_id,
                        FieldCandidate.field == name,
                        FieldCandidate.source_system == item.source_system,
                    )
                )
                continue
            values = {"source_item_id": item.id, "value": value, "observed_at": item.observed_at}
            await session.execute(
                insert(FieldCandidate)
                .values(object_id=item.object_id, field=name, source_system=item.source_system, **values)
                .on_conflict_do_update(index_elements=["object_id", "field", "source_system"], set_=values)
            )

    async def recompute(self, session: AsyncSession, object_id: UUID) -> list[str]:
        """Recompute the effective fields of one object; returns the names that changed."""
        row = await session.get(MediaObject, object_id, with_for_update=True)
        if row is None:
            return []
        candidates = (
            (await session.execute(select(FieldCandidate).where(FieldCandidate.object_id == object_id)))
            .scalars()
            .all()
        )
        active = {
            source
            for (source,) in await session.execute(
                select(SourceItem.source_system).where(
                    SourceItem.object_id == object_id, SourceItem.active.is_(True)
                )
            )
        }
        by_source: dict[str, dict[str, Any]] = {}
        overrides: dict[str, Any] = {}
        for candidate in candidates:
            if candidate.source_system == ADMIN:
                overrides[candidate.field] = candidate.value
            else:
                by_source.setdefault(candidate.source_system, {})[candidate.field] = candidate.value
        priorities = await self.priorities(row.kind)
        merged = reconcile(by_source, priorities, default_order=sorted(active))
        effective = dict(merged.values)
        provenance = dict(merged.provenance)
        for name, value in overrides.items():
            effective[name], provenance[name] = value, ADMIN
        if not effective.get("title"):
            effective["title"] = row.title  # an object always keeps its last known title
        changed = sorted(
            k for k in set(effective) | set(row.effective) if effective.get(k) != row.effective.get(k)
        )
        if not changed and provenance == row.field_provenance:
            return []
        row.effective, row.field_provenance = effective, provenance
        row.title = str(effective["title"])[:500]
        row.sort_title = sort_title(row.title)
        year = effective.get("year")
        row.year = int(year) if isinstance(year, int | float) else None
        await self._tags(session, object_id, effective)
        return changed

    async def _tags(self, session: AsyncSession, object_id: UUID, effective: Mapping[str, Any]) -> None:
        await session.execute(delete(ObjectTag).where(ObjectTag.object_id == object_id))
        seen: set[tuple[str, str]] = set()
        for tag_kind, name in (("genre", "genres"), ("person", "people")):
            for value in effective.get(name) or []:
                text = str(value).strip()[:120]
                if text and (tag_kind, text.casefold()) not in seen:
                    seen.add((tag_kind, text.casefold()))
                    session.add(ObjectTag(object_id=object_id, tag_kind=tag_kind, value=text))
