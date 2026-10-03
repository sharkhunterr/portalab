"""Project lifecycle state machine (T009; R2, CD-008): ``idea → proposal → open → validation →
development → beta → released`` with off-ramps ``rejected`` and ``abandoned``. Votes are accepted in
``idea|proposal|open``; funding only in ``open``; the funding rules freeze when the project opens."""

from portalab.capabilities.marketplace import TERMINAL_STATES, VOTING_STATES, ProjectState

TRANSITIONS: dict[str, frozenset[str]] = {
    "idea": frozenset({"proposal", "rejected", "abandoned"}),
    "proposal": frozenset({"open", "rejected", "abandoned"}),
    "open": frozenset({"validation", "rejected", "abandoned"}),
    "validation": frozenset({"development", "rejected", "abandoned"}),
    "development": frozenset({"beta", "released", "abandoned"}),
    "beta": frozenset({"released", "abandoned"}),
    "released": frozenset(),
    "rejected": frozenset(),
    "abandoned": frozenset(),
}
# the order used for milestone consumption ("consume 50 % at beta, the rest at release")
ORDER: tuple[ProjectState, ...] = (
    "idea",
    "proposal",
    "open",
    "validation",
    "development",
    "beta",
    "released",
)


def allowed(source: str, target: str) -> bool:
    return target in TRANSITIONS.get(source, frozenset())


def accepts_votes(state: str) -> bool:
    return state in VOTING_STATES


def accepts_funding(state: str) -> bool:
    return state == "open"


def terminal(state: str) -> bool:
    return state in TERMINAL_STATES


def reached(state: str, milestone: str) -> bool:
    """Whether a project in ``state`` has passed ``milestone`` on the forward path."""
    if state not in ORDER or milestone not in ORDER:
        return False
    return ORDER.index(state) >= ORDER.index(milestone)
