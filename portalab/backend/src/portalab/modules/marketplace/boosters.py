"""#81 (proof of concept): boosters — a sealed pack of cosmetic items drawn at random, revealed card by card.

One booster for now, defined here; its odds per rarity will be set by the administrators later. The draw
happens on the server (a system random source): each card's rarity by the odds, the last one at least
rare, never the same item twice in a pack. A card the member already owns is a duplicate — it will be
refunded in Coins. **Nothing is charged, granted or refunded yet**: the reveal is visual only.
"""

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

RARITIES = ("common", "rare", "epic", "legendary")
# what a booster may hold: the looks (never features, services, requests or packs)
COSMETIC_TYPES = frozenset(
    {
        "ambient",
        "avatar_frame",
        "profile_banner",
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
DUPLICATE_SHARE = 0.25  # a duplicate gives back a quarter of the item's price (shown, not paid yet)
DUPLICATE_MIN = 10


@dataclass(frozen=True, slots=True)
class Booster:
    key: str
    names: Mapping[str, str]
    descriptions: Mapping[str, str]
    price: int
    cards: int
    odds: Mapping[str, int]  # weight per rarity
    guarantee: str  # the last card's rarity at least
    theme: str = "cosmos"
    types: frozenset[str] = field(default=COSMETIC_TYPES)


BOOSTERS: dict[str, Booster] = {
    "booster_cosmos": Booster(
        key="booster_cosmos",
        names={"fr": "Booster Cosmos", "en": "Cosmos booster"},
        descriptions={
            "fr": "Cinq looks tirés au hasard — ambiances, cadres, bannières, titres, badges, styles… "
            "dont au moins un rare. Un doublon vous rend des Coins.",
            "en": "Five looks drawn at random — ambiences, frames, banners, titles, badges, styles… at least "
            "one rare. A duplicate gives you Coins back.",
        },
        price=450,
        cards=5,
        odds={"common": 62, "rare": 26, "epic": 10, "legendary": 2},
        guarantee="rare",
    )
}


def odds_percent(booster: Booster) -> dict[str, float]:
    total = sum(booster.odds.values()) or 1
    return {rarity: round(booster.odds.get(rarity, 0) * 100 / total, 1) for rarity in RARITIES}


def refund_of(price: int | None) -> int:
    return max(DUPLICATE_MIN, round((price or 0) * DUPLICATE_SHARE))


def draw[T](
    booster: Booster,
    pool: Sequence[T],
    rarity_of: Callable[[T], str],
    key_of: Callable[[T], str],
    rng: random.Random | None = None,
) -> list[T]:
    """The booster's cards from ``pool``: a rarity per card by the odds (the last at least the guarantee),
    then an item of that rarity — the nearest rarity below when there is none — never twice the same."""
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
    # the pack is revealed from the plainest card to the rarest (the anticipation builds up)
    cards.sort(key=lambda c: RARITIES.index(rarity_of(c)) if rarity_of(c) in RARITIES else 0)
    return cards
