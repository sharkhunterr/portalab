"""#81: boosters — a sealed pack of items drawn at random, revealed card by card.

A booster is a product of the catalog (type ``booster``): a tile in the shop and its sheet like any
other, a price, versions and presentation set by the administrators — and in its payload what it holds
(``pool``: the looks, the looks drawn by the graphics chip, or the items one keeps), the season it draws
from or the packs it draws from (#130: a collection's own booster), how many cards, the odds per rarity,
the rarity guaranteed, what a duplicate gives back per rarity, how many times a member may open it and its
pack's look. A season's booster is on sale only in its weeks.

The draw happens on the server (a system random source): each card's rarity by the odds, one at least the
guaranteed rarity, never the same item twice in a pack, the cards then shuffled (their place tells
nothing). Opening one charges its price (or uses a sealed one offered — a level reward, an achievement);
a look not owned yet is granted, one already owned is a duplicate that gives back a fixed amount of Coins
per rarity, an item to keep goes to the member's reserve.
"""

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

RARITIES = ("common", "rare", "epic", "legendary")
# the looks (never features, services, packs…)
COSMETIC_TYPES = frozenset(
    {
        "ambient",
        "avatar_frame",
        "profile_banner",
        "profile_background",
        "name_style",
        "level_badge",
        "level_up",
        "badge",
        "title",
        "notification_style",
        "notification_animation",
        "effect",
        "palette",
    }
)
# the items one keeps in the reserve and uses when one wants (sold « repeatable »: they stack, never a
# duplicate)
RESERVE_TYPES = frozenset(
    {"quota", "streak_freeze", "xp_boost", "media_rescue", "special_request", "project_launch"}
)
POOLS = ("looks", "hd", "reserve")
# a duplicate gives back a fixed amount per rarity, whatever the item's price
DUPLICATE_REFUNDS: Mapping[str, int] = {"common": 10, "rare": 15, "epic": 20, "legendary": 30}
DEFAULT_ODDS: Mapping[str, int] = {"common": 62, "rare": 26, "epic": 10, "legendary": 2}
# Prestige HD: the looks the packs drawn by the graphics chip hold
HD_PACKS = ("pack_hd_", "pack_living_badges")
PAYLOAD_FIELDS = ("pool", "season", "packs", "cards", "odds", "guarantee", "refunds", "per_member", "look")

Day = tuple[int, int]  # (month, day)


@dataclass(frozen=True, slots=True)
class Season:
    """A time of the year: its looks, its pack and its booster are highlighted (the booster on sale) then."""

    key: str
    names: Mapping[str, str]
    window: tuple[Day, Day]  # inclusive; may run over the new year


SEASONS: dict[str, Season] = {
    s.key: s
    for s in (
        Season("valentine", {"fr": "Saint-Valentin", "en": "Valentine's Day"}, ((2, 1), (2, 20))),
        Season("spring", {"fr": "Printemps", "en": "Spring"}, ((3, 20), (5, 31))),
        Season("summer", {"fr": "Été", "en": "Summer"}, ((6, 21), (9, 22))),
        Season("halloween", {"fr": "Halloween", "en": "Halloween"}, ((10, 1), (11, 10))),
        Season("christmas", {"fr": "Noël", "en": "Christmas"}, ((12, 1), (1, 6))),
    )
}


def in_window(window: tuple[Day, Day], today: date) -> bool:
    start, end = window
    day = (today.month, today.day)
    return start <= day <= end if start <= end else day >= start or day <= end


def season_now(today: date) -> Season | None:
    return next((s for s in SEASONS.values() if in_window(s.window, today)), None)


def season_end(season: Season, today: date) -> date | None:
    """The last day of the season's current weeks (``None``: not now)."""
    if not in_window(season.window, today):
        return None
    month, day = season.window[1]
    year = today.year + (1 if (month, day) < (today.month, today.day) else 0)
    return date(year, month, day)


