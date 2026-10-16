"""028 (US6): packs' widgets, self-contained — the data contracts they may ask for (the catalog's and every
dashboard widget's data), the analysis of their elements, their place on the dashboard (registered while
their pack is live), the contracts a member may not read, the frame's look a pack brings (``_skin``), the
options it brings (add-ons worn through ``_options``, values of its own widget's settings), and what the
administrator gives everyone rather than sells."""

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from portalab.capabilities.dashboard import RegisteredWidget, WidgetDefinition, WidgetRegistry
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.visuals import WIDGET_CONTRACTS, contract_known
from portalab.core.authz_port import Principal, ResourceRef
from portalab.modules.dashboard.gateway.gateway import WidgetGateway, config_errors, worn
from portalab.modules.visuals.analysis import analyse
from portalab.modules.visuals.api.routes import contracts
from portalab.modules.visuals.service import VisualPacks
from portalab.modules.visuals.store import read_folder
from portalab.modules.visuals.widgets import PackWidgetProvider, PackWidgets, pack_widget_key, size_limits
from tests.unit.visuals.support import files_of, tiny_pack

EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "visual-packs" / "widgets"
MEMBER = Principal(user_id=uuid4(), channel="user")


class Permissions:
    def __init__(self, *granted: str) -> None:
        self.granted = set(granted)

    async def is_allowed(
        self, principal: Principal, permission: str, resource: ResourceRef | None = None
    ) -> bool:
        return permission in self.granted


def widget(**change: Any) -> dict[str, bytes | str]:
    element: dict[str, Any] = {
        "type": "widget",
        "look": "cap",
        "render": {"kind": "js", "file": "w.js"},
        "contracts": ["me.progression"],
        "payload": {"sizes": [{"w": 4, "h": 2}], "refresh_s": 60},
        **change,
    }
    files = tiny_pack(**element)
    files["elements/frame/w.js"] = "export default function mount(root, api) { return () => {}; }"
    return files


def codes(files: dict[str, bytes | str], level: str = "blocking") -> set[str]:
    return {i["code"] for i in analyse(files_of(files))["items"] if i["level"] == level}


def test_the_portal_describes_every_contract_it_offers() -> None:
    assert set(WIDGET_CONTRACTS) == {"me.progression", "me.watching", "media.recently_added", "me.statistics"}
    for contract in WIDGET_CONTRACTS.values():
        out = contract.out()
        assert out["permission"] and out["refresh_s"] >= 30 and out["fields"]
        assert out["descriptions"]["fr"] and out["descriptions"]["en"]


async def test_the_administrators_read_the_contracts() -> None:
    registry = WidgetRegistry()
    registry.register(
        WidgetDefinition(
            key="media.stats", owner="module:media", title_key="t", required_permission="media.read"
        ),
        PackWidgetProvider({"pack": "p", "sha": "s", "look": "l"}, None),
    )
    packs = VisualPacks.__new__(VisualPacks)
    packs.widgets = PackWidgets(registry)
    listed = await contracts(MEMBER, packs)
    assert [c["key"] for c in listed["contracts"]] == list(WIDGET_CONTRACTS)
    assert listed["widgets"] == [
        {"key": "widget:media.stats", "widget": "media.stats", "title_key": "t", "permission": "media.read"}
    ]


def test_every_widgets_data_is_a_contract_but_a_packs_own() -> None:
    assert contract_known("widget:media.recently_added") and contract_known("widget:health.host")
    assert not contract_known("widget:pack.vigie-cap")  # a pack's widget holds no data of its own
    assert not contract_known("widget:../admin") and not contract_known("widget:nodot")
    assert not contract_known("me.password")


def test_the_example_widget_pack_is_publishable() -> None:
    report = analyse(read_folder(EXAMPLE))
    assert report["summary"]["publishable"] and report["summary"]["script"]
    assert [i for i in report["items"] if i["level"] != "info"] == []
    cap = next(e for e in report["elements"] if e["type"] == "widget")
    assert cap["contracts"] == ["me.progression", "me.statistics", "widget:media.recently_added"]
    # a widget, its look, its own setting's values (one offered to everyone), add-ons for any widget or one
    kinds = sorted((e["type"], e["kind"]) for e in report["elements"])
    assert kinds == [
        ("widget", "js"),
        ("widget_option", "css"),
        ("widget_option", "data"),
        ("widget_option", "data"),
        ("widget_option", "js"),
        ("widget_option", "js"),
        ("widget_style", "css"),
    ]
    assert "economy.given" in {i["code"] for i in report["items"]}


def test_a_widget_asks_only_for_the_portals_contracts() -> None:
    assert codes(widget()) == set()
    assert "widget.unknown_contract" in codes(widget(contracts=["me.password"]))
    assert codes(widget(contracts=["widget:services.status", "me.watching"])) == set()
    assert "widget.no_contract" in codes(widget(contracts=[]), "info")
    assert "widget.contract_twice" in codes(widget(contracts=["me.progression"] * 2), "warning")
    # only a widget is handed data
    files = tiny_pack(contracts=["me.progression"])
    assert "widget.contracts_elsewhere" in codes(files)


