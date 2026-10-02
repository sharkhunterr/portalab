"""002 T007 — exhaustive allowed/forbidden transition table (spec 002 "Account State Model")."""

import itertools

import pytest

from portalab.modules.identity.domain.state_machine import (
    GUARDS,
    SIGN_IN_ALLOWED,
    AccountState,
    StateTransitionForbidden,
    check_transition,
    event_for,
    is_active_account,
    is_allowed,
)

pytestmark = pytest.mark.unit

S = AccountState
ACTORS = ("self", "admin", "system")

# the spec table, written independently of the implementation
EXPECTED: dict[tuple[AccountState, AccountState], set[str]] = {
    (S.PENDING_VERIFICATION, S.ACTIVE): {"system"},
    (S.PENDING_VERIFICATION, S.PENDING_DELETION): {"system", "admin"},
    (S.PENDING_VERIFICATION, S.DELETED): {"system", "admin"},
    (S.ACTIVE, S.INACTIVE): {"system"},
    (S.INACTIVE, S.ACTIVE): {"self", "system", "admin"},
    (S.ACTIVE, S.SUSPENDED): {"admin"},
    (S.INACTIVE, S.SUSPENDED): {"admin"},
    (S.SUSPENDED, S.ACTIVE): {"admin"},
    (S.ACTIVE, S.PENDING_DELETION): {"self", "admin"},
    (S.INACTIVE, S.PENDING_DELETION): {"self", "admin"},
    (S.SUSPENDED, S.PENDING_DELETION): {"self", "admin"},
    (S.PENDING_DELETION, S.PENDING_VERIFICATION): {"self", "admin"},
    (S.PENDING_DELETION, S.ACTIVE): {"self", "admin"},
    (S.PENDING_DELETION, S.INACTIVE): {"self", "admin"},
    (S.PENDING_DELETION, S.SUSPENDED): {"self", "admin"},
    (S.PENDING_DELETION, S.DELETED): {"system"},
}


def test_guard_table_matches_the_spec() -> None:
    assert {key: set(value) for key, value in GUARDS.items()} == EXPECTED


@pytest.mark.parametrize(("current", "target", "actor"), list(itertools.product(list(S), list(S), ACTORS)))
def test_every_combination(current: AccountState, target: AccountState, actor: str) -> None:
    prior = target if current is S.PENDING_DELETION and target is not S.DELETED else None
    expected = actor in EXPECTED.get((current, target), set())
    assert is_allowed(current, target, actor, prior_state=prior) is expected  # type: ignore[arg-type]
    if not expected:
        with pytest.raises(StateTransitionForbidden) as caught:
            check_transition(current, target, actor, prior_state=prior)  # type: ignore[arg-type]
        assert caught.value.code == "user.state_transition_forbidden"


def test_deleted_is_terminal() -> None:
    for target, actor in itertools.product(list(S), ACTORS):
        assert not is_allowed(S.DELETED, target, actor)  # type: ignore[arg-type]


@pytest.mark.parametrize("prior", [S.ACTIVE, S.INACTIVE, S.SUSPENDED, S.PENDING_VERIFICATION])
def test_cancel_only_restores_the_prior_state(prior: AccountState) -> None:
    assert is_allowed(S.PENDING_DELETION, prior, "self", prior_state=prior)
    for other in {S.ACTIVE, S.INACTIVE, S.SUSPENDED, S.PENDING_VERIFICATION} - {prior}:
        assert not is_allowed(S.PENDING_DELETION, other, "self", prior_state=prior)
    assert not is_allowed(S.PENDING_DELETION, prior, "self", prior_state=None)


def test_events_per_transition() -> None:
    assert event_for(S.PENDING_VERIFICATION, S.ACTIVE) == "user.verified"
    assert event_for(S.ACTIVE, S.INACTIVE) == "user.deactivated"
    assert event_for(S.INACTIVE, S.ACTIVE) == "user.reactivated"
    assert event_for(S.SUSPENDED, S.ACTIVE) == "user.reactivated"
    assert event_for(S.ACTIVE, S.SUSPENDED) == "user.suspended"
    assert event_for(S.SUSPENDED, S.PENDING_DELETION) == "user.deletion_requested"
    assert event_for(S.PENDING_DELETION, S.SUSPENDED) == "user.deletion_cancelled"
    assert event_for(S.PENDING_DELETION, S.DELETED) == "user.deleted"
    for current, target in EXPECTED:
        assert event_for(current, target).startswith("user.")


def test_only_active_is_an_active_account() -> None:
    assert [state for state in S if is_active_account(state)] == [S.ACTIVE]
    assert {S.ACTIVE, S.INACTIVE} == SIGN_IN_ALLOWED