def _int(value: Any, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _weights(raw: Any, fallback: Mapping[str, int], high: int) -> dict[str, int]:
    values = raw if isinstance(raw, Mapping) else fallback
    return {r: _int(values.get(r, fallback.get(r, 0)), fallback.get(r, 0), 0, high) for r in RARITIES}


@dataclass(frozen=True, slots=True)
class Booster:
    key: str
    names: Mapping[str, str]
    price: int
    cards: int = 5
    odds: Mapping[str, int] = field(default_factory=lambda: dict(DEFAULT_ODDS))  # weight per rarity
    guarantee: str = "common"  # one card at least of this rarity
    refunds: Mapping[str, int] = field(default_factory=lambda: dict(DUPLICATE_REFUNDS))
    pool: str = "looks"
    season: str | None = None  # draws from that season's looks, on sale in its weeks only
    per_member: int | None = None  # how many times a member may open it, ever
    look: str = "cosmos"  # how its pack looks
    # #130: draws only from what these packs hold (keys, or the start of keys) — a collection's booster
    from_packs: tuple[str, ...] = ()

    @property
    def types(self) -> frozenset[str]:
        return RESERVE_TYPES if self.pool == "reserve" else COSMETIC_TYPES

    @property
    def packs(self) -> tuple[str, ...]:
        if self.from_packs:
            return self.from_packs
        return HD_PACKS if self.pool == "hd" else ()


def booster_of(key: str, names: Mapping[str, str], price: int | None, payload: Mapping[str, Any]) -> Booster:
    """A booster product's settings from its payload — values out of bounds brought back within them."""
    odds = _weights(payload.get("odds"), {r: 0 for r in RARITIES}, 10_000)
    season = payload.get("season")
    per_member = payload.get("per_member")
    packs = payload.get("packs")
    from_packs: tuple[str, ...] = ()
    if isinstance(packs, list):
        from_packs = tuple(str(key)[:64] for key in packs if isinstance(key, str) and key)[:20]
    return Booster(
        key=key,
        names=dict(names),
        price=max(0, int(price or 0)),
        cards=_int(payload.get("cards"), 5, 1, 10),
        odds=odds if sum(odds.values()) else dict(DEFAULT_ODDS),
        guarantee=str(payload.get("guarantee")) if payload.get("guarantee") in RARITIES else "common",
        refunds=_weights(payload.get("refunds"), DUPLICATE_REFUNDS, 100_000),
        pool=str(payload.get("pool")) if payload.get("pool") in POOLS else "looks",
        season=str(season) if season in SEASONS else None,
        per_member=_int(per_member, 1, 1, 1000) if per_member else None,
        look=str(payload.get("look") or "cosmos")[:24],
        from_packs=from_packs,
    )


def on_sale(booster: Booster, today: date) -> bool:
    """Whether the booster is on sale that day (always, or within its season's weeks)."""
    season = SEASONS.get(booster.season or "")
    return season is None or in_window(season.window, today)


def until(booster: Booster, today: date) -> date | None:
    """The last day a season's booster is on sale now (``None``: always on sale, or not now)."""
    season = SEASONS.get(booster.season or "")
    return season_end(season, today) if season else None


def booster_info(
    key: str, names: Mapping[str, str], price: int | None, payload: Mapping[str, Any], today: date | None
) -> dict[str, Any]:
    """What the shop shows of a booster: how many cards, the odds, the rarity guaranteed, what a duplicate
    gives back, what it draws from, its season and until when it is on sale, its pack's look."""
    booster = booster_of(key, names, price, payload)
    end = until(booster, today) if today else None
    return {
        "cards": booster.cards,
        "odds": odds_percent(booster),
        "weights": dict(booster.odds),
        "guarantee": booster.guarantee,
        "refunds": {rarity: refund_of(booster, rarity) for rarity in RARITIES},
        "pool": booster.pool,
        "kind": "reserve" if booster.pool == "reserve" else "looks",
        "season": booster.season,
        "packs": list(booster.from_packs),
        "until": end.isoformat() if end else None,
        "per_member": booster.per_member,
        "look": booster.look,
    }


def odds_percent(booster: Booster) -> dict[str, float]:
    total = sum(booster.odds.values()) or 1
    return {rarity: round(booster.odds.get(rarity, 0) * 100 / total, 1) for rarity in RARITIES}


def refund_of(booster: Booster, rarity: str | None) -> int:
    """The Coins a duplicate of this rarity gives back — fixed per rarity, not the item's price."""
    return booster.refunds.get(rarity or "common", booster.refunds.get("common", 0))


def draw[T](
    booster: Booster,
    pool: Sequence[T],
    rarity_of: Callable[[T], str],
    key_of: Callable[[T], str],
    rng: random.Random | None = None,
) -> list[T]:
    """The booster's cards from ``pool``: a rarity per card by the odds (one at least the guarantee), then
    an item of that rarity — the nearest rarity below when there is none — never twice the same; shuffled."""
    chance = rng or random.SystemRandom()
    by_rarity: dict[str, list[T]] = {r: [] for r in RARITIES}
    for item in pool:
        by_rarity.setdefault(rarity_of(item), []).append(item)
    taken: set[str] = set()
    cards: list[T] = []
    floor = RARITIES.index(booster.guarantee) if booster.guarantee in RARITIES else 0
    for slot in range(booster.cards):
        allowed = RARITIES[floor:] if slot == booster.cards - 1 else RARITIES
        weights = [booster.odds.get(r, 0) for r in allowed]
        rarity = chance.choices(allowed, weights=weights)[0] if sum(weights) else allowed[0]
        for candidate in [rarity, *reversed(RARITIES[: RARITIES.index(rarity)]), *RARITIES]:
            left = [i for i in by_rarity.get(candidate, []) if key_of(i) not in taken]
            if left:
                picked = chance.choice(left)
                taken.add(key_of(picked))
                cards.append(picked)
                break
    # in no particular order: the guaranteed card is not always last, the rarest not always at the end
    chance.shuffle(cards)
    return cards
