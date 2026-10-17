"""028 (US2, SC-001): Portalab's own catalog delivered as packs — every product, look and interface that
existed is held by exactly one element of one built-in pack, and every built-in pack passes the analysis."""

import json
from collections import Counter
from pathlib import Path

import pytest

from portalab.modules.visuals.analysis import analyse
from portalab.modules.visuals.manifest import LOOK_FIELD, parse_element, parse_pack
from portalab.modules.visuals.store import read_folder
from tests.unit.visuals.support import FakeInterfaces

ROOT = Path(__file__).resolve().parents[4]
BUILTIN = ROOT / "packs" / "builtin"
BEFORE = json.loads((ROOT / "tests" / "fixtures" / "builtin-looks-before.json").read_text(encoding="utf-8"))


def _elements() -> list[tuple[str, dict[str, object]]]:
    out = []
    for path in sorted(BUILTIN.glob("*/elements/*/element.json")):
        out.append((path.parents[2].name, json.loads(path.read_text(encoding="utf-8"))))
    return out


def test_every_product_is_held_by_exactly_one_element() -> None:
    held = Counter(str(e["product"]) for _, e in _elements() if e.get("product"))
    assert {k for k, n in held.items() if n > 1} == set()
    assert set(BEFORE["products"]) == set(held)


def test_every_look_and_interface_is_still_there() -> None:
    found: dict[str, set[str]] = {}
    for _, element in _elements():
        kind = str(element["type"])
        payload: dict[str, object] = element.get("payload") or {}  # type: ignore[assignment]
        look = element.get("look") or payload.get(LOOK_FIELD.get(kind, ""))
        if look:
            found.setdefault(kind, set()).add(str(look))
    for kind, looks in BEFORE["looks"].items():
        missing = set(looks) - found.get(kind, set())
        if kind in ("badge", "title"):
            missing -= found.get("badge", set()) | found.get("title", set())  # the styles both wear
        assert missing == set(), (kind, sorted(missing)[:10])
    assert set(BEFORE["interfaces"]) <= found["theme"]


def test_the_socle_is_one_and_always_there() -> None:
    socle = parse_pack((BUILTIN / "portalab-socle" / "pack.json").read_text())
    assert socle.id == "portalab-socle"
    free = [e for pack, e in _elements() if pack == "portalab-socle"]
    assert free and all(e.get("free") for e in free)


@pytest.mark.parametrize("folder", sorted(p.name for p in BUILTIN.iterdir()))
def test_every_builtin_pack_passes_the_analysis(folder: str) -> None:
    report = analyse(read_folder(BUILTIN / folder), interfaces=FakeInterfaces(), builtin=True)
    blocking = [i for i in report["items"] if i["level"] == "blocking"]
    assert blocking == [], blocking[:3]
    assert folder.startswith("portalab-")


def test_a_builtin_renderer_is_reserved_to_portalab() -> None:
    raw = {"type": "avatar_frame", "look": "x", "names": {"en": "X"}}
    element = parse_element(json.dumps({**raw, "render": {"kind": "renderer", "renderer": "builtin"}}), "x")
    assert element.render.renderer == "builtin"
    files = {
        "pack.json": json.dumps(
            {"format": 1, "id": "copy", "version": "1.0.0", "names": {"en": "C"}}
        ).encode(),
        "elements/x/element.json": element.model_dump_json().encode(),
    }
    from portalab.modules.visuals.store import Files

    codes = {i["code"] for i in analyse(Files(files))["items"] if i["level"] == "blocking"}
    assert "render.builtin_reserved" in codes


def test_every_builtin_pack_s_version_follows_its_content() -> None:
    """028: Portalab's packs are edited by hand — a release synchronises an edited pack only under a new
    version (``scripts/stamp_builtin_packs.py`` stamps them)."""
    import importlib.util

    script = Path(__file__).resolve().parents[3] / "scripts" / "stamp_builtin_packs.py"
    spec = importlib.util.spec_from_file_location("stamp_builtin_packs", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.stamp(module.ROOT, check=True) == []
