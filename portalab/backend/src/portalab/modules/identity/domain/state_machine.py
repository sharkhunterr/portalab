"""Account lifecycle state machine (spec 002 "Account State Model", research R8).

The guard table lists every allowed ``(from, to)`` transition with the actor kinds allowed to perform it.
Anything absent is forbidden; ``deleted`` is terminal. Leaving ``pending_deletion`` back to a live state is
only allowed towards the state recorded when deletion was requested ("prior state").
"""

from enum import StrEnum
from typing import Literal

from portalab.core.errors import Conflict


class AccountState(StrEnum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_DELETION = "pending_deletion"
    DELETED = "deleted"


ActorKind = Literal["self", "admin", "system"]

S = AccountState
_RESTORABLE = (S.PENDING_VERIFICATION, S.ACTIVE, S.INACTIVE, S.SUSPENDED)

GUARDS: dict[tuple[AccountState, AccountState], frozenset[ActorKind]] = {
    (S.PENDING_VERIFICATION, S.ACTIVE): frozenset({"system"}),
    (S.PENDING_VERIFICATION, S.PENDING_DELETION): frozenset({"system", "admin"}),
    (S.PENDING_VERIFICATION, S.DELETED): frozenset({"system", "admin"}),
    (S.ACTIVE, S.INACTIVE): frozenset({"system"}),
    (S.INACTIVE, S.ACTIVE): frozenset({"self", "system", "admin"}),
    (S.ACTIVE, S.SUSPENDED): frozenset({"admin"}),
    (S.INACTIVE, S.SUSPENDED): frozenset({"admin"}),
    (S.SUSPENDED, S.ACTIVE): frozenset({"admin"}),
    (S.ACTIVE, S.PENDING_DELETION): frozenset({"self", "admin"}),
    (S.INACTIVE, S.PENDING_DELETION): frozenset({"self", "admin"}),
    (S.SUSPENDED, S.PENDING_DELETION): frozenset({"self", "admin"}),
    **{(S.PENDING_DELETION, prior): frozenset({"self", "admin"}) for prior in _RESTORABLE},
    (S.PENDING_DELETION, S.DELETED): frozenset({"system"}),
}

# event emitted for a transition (cancellation and verification are recognised by their source state)
_EVENTS: dict[tuple[AccountState, AccountState], str] = {
    (S.PENDING_VERIFICATION, S.ACTIVE): "user.verified",
    (S.ACTIVE, S.INACTIVE): "user.deactivated",
    (S.INACTIVE, S.ACTIVE): "user.reactivated",
    (S.SUSPENDED, S.ACTIVE): "user.reactivated",
    (S.ACTIVE, S.SUSPENDED): "user.suspended",
    (S.INACTIVE, S.SUSPENDED): "user.suspended",
    (S.PENDING_VERIFICATION, S.DELETED): "user.deleted",
    (S.PENDING_DELETION, S.DELETED): "user.deleted",
}


class StateTransitionForbidden(Conflict):
    default_code = "user.state_transition_forbidden"
    default_title = "This account state change is not allowed"


def is_allowed(
    current: AccountState,
    target: AccountState,
    actor: ActorKind,
    *,
    prior_state: AccountState | None = None,
) -> bool:
    allowed = GUARDS.get((current, target))
    if allowed is None or actor not in allowed:
        return False
    return not (current is S.PENDING_DELETION and target is not S.DELETED and target is not prior_state)


def check_transition(
    current: AccountState,
    target: AccountState,
    actor: ActorKind,
    *,
    prior_state: AccountState | None = None,
) -> None:
    if not is_allowed(current, target, actor, prior_state=prior_state):
        raise StateTransitionForbidden(
            "This account state change is not allowed.",
            extensions={"from_state": current.value, "to_state": target.value},
        )


def event_for(current: AccountState, target: AccountState) -> str:
    if target is S.PENDING_DELETION:
        return "user.deletion_requested"
    if current is S.PENDING_DELETION and target is not S.DELETED:
        return "user.deletion_cancelled"
    return _EVENTS[(current, target)]


def is_active_account(state: AccountState) -> bool:
    """Only Active accounts are eligible for "active account" capabilities (voting, rewards)."""
    return state is S.ACTIVE


SIGN_IN_ALLOWED: frozenset[AccountState] = frozenset({S.ACTIVE, S.INACTIVE})
"""States from which valid credentials open a session (Inactive returns to Active on sign-in)."""
