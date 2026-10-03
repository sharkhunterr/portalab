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
