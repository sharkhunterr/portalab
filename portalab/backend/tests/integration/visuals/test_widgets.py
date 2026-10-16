"""028 (US6): a pack's widget and widget style through the workflow — the administrator accepts each data
contract the widget asks for before it is published; once live it is on the dashboard (its element served
with its sizes and words), and off it again when its pack is switched off."""

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.visuals import CATALOG_WRITER, INTERFACE_REGISTRY, live_looks
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.modules.visuals.service import VisualPackError, VisualPacks
from portalab.modules.visuals.widgets import PackWidgets
from tests.unit.visuals.support import FakeInterfaces, FakeWriter

EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "visual-packs" / "widgets"
ADMIN = Principal(user_id=uuid4(), channel="user")
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _no_live_looks() -> Iterator[None]:
    yield
    live_looks.replace({})


async def test_contracts_are_accepted_at_review_then_the_widget_is_on_the_dashboard(
    database: Database, tmp_path: Path
) -> None:
    registry = new_registry()
    writer = FakeWriter()
    registry.provide(CATALOG_WRITER, writer, instance_ref="test", owner="test")
    registry.provide(INTERFACE_REGISTRY, FakeInterfaces(), instance_ref="test", owner="test")
    dashboard = WidgetRegistry()
    service = VisualPacks(database, tmp_path, registry, widgets=PackWidgets(dashboard))
    shutil.copytree(EXAMPLE, tmp_path / "inbox" / "vigie")
    await service.scan(ADMIN)
    version = json.loads((EXAMPLE / "pack.json").read_text())["version"]
    # scripts and their contracts: each said out loud
    contracts = ["me.progression", "me.statistics", "widget:media.recently_added", "me.watching"]
    with pytest.raises(VisualPackError):
        await service.publish(ADMIN, "vigie", version, confirmations={"scripts": True})
    with pytest.raises(VisualPackError):
        await service.publish(
            ADMIN, "vigie", version, confirmations={"scripts": True, "contracts": contracts[:2]}
        )
    # the administrator changes what the pack proposed: the silver dial offered too, the swell dearer
    economy = {"widget_option_vigie_cap_silver": {"sold": False}, "widget_option_houle": {"price": 400}}
    result = await service.publish(
        ADMIN, "vigie", version, economy, confirmations={"scripts": True, "contracts": contracts}
    )
    assert result["products"]["widget_option_vigie_cap_night"] == "given"  # the pack offers it
    assert result["products"]["widget_option_vigie_cap_silver"] == "given"
    assert "widget_option_vigie_cap_silver" not in writer.products
    assert writer.products["widget_vigie_cap"]["payload"] == {"widget": "pack.vigie-cap"}
    assert writer.products["widget_style_vigie"]["payload"] == {"option": "*:_skin=vigie"}
    assert writer.products["widget_option_houle"]["payload"] == {"option": "*:_options=houle"}
    assert writer.products["widget_option_houle"]["price"] == 400
    assert writer.products["widget_option_journal"]["payload"] == {
        "option": "media.recently_added:_options=journal"
    }
    assert {writer.products[k]["type"] for k in writer.products} == {"widget", "widget_option"}
    await service.refresh(force=True)
    placed = dashboard.get("pack.vigie-cap")
    assert placed is not None and placed.definition.size.default.w == 4
    assert placed.definition.config_defaults == {"dial": "brass"}  # its own setting
    assert placed.definition.size.min.h == 1 and placed.definition.size.min.w == 2  # a line, a column
    served = next(e for e in (await service.active())["elements"] if e["type"] == "widget")
    assert served["contracts"] == ["me.progression", "me.statistics", "widget:media.recently_added"]
    assert served["widget"]["options"][0]["key"] == "dial"
    journal = next(e for e in (await service.active())["elements"] if e.get("look") == "journal")
    assert journal["widget"] == {"for": "media.recently_added", "place": "replace"}
    assert journal["contracts"] == ["me.watching"]
    assert served["widget"]["sizes"][0] == {"w": 4, "h": 2} and served["widget"]["empty"]["fr"]
    # switched off: off the dashboard (members' placed instances stay with the dashboard)
    await service.set_state(ADMIN, "vigie", False)
    await service.refresh(force=True)
    assert dashboard.get("pack.vigie-cap") is None
