"""Provider helper kit (spec 008 T011; research R2, R13): PostgreSQL full-text + ``unaccent`` + ``pg_trgm``
building blocks every provider reuses — parameterized expressions only (no query text ever becomes SQL),
plain-text snippets with highlight segments (no markup), opaque offset cursors and migration DDL helpers."""

import base64
import json
import re
import unicodedata
from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Float, cast, func, literal, or_
from sqlalchemy.dialects.postgresql import REGCONFIG

from portalab.capabilities.search import ParsedQuery, Segment

FTS_CONFIGS: dict[str, str] = {
    "da": "danish",
    "de": "german",
    "en": "english",
    "es": "spanish",
    "fi": "finnish",
    "fr": "french",
    "hu": "hungarian",
    "it": "italian",
    "nl": "dutch",
    "no": "norwegian",
    "pt": "portuguese",
    "ro": "romanian",
    "ru": "russian",
    "sv": "swedish",
    "tr": "turkish",
}
TRIGRAM_THRESHOLD = 0.3
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def fts_config(language: str | None) -> str:
    """PostgreSQL text-search configuration for a document language (``simple`` when unknown)."""
    return FTS_CONFIGS.get((language or "").split("-")[0].lower(), "simple")


def folded(column: Any) -> ColumnElement[str]:
    """``unaccent(lower(column))`` — the SQL twin of ``normalize_for_search`` for matching."""
    return func.unaccent(func.lower(column))


def text_match(columns: Sequence[Any], query: ParsedQuery) -> ColumnElement[bool]:
    """Typo- and accent-tolerant match on short text columns: substring or trigram word similarity."""
    if not query.normalized:
        return literal(True)
    needle = query.normalized
    clauses: list[ColumnElement[bool]] = []
    for column in columns:
        target = folded(column)
        clauses.append(target.contains(needle, autoescape=True))
        clauses.append(func.word_similarity(needle, target) >= TRIGRAM_THRESHOLD)
    return or_(*clauses)


def text_rank(columns: Sequence[Any], query: ParsedQuery) -> ColumnElement[float]:
    if not query.normalized:
        return cast(literal(0.0), Float)
    return func.greatest(*(func.word_similarity(query.normalized, folded(c)) for c in columns), literal(0.0))


def websearch(query: ParsedQuery, language: str | None = None) -> ColumnElement[Any]:
    """``websearch_to_tsquery(config, text)`` — PostgreSQL parses the operators, never us."""
    return func.websearch_to_tsquery(cast(literal(fts_config(language)), REGCONFIG), query.text)


def fts_match(vector_column: Any, query: ParsedQuery, language: str | None = None) -> ColumnElement[bool]:
    match: ColumnElement[bool] = vector_column.op("@@")(websearch(query, language))
    return match


def fts_rank(vector_column: Any, query: ParsedQuery, language: str | None = None) -> ColumnElement[float]:
    return func.ts_rank_cd(vector_column, websearch(query, language))


def tsvector_ddl(schema: str, table: str, sources: Sequence[str], *, config: str = "simple") -> list[str]:
    """Migration helper: a generated ``search_vector`` column over ``sources`` and its GIN index."""
    for name in (schema, table, config, *sources):
        if not _IDENT.fullmatch(name):
            raise ValueError(f"invalid identifier {name!r}")
    document = " || ' ' || ".join(f"coalesce({column}, '')" for column in sources)
    return [
        f"ALTER TABLE {schema}.{table} ADD COLUMN search_vector tsvector "
        f"GENERATED ALWAYS AS (to_tsvector('{config}'::regconfig, {document})) STORED",
        f"CREATE INDEX ix_{table}_search_vector ON {schema}.{table} USING gin (search_vector)",
    ]


def fold_text(text: str) -> str:
    """Casefold and strip diacritics *character by character* (positions stay aligned with ``text``)."""
    out = []
    for char in text:
        base = unicodedata.normalize("NFKD", char)
        stripped = "".join(c for c in base if not unicodedata.combining(c)).casefold()
        out.append(stripped[:1] if stripped else char.casefold()[:1] or char)
    return "".join(out)


def snippet(text: str, terms: Sequence[str], *, width: int = 160) -> tuple[Segment, ...]:
    """A window of ``text`` around the first hit, split into plain-text segments flagging the hits."""
    if not text:
        return ()
    plain = " ".join(text.split())
    haystack = fold_text(plain)
    needles = sorted({fold_text(t) for t in terms if t.strip()}, key=len, reverse=True)
    spans: list[tuple[int, int]] = []
    for needle in needles:
        start = 0
        while (index := haystack.find(needle, start)) != -1:
            end = index + len(needle)
            if not any(a < end and index < b for a, b in spans):
                spans.append((index, end))
            start = end
    spans.sort()
    first = spans[0][0] if spans else 0
    lo = max(0, min(first - width // 3, len(plain) - width))
    hi = min(len(plain), lo + width)
    segments: list[Segment] = []
    cursor = lo
    for a, b in spans:
        a, b = max(a, lo), min(b, hi)
        if a >= b:
            continue
        if cursor < a:
            segments.append(Segment(plain[cursor:a]))
        segments.append(Segment(plain[a:b], hit=True))
        cursor = b
    if cursor < hi:
        segments.append(Segment(plain[cursor:hi]))
    if lo > 0:
        segments.insert(0, Segment("…"))
    if hi < len(plain):
        segments.append(Segment("…"))
    return tuple(segments)


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    """Offset from an opaque cursor; anything malformed restarts at 0 (never an error, never SQL)."""
    if not cursor:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        offset = int(json.loads(base64.urlsafe_b64decode(padded.encode()))["o"])
    except (ValueError, KeyError, TypeError):
        return 0
    return max(0, min(offset, 10_000))
