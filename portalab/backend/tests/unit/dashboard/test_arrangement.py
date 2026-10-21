"""027 T066 — the server's arrangement engine produces exactly the expected results of the cases shared with
the editor (``tests/fixtures/dashboard-arrangements.json``, also read by ``engine.ts``)."""

import json
from pathlib import Path
from typing import Any

import pytest

from portalab.modules.dashboard.arrangement import (
    Item,
    Size,
    autofit,
    compact,
    derive,
    first_free,
    flow,
    move,
    normalize,
    reading_order,
    resize,
)

FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "dashboard-arrangements.json"
CASES: list[dict[str, Any]] = json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]


def _item(raw: dict[str, Any]) -> Item:
    size = lambda key: Size(raw[key]["w"], raw[key]["h"]) if key in raw else None  # noqa: E731
    return Item(
        raw["id"], raw["x"], raw["y"], raw["w"], raw["h"], size("min"), size("max"), raw.get("locked", False)
    )


def _strip(items: list[Item]) -> list[dict[str, Any]]:
    return [{"id": i.id, "x": i.x, "y": i.y, "w": i.w, "h": i.h} for i in items]


def _run(case: dict[str, Any]) -> Any:
    items = [_item(raw) for raw in case["items"]]
    match case["op"]:
        case "compact":
            return _strip(compact(items))
        case "move":
            return _strip(move(items, case["id"], case["to"]["x"], case["to"]["y"]))
        case "resize":
            return _strip(resize(items, case["id"], case["size"]["w"], case["size"]["h"]))
        case "firstFree":
            x, y = first_free(items, case["size"]["w"], case["size"]["h"])
            return {"x": x, "y": y}
        case "normalize":
            return _strip(normalize(items))
        case "autofit":
            return _strip(autofit(items))
        case "flow":
            return _strip(flow(items))
        case "derive":
            return _strip(derive(items, case["columns"]))
        case "readingOrder":
            return [i.id for i in reading_order(items)]
    raise AssertionError(case["op"])


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_shared_case(case: dict[str, Any]) -> None:
    assert _run(case) == case["expected"]


def test_flow_beside_pinned_widgets() -> None:
    """Issue 186: a starter flows beside the pinned widgets — not under them while their row has room."""
    pinned = [Item("incidents", 0, 0, 3, 1, locked=True), Item("campaign", 3, 0, 3, 1, locked=True)]
    others = [Item(key, 0, 0, w, h) for key, w, h in (("level", 3, 1), ("goals", 3, 1), ("hello", 12, 1))]
    placed = {i.id: (i.x, i.y) for i in normalize([*pinned, *flow(others, around=pinned)])}
    assert placed == {
        "incidents": (0, 0),
        "campaign": (3, 0),
        "level": (6, 0),
        "goals": (9, 0),
        "hello": (0, 1),
    }
    full_row = [Item("wide", 0, 0, 12, 1, locked=True)]
    assert [(i.x, i.y) for i in flow(others[:1], around=full_row)] == [(0, 1)]
