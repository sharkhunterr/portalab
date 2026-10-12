"""#81: boosters — a sealed pack of items drawn at random, revealed card by card.

The boosters are defined here (their odds will be set by the administrators later): the classic one
(Cosmos), the legendary one (dear, a legendary card sure), Prestige HD (only looks drawn by the graphics
chip), the Reserve (only items to keep: requests, freezes, boosts, rescues, tickets), the season's (on sale
for its weeks only, with the looks of the season) and Discovery (small and cheap, three per member).

The draw happens on the server (a system random source): each card's rarity by the odds, one at least the
guaranteed rarity, never the same item twice in a pack, the cards then shuffled (their place tells
nothing). Opening one charges its price; a look not owned yet is granted, one already owned is a duplicate
that gives back a fixed amount of Coins per rarity, an item to keep goes to the member's reserve.
"""

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

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
# a duplicate gives back a fixed amount per rarity, whatever the item's price
DUPLICATE_REFUNDS: Mapping[str, int] = {"common": 10, "rare": 15, "epic": 20, "legendary": 30}
# Prestige HD: the looks the packs drawn by the graphics chip hold
HD_PACKS = ("pack_hd_", "pack_living_badges")

Day = tuple[int, int]  # (month, day)


@dataclass(frozen=True, slots=True)
class Booster:
    key: str
    names: Mapping[str, str]
    descriptions: Mapping[str, str]
    price: int
    cards: int
    odds: Mapping[str, int]  # weight per rarity
    guarantee: str  # one card at least of this rarity
    theme: str = "cosmos"  # how its pack looks
    types: frozenset[str] = field(default=COSMETIC_TYPES)
    refunds: Mapping[str, int] = field(default_factory=lambda: dict(DUPLICATE_REFUNDS))
    # the pool limited to what these packs hold (a key, or the start of keys); empty: every product of
    # its types
    packs: tuple[str, ...] = ()
    # on sale from one day to another of each year (inclusive; may run over the new year)
    window: tuple[Day, Day] | None = None
    # how many times a member may open it, ever
    per_member: int | None = None


def _season(
    key: str, theme: str, names: Mapping[str, str], about: Mapping[str, str], packs: tuple[str, ...],
    window: tuple[Day, Day],
) -> Booster:  # fmt: skip
    return Booster(
        key=key,
        names=names,
        descriptions=about,
        price=450,
        cards=5,
        odds={"common": 55, "rare": 33, "epic": 10, "legendary": 2},
        guarantee="rare",
        theme=theme,
        packs=packs,
        window=window,
    )


