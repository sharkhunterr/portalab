"""Automation contracts (spec 019, contracts/automations-contracts.md).

* **Actions** are owned by domains: ``ActionType`` / ``ActionRegistry`` (``capabilities.automation_actions``)
  with params, permission, sensitivity and idempotency; the engine only orchestrates. A running step is
  visible to handlers through ``current_action()``.
* **Condition leaves** form a closed catalog (``ConditionRegistry``): only core modules add leaves; plugins
  may contribute event *attributes*, never operators.
* **Triggers** are the event types flagged ``automatable`` in the 007 registry, plus bounded schedules.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from portalab.capabilities.automation_actions import (
    ActionContext,
    ActionRegistry,
    ActionType,
    action_context,
    current_action,
    default_actions,
)
from portalab.capabilities.events import Envelope
from portalab.core.authz_port import Principal


@dataclass(frozen=True, slots=True)
class LeafContext:
    principal: Principal  # the automation identity (acting for its author)
    at: datetime
    event: Envelope | None = None
    subject_user: UUID | None = None  # the trigger's actor or user subject


LeafEvaluator = Callable[[LeafContext, Mapping[str, Any]], Awaitable[bool | None]]  # None: unknown


@dataclass(frozen=True, slots=True)
class ConditionLeaf:
    key: str
    description: str
    evaluate: LeafEvaluator = field(compare=False)
    params_schema: Mapping[str, str] = field(default_factory=dict)
    owner: str = "core"


class ConditionRegistry:
    def __init__(self) -> None:
        self._leaves: dict[str, ConditionLeaf] = {}

    def register(self, leaf: ConditionLeaf) -> ConditionLeaf:
        if leaf.owner.startswith("plugin:"):
            raise ValueError("plugins contribute event attributes, not condition operators")
        existing = self._leaves.get(leaf.key)
        if existing is not None and existing.owner != leaf.owner:
            raise ValueError(f"condition {leaf.key!r} belongs to {existing.owner}")
        self._leaves[leaf.key] = leaf
        return leaf

    def get(self, key: str) -> ConditionLeaf | None:
        return self._leaves.get(key)

    def all(self) -> list[ConditionLeaf]:
        return [self._leaves[k] for k in sorted(self._leaves)]

    def unregister(self, owner: str) -> int:
        doomed = [k for k, leaf in self._leaves.items() if leaf.owner == owner]
        for key in doomed:
            del self._leaves[key]
        return len(doomed)


default_conditions = ConditionRegistry()


def register_action_type(action: ActionType, registry: ActionRegistry = default_actions) -> ActionType:
    return registry.register(action)


def register_condition_leaf(
    leaf: ConditionLeaf, registry: ConditionRegistry = default_conditions
) -> ConditionLeaf:
    return registry.register(leaf)


__all__ = [
    "ActionContext",
    "ActionRegistry",
    "ActionType",
    "ConditionLeaf",
    "ConditionRegistry",
    "LeafContext",
    "action_context",
    "current_action",
    "default_actions",
    "default_conditions",
    "register_action_type",
    "register_condition_leaf",
]
