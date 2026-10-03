"""019 T017 — condition leaves (true / false / unknown ⇒ false with a trace), ``all_of / any_of / not``
evaluated order-independently (shuffle property), depth limit enforced by the schema."""

import random
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from portalab.capabilities.automations import ConditionLeaf, ConditionRegistry, LeafContext
from portalab.core.authz_port import Principal
from portalab.modules.automations.definitions.schema import Node
from portalab.modules.automations.evaluator.evaluator import Evaluator

AT = datetime(2026, 10, 7, 21, 30, tzinfo=UTC)


def registry() -> ConditionRegistry:
    leaves = ConditionRegistry()

    async def fixed(ctx: LeafContext, params: Mapping[str, Any]) -> bool | None:
        value = params.get("value")
        if value == "boom":
            raise RuntimeError("provider down")
        return None if value is None else bool(value)

    leaves.register(ConditionLeaf("fixed", "fixed answer", fixed, {"value": "bool?"}))
    return leaves


def leaf(value: Any) -> dict[str, Any]:
    return {"leaf": "fixed", "params": {"value": value}}


CTX = LeafContext(Principal(channel="automation", acting_for=uuid4()), AT)


@pytest.mark.parametrize(
    ("tree", "expected"),
    [
        (leaf(True), True),
        (leaf(False), False),
        (leaf(None), False),
        (leaf("boom"), False),
        ({"all_of": [leaf(True), leaf(True)]}, True),
        ({"all_of": [leaf(True), leaf(None)]}, False),
        ({"any_of": [leaf(False), leaf(True)]}, True),
        ({"not": leaf(False)}, True),
        ({"not": leaf(None)}, True),
        ({"any_of": [{"all_of": [leaf(True), {"not": leaf(True)}]}, leaf(True)]}, True),
    ],
)
async def test_trees(tree: dict[str, Any], expected: bool) -> None:
    result, trace = await Evaluator(registry()).evaluate(Node.model_validate(tree), CTX)
    assert result is expected
    assert all(item["result"] in (True, False, "unknown") for item in trace)


async def test_order_independence() -> None:
    rng = random.Random(19)  # noqa: S311 — deterministic shuffles
    evaluator = Evaluator(registry())
    values = [True, False, None, True, False]
    for _ in range(25):
        rng.shuffle(values)
        for kind in ("all_of", "any_of"):
            tree = Node.model_validate({kind: [leaf(v) for v in values]})
            result, trace = await evaluator.evaluate(tree, CTX)
            assert result is (
                all(bool(v) for v in values) if kind == "all_of" else any(bool(v) for v in values)
            )
            assert len(trace) == len(values)  # every leaf is evaluated and traced


@pytest.mark.integration
async def test_builtin_leaves(au) -> None:  # type: ignore[no-untyped-def]
    from portalab.capabilities.events import Envelope

    leaves = au.conditions
    user = au.people["ursula"]
    event = Envelope(
        uuid4(),
        0,
        "test.happened",
        1,
        AT,
        AT,
        "t",
        None,
        user,
        "user",
        None,
        None,
        {"value": 5, "label": "Hallowéen"},
        {},
        None,
    )
    ctx = LeafContext(Principal(channel="automation", acting_for=au.people["boss"]), AT, event, user)

    async def check(key: str, params: dict[str, Any]) -> bool | None:
        found = leaves.get(key)
        assert found is not None
        return await found.evaluate(ctx, params)

    assert await check("user_is", {"users": [str(user)]}) is True
    assert await check("event_field", {"field": "value", "op": "gte", "value": 5}) is True
    assert await check("event_field", {"field": "label", "op": "contains", "value": "halloween"}) is True
    assert await check("event_field", {"field": "missing", "op": "eq", "value": 1}) is None
    assert await check("time_window", {"start": "21:00", "end": "23:00", "timezone": "UTC"}) is True
    assert (
        await check("time_window", {"start": "22:00", "end": "06:00", "timezone": "Europe/Paris"}) is True
    )  # 23:30 local
    assert (
        await check("time_window", {"start": "09:00", "end": "17:00", "timezone": "UTC", "weekdays": [0]})
        is False
    )
    assert await check("permission_held", {"permission": "users.manage"}) is False
    assert await check("campaign_active", {"campaign": "x"}) is None  # no campaigns provider: unknown
    assert await check("level_at_least", {"level": 1}) is None
    assert await check("service_state_in", {"service_id": "s1", "states": ["operational"]}) is None
    assert await check("media_kind", {"kinds": ["movie"]}) is None
