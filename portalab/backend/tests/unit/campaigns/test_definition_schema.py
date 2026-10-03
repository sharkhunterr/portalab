"""014 T004 — the campaign definition is closed: unknown fields/operators rejected, bounded sizes, modifier
factor range, recurrence parameters, no expressions; theme keys must exist (checked against 022's catalog)."""

import copy
from typing import Any

import pytest

from portalab.core.errors import ValidationFailed
from portalab.modules.campaigns.definitions.schema import parse_definition
from tests.integration.campaigns.conftest import HALLOWEEN


def variant(**changes: Any) -> dict[str, Any]:
    raw = copy.deepcopy(HALLOWEEN)
    for path, value in changes.items():
        target = raw
        *parents, leaf = path.split("__")
        for part in parents:
            target = target[int(part)] if part.isdigit() else target[part]
        target[leaf] = value
    return raw


def test_valid_definition() -> None:
    definition = parse_definition(HALLOWEEN)
    assert definition.name("fr") == "Halloween" and definition.schedule.recurrence.kind == "yearly"
    assert [m.id for m in definition.modifiers] == ["horror_xp", "horror_coins", "title_xp"]


@pytest.mark.parametrize(
    "raw",
    [
        variant(script="return 1"),
        variant(modifiers__0__when={"expression": "genre == 'horror'"}),
        variant(modifiers__0__when={"genre": ["horror"], "op": "regex"}),
        variant(modifiers__0__factor=0),
        variant(modifiers__0__factor=11),
        variant(modifiers__0__value="gems"),
        variant(modifiers__1__id="horror_xp"),
        variant(schedule__recurrence={"kind": "cron", "every": 1}),
        variant(schedule__recurrence={"kind": "custom", "every": 0}),
        variant(schedule__end_at="2026-10-19T00:00:00"),
        variant(schedule={"start_at": "2026-10-20T00:00:00"}),
        variant(timezone="Mars/Olympus"),
        variant(names={}),
        variant(names={"en": "x" * 121}),
        variant(modifiers=[{"id": f"m{i}", "value": "xp", "factor": 2} for i in range(21)]),
        variant(
            achievements=[
                {
                    "key": "deep",
                    "definition": {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": 1}}}}}}}}},
                }
            ]
        ),
        variant(achievements=[{"key": "big", "definition": {"label": "x" * 20_000}}]),
    ],
)
def test_rejections(raw: dict[str, Any]) -> None:
    with pytest.raises(ValidationFailed) as error:
        parse_definition(raw)
    assert error.value.code == "campaign.invalid_definition" and error.value.extensions["errors"]


@pytest.mark.integration
async def test_theme_must_exist(cm) -> None:  # type: ignore[no-untyped-def]
    from portalab.capabilities.themes import CAPABILITY

    class Catalog:
        async def allowed_keys(self) -> frozenset[str]:
            return frozenset({"pumpkin"})

    cm.ev.full.identity.capabilities.provide(CAPABILITY, Catalog(), instance_ref="t", owner="module:ui")
    with pytest.raises(ValidationFailed):
        await cm.campaigns.definitions.validate({**HALLOWEEN, "theme": {"theme_key": "neon"}})
    assert (await cm.campaigns.definitions.validate({**HALLOWEEN, "theme": {"theme_key": "pumpkin"}})).theme
