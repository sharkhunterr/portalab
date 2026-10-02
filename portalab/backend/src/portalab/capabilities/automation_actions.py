"""Automation action types (contract consumed by Automations 019, F14): owners declare what an automation may
do, with the permission it requires and how a duplicate execution is made harmless."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from portalab.core.authz_port import Principal

ActionRunner = Callable[[Mapping[str, Any], Principal], Awaitable[Mapping[str, Any]]]


@dataclass(frozen=True, slots=True)
class ActionType:
    key: str
    description: str
    permission: str
    idempotency: str
    run: ActionRunner = field(compare=False)
    owner: str = "core"
    params_schema: Mapping[str, str] = field(default_factory=dict)


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
