"""Declarative ticket workflows (T018; R3, OQ-75 default): states and guarded transitions as **data** with a
closed schema — no scripting. Guards name who may act (``requester``, ``assignee``, ``staff`` =
``tickets.manage``), whether a comment is required and whether the move is a reopen (only within
``support.reopenWindowDays``). Custom workflows are validated (unknown states, unreachable states and dead
ends are refused) and versioned; tickets keep the version they started with. Reactions to transitions are
events consumed elsewhere (019), never code here."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from portalab.core.errors import Forbidden, ValidationFailed

Actor = Literal["requester", "assignee", "staff"]
StateKind = Literal["open", "active", "waiting", "resolved", "closed"]


class StateDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=80)
    kind: StateKind
    terminal: bool = False


class TransitionDef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=80)
    from_states: list[str] = Field(alias="from", min_length=1)
    to: str
    who: list[Actor] = Field(min_length=1)
    comment_required: bool = False
    reopen: bool = False


class WorkflowDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    states: list[StateDef] = Field(min_length=2, max_length=30)
    initial: str
    transitions: list[TransitionDef] = Field(min_length=1, max_length=80)

    def state(self, key: str) -> StateDef | None:
        return next((s for s in self.states if s.key == key), None)


class WorkflowInvalid(ValidationFailed):
    default_code = "ticket.workflow_invalid"
    default_title = "This workflow is not valid"


class TransitionForbidden(Forbidden):
    default_code = "ticket.transition_forbidden"
    default_title = "This transition is not allowed"


BASELINE: dict[str, Any] = {
    "states": [
        {"key": "open", "label": "Open", "kind": "open"},
        {"key": "in_progress", "label": "In progress", "kind": "active"},
        {"key": "waiting_user", "label": "Waiting for you", "kind": "waiting"},
        {"key": "resolved", "label": "Resolved", "kind": "resolved"},
        {"key": "closed", "label": "Closed", "kind": "closed", "terminal": True},
        {"key": "cancelled", "label": "Cancelled", "kind": "closed", "terminal": True},
    ],
    "initial": "open",
    "transitions": [
        {"key": "start", "label": "Start", "from": ["open"], "to": "in_progress", "who": ["staff"]},
        {
            "key": "ask_user",
            "label": "Ask the requester",
            "from": ["in_progress"],
            "to": "waiting_user",
            "who": ["staff"],
            "comment_required": True,
        },
        {
            "key": "respond",
            "label": "Respond",
            "from": ["waiting_user"],
            "to": "in_progress",
            "who": ["requester", "staff"],
        },
        {
            "key": "resolve",
            "label": "Resolve",
            "from": ["open", "in_progress", "waiting_user"],
            "to": "resolved",
            "who": ["staff", "assignee"],
        },
        {
            "key": "close",
            "label": "Close",
            "from": ["resolved"],
            "to": "closed",
            "who": ["requester", "staff"],
        },
        {
            "key": "reopen",
            "label": "Reopen",
            "from": ["resolved"],
            "to": "open",
            "who": ["requester", "staff"],
            "reopen": True,
        },
        {
            "key": "cancel",
            "label": "Cancel",
            "from": ["open", "in_progress", "waiting_user"],
            "to": "cancelled",
            "who": ["requester", "staff"],
        },
    ],
}


def parse(definition: Mapping[str, Any]) -> WorkflowDef:
    try:
        workflow = WorkflowDef.model_validate(dict(definition))
    except ValidationError as exc:
        raise WorkflowInvalid(
            "The workflow does not follow the schema.",
            extensions={"errors": [".".join(str(p) for p in e["loc"]) for e in exc.errors()]},
        ) from exc
    validate(workflow)
    return workflow


def validate(workflow: WorkflowDef) -> None:
    errors: list[str] = []
    keys = [s.key for s in workflow.states]
    if len(set(keys)) != len(keys):
        errors.append("duplicate state")
    known = set(keys)
    if workflow.initial not in known:
        errors.append(f"unknown initial state {workflow.initial}")
    if len({t.key for t in workflow.transitions}) != len(workflow.transitions):
        errors.append("duplicate transition")
    for transition in workflow.transitions:
        for name in (*transition.from_states, transition.to):
            if name not in known:
                errors.append(f"transition {transition.key} uses unknown state {name}")
    reachable = {workflow.initial}
    changed = True
    while changed:
        changed = False
        for transition in workflow.transitions:
            if transition.to not in reachable and reachable & set(transition.from_states):
                reachable.add(transition.to)
                changed = True
    for state in workflow.states:
        if state.key not in reachable:
            errors.append(f"state {state.key} is unreachable")
        leaving = any(state.key in t.from_states for t in workflow.transitions)
        if not state.terminal and not leaving:
            errors.append(f"state {state.key} is a dead end (mark it terminal or add a transition)")
    if not any(s.terminal for s in workflow.states):
        errors.append("no terminal state")
    if errors:
        raise WorkflowInvalid("The workflow is not valid.", extensions={"errors": errors})


@dataclass(frozen=True, slots=True)
class Move:
    transition: TransitionDef
    target: StateDef


def available(
    workflow: WorkflowDef, state: str, actors: Iterable[str], *, reopen_open: bool
) -> list[TransitionDef]:
    roles = set(actors)
    return [
        t
        for t in workflow.transitions
        if state in t.from_states and roles & set(t.who) and (not t.reopen or reopen_open or "staff" in roles)
    ]


def check(
    workflow: WorkflowDef,
    state: str,
    transition_key: str,
    actors: Iterable[str],
    *,
    has_comment: bool,
    reopen_open: bool,
) -> Move:
    transition = next((t for t in workflow.transitions if t.key == transition_key), None)
    roles = set(actors)
    if transition is None or state not in transition.from_states:
        raise TransitionForbidden("This transition does not exist from the ticket's current state.")
    if not roles & set(transition.who):
        raise TransitionForbidden("You may not perform this transition.")
    if transition.reopen and not reopen_open and "staff" not in roles:
        raise TransitionForbidden("The reopening window has passed.", code="ticket.reopen_window_passed")
    if transition.comment_required and not has_comment:
        raise ValidationFailed("This transition requires a comment.", code="ticket.comment_required")
    target = workflow.state(transition.to)
    assert target is not None
    return Move(transition, target)
