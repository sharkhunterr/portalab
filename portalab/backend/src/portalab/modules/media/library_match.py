"""Issue 363: ``media.library_match`` — the library's title for each title a member asks for: one of the
identifiers the library holds for it (whatever its scheme), else its title — or its original title — of the
same kind, by one of its creators when the request tells them (the author of a book…)."""

import re
from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import func, or_, select

from portalab.capabilities.media_core import LibraryTitle, WantedTitle
from portalab.core.db import Database
from portalab.modules.media.matching import _names, fold
from portalab.modules.media.models import ExternalId, MediaObject

_SPACING = re.compile(r"[\s\-]+")
MAX_IDS = 50


def _values(value: str) -> set[str]:
    """An identifier as it is told and without its spaces and dashes (« 978-2-290… »)."""
    value = value.strip()[:200]
    return {v for v in (value, _SPACING.sub("", value)) if v}


def _creators(row: MediaObject) -> set[str]:
    effective = row.effective or {}
    return {
        fold(name)
        for key in ("authors", "narrators", "directors", "people", "developers", "publishers")
        for name in _names(effective.get(key))
    }


def _by(creators: Sequence[str], row: MediaObject) -> bool:
    """One of the creators told among the title's people: the same name, or every word of it in one."""
    wanted = [fold(c) for c in creators if fold(c)]
    if not wanted:
        return True
    names = _creators(row)
    return any(name == want or set(want.split()) <= set(name.split()) for want in wanted for name in names)


def _title(row: MediaObject) -> LibraryTitle:
    return LibraryTitle(row.id, row.kind, row.title, bool(row.available), row.year)


class MediaLibraryMatch:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def get(self, object_id: UUID) -> LibraryTitle | None:
        async with self.database.session() as session:
            row = await session.get(MediaObject, object_id)
        return _title(row) if row is not None and row.status == "active" else None

    async def find(self, wanted: Sequence[WantedTitle]) -> Mapping[str, LibraryTitle]:
        out: dict[str, LibraryTitle] = {}
        if not wanted:
            return out
        async with self.database.session() as session:
            for item in wanted:
                pairs = [
                    (scheme[:32], value)
                    for scheme, values in item.ids.items()
                    for raw in values
                    for value in _values(str(raw))
                ][:MAX_IDS]
                rows: list[MediaObject] = []
                if pairs:
                    rows = list(
                        (
                            await session.execute(
                                select(MediaObject)
                                .join(ExternalId, ExternalId.object_id == MediaObject.id)
                                .where(
                                    or_(
                                        *(
                                            (ExternalId.scheme == s) & (ExternalId.value == v)
                                            for s, v in pairs
                                        )
                                    ),
                                    MediaObject.kind == item.kind,
                                    MediaObject.status == "active",
                                )
                            )
                        ).scalars()
                    )
                folded = fold(item.title)
                if not rows and folded:
                    candidates = (
                        await session.execute(
                            select(MediaObject)
                            .where(
                                or_(
                                    func.media.search_fold(MediaObject.title) == folded,
                                    func.media.search_fold(MediaObject.effective["original_title"].astext)
                                    == folded,
                                ),
                                MediaObject.kind == item.kind,
                                MediaObject.status == "active",
                            )
                            .limit(20)
                        )
                    ).scalars()
                    rows = [row for row in candidates if _by(item.creators, row)]
                if rows:
                    # the one there to be read, watched or played first
                    best = min(rows, key=lambda row: (not row.available, row.title, str(row.id)))
                    out[item.key] = _title(best)
        return out
