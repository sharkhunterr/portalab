"""Automation action types (contract consumed by Automations 019, F14): owners declare what an automation may
do, with the permission it requires and how a duplicate execution is made harmless."""

from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from portalab.core.authz_port import Principal

ActionRunner = Callable[[Mapping[str, Any], Principal], Awaitable[Mapping[str, Any]]]


Sensitivity = Literal["normal", "sensitive", "destructive"]


@dataclass(frozen=True, slots=True)
class ActionType:
    """``params_schema`` maps each parameter to a type hint; a trailing ``?`` marks it optional unless
    ``required`` lists the mandatory ones. ``sensitivity`` (or the permission's own flags) decides the
    approval gate of 019; ``ai_output_allowed`` lets ``ai.invoke`` text flow into this action's params."""

    key: str
    description: str
    permission: str
    idempotency: str
    run: ActionRunner = field(compare=False)
    owner: str = "core"
    params_schema: Mapping[str, str] = field(default_factory=dict)
    sensitivity: Sensitivity = "normal"
    required: tuple[str, ...] | None = None
    ai_output_allowed: bool = False
    summarize: Callable[[Mapping[str, Any]], str] | None = field(default=None, compare=False)

    def required_params(self) -> tuple[str, ...]:
        if self.required is not None:
            return self.required
        return tuple(k for k, hint in self.params_schema.items() if not hint.rstrip().endswith("?"))


@dataclass(frozen=True, slots=True)
class ActionContext:
    """The running automation step (019): handlers may read it (``current_action``) to propagate
    ``provenance.automation``; events they publish carry ``correlation_id = chain_id`` automatically."""

    automation_id: UUID
    execution_id: UUID
    chain_id: str
    depth: int
    step_id: str
    deadline: datetime | None = None


_CURRENT: ContextVar[ActionContext | None] = ContextVar("portalab_action_context", default=None)


def current_action() -> ActionContext | None:
    return _CURRENT.get()


@contextmanager
def action_context(context: ActionContext) -> Iterator[None]:
    token = _CURRENT.set(context)
    try:
        yield
    finally:
        _CURRENT.reset(token)


class ActionRegistry:
    def __init__(self) -> None:
        self._actions: dict[str, ActionType] = {}

    def register(self, action: ActionType) -> ActionType:
        if not action.idempotency.strip():
            raise ValueError(f"action {action.key!r} must declare its idempotency")
        existing = self._actions.get(action.key)
        if existing is not None and existing.owner != action.owner:
            raise ValueError(f"action {action.key!r} is already registered by {existing.owner}")
        self._actions[action.key] = action
        return action

    def get(self, key: str) -> ActionType | None:
        return self._actions.get(key)

    def all(self) -> list[ActionType]:
        return [self._actions[key] for key in sorted(self._actions)]

    def unregister(self, owner: str) -> int:
        doomed = [key for key, item in self._actions.items() if item.owner == owner]
        for key in doomed:
            del self._actions[key]
        return len(doomed)


default_actions = ActionRegistry()
