"""014 T017 — horror movie ⇒ XP x2 and Coins x1.5; title containing "Halloween" ⇒ XP x2 too, but a title is
rewarded once by a campaign's themed bonuses (issue 223: the best, not both); each modifier at most once per
occurrence; eligibility by ``occurred_at`` (late and duplicate events resolve
identically, also after the campaign ended); references ``campaign:key:version:modifier``."""

import pytest

from portalab.capabilities.economy import MODIFIERS
from tests.integration.campaigns.conftest import CampHarness, later, paris
from tests.integration.gamification.conftest import GamHarness

pytestmark = pytest.mark.integration


def envelope(cm: CampHarness, user: object, media_id: str, at: object) -> object:
    return GamHarness.envelope(None, user, {"media_id": media_id}, at=at, event_type="media.played")  # type: ignore[arg-type]


async def test_factors_by_occurrence(cm: CampHarness) -> None:
    await cm.create()
    provider = next(
        p.provider
        for p in cm.ev.full.identity.capabilities.system_providers(MODIFIERS)
        if p.instance_ref == "campaigns"
    )
    user = cm.people["ursula"]
    inside = paris(10, 25, 21)
    before = paris(10, 10, 21)
    await cm.at(later(paris(10, 20, 0), seconds=10))
    halloween_night = envelope(cm, user, "m1", inside)
    xp = await provider.modifiers_for(user, halloween_night, "xp", inside)
    coins = await provider.modifiers_for(user, halloween_night, "coins", inside)
    assert [(m.source_ref, m.factor) for m in xp] == [("campaign:halloween:1:horror_xp", 2.0)]
    assert [(m.source_ref, m.factor) for m in coins] == [("campaign:halloween:1:horror_coins", 1.5)]
    assert await provider.modifiers_for(user, envelope(cm, user, "m2", inside), "xp", inside) == []
    assert (
        await provider.modifiers_for(user, envelope(cm, user, "m3", inside), "xp", inside) == []
    )  # a series
    assert await provider.modifiers_for(user, envelope(cm, user, "m1", before), "xp", before) == []
    await cm.at(later(paris(11, 1, 0), hours=5))
    late = await provider.modifiers_for(user, halloween_night, "xp", inside)  # delivered after the end
    assert sorted(m.source_ref for m in late) == sorted(m.source_ref for m in xp)
    assert all(not hasattr(m, "amount") for m in late)  # factors only — never amounts