@pytest.mark.parametrize(
    "payload",
    [
        {"sizes": [{"w": 13, "h": 2}]},
        {"sizes": [{"w": 4, "h": 0}]},
        {"sizes": []},
        {"sizes": "big"},
        {"refresh_s": 5},
        {"empty": {"fr": "x" * 300}},
    ],
)
def test_a_widgets_sizes_pace_and_words_are_bounded(payload: dict[str, Any]) -> None:
    assert codes(widget(payload=payload)) & {"widget.size", "widget.refresh", "widget.empty"}


def test_its_sizes_bound_how_far_it_may_be_resized() -> None:
    limits = size_limits([{"w": 4, "h": 2}, {"w": 3, "h": 2}, {"w": 6, "h": 3}])
    assert (limits.default.w, limits.default.h) == (4, 2)
    assert (limits.min.w, limits.min.h, limits.max.w, limits.max.h) == (3, 2, 6, 3)
    fallback = size_limits(None)
    assert (fallback.default.w, fallback.default.h) == (4, 2)


def test_a_live_widget_is_on_the_dashboard_until_its_pack_goes_off() -> None:
    registry = WidgetRegistry()
    widgets = PackWidgets(registry)
    entry = {"pack": "vigie", "sha": "a" * 16, "look": "vigie-cap", "contracts": ["me.progression"]}
    widgets.sync([{**entry, "payload": {"sizes": [{"w": 3, "h": 2}], "refresh_s": 90}}])
    registered = registry.get(pack_widget_key("vigie-cap"))
    assert registered is not None
    definition = registered.definition
    assert (
        definition.component_id == "visuals.pack" and definition.title_key == "dashboard:packWidget.vigie-cap"
    )
    assert definition.refresh.mode == "interval" and definition.refresh.interval_s == 90
    widgets.sync([])
    assert registry.get(pack_widget_key("vigie-cap")) is None


def test_a_key_another_module_holds_stays_its_own() -> None:
    registry = WidgetRegistry()
    registry.register(
        WidgetDefinition(key="pack.clock", owner="module:other", title_key="x", required_permission="p"),
        PackWidgetProvider({"pack": "p", "sha": "s", "look": "clock"}, None),
    )
    PackWidgets(registry).sync([{"pack": "p", "sha": "s", "look": "clock", "contracts": []}])
    held = registry.get("pack.clock")
    assert isinstance(held, RegisteredWidget) and held.owner == "module:other"


async def test_the_member_is_told_which_contracts_they_may_not_read() -> None:
    entry = {
        "pack": "vigie",
        "sha": "a" * 16,
        "look": "cap",
        "contracts": ["me.progression", "media.recently_added", "x.y"],
    }
    payload = await PackWidgetProvider(entry, Permissions("users.self.manage")).load(
        MEMBER, {}, LocaleContext()
    )
    assert payload.state == "available" and payload.data is not None
    # an unknown contract is never passed on; one this member may not read is « forbidden »
    assert payload.data["contracts"] == ["me.progression", "media.recently_added"]
    assert payload.data["forbidden"] == ["media.recently_added"]
    # no authorizer: nothing is readable (fail closed)
    closed = await PackWidgetProvider(entry, None).load(MEMBER, {}, LocaleContext())
    assert closed.data is not None and closed.data["forbidden"] == ["me.progression", "media.recently_added"]
    # a widget's data: that widget's permission (a widget that is not there: forbidden)
    registry = WidgetRegistry()
    registry.register(
        WidgetDefinition(
            key="services.status", owner="module:s", title_key="t", required_permission="services.read"
        ),
        PackWidgetProvider({"pack": "p", "sha": "s", "look": "l"}, None),
    )
    entry["contracts"] = ["widget:services.status", "widget:downloads.queue"]
    allowed = await PackWidgetProvider(entry, Permissions("services.read"), registry).load(
        MEMBER, {}, LocaleContext()
    )
    assert allowed.data is not None and allowed.data["forbidden"] == ["widget:downloads.queue"]


def option(**change: Any) -> dict[str, bytes | str]:
    """A pack with a widget (its own setting « dial ») and one option."""
    files = widget(
        payload={
            "sizes": [{"w": 4, "h": 2}],
            "options": [
                {
                    "key": "dial",
                    "names": {"fr": "Cadran", "en": "Dial"},
                    "default": "brass",
                    "values": [{"value": "brass"}, {"value": "night", "names": {"en": "Night"}}],
                }
            ],
        }
    )
    files["elements/opt/element.json"] = json.dumps(
        {"type": "widget_option", "names": {"fr": "O", "en": "O"}, "economy": {"price": 300}, **change}
    )
    files["elements/opt/o.css"] = (
        '[data-widget-option~="swell"] .widget-rows { animation: swell 3s infinite; }'
    )
    files["elements/opt/o.js"] = "export default function mount(root, api) { return () => {}; }"
    return files


