"""014 T014 — conditions: media kind, canonical genres, title contains (NFKC, casefold, diacritics-
insensitive, original and effective title), activity, audience (all / roles / users / level range), AND
semantics; unknown attributes ⇒ the modifier does not apply."""

from uuid import UUID, uuid4

import pytest

from portalab.capabilities.activity import ActivityAttributes
from portalab.capabilities.catalog import new_registry
from portalab.capabilities.statistics import PROGRESSION
from portalab.capabilities.user_grants import ROLES_CAPABILITY
from portalab.modules.campaigns.definitions.schema import Audience, When
from portalab.modules.campaigns.matching.conditions import Matcher, match_attributes

MOVIE = ActivityAttributes(
    "movie",
    ("Horror", "Thriller"),
    "\uff28alloween \uff2eight",
    "La nuit d'Hallowéen",  # full-width letters (NFKC)
)


@pytest.mark.parametrize(
    ("when", "attributes", "verdict"),
    [
        (When(), None, "match"),
        (When(media_kind=["movie"], genre=["horror"]), MOVIE, "match"),
        (When(media_kind=["series"], genre=["horror"]), MOVIE, "no_match"),
        (When(genre=["comedy"]), MOVIE, "no_match"),
        (When(title_contains=["halloween"]), MOVIE, "match"),
        (
            When(title_contains=["HALLOWEEN"]),
            ActivityAttributes(title="x", original_title="Hallowéen"),
            "match",
        ),
        (When(title_contains=["christmas"]), MOVIE, "no_match"),
        (When(genre=["horror"]), None, "unknown"),
        (When(genre=["horror"]), ActivityAttributes(media_kind="movie"), "unknown"),
        (When(title_contains=["x"]), ActivityAttributes(media_kind="movie"), "unknown"),
    ],
)
def test_attribute_conditions(when: When, attributes: ActivityAttributes | None, verdict: str) -> None:
    assert match_attributes(when, attributes) == verdict


class Roles:
    async def roles_of(self, user_id: UUID) -> frozenset[str]:
        return frozenset({"user", "vip"})


class Levels:
    async def level(self, user_id: UUID) -> int:
        return 7

    async def has_achievement(self, user_id: UUID, achievement: str) -> bool:
        return False


async def test_audience() -> None:
    capabilities = new_registry()
    capabilities.provide(ROLES_CAPABILITY, Roles(), instance_ref="t", owner="module:authz")
    capabilities.provide(PROGRESSION, Levels(), instance_ref="t", owner="module:gamification")
    matcher = Matcher(capabilities, None, record_failures=False)  # type: ignore[arg-type]
    user = uuid4()
    assert await matcher.in_audience(Audience(), user)
    assert await matcher.in_audience(Audience(kind="roles", roles=["vip"]), user)
    assert not await matcher.in_audience(Audience(kind="roles", roles=["staff"]), user)
    assert await matcher.in_audience(Audience(kind="users", users=[str(user)]), user)
    assert not await matcher.in_audience(Audience(kind="users", users=[str(uuid4())]), user)
    assert await matcher.in_audience(Audience(kind="level_range", min_level=5, max_level=10), user)
    assert not await matcher.in_audience(Audience(kind="level_range", min_level=8), user)
    assert not await Matcher(new_registry(), None, record_failures=False).in_audience(  # type: ignore[arg-type]
        Audience(kind="roles", roles=["vip"]), user
    )


def test_a_christmas_film_by_its_title_its_keywords_or_picked() -> None:
    """Title, keyword or hand-picked: any one is enough; the kind still has to match."""
    when = When(
        media_kind=["movie"],
        title_contains=["noël"],
        keyword=["christmas"],
        objects=["11111111-1111-1111-1111-111111111111"],
    )
    by_title = ActivityAttributes(media_kind="movie", title="Hyper Noël")
    by_keyword = ActivityAttributes(media_kind="movie", title="Die Hard 2", keywords=("christmas eve",))
    picked = ActivityAttributes(
        media_kind="movie", title="Love Actually", objects=("11111111-1111-1111-1111-111111111111",)
    )
    other = ActivityAttributes(media_kind="movie", title="Alien", keywords=("space",))
    series = ActivityAttributes(media_kind="episode", title="Hyper Noël")
    assert match_attributes(when, by_title) == "match"
    assert match_attributes(when, by_keyword) == "match"
    assert match_attributes(when, picked) == "match"
    assert match_attributes(when, other) == "no_match"
    assert match_attributes(when, series) == "no_match"


def test_a_picked_series_counts_its_episodes() -> None:
    when = When(objects=["series-1"])
    episode = ActivityAttributes(
        media_kind="episode", title="Pilot", objects=("ep-9", "season-2", "series-1")
    )
    assert match_attributes(when, episode) == "match"


def test_a_season_discount_covers_every_product_of_the_season() -> None:
    from portalab.capabilities.campaigns import ShopDiscount, best_discount

    christmas = ShopDiscount(campaign="xmas", name="Noël", ref="r", percent=20, seasons=("christmas",))
    assert best_discount([christmas], "badge_elf", None, "christmas") is christmas
    assert best_discount([christmas], "badge_bat", None, "halloween") is None
    assert best_discount([christmas], "badge_elf", None) is None


def test_one_bonus_multiplies_several_values() -> None:
    from portalab.modules.campaigns.definitions.schema import ModifierDef

    both = ModifierDef(id="xmas", gains=[{"value": "xp", "factor": 2}, {"value": "coins", "factor": 1.5}])
    assert [(g.value, g.factor) for g in both.all_gains()] == [("xp", 2.0), ("coins", 1.5)]
    older = ModifierDef(id="festive", value="xp", factor=1.5)  # one value, as before
    assert [(g.value, g.factor) for g in older.all_gains()] == [("xp", 1.5)]
    with pytest.raises(ValueError):
        ModifierDef(id="none")
    with pytest.raises(ValueError):
        ModifierDef(id="twice", gains=[{"value": "xp", "factor": 2}, {"value": "xp", "factor": 3}])
