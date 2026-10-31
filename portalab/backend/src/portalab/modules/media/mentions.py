"""#299 — which library titles and people a text names (a news item's title and summary), for the news to
link its items to the library: every run of one to six words of the text, folded, looked up as a work's title
or a credited name. A title of a single short word (« Up », « Heat ») or a one-word name would match too much:
only titles of two words or more, or of one long word, and people with two names or more. A one-word title
(« Novembre », « Halloween ») is still a common word: only when the text quotes it, or a headline opens on it
(« Nocturne : … »)."""

import re
from collections.abc import Sequence
from urllib.parse import quote

from sqlalchemy import func, select

from portalab.capabilities.media import Mention
from portalab.core.db import Database
from portalab.modules.media.matching import fold
from portalab.modules.media.models import Credit, MediaObject

WORKS = ("movie", "series", "book", "audiobook", "game", "album")
LONGEST = 6  # words in a title or a name looked for
SHORTEST_WORD_TITLE = 7  # letters of a one-word title


def _runs(text: str) -> set[str]:
    tokens = fold(text).split()
    return {" ".join(tokens[i : i + n]) for n in range(1, LONGEST + 1) for i in range(0, len(tokens) - n + 1)}


def _title_ok(folded: str) -> bool:
    return " " in folded or len(folded) >= SHORTEST_WORD_TITLE


# a title between quotes: French guillemets, curly double or single quotes, straight double or single ones
_PAIRS = (("\u00ab", "\u00bb"), ("\u201c", "\u201d"), ("\u2018", "\u2019"), ('"', '"'), ("'", "'"))
_QUOTED = re.compile("|".join(f"{o}\\s*([^{c}]{{1,120}}?)\\s*{c}" for o, c in _PAIRS))


def _cased(text: str, title: str) -> bool:
    """A title of two words written as a title (« Old Boy », « OLD BOY »), not as words of a sentence
    (« a 12-year-old boy », « it follows a boy »); one word is never enough (``_named`` decides)."""
    words = title.split()
    if len(words) != 2:
        return False
    pattern = r"\b" + r"[\s\-:.,']+".join(re.escape(w) for w in words) + r"\b"
    for found in re.finditer(pattern, text, re.IGNORECASE):
        if all(
            t[:1].isupper() == w[:1].isupper() or t.isupper()
            for t, w in zip(re.split(r"[\s\-:.,']+", found.group(0)), words, strict=False)
        ):
            return True
    return False


def _named(text: str) -> set[str]:
    """What a text names explicitly (folded): its quoted words, and the words a headline opens on."""
    found = {fold(next(g for g in m.groups() if g)) for m in _QUOTED.finditer(text)}
    head = text.split(":", 1)[0] if ":" in text[:80] else ""
    if head:
        found.add(fold(head))
    return found


class LibraryMentions:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def mentions(self, texts: Sequence[str], limit: int = 6) -> list[list[Mention]]:
        runs = [_runs(text) for text in texts]
        wanted = set().union(*runs) if runs else set()
        titles = {run for run in wanted if _title_ok(run)}
        names = {run for run in wanted if " " in run}
        if not wanted:
            return [[] for _ in texts]
        folded_title = func.media.search_fold(MediaObject.title)
        async with self.database.session() as session:
            found_titles: dict[str, tuple[str, str]] = {}
            if titles:
                rows = await session.execute(
                    select(folded_title, MediaObject.id, MediaObject.title)
                    .where(
                        MediaObject.kind.in_(WORKS),
                        MediaObject.status == "active",
                        MediaObject.parent_id.is_(None),
                        folded_title.in_(titles),
                    )
                    .order_by(MediaObject.available.desc(), MediaObject.year.desc().nulls_last())
                )
                for folded, object_id, title in rows.all():
                    found_titles.setdefault(folded, (str(object_id), title))
            found_people: dict[str, str] = {}
            if names:
                rows = await session.execute(
                    select(Credit.folded, func.min(Credit.name))
                    .where(Credit.folded.in_(names))
                    .group_by(Credit.folded)
                )
                found_people = {folded: name for folded, name in rows.all()}
        out: list[list[Mention]] = []
        for text, text_runs in zip(texts, runs, strict=True):
            named = _named(text)
            mentions: list[Mention] = []
            matched: list[str] = []
            # the longest first: « star wars the last jedi », and then not « star wars » inside it
            for run in sorted(text_runs, key=len, reverse=True):
                if len(mentions) >= limit:
                    break
                known = run in found_titles or run in found_people
                if known and any(f" {run} " in f" {m} " for m in matched):
                    continue
                if run in found_titles and (
                    run.count(" ") > 1 or run in named or _cased(text, found_titles[run][1])
                ):
                    object_id, title = found_titles[run]
                    matched.append(run)
                    if all(m.ref != object_id for m in mentions):
                        mentions.append(Mention("title", object_id, title, f"/media/{object_id}"))
                elif run in found_people:
                    name = found_people[run]
                    matched.append(run)
                    if all(m.ref != name for m in mentions):
                        route = f"/media/people/{quote(name, safe='')}"
                        mentions.append(Mention("person", name, name, route))
            out.append(mentions)
        return out
