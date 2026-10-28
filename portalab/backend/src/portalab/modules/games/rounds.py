"""Issue 265: the questions of the games played question after question — made on the server with their
answers, the page given only what it may show (the choices under opaque ids, an image or a sound to ask the
server for); and what an answer is worth (right, then the quicker the more).

* ``poster`` — a scene of a work (never its poster: its title is written on it), blurred, sharper as the
  time runs: which title?
* ``casting`` — three actors of a work: which one?
* ``synopsis`` — what it tells, its names hidden: which one?
* ``higher_lower`` — two titles: the better rated, the more recent, the longer?
* ``timeline`` — titles to put in the order they came out.
* ``blindtest`` — a series' theme music: which series?
* ``memories`` — my own history: which did I see first, which did I never see?
* ``whowatched`` — a party's: who among the players watched it? (only those who agreed)
"""

import random
import re
import secrets
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from portalab.capabilities.media_core import SeenWork
from portalab.modules.games.pool import Item, NoTitles, fold
from portalab.modules.games.settings import RoundGame

GRACE = 2.0  # seconds a late answer is still taken (the network)
HIDDEN = "▇▇▇"
ORDERED = ("timeline",)


def _token() -> str:
    return secrets.token_hex(4)


def _label(item: Item, *, year: bool = True) -> str:
    return f"{item.title} ({item.year})" if year and item.year else item.title


def _others(rng: random.Random, right: Item, items: Sequence[Item], count: int) -> list[Item]:
    """Wrong answers that could be right: the same kind, near in time, another title."""
    seen = {fold(right.title)}
    near = [
        i
        for i in items
        if i.kind == right.kind
        and i.id != right.id
        and (right.year is None or i.year is None or abs(i.year - right.year) <= 12)
    ]
    rng.shuffle(near)
    rest = [i for i in items if i.id != right.id]
    rng.shuffle(rest)
    out: list[Item] = []
    for item in [*near, *rest]:
        key = fold(item.title)
        if key not in seen:
            seen.add(key)
            out.append(item)
            if len(out) >= count:
                break
    return out


