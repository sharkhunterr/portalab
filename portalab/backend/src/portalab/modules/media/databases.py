"""#373: titles the library lacks, found in the book and game databases (Hardcover, IGDB) — offered among the
search's « ask for it » results beside the request service's films and series, each opening its sheet
(where it is asked of the team). A title the library has in that kind is left to the library's results."""

import asyncio
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlencode

from portalab.capabilities.media import BOOK_SERIES, GAME_DATABASE, PersonCredit, unwrap
from portalab.capabilities.media_core import WantedTitle
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import SearchItem
from portalab.capabilities.search.fts import snippet
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.modules.media.library_match import MediaLibraryMatch

log = get_logger("portalab.media")
TIMEOUT = 6.0  # seconds a database may take before the search goes on without it
# per database: its capability, the kind of its titles, its sheet's route and its images' address
KINDS: tuple[tuple[str, str, str, str, dict[str, str]], ...] = (
    (BOOK_SERIES, "book", "/media/book", "/api/v1/media/book-covers", {}),
    (GAME_DATABASE, "game", "/media/game", "/api/v1/media/game-images", {"size": "cover"}),
)


class DatabaseTitles:
    def __init__(self, capabilities: CapabilityRegistry, database: Database) -> None:
        self.capabilities = capabilities
        self.database = database

    async def _ask(self, capability: str, provider: Any, text: str, language: str, limit: int) -> Any:
        found = (
            provider.search(text, language, limit)
            if capability == BOOK_SERIES
            else provider.search(text, limit)
        )
        return unwrap(await asyncio.wait_for(found, timeout=TIMEOUT))

    async def found(self, text: str, language: str, limit: int) -> list[SearchItem]:
        asked: list[tuple[str, str, str, str, dict[str, str], Any]] = []
        for capability, kind, sheet, images, extra in KINDS:
            for registration in self.capabilities.system_providers(capability):
                asked.append(
                    (
                        kind,
                        registration.instance_ref,
                        sheet,
                        images,
                        extra,
                        self._ask(capability, registration.provider, text, language, limit),
                    )
                )
        if not asked:
            return []
        answers = await asyncio.gather(*(a[-1] for a in asked), return_exceptions=True)
        hits: list[tuple[str, str, str, str, dict[str, str], PersonCredit]] = []
        for (kind, service, sheet, images, extra, _), answer in zip(asked, answers, strict=True):
            if isinstance(answer, BaseException):
                log.info("database search failed", extra={"fields": {"error": type(answer).__name__}})
                continue
            for credit in answer or ():
                if isinstance(credit, PersonCredit):
                    hits.append((kind, service, sheet, images, extra, credit))
        held = await MediaLibraryMatch(self.database).find(
            [
                WantedTitle(
                    str(index),
                    kind,
                    credit.title,
                    tuple(c.strip() for c in (credit.role or "").split(",") if c.strip()),
                    {"igdb": [credit.tmdb_id]} if kind == "game" else {},
                )
                for index, (kind, _, _, _, _, credit) in enumerate(hits)
            ]
        )
        items = []
        for index, (kind, service, sheet, images, extra, credit) in enumerate(hits):
            if str(index) in held:
                continue  # the library has it in that kind: its own result tells it
            facets = {"type": kind}
            if credit.poster:
                facets["cover"] = f"{images}?{urlencode({'service': service, 'ref': credit.poster, **extra})}"
            if credit.year:
                facets["year"] = str(credit.year)
            items.append(
                SearchItem(
                    kind="request",
                    id=f"{kind}:{service}:{credit.tmdb_id}",
                    title=f"{credit.title} ({credit.year})" if credit.year else credit.title,
                    url_ref=f"{sheet}?{urlencode({'service': service, 'ref': credit.tmdb_id})}",
                    snippet=snippet(credit.role or "", []),  # its authors, its studio
                    score=0.4,
                    facets=facets,
                )
            )
        return items


def interleave(*groups: Sequence[SearchItem]) -> list[SearchItem]:
    """The results of several sources taken in turn (a film, a book, a game, a film…)."""
    out: list[SearchItem] = []
    for index in range(max((len(g) for g in groups), default=0)):
        out.extend(g[index] for g in groups if index < len(g))
    return out
