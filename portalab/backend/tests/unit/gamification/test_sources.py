"""#129 — where a gain comes from: asking for a title is a request of its own, never a play."""

from portalab.modules.gamification.progression.sources import action_of


def test_each_action_has_its_source() -> None:
    assert action_of("media.request_created") == "requests"
    assert action_of("media.request_available") == "requests"
    assert action_of("media.played") == "media"
    assert action_of("marketplace.purchased") == "shop"
    assert action_of("ticket.created") == "support"
    # issue 265: the games page's games, the day's title, the week's challenges, the boards
    assert action_of("games.played") == action_of("games.board_ranked") == "minigames"
    assert action_of("user.signed_in") == "visits"
    assert action_of("dashboard.layout_changed") == "activity"
    assert action_of(None) == "activity"
