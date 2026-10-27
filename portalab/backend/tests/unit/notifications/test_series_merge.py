"""Issues 258, 261: a series of gains merged into one notification — the rewards and the minutes counted added
up, the work left unsaid when the series is about several; a work told by its series, season and number."""

from types import SimpleNamespace

from portalab.modules.gamification.notify import work_name
from portalab.modules.notifications.fanout.merge import merged


def test_a_series_adds_up_its_rewards_and_minutes() -> None:
    first = {"value": "xp", "amount": 5, "xp": 5, "minutes": 16, "work": "none", "rule": "radio_listening"}
    then = {"value": "xp", "amount": 7, "xp": 7, "minutes": 22, "work": "none", "rule": "radio_listening"}
    assert merged(first, then) | {} == then | {"xp": 12, "minutes": 38}


def test_a_series_about_several_works_names_none() -> None:
    one = {"xp": 50, "minutes": 50, "work": "Sissi · S2 E5"}
    other = {"xp": 48, "minutes": 48, "work": "Sissi · S2 E6"}
    assert merged(one, other)["work"] == "none"
    assert merged(other, other)["work"] == "Sissi · S2 E6"


def test_a_work_is_told_by_its_series_season_and_number() -> None:
    def work(**fields: object) -> SimpleNamespace:
        return SimpleNamespace(**({"series": None, "season": None, "number": None, "year": None} | fields))

    assert work_name(work(kind="episode", title="Épisode 6", series="Sissi", season=2, number=6)) == (
        "Sissi · S2 E6"
    )
    assert work_name(work(kind="episode", title="La fuite", series="Sissi", season=2, number=6)) == (
        "Sissi · S2 E6 · La fuite"
    )
    assert work_name(work(kind="movie", title="Dune", year=2021)) == "Dune (2021)"
    assert work_name(work(kind="book", title="Fondation")) == "Fondation"
