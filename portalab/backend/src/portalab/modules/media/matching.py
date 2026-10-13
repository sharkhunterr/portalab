"""#92 — how a query finds a title: every word of it must be found in what the search reads of the title
(``MediaObject.search_text``: its title, original title and series, and the people behind it), as a
substring or, for a word of four letters or more, a close spelling (trigram word similarity) — so
« assassin royal », « royal assassin » and « assasin royal » all find *L'Assassin royal*. The query is folded
the way the database folds ``search_text`` (lower case, no accents, apostrophes and dashes as spaces).

Also says who, among a title's people, a query found — the author, the narrator, the director or a member
of the cast — so a result can read « by Robin Hobb » or « with Chris O'Dowd »."""

import re
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Numeric, and_, case, cast, func, or_, select, true

from portalab.capabilities.i18n import normalize_for_search
from portalab.modules.media.models import MediaObject, ObjectMetadata

# the same separators as ``media.search_fold`` (migration media_0008)
_SEPARATORS = re.compile(r"[\s!-/:-@\[-`{-~\u00a0-\u00bf\u2010-\u206f]+")
_LIGATURES = str.maketrans({"œ": "oe", "æ": "ae", "ø": "o", "ł": "l", "đ": "d"})
FUZZY_FROM = 5  # shorter words must be found as they are typed
FUZZY_SIMILARITY = 0.7  # how close a misspelt word must be (« assasin » is 0.86 of « assassin »)
MAX_WORDS = 8
BOOKS = frozenset({"book", "audiobook"})
SCREEN = frozenset({"movie", "series", "season", "episode", "live"})
DEPARTMENTS = {"cast": "cast", "directing": "director", "writing": "writer", "creator": "creator"}


def fold(text: str) -> str:
    """Lower case, no accents, every separator a single space — ``media.search_fold`` in Python."""
    folded = normalize_for_search(text).translate(_LIGATURES)
    return " ".join(_SEPARATORS.sub(" ", folded).split())


def words(text: str) -> list[str]:
    """The words of a query, folded; a lone letter (the ``l`` of « l'assassin ») only when it is alone."""
    found = list(dict.fromkeys(fold(text).split()))
    longer = [word for word in found if len(word) > 1]
    return (longer or found)[:MAX_WORDS]


def fuzzy(column: Any, word: str) -> ColumnElement[bool]:
    """A close spelling of a long enough word (the trigram index finds the candidates, then the bar)."""
    return and_(column.op("%>")(word), func.word_similarity(word, column) >= FUZZY_SIMILARITY)


def found(column: Any, word: str) -> ColumnElement[bool]:
    exact = column.contains(word, autoescape=True)
    return or_(exact, fuzzy(column, word)) if len(word) >= FUZZY_FROM else exact


def whole(column: Any, word: str) -> ColumnElement[bool]:
    """The word as a word of its own (« robin », not « robinson »)."""
    matched: ColumnElement[bool] = column.regexp_match(rf"\m{re.escape(word)}\M")
    return matched


def escaped(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def matching(query_words: Sequence[str]) -> ColumnElement[bool]:
    """Every word found — exactly, or for the longer ones, closely."""
    return and_(*(found(MediaObject.search_text, word) for word in query_words)) if query_words else true()


def relevance(query_words: Sequence[str], phrase: str) -> ColumnElement[int]:
    """0 the exact title, 1 a title starting with the query, 2 a word of the title starting with it, 3 the
    words all in the title; then, elsewhere (its series, its people): 4 the query as it is typed (« chris o
    dowd »), 5 the words as words, 6 the words inside others; 7 a close spelling."""
    text = phrase or " ".join(query_words)
    title = func.media.search_fold(MediaObject.title)
    like = escaped(text)
    padded = func.concat(" ", MediaObject.search_text, " ")
    return case(
        (title == text, 0),
        (title.like(f"{like}%", escape="\\"), 1),
        (title.like(f"% {like}%", escape="\\"), 2),
        (and_(*(title.contains(word, autoescape=True) for word in query_words)), 3),
        (padded.like(f"% {like} %", escape="\\"), 4),
        (and_(*(whole(MediaObject.search_text, word) for word in query_words)), 5),
        (and_(*(MediaObject.search_text.contains(word, autoescape=True) for word in query_words)), 6),
        else_=7,
    )


def series_order() -> list[Any]:
    """Within a series, its volumes in order (1, 2… 13)."""
    position = MediaObject.effective["series_position"].astext
    return [
        MediaObject.effective["series"].astext,
        case((position.regexp_match(r"^\d{1,6}(\.\d{1,3})?$"), cast(position, Numeric)), else_=None),
    ]


async def metadata_people(session: Any, ids: Sequence[UUID]) -> dict[UUID, list[Mapping[str, Any]]]:
    """The people the metadata provider (TMDB…) lists for these titles, with their department."""
    if not ids:
        return {}
    rows = await session.execute(
        select(ObjectMetadata.object_id, ObjectMetadata.data["people"]).where(
            ObjectMetadata.object_id.in_(ids), ObjectMetadata.status == "found"
        )
    )
    return {
        object_id: [p for p in people if isinstance(p, Mapping)]
        for object_id, people in rows
        if isinstance(people, list)
    }


def _names(value: Any) -> list[str]:
    out = []
    for item in value if isinstance(value, list) else []:
        name = item.get("name") if isinstance(item, Mapping) else item
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
    return out


def credited(
    row: MediaObject, query_words: Sequence[str], provider_people: Sequence[Mapping[str, Any]] = ()
) -> tuple[str, str] | None:
    """Who among the title's people a query found, and as what (``author``, ``narrator``, ``director``,
    ``writer``, ``creator``, ``cast`` or ``credit``) — ``None`` when its words are all in the title."""
    effective = row.effective or {}
    named = fold(" ".join(str(effective.get(k) or "") for k in ("original_title", "series", "title")))
    pending = [word for word in query_words if word not in named]
    if not pending:
        return None
    fallback = "author" if row.kind in BOOKS else "cast" if row.kind in SCREEN else "credit"
    candidates: list[tuple[str, str]] = [
        *((name, "author") for name in _names(effective.get("authors"))),
        *((name, "narrator") for name in _names(effective.get("narrators"))),
        *((name, "director") for name in _names(effective.get("directors"))),
        *(
            (str(p["name"]), DEPARTMENTS.get(str(p.get("department") or ""), "credit"))
            for p in provider_people
            if p.get("name")
        ),
        *((name, fallback) for name in _names(effective.get("people"))),
    ]
    best: tuple[int, str, str] | None = None
    for name, role in candidates:
        folded = fold(name)
        hits = sum(1 for word in pending if word in folded)
        if hits and (best is None or hits > best[0]):
            best = (hits, name, role)
    return (best[1], best[2]) if best else None
