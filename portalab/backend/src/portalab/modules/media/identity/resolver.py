"""``IdentityResolver`` (T012; R1, R2, CD-015): media identity is the portal's, never a source's.

* **id-first**: a source item sharing a strong external id (``tmdb``, ``imdb``…) with an object resolves
  to it; ids pointing to *different* objects are a conflict — the item goes to the object of its first
  matching id and nothing is merged;
* children without ids resolve by ``(parent object, kind, position)``;
* otherwise a new object is created; when a same-kind object has a very similar title and the same year
  and no conflicting ids, a **match candidate** is queued for the Admin (fuzzy evidence never merges);
* merge/split are Admin actions, audited, logged in the append-only ``merge_log`` and reversible: the log
  keeps every moved row so a split restores exactly what the merge moved.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.errors import Conflict, NotFound
from portalab.modules.media.common import normalize_title, sort_title, strong_ids
from portalab.modules.media.models import (
    ExternalId,
    FieldCandidate,
    HistoryEntry,
    MatchCandidate,
    MediaObject,
    MediaRequest,
    MergeLog,
    PlaybackSession,
    SourceItem,
)

SCHEME_ORDER = (
    "tmdb",
    "imdb",
    "tvdb",
    "igdb",
    "isbn",
    "asin",
    "musicbrainz",
    "anilist",
    "openlibrary",
    "hardcover",
    "goodreads",
)


class MediaNotFound(NotFound):
    default_code = "media.not_found"
    default_title = "Media not found"


class MergeConflict(Conflict):
    default_code = "media.merge_conflict"
    default_title = "These objects cannot be merged"


@dataclass(frozen=True, slots=True)
class Attached:
    object_id: UUID
    created: bool


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


async def live_object(session: AsyncSession, object_id: UUID) -> MediaObject | None:
    """Follow ``merged_into`` pointers to the surviving object."""
    seen: set[UUID] = set()
    row = await session.get(MediaObject, object_id)
    while row is not None and row.merged_into is not None and row.id not in seen:
        seen.add(row.id)
        row = await session.get(MediaObject, row.merged_into)
    return row


class IdentityResolver:
    def __init__(self, threshold: Any) -> None:
        self.threshold = threshold  # callable → float

    async def attach(self, session: AsyncSession, item: SourceItem, now: datetime) -> Attached:
        payload = item.payload
        ids = strong_ids(payload.get("ids") or {})
        if item.object_id is not None:
            current = await live_object(session, item.object_id)
            if current is not None:
                item.object_id = current.id
                await self._claim_ids(session, current.id, ids)
                await self._parent(session, item, current)
                return Attached(current.id, False)
        owners = await self._owners(session, ids)
        if owners:
            target = owners[0]
            item.object_id = target
            await self._claim_ids(session, target, ids)
            row = await session.get(MediaObject, target)
            if row is not None:
                await self._parent(session, item, row)
            return Attached(target, False)
        parent = await self._parent_object(session, item)
        if parent is not None and payload.get("position") is not None:
            sibling = (
                await session.execute(
                    select(MediaObject.id).where(
                        MediaObject.parent_id == parent,
                        MediaObject.kind == item.kind,
                        MediaObject.position == int(payload["position"]),
                        MediaObject.status == "active",
                    )
                )
            ).scalar_one_or_none()
            if sibling is not None:
                item.object_id = sibling
                return Attached(sibling, False)
        title = str(payload.get("title") or item.external_id)[:500]
        row = MediaObject(
            kind=item.kind,
            parent_id=parent,
            position=payload.get("position"),
            title=title,
            sort_title=sort_title(title),
            year=payload.get("year"),
            available=False,
            effective={},
            field_provenance={},
            status="active",
            first_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
        item.object_id = row.id
        await self._claim_ids(session, row.id, ids)
        await self._propose(session, row, ids, now)
        return Attached(row.id, True)

    async def _owners(self, session: AsyncSession, ids: Mapping[str, str]) -> list[UUID]:
        if not ids:
            return []
        rows = (
            await session.execute(
                select(ExternalId.scheme, ExternalId.object_id).where(
                    or_(*(and_(ExternalId.scheme == s, ExternalId.value == v) for s, v in ids.items()))
                )
            )
        ).all()
        rank = {scheme: i for i, scheme in enumerate(SCHEME_ORDER)}
        owners: list[UUID] = []
        for _, object_id in sorted(rows, key=lambda r: rank.get(r[0], 99)):
            live = await live_object(session, object_id)
            if live is not None and live.id not in owners:
                owners.append(live.id)
        return owners

    async def _claim_ids(self, session: AsyncSession, object_id: UUID, ids: Mapping[str, str]) -> None:
        for scheme, value in ids.items():
            # an id already owned by another object stays there (conflict: never merged silently)
            await session.execute(
                insert(ExternalId)
                .values(scheme=scheme, value=value, object_id=object_id)
                .on_conflict_do_nothing(index_elements=["scheme", "value"])
            )

    async def _parent_object(self, session: AsyncSession, item: SourceItem) -> UUID | None:
        parent_ref = item.payload.get("parent")
        if not parent_ref:
            return None
        parent = (
            await session.execute(
                select(SourceItem.object_id).where(
                    SourceItem.service_id == item.service_id, SourceItem.external_id == str(parent_ref)
                )
            )
        ).scalar_one_or_none()
        if parent is None:
            return None
        live = await live_object(session, parent)
        return live.id if live is not None else None

    async def _parent(self, session: AsyncSession, item: SourceItem, row: MediaObject) -> None:
        if row.parent_id is None:
            parent = await self._parent_object(session, item)
            if parent is not None and parent != row.id:
                row.parent_id = parent
                if row.position is None and item.payload.get("position") is not None:
                    row.position = int(item.payload["position"])

    async def _propose(
        self, session: AsyncSession, row: MediaObject, ids: Mapping[str, str], now: datetime
    ) -> None:
        if row.parent_id is not None:
            return  # children follow their parent's identity
        threshold = float(self.threshold())
        candidates = (
            (
                await session.execute(
                    select(MediaObject).where(
                        MediaObject.kind == row.kind,
                        MediaObject.status == "active",
                        MediaObject.id != row.id,
                        MediaObject.parent_id.is_(None),
                        MediaObject.sort_title.ilike(f"{row.sort_title[:3]}%"),
                    )
                )
            )
            .scalars()
            .all()
        )
        for other in candidates:
            theirs = {
                scheme: value
                for scheme, value in await session.execute(
                    select(ExternalId.scheme, ExternalId.value).where(ExternalId.object_id == other.id)
                )
            }
            if any(scheme in theirs and theirs[scheme] != value for scheme, value in ids.items()):
                continue  # conflicting strong ids: different works
            title_score = similarity(row.title, other.title)
            year_score = 1.0 if row.year is not None and row.year == other.year else 0.0
            score = round(0.8 * title_score + 0.2 * year_score, 3)
            if score >= threshold:
                first, second = sorted((other.id, row.id))
                await session.execute(
                    insert(MatchCandidate)
                    .values(
                        object_a=first,
                        object_b=second,
                        score=score,
                        evidence={"title": round(title_score, 3), "year": bool(year_score)},
                        state="proposed",
                        created_at=now,
                    )
                    .on_conflict_do_nothing(constraint="uq_match_candidates_pair")
                )

    # --- merge / split (Admin) ----------------------------------------------------------------------------
    async def merge(self, session: AsyncSession, survivor: UUID, other: UUID, now: datetime) -> MergeLog:
        keep = await session.get(MediaObject, survivor, with_for_update=True)
        gone = await session.get(MediaObject, other, with_for_update=True)
        if keep is None or gone is None or keep.status == "merged" or gone.status == "merged":
            raise MediaNotFound("This object does not exist.")
        if keep.id == gone.id or keep.kind != gone.kind:
            raise MergeConflict("Only two different objects of the same kind can be merged.")
        mine: dict[str, str] = {
            scheme: value
            for scheme, value in await session.execute(
                select(ExternalId.scheme, ExternalId.value).where(ExternalId.object_id == keep.id)
            )
        }
        theirs = (
            await session.execute(
                select(ExternalId.scheme, ExternalId.value).where(ExternalId.object_id == gone.id)
            )
        ).all()
        if any(scheme in mine and mine[scheme] != value for scheme, value in theirs):
            raise MergeConflict("The two objects carry different strong ids for the same scheme.")
        moved: dict[str, list[Any]] = {}
        for model, column, key in (
            (SourceItem, SourceItem.object_id, "source_items"),
            (HistoryEntry, HistoryEntry.object_id, "history_entries"),
            (MediaRequest, MediaRequest.object_id, "requests"),
        ):
            ids = [r[0] for r in await session.execute(select(model.id).where(column == gone.id))]
            moved[key] = [str(i) for i in ids]
            if ids:
                await session.execute(update(model).where(model.id.in_(ids)).values(object_id=keep.id))
        sessions = [
            r[0]
            for r in await session.execute(
                select(PlaybackSession.session_key).where(PlaybackSession.object_id == gone.id)
            )
        ]
        moved["playback_sessions"] = sessions
        if sessions:
            await session.execute(
                update(PlaybackSession)
                .where(PlaybackSession.session_key.in_(sessions))
                .values(object_id=keep.id)
            )
        children = [
            r[0]
            for r in await session.execute(select(MediaObject.id).where(MediaObject.parent_id == gone.id))
        ]
        moved["children"] = [str(c) for c in children]
        if children:
            await session.execute(
                update(MediaObject).where(MediaObject.id.in_(children)).values(parent_id=keep.id)
            )
        moved["external_ids"] = [[s, v] for s, v in theirs]
        await session.execute(
            update(ExternalId).where(ExternalId.object_id == gone.id).values(object_id=keep.id)
        )
        candidates = (
            (await session.execute(select(FieldCandidate).where(FieldCandidate.object_id == gone.id)))
            .scalars()
            .all()
        )
        moved["field_candidates"] = []
        for candidate in candidates:
            exists = await session.get(FieldCandidate, (keep.id, candidate.field, candidate.source_system))
            if exists is None and candidate.source_system != "admin":
                moved["field_candidates"].append([candidate.field, candidate.source_system])
                await session.execute(
                    update(FieldCandidate)
                    .where(
                        FieldCandidate.object_id == gone.id,
                        FieldCandidate.field == candidate.field,
                        FieldCandidate.source_system == candidate.source_system,
                    )
                    .values(object_id=keep.id)
                )
        gone.status, gone.merged_into, gone.updated_at = "merged", keep.id, now
        keep.first_seen_at = min(keep.first_seen_at, gone.first_seen_at)
        keep.updated_at = now
        await session.execute(
            update(MatchCandidate)
            .where(
                or_(
                    and_(MatchCandidate.object_a == keep.id, MatchCandidate.object_b == gone.id),
                    and_(MatchCandidate.object_a == gone.id, MatchCandidate.object_b == keep.id),
                )
            )
            .values(state="accepted", decided_at=now)
        )
        entry = MergeLog(action="merge", object_id=keep.id, other_id=gone.id, details=moved, created_at=now)
        session.add(entry)
        await session.flush()
        return entry

    async def split(self, session: AsyncSession, merge_id: UUID, now: datetime) -> MergeLog:
        entry = await session.get(MergeLog, merge_id)
        if entry is None or entry.action != "merge":
            raise MediaNotFound("This merge does not exist.")
        undone = (
            await session.execute(
                select(MergeLog.id).where(
                    MergeLog.action == "split", MergeLog.details["merge"].astext == str(merge_id)
                )
            )
        ).first()
        if undone is not None:
            raise MergeConflict("This merge was already split.")
        keep = await session.get(MediaObject, entry.object_id, with_for_update=True)
        gone = await session.get(MediaObject, entry.other_id, with_for_update=True)
        if keep is None or gone is None or gone.merged_into != keep.id:
            raise MergeConflict("The objects changed since the merge; split is no longer possible.")
        moved = entry.details
        for model, key in (
            (SourceItem, "source_items"),
            (HistoryEntry, "history_entries"),
            (MediaRequest, "requests"),
        ):
            ids = [UUID(i) for i in moved.get(key, [])]
            if ids:
                await session.execute(
                    update(model)
                    .where(model.id.in_(ids), model.object_id == keep.id)
                    .values(object_id=gone.id)
                )
        if moved.get("playback_sessions"):
            await session.execute(
                update(PlaybackSession)
                .where(PlaybackSession.session_key.in_(moved["playback_sessions"]))
                .values(object_id=gone.id)
            )
        children = [UUID(c) for c in moved.get("children", [])]
        if children:
            await session.execute(
                update(MediaObject).where(MediaObject.id.in_(children)).values(parent_id=gone.id)
            )
        for scheme, value in moved.get("external_ids", []):
            await session.execute(
                update(ExternalId)
                .where(ExternalId.scheme == scheme, ExternalId.value == value)
                .values(object_id=gone.id)
            )
        for name, source in moved.get("field_candidates", []):
            await session.execute(
                update(FieldCandidate)
                .where(
                    FieldCandidate.object_id == keep.id,
                    FieldCandidate.field == name,
                    FieldCandidate.source_system == source,
                )
                .values(object_id=gone.id)
            )
        gone.status, gone.merged_into, gone.updated_at = "active", None, now
        keep.updated_at = now
        log = MergeLog(
            action="split",
            object_id=keep.id,
            other_id=gone.id,
            details={"merge": str(merge_id)},
            created_at=now,
        )
        session.add(log)
        await session.flush()
        return log
