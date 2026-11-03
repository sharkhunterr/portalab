"""#347 — the play gauge's menu: the cards from « collector » up, the day's games and the parties only for the
keen (« full »), the quests not without the game; a member who did not answer sees it all."""

from portalab.modules.shell.assembler.assembler import hidden_by_play


def test_what_each_notch_of_the_play_gauge_leaves_out_of_the_menu() -> None:
    games = {"games.page", "games.party"}
    assert hidden_by_play(None) == (False, frozenset())
    assert hidden_by_play("full") == (False, frozenset())
    assert hidden_by_play("collector") == (False, frozenset(games))
    assert hidden_by_play("progression") == (True, frozenset(games))
    assert hidden_by_play("none") == (True, frozenset({*games, "community.quests"}))
