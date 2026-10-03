"""Condition evaluator (T018; R3): a deterministic, order-independent evaluation of the closed condition tree.
Every leaf is evaluated (no short-circuit) so the trace is complete; an unknown leaf (provider unavailable,
attribute missing) counts as **false** and is traced as ``unknown`` — nothing is ever granted by a guess."""

import asyncio
from typing import Any

from portalab.capabilities.automations import ConditionRegistry, LeafContext
from portalab.modules.automations.definitions.schema import Node

LEAF_TIMEOUT = 3.0


class Evaluator:
    def __init__(self, conditions: ConditionRegistry) -> None:
        self.conditions = conditions

    async def evaluate(self, node: Node | None, ctx: LeafContext) -> tuple[bool, list[dict[str, Any]]]:
        trace: list[dict[str, Any]] = []
        if node is None:
            return True, trace
        return await self._node(node, ctx, trace), trace

    async def _node(self, node: Node, ctx: LeafContext, trace: list[dict[str, Any]]) -> bool:
        if node.leaf is not None:
            leaf = self.conditions.get(node.leaf)
            result: bool | None
            if leaf is None:
                result = None
            else:
                try:
                    result = await asyncio.wait_for(leaf.evaluate(ctx, node.params), LEAF_TIMEOUT)
                except Exception:
                    result = None
            trace.append({"leaf": node.leaf, "result": "unknown" if result is None else bool(result)})
            return bool(result)
        if node.not_ is not None:
            return not await self._node(node.not_, ctx, trace)
        children = node.all_of if node.all_of is not None else node.any_of or []
        results = [await self._node(child, ctx, trace) for child in children]
        return all(results) if node.all_of is not None else any(results)
