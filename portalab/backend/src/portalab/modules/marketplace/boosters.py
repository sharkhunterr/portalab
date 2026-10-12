"""#81 (proof of concept): boosters — a sealed pack of cosmetic items drawn at random, revealed card by card.

One booster for now, defined here; its odds per rarity will be set by the administrators later. The draw
happens on the server (a system random source): each card's rarity by the odds, one at least rare, never
the same item twice in a pack, the cards then shuffled (their place tells nothing). A card the member
already owns is a duplicate — it will give back a fixed amount of Coins per rarity. **Nothing is
charged, granted or refunded yet**: the reveal is visual only.
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
# a duplicate gives back a fixed amount per rarity, whatever the item's price (shown, not paid yet)
DUPLICATE_REFUNDS: Mapping[str, int] = {"common": 10, "rare": 15, "epic": 20, "legendary": 30}


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
    refunds: Mapping[str, int] = field(default_factory=lambda: dict(DUPLICATE_REFUNDS))


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
