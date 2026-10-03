"""015 T007 — the project state machine: allowed and forbidden transitions, votes accepted only in
idea/proposal/open, funding only in open, milestones, funding rules validation and tranche splitting."""

from itertools import pairwise

import pytest

from portalab.core.errors import ValidationFailed
from portalab.modules.marketplace.projects.rules import parse_rules, split
from portalab.modules.marketplace.projects.state import (
    TRANSITIONS,
    accepts_funding,
    accepts_votes,
    allowed,
    reached,
    terminal,
)

PATH = ["idea", "proposal", "open", "validation", "development", "beta", "released"]


def test_forward_path_and_off_ramps() -> None:
    for source, target in pairwise(PATH):
        assert allowed(source, target), (source, target)
    for state in ("idea", "proposal", "open", "validation", "development", "beta"):
        assert allowed(state, "abandoned")
    for state in ("idea", "proposal", "open", "validation"):
        assert allowed(state, "rejected")
    assert allowed("development", "released")  # beta is optional
    for forbidden in (("idea", "open"), ("open", "development"), ("released", "beta"), ("rejected", "open")):
        assert not allowed(*forbidden)
    assert all(not TRANSITIONS[s] and terminal(s) for s in ("released", "rejected", "abandoned"))


def test_votes_and_funding_windows() -> None:
    assert [s for s in TRANSITIONS if accepts_votes(s)] == ["idea", "proposal", "open"]
    assert [s for s in TRANSITIONS if accepts_funding(s)] == ["open"]
    assert reached("beta", "development") and not reached("development", "beta")
    assert not reached("rejected", "released")


def test_rules() -> None:
    rules = parse_rules(
        {"consume_at": [{"state": "beta", "percent": 30}, {"state": "released", "percent": 70}]}
    )
    assert split(101, rules) == [("beta", 30), ("released", 71)]
    assert split(1, rules) == [("released", 1)]  # empty tranches dropped
    assert split(50, parse_rules({})) == [("released", 50)]
    for invalid in (
        {"consume_at": [{"state": "beta", "percent": 30}]},
        {"consume_at": [{"state": "released", "percent": 50}, {"state": "beta", "percent": 50}]},
        {"refund_on_reject": 50},
        {"min_funding": 10, "max_funding_per_user": 5},
        {"surprise": True},
    ):
        with pytest.raises(ValidationFailed):
            parse_rules(invalid)