BOOSTERS: dict[str, Booster] = {
    b.key: b
    for b in (
        Booster(
            key="booster_cosmos",
            names={"fr": "Booster Cosmos", "en": "Cosmos booster"},
            descriptions={
                "fr": "Le classique : cinq looks tirés au hasard — ambiances, cadres, bannières, titres, "
                "badges, styles… dont au moins un rare.",
                "en": "The classic: five looks drawn at random — ambiences, frames, banners, titles, "
                "badges, styles… at least one rare.",
            },
            price=450,
            cards=5,
            odds={"common": 62, "rare": 26, "epic": 10, "legendary": 2},
            guarantee="rare",
        ),
        Booster(
            key="booster_legend",
            names={"fr": "Booster Légendaire", "en": "Legendary booster"},
            descriptions={
                "fr": "Trois cartes, pas une en dessous d'épique, et une légendaire assurée.",
                "en": "Three cards, none below epic, and a legendary one for sure.",
            },
            price=3000,
            cards=3,
            odds={"epic": 70, "legendary": 30},
            guarantee="legendary",
            theme="legend",
        ),
        Booster(
            key="booster_prestige",
            names={"fr": "Booster Prestige HD", "en": "Prestige HD booster"},
            descriptions={
                "fr": "Uniquement des looks dessinés par la puce graphique — flammes, plasma, or liquide… "
                "Trois cartes, dont au moins une épique.",
                "en": "Only looks drawn by the graphics chip — flames, plasma, liquid gold… Three cards, at "
                "least one epic.",
            },
            price=1200,
            cards=3,
            odds={"rare": 20, "epic": 62, "legendary": 18},
            guarantee="epic",
            theme="prestige",
            packs=HD_PACKS,
        ),
        Booster(
            key="booster_reserve",
            names={"fr": "Booster Réserve", "en": "Reserve booster"},
            descriptions={
                "fr": "Des objets à garder pour plus tard : demandes en plus, gels de série, boosts, "
                "sauvetages… et peut-être un film en 4K. Ils vont dans votre réserve.",
                "en": "Items to keep for later: extra requests, streak freezes, boosts, rescues… and maybe "
                "a film in 4K. They go to your reserve.",
            },
            price=300,
            cards=3,
            odds={"common": 60, "rare": 30, "epic": 9, "legendary": 1},
            guarantee="rare",
            theme="reserve",
            types=RESERVE_TYPES,
        ),
        Booster(
            key="booster_discovery",
            names={"fr": "Booster Découverte", "en": "Discovery booster"},
            descriptions={
                "fr": "Pour commencer : trois looks pour un petit prix. Trois ouvertures par membre.",
                "en": "To get started: three looks for a small price. Three openings per member.",
            },
            price=120,
            cards=3,
            odds={"common": 72, "rare": 25, "epic": 3},
            guarantee="common",
            theme="discovery",
            per_member=3,
        ),
        _season(
            "booster_spring",
            "spring",
            {"fr": "Booster Printemps", "en": "Spring booster"},
            {
                "fr": "De saison : fleurs, grand air et couleurs fraîches — jusqu'au 20 juin.",
                "en": "In season: blossom, fresh air and bright colours — until 20 June.",
            },
            ("pack_hd_sakura", "pack_great_outdoors", "pack_paint_studio"),
            ((3, 20), (6, 20)),
        ),
        _season(
            "booster_summer",
            "summer",
            {"fr": "Booster Été", "en": "Summer booster"},
            {
                "fr": "De saison : sable, océan et nuits néon — jusqu'au 22 septembre.",
                "en": "In season: sand, ocean and neon nights — until 22 September.",
            },
            ("ultimate_desert", "pack_hd_ocean", "pack_retro", "pack_neon_nights"),
            ((6, 21), (9, 22)),
        ),
        _season(
            "booster_halloween",
            "halloween",
            {"fr": "Booster Halloween", "en": "Halloween booster"},
            {
                "fr": "De saison : frissons, ténèbres et monde à l'envers — jusqu'au 10 novembre.",
                "en": "In season: chills, darkness and the upside down — until 10 November.",
            },
            ("ultimate_halloween", "ultimate_horror", "pack_chills", "ultimate_upsidedown"),
            ((10, 1), (11, 10)),
        ),
        _season(
            "booster_winter",
            "winter",
            {"fr": "Booster Noël", "en": "Christmas booster"},
            {
                "fr": "De saison : neige, guirlandes et coin du feu — jusqu'au 6 janvier.",
                "en": "In season: snow, fairy lights and the fireside — until 6 January.",
            },
            ("ultimate_christmas", "pack_christmas_eve", "pack_cocooning"),
            ((12, 1), (1, 6)),
        ),
    )
}


def on_sale(booster: Booster, today: date) -> bool:
    """Whether the booster is on sale that day (always, or within its window of the year)."""
    if booster.window is None:
        return True
    start, end = booster.window
    day = (today.month, today.day)
    return start <= day <= end if start <= end else day >= start or day <= end


def until(booster: Booster, today: date) -> date | None:
    """The last day of its current window (``None``: always on sale, or not on sale now)."""
    if booster.window is None or not on_sale(booster, today):
        return None
    (_, _), (month, day) = booster.window
    year = today.year + (1 if (month, day) < (today.month, today.day) else 0)
    return date(year, month, day)


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