def _guess(
    rng: random.Random,
    game: str,
    right: Item,
    items: Sequence[Item],
    choices: int,
    prompt: dict[str, Any],
    media: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = [right, *_others(rng, right, items, choices - 1)]
    rng.shuffle(options)
    ids = {item.id: _token() for item in options}
    return {
        "game": game,
        "prompt": prompt,
        "choices": [{"id": ids[i.id], "label": _label(i)} for i in options],
        "answer": ids[right.id],
        "reveal": {"title": right.title, "year": right.year, "poster": right.poster, "id": str(right.id)},
        "media": media or {},
    }


def _mask(text: str, item: Item) -> str:
    """What a work tells, its title's words and its people's names hidden."""
    banned = {w for w in fold(item.title).split() if len(w) >= 3}
    for person in item.cast[:12]:
        banned.update(w for w in fold(person.name).split() if len(w) >= 3)
        if person.role:
            banned.update(w for w in fold(person.role).split() if len(w) >= 3)

    def hide(match: re.Match[str]) -> str:
        return HIDDEN if fold(match.group(0)) in banned else match.group(0)

    return re.sub(r"[^\W_]+(?:['\u2019][^\W_]+)?", hide, text)


def _pick(rng: random.Random, items: Sequence[Item], count: int) -> list[Item]:
    chosen = list(items)
    rng.shuffle(chosen)
    return chosen[:count]


def make(
    game: str,
    items: Sequence[Item],
    settings: RoundGame,
    rng: random.Random,
    *,
    themed: Sequence[Item] = (),
    seen: Sequence[SeenWork] = (),
    unseen: Sequence[Item] = (),
    players: Mapping[UUID, tuple[str, Sequence[SeenWork]]] | None = None,
) -> list[dict[str, Any]]:
    """The questions of a game (as many as it can make, up to its rounds)."""
    rounds, choices = settings.rounds, settings.choices
    out: list[dict[str, Any]] = []
    if game == "poster":
        for right in _pick(rng, [i for i in items if i.scenes], rounds):
            scene = rng.choice(right.scenes)
            out.append(_guess(rng, game, right, items, choices, {"kind": right.kind}, {"poster": scene}))
    elif game == "casting":
        fit = [i for i in items if sum(1 for p in i.cast[:4] if p.image) >= 3]
        for right in _pick(rng, fit, rounds):
            people = [{"name": p.name, "image": p.image} for p in right.cast[:4] if p.image][:3]
            out.append(_guess(rng, game, right, items, choices, {"kind": right.kind, "people": people}))
    elif game == "synopsis":
        fit = [i for i in items if i.overview and len(i.overview) >= 120]
        for right in _pick(rng, fit, rounds):
            text = _mask(str(right.overview)[:700], right)
            out.append(_guess(rng, game, right, items, choices, {"kind": right.kind, "text": text}))
    elif game == "blindtest":
        for right in list(themed)[:rounds]:
            series = [i for i in items if i.kind == "series"]
            out.append(
                _guess(rng, game, right, series, choices, {"kind": "series"}, {"theme": str(right.id)})
            )
    elif game == "higher_lower":
        out = [q for q in (_duel(rng, items) for _ in range(rounds * 3)) if q][:rounds]
    elif game == "timeline":
        out = [q for q in (_timeline(rng, items, max(3, choices)) for _ in range(rounds * 3)) if q][:rounds]
    elif game == "memories":
        out = _memories(rng, seen, unseen, rounds, choices)
    elif game == "whowatched":
        out = _whowatched(rng, players or {}, rounds, choices)
    if not out:
        raise NoTitles("Not enough titles for this game.")
    return out


CRITERIA = ("rating", "year", "runtime")


def _duel(rng: random.Random, items: Sequence[Item]) -> dict[str, Any] | None:
    criterion = rng.choice(CRITERIA)
    a, b = rng.sample(list(items), 2) if len(items) >= 2 else (None, None)
    if a is None or b is None or fold(a.title) == fold(b.title):
        return None
    values = {
        "rating": (a.rating, b.rating, 0.3),
        "year": (a.year, b.year, 1),
        "runtime": (a.runtime, b.runtime, 8),
    }[criterion]
    va, vb, gap = values
    if va is None or vb is None or abs(float(va) - float(vb)) < gap:
        return None
    if criterion == "runtime" and (a.kind != "movie" or b.kind != "movie"):
        return None
    ids = {a.id: _token(), b.id: _token()}
    best = a if float(va) > float(vb) else b
    return {
        "game": "higher_lower",
        "prompt": {"criterion": criterion},
        "choices": [
            {"id": ids[i.id], "label": _label(i, year=criterion != "year"), "image": i.poster} for i in (a, b)
        ],
        "answer": ids[best.id],
        "reveal": {
            "title": best.title,
            "year": best.year,
            "poster": best.poster,
            "id": str(best.id),
            "values": {ids[a.id]: va, ids[b.id]: vb},
        },
        "media": {},
    }


def _timeline(rng: random.Random, items: Sequence[Item], count: int) -> dict[str, Any] | None:
    pool = [i for i in items if i.year and i.poster]
    if len(pool) < count:
        return None
    chosen: list[Item] = []
    years: set[int] = set()
    for item in _pick(rng, pool, count * 8):
        if item.year not in years:
            years.add(int(item.year or 0))
            chosen.append(item)
            if len(chosen) == count:
                break
    if len(chosen) < count:
        return None
    ids = {i.id: _token() for i in chosen}
    ordered = sorted(chosen, key=lambda i: int(i.year or 0))
    return {
        "game": "timeline",
        "prompt": {"count": count},
        "choices": [{"id": ids[i.id], "label": i.title, "image": i.poster} for i in chosen],
        "answer": [ids[i.id] for i in ordered],
        "reveal": {"values": {ids[i.id]: i.year for i in chosen}},
        "media": {},
    }


def _memories(
    rng: random.Random, seen: Sequence[SeenWork], unseen: Sequence[Item], rounds: int, choices: int
) -> list[dict[str, Any]]:
    """My own history: which of these did I see first; which did I never see."""
    mine = [w for w in seen if w.kind in ("movie", "series", "book", "audiobook", "game")]
    known = {fold(w.title) for w in mine}
    strangers = [i for i in unseen if fold(i.title) not in known]
    out: list[dict[str, Any]] = []
    for at in range(rounds * 2):
        if len(out) >= rounds or len(mine) < choices:
            break
        if at % 2 == 0:
            options = rng.sample(mine, choices)
            if len({w.last_at.date() for w in options}) < choices:
                continue
            first = min(options, key=lambda w: w.last_at)
            ids = {w.object_id: _token() for w in options}
            out.append(
                {
                    "game": "memories",
                    "prompt": {"question": "first"},
                    "choices": [{"id": ids[w.object_id], "label": w.title} for w in options],
                    "answer": ids[first.object_id],
                    "reveal": {
                        "title": first.title,
                        "values": {ids[w.object_id]: w.last_at.date().isoformat() for w in options},
                    },
                    "media": {},
                }
            )
        elif strangers:
            stranger = rng.choice(strangers)
            options_seen = rng.sample(mine, choices - 1)
            ids = {w.object_id: _token() for w in options_seen}
            stranger_id = _token()
            listed = [{"id": ids[w.object_id], "label": w.title} for w in options_seen]
            listed.append({"id": stranger_id, "label": stranger.title})
            rng.shuffle(listed)
            out.append(
                {
                    "game": "memories",
                    "prompt": {"question": "never"},
                    "choices": listed,
                    "answer": stranger_id,
                    "reveal": {"title": stranger.title, "year": stranger.year, "poster": stranger.poster},
                    "media": {},
                }
            )
    return out


def _whowatched(
    rng: random.Random,
    players: Mapping[UUID, tuple[str, Sequence[SeenWork]]],
    rounds: int,
    choices: int,
) -> list[dict[str, Any]]:
    """A title one player only watched (of those who agreed): who was it?"""
    if len(players) < 2:
        return []
    watchers: dict[str, set[UUID]] = {}
    titles: dict[str, SeenWork] = {}
    for user, (_, works) in players.items():
        for work in works:
            if work.kind not in ("movie", "series"):
                continue
            key = fold(work.title)
            watchers.setdefault(key, set()).add(user)
            titles.setdefault(key, work)
    single = [key for key, users in watchers.items() if len(users) == 1]
    rng.shuffle(single)
    ids = {user: _token() for user in players}
    out: list[dict[str, Any]] = []
    for key in single[:rounds]:
        (who,) = watchers[key]
        others = [u for u in players if u != who]
        rng.shuffle(others)
        options = [who, *others[: max(1, choices - 1)]]
        rng.shuffle(options)
        work = titles[key]
        out.append(
            {
                "game": "whowatched",
                "prompt": {"title": work.title, "year": work.year, "kind": work.kind},
                "choices": [{"id": ids[u], "label": players[u][0]} for u in options],
                "answer": ids[who],
                "reveal": {"title": work.title, "year": work.year, "who": players[who][0]},
                "media": {},
            }
        )
    return out


def public(question: dict[str, Any]) -> dict[str, Any]:
    """What the page may know of a question before it is answered."""
    media = question.get("media") or {}
    return {
        "game": question["game"],
        "prompt": question["prompt"],
        "choices": question["choices"],
        "ordered": question["game"] in ORDERED,
        "image": bool(media.get("poster")),
        "audio": bool(media.get("theme")),
    }


def worth(question: dict[str, Any], answer: Any, elapsed: float, seconds: int) -> tuple[bool, int]:
    """Whether an answer is right, and its points: 100, and up to 100 more the quicker it came (an order:
    40 per title in its place, the bonus when all are)."""
    if elapsed > seconds + GRACE:
        return False, 0
    speed = int(100 * max(0.0, 1 - elapsed / seconds))
    expected = question["answer"]
    if isinstance(expected, list):
        given = list(answer) if isinstance(answer, list) else []
        placed = sum(1 for a, b in zip(given, expected, strict=False) if a == b)
        right = placed == len(expected)
        return right, placed * 40 + ((100 + speed) if right else 0)
    if answer == expected:
        return True, 100 + speed
    return False, 0
