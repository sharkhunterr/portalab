"""028 (US2, FR-005…FR-008a, SC-001): Portalab's own packs synchronised — the first time adopting what exists
(nothing of the existing products touched), then following each release (a new pack arrives switched off, a
changed one keeps the administrator's choices and says what changed); idempotent."""

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.visuals import CATALOG_WRITER, INTERFACE_REGISTRY, live_looks
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.modules.visuals.builtin import BuiltinSync
from portalab.modules.visuals.models import Pack
from portalab.modules.visuals.service import VisualPacks
from tests.unit.visuals.support import FakeInterfaces, FakeWriter

ROOT = Path(__file__).resolve().parents[4] / "packs" / "builtin"
ADMIN = Principal(user_id=uuid4(), channel="user")
pytestmark = pytest.mark.integration


def _copy(target: Path, *packs: str) -> Path:
    for pack in packs:
        shutil.copytree(ROOT / pack, target / pack)
    return target


def _service(database: Database, root: Path) -> tuple[VisualPacks, FakeWriter, FakeInterfaces]:
    registry = new_registry()
    writer, interfaces = FakeWriter(), FakeInterfaces()
    registry.provide(CATALOG_WRITER, writer, instance_ref="test", owner="test")
    registry.provide(INTERFACE_REGISTRY, interfaces, instance_ref="test", owner="test")
    return VisualPacks(database, root, registry), writer, interfaces


async def _states(database: Database) -> dict[str, str]:
    async with database.session() as session:
        return {p.id: p.state for p in (await session.execute(select(Pack))).scalars()}


async def test_the_first_synchronisation_adopts_what_exists(database: Database, tmp_path: Path) -> None:
    packs = _copy(tmp_path / "builtin", "portalab-socle", "portalab-academy", "portalab-alien")
    service, writer, _ = _service(database, tmp_path / "data")
    # a portal that already sells the academy universe (its products exist, an administrator set a price)
    academy = [
        json.loads(p.read_text()) for p in (packs / "portalab-academy").glob("elements/*/element.json")
    ]
    for element in academy:
        writer.products[element["product"]] = {"key": element["product"], "price": 1}
    report = await BuiltinSync(service, packs).run(ADMIN)
    assert report.first and sorted(report.created) == ["portalab-academy", "portalab-alien", "portalab-socle"]
    assert report.enabled == ["portalab-academy"] and report.failed == {}
    assert await _states(database) == {
        "portalab-academy": "enabled",
        "portalab-alien": "disabled",  # nothing of it exists: a fresh universe stays off
        "portalab-socle": "enabled",
    }
    # nothing of the existing products is touched: published with keep_existing, never put back on sale
    for element in academy:
        product = writer.products[element["product"]]
        assert product.get("keep_existing") is True and product.get("resume") is False
    # the looks of the live built-in packs are claimed; those drawn by their pack (B2: their stylesheets,
    # their GPU fragments, an ambience's layers) reach the interface like an imported pack's, the others
    # are still drawn by its code (never sent)
    await service.refresh(force=True)
    active = await service.active()
    own = [e for e in active["elements"] if e.get("pack", "").startswith("portalab-")]
    drawn = {"css": "css", "glsl": "file", "renderer": "params", "data": "palette", "theme": "file"}
    assert own and all(e.get(drawn.get(e["kind"], "-")) for e in own)
    assert "portalab-alien" not in {e.get("pack") for e in active["elements"]}
    assert active["withheld"]  # the alien universe's looks: its wearers see the defaults
    assert "sidebar" in live_looks.of("navigation")  # the socle's built-in navigations
    # idempotent
    again = await BuiltinSync(service, packs).run(ADMIN)
    assert again.unchanged == 3 and not again.created and not again.updated
    # #253: the data folder emptied under a registry that still has them — their files kept again, so an
    # interface they bring can be switched on
    shutil.rmtree(service.store.root / "store")
    repaired = await BuiltinSync(service, packs).run(ADMIN)
    assert repaired.unchanged == 3 and not repaired.created
    for pack in ("portalab-socle", "portalab-academy", "portalab-alien"):
        assert (service.store.root / "store" / pack).is_dir(), pack
    await service.set_state(ADMIN, "portalab-alien", True)


async def test_a_release_updates_keeps_choices_and_a_new_pack_arrives_off(
    database: Database, tmp_path: Path
) -> None:
    packs = _copy(tmp_path / "builtin", "portalab-socle", "portalab-alien")
    service, _, _ = _service(database, tmp_path / "data")
    await BuiltinSync(service, packs).run(ADMIN)
    await service.set_state(ADMIN, "portalab-alien", True)  # the administrator switches it on
    # the next release: alien loses an element, a universe is new
    meta = json.loads((packs / "portalab-alien" / "pack.json").read_text())
    (packs / "portalab-alien" / "pack.json").write_text(json.dumps({**meta, "version": "1.1.0"}))
    dropped = min((packs / "portalab-alien" / "elements").iterdir())
    shutil.rmtree(dropped)
    shutil.copytree(ROOT / "portalab-academy", packs / "portalab-academy")
    report = await BuiltinSync(service, packs).run(ADMIN)
    assert (
        report.updated == ["portalab-alien"] and report.created == ["portalab-academy"] and not report.first
    )
    states = await _states(database)
    assert states["portalab-alien"] == "enabled" and states["portalab-academy"] == "disabled"
    detail = await service.detail("portalab-alien", "1.1.0")
    assert detail["changes"]["removed"] and detail["step"] == "published"


async def test_the_socle_is_always_on(database: Database, tmp_path: Path) -> None:
    packs = _copy(tmp_path / "builtin", "portalab-socle")
    service, _, _ = _service(database, tmp_path / "data")
    await BuiltinSync(service, packs).run(ADMIN)
    from portalab.core.errors import Conflict

    with pytest.raises(Conflict):
        await service.set_state(ADMIN, "portalab-socle", False)
    with pytest.raises(Conflict):
        await service.remove(ADMIN, "portalab-socle")
