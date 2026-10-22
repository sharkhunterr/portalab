"""Issue 223 — a title is rewarded once by a campaign's themed bonuses (genre, title, keyword, picked titles):
the best applies, the others are « covered »; a general bonus (every play) still adds up, and two campaigns
still add up."""

from portalab.modules.campaigns.definitions.schema import When
from portalab.modules.campaigns.modifiers.provider import Explanation, _once_per_title, themed


def _item(campaign: str, modifier: str, factor: float, *, is_themed: bool, value: str = "xp") -> Explanation:
    return Explanation(campaign, 1, modifier, value, factor, "match", is_themed)


def test_themed_bonuses_of_a_campaign_apply_once() -> None:
    found = [
        _item("halloween", "horror", 2, is_themed=True),
        _item("halloween", "keywords", 2, is_themed=True),
        _item("halloween", "keywords", 2, is_themed=True, value="coins"),
        _item("christmas", "festive", 1.5, is_themed=False),
        _item("christmas", "xmas", 2, is_themed=True),
        _item("christmas", "picked", 3, is_themed=True),
        _item("other", "horror", 1.5, is_themed=True),
    ]
    verdicts = [(i.campaign, i.modifier, i.value, i.verdict) for i in _once_per_title(found)]
    assert verdicts == [
        ("halloween", "horror", "xp", "match"),
        ("halloween", "keywords", "xp", "covered"),
        ("halloween", "keywords", "coins", "match"),  # another value: its own best
        ("christmas", "festive", "xp", "match"),  # general: adds up
        ("christmas", "xmas", "xp", "covered"),
        ("christmas", "picked", "xp", "match"),  # the best of the themed ones
        ("other", "horror", "xp", "match"),  # another campaign: adds up
    ]


def test_what_is_themed() -> None:
    assert themed(When(genre=["horror"])) and themed(When(keyword=["halloween"]))
    assert not themed(When(activity=["media.playback_finished"], media_kind=["movie"]))