def test_an_option_is_a_value_of_its_widgets_setting_or_an_add_on() -> None:
    value = {"render": {"kind": "data"}, "payload": {"widget": "cap", "setting": "dial", "value": "night"}}
    assert codes(option(**value)) == set()
    assert "widget.option_default" in codes(
        option(**{**value, "payload": {**value["payload"], "value": "brass"}}), "warning"
    )
    assert "widget.option_unknown" in codes(
        option(**{**value, "payload": {**value["payload"], "value": "gold"}})
    )
    # an add-on: any widget's (Portalab's, this pack's, every one), a stylesheet or a script with its place
    css = {"look": "swell", "render": {"kind": "css", "css": ["o.css"]}}
    for target in ("*", "media.recently_added", "cap", "pack.cap"):
        assert codes(option(**css, payload={"widget": target})) == set(), target
    assert "widget.option_target" in codes(option(**css, payload={"widget": "other"}))
    script = {"look": "sonar", "render": {"kind": "js", "file": "o.js"}, "payload": {"widget": "*"}}
    assert "widget.option_place" in codes(option(**script))
    placed = {
        **script,
        "render": {**script["render"], "place": "overlay"},
        "contracts": ["widget:services.status"],
    }
    assert codes(option(**placed)) == set()
    assert "widget.unknown_contract" in codes(option(**{**placed, "contracts": ["me.secrets"]}))


def test_only_widgets_their_looks_and_options_may_be_given_to_everyone() -> None:
    assert codes(widget(economy={"price": 800, "rarity": "epic", "sold": False})) == set()
    assert "economy.not_giveable" in codes(tiny_pack(economy={"price": 400, "rarity": "rare", "sold": False}))


def test_the_shop_sells_a_widget_and_a_frames_look() -> None:
    style = {"type": "widget_style", "look": "vigie", "product": "widget_style_vigie", "payload": {}}
    cap = {"type": "widget", "look": "vigie-cap", "product": "widget_vigie_cap", "payload": {"sizes": []}}
    for element in (style, cap):
        element.update(economy={"price": 400}, names={"en": "x"}, descriptions={})
    assert VisualPacks.product_of(style, {})["type"] == "widget_option"
    assert VisualPacks.product_of(style, {})["payload"] == {"option": "*:_skin=vigie"}
    assert VisualPacks.product_of(cap, {})["payload"] == {"widget": "pack.vigie-cap"}
    value = {
        "type": "widget_option",
        "product": "o1",
        "payload": {"widget": "vigie-cap", "setting": "dial", "value": "night"},
    }
    addon = {"type": "widget_option", "product": "o2", "look": "swell", "payload": {"widget": "*"}}
    aimed = {
        "type": "widget_option",
        "product": "o3",
        "look": "deck",
        "payload": {"widget": "media.recently_added"},
    }
    for element in (value, addon, aimed):
        element.update(economy={"price": 300}, names={"en": "x"}, descriptions={})
    assert VisualPacks.product_of(value, {})["payload"] == {"option": "pack.vigie-cap:dial=night"}
    assert VisualPacks.product_of(addon, {})["payload"] == {"option": "*:_options=swell"}
    assert VisualPacks.product_of(aimed, {})["payload"] == {"option": "media.recently_added:_options=deck"}


def test_a_frames_look_is_a_frame_setting_of_any_widget() -> None:
    registry = WidgetRegistry()
    strict = WidgetDefinition(
        key="demo.strict",
        owner="module:demo",
        title_key="x",
        required_permission="p",
        config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    registry.register(strict, PackWidgetProvider({"pack": "p", "sha": "s", "look": "l"}, None))
    held = registry.get("demo.strict")
    assert held is not None
    assert config_errors(held, {"_skin": "vigie", "_hide_title": True}) == []
    assert config_errors(held, {"_skin": ""}) == []
    assert config_errors(held, {"_skin": "../../x"}) and config_errors(held, {"_skin": 3})
    gateway = WidgetGateway.__new__(WidgetGateway)
    gateway.registry = registry
    # not owned (any more): the frame falls back to the interface's own, the saved choice kept for later
    locked = frozenset({"*:_skin=vigie"})
    assert "_skin" not in gateway.unlocked("demo.strict", {"_skin": "vigie"}, locked)
    assert gateway.unlocked("demo.strict", {"_skin": "other"}, locked)["_skin"] == "other"
    # the add-ons worn: each looked at on its own
    assert config_errors(held, {"_options": ["swell", "sonar"]}) == []
    assert config_errors(held, {"_options": "swell"}) and config_errors(held, {"_options": ["x"] * 9})
    locked = frozenset({"*:_options=sonar", "demo.strict:_options=deck"})
    kept = gateway.unlocked("demo.strict", {"_options": ["swell", "sonar", "deck"]}, locked)
    assert kept["_options"] == ["swell"]
    assert worn({"_options": ["a", "b"], "style": "x"}) == [
        ("_options", "a"),
        ("_options", "b"),
        ("style", "x"),
    ]
