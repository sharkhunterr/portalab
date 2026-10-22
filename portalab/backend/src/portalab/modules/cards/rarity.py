"""How rare a card is (issue 229). A card's score is how known its work is (the votes it gathered, on a log
scale, a little of its rating), weighted by the part the card plays in it (the work itself, its director, the
first names of its credits higher than the last ones), plus how often its person appears in the library.

Its rarity is its rank among the cards **of its own country** (the work's first country of production): a
lead in a French success is compared with French cinema, not with Hollywood — so every country has its
legendary cards. A country with too few cards is ranked with the whole library.
"""

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

# the share of each rarity, from the top: 2.5 % legendary, 9.5 % epic, 28 % rare, the rest common
THRESHOLDS = ((0.975, "legendary"), (0.88, "epic"), (0.6, "rare"))
COHORT_MIN = 300  # cards a country needs to be ranked on its own
KIND_WEIGHT = {"title": 1.05, "director": 0.95, "creator": 0.9, "writer": 0.6, "composer": 0.55}
CAST_WEIGHT = (1.0, 0.92, 0.84, 0.76, 0.68, 0.62, 0.56, 0.52, 0.48, 0.45)


def work_fame(vote_count: int, vote_average: float | None) -> float:
    rating = (vote_average - 6.0) * 0.1 if vote_average else 0.0
    return math.log10(1 + max(0, vote_count)) + max(-0.3, min(0.3, rating))


def card_score(kind: str, billing: int, fame: float, appearances: int) -> float:
    weight = CAST_WEIGHT[min(billing, len(CAST_WEIGHT) - 1)] if kind == "cast" else KIND_WEIGHT.get(kind, 0.5)
    person = 0.25 * math.log2(1 + appearances) if kind != "title" else 0.0
    return round(fame * weight + person, 4)


@dataclass(frozen=True, slots=True)
class Ranked:
    key: object
    score: float
    country: str | None


def rarities(cards: Iterable[Ranked]) -> Mapping[object, str]:
    """Each card's rarity: its percentile among its country's cards (or the library's)."""
    items = list(cards)
    per_country: dict[str, int] = defaultdict(int)
    for card in items:
        per_country[card.country or "*"] += 1
    cohorts: dict[str, list[Ranked]] = defaultdict(list)
    for card in items:
        country = card.country or "*"
        cohorts[country if per_country[country] >= COHORT_MIN else "*"].append(card)
    out: dict[object, str] = {}
    for members in cohorts.values():
        ordered = sorted(members, key=lambda c: c.score)
        count = len(ordered)
        for index, card in enumerate(ordered):
            rank = (index + 0.5) / count
            out[card.key] = next((name for floor, name in THRESHOLDS if rank >= floor), "common")
    return out
