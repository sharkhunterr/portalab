"""Packs' widgets on the dashboard (spec 028, US6; R26).

A live pack's ``widget`` element becomes a dashboard widget (``pack.<look>``), registered in this process
whenever the registry's epoch moves and taken away when its pack goes off (members' placed instances are kept
by the dashboard, shown again when it comes back). Its data provider hands the member's page what to run —
the element and the contracts it declared, minus those this member may not read — never the contracts' data:
the page reads them through the portal's usual routes with the member's own session and gives the widget only
their fields (``frontend/src/features/dashboard/contracts``). Everything the widget does is in its pack: the
portal holds no code of any pack's widget.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from portalab.capabilities.dashboard import (
    Refresh,
    Size,
    SizeLimits,
    WidgetDefinition,
    WidgetPayload,
    WidgetRegistry,
    WidgetRegistryError,
)
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.visuals import WIDGET_CONTRACTS, WIDGET_DATA, contract_known
from portalab.core.authz_port import Authorizer, Principal
from portalab.modules.visuals.analysis import settings_of

OWNER = "module:visuals"
COMPONENT = "visuals.pack"
PREFIX = "pack."
# any member may place one (its contracts decide what it shows): the permission members have on their own data
PERMISSION = "users.self.manage"


def pack_widget_key(look: str) -> str:
    return f"{PREFIX}{look}"


def size_limits(sizes: Any) -> SizeLimits:
    """The sizes a widget declared: the first is its default, the others bound how far it may be resized."""
    valid = [
        Size(int(size["w"]), int(size["h"]))
        for size in (sizes if isinstance(sizes, list) else [])
        if isinstance(size, Mapping)
        and isinstance(size.get("w"), int)
        and isinstance(size.get("h"), int)
        and 1 <= size["w"] <= 12
        and 1 <= size["h"] <= 6
    ]
    if not valid:
        return SizeLimits(default=Size(4, 2), min=Size(2, 1), max=Size(6, 3))
    return SizeLimits(
        default=valid[0],
        min=Size(min(s.w for s in valid), min(s.h for s in valid)),
        max=Size(max(s.w for s in valid), max(s.h for s in valid)),
    )


def contract_permission(contract: str, registry: WidgetRegistry) -> str | None:
    """The permission a contract needs (``None``: no such contract here)."""
    if contract in WIDGET_CONTRACTS:
        return WIDGET_CONTRACTS[contract].permission
    if contract_known(contract):
        widget = registry.get(contract.removeprefix(WIDGET_DATA))
        return widget.definition.required_permission if widget is not None else None
    return None


async def forbidden_contracts(
    contracts: Iterable[str], principal: Principal, authorizer: Authorizer | None, registry: WidgetRegistry
) -> list[str]:
    """The contracts this member may not read (a widget's data also needs its purchase: the dashboard
    answers ``unauthorized`` then, and the page hands the widget « forbidden »)."""
    out = []
    for contract in contracts:
        permission = contract_permission(contract, registry)
        allowed = False
        if permission is not None and authorizer is not None:
            try:
                allowed = await authorizer.is_allowed(principal, permission)
            except Exception:
                allowed = False  # fail closed
        if not allowed:
            out.append(contract)
    return out


class PackWidgetProvider:
    """What the member's page needs to run the widget: its element and the contracts it may be handed."""

    def __init__(
        self, entry: Mapping[str, Any], authorizer: Authorizer | None, registry: WidgetRegistry | None = None
    ) -> None:
        self.entry = dict(entry)
        self.authorizer = authorizer
        self.registry = registry or WidgetRegistry()

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        contracts = [c for c in self.entry.get("contracts") or [] if contract_known(c)]
        forbidden = await forbidden_contracts(contracts, principal, self.authorizer, self.registry)
        return WidgetPayload(
            "available",
            data={
                "pack": self.entry["pack"],
                "sha": self.entry["sha"],
                "look": self.entry["look"],
                "contracts": contracts,
                "forbidden": forbidden,
            },
        )


class PackWidgets:
    """Keeps this process's dashboard registry in step with the live packs' widgets."""

    def __init__(self, registry: WidgetRegistry, authorizer: Authorizer | None = None) -> None:
        self.registry = registry
        self.authorizer = authorizer
        self._registered: set[str] = set()

    def definition(self, entry: Mapping[str, Any]) -> WidgetDefinition:
        look = str(entry["look"])
        payload = entry.get("payload") or {}
        refresh = payload.get("refresh_s")
        settings = settings_of(payload.get("options")) or {}
        return WidgetDefinition(
            key=pack_widget_key(look),
            # its own settings (a dial, a theme…): their values sold on their own (``widget_option``) or not
            config_schema={
                "type": "object",
                "properties": {k: {"type": "string", "enum": values} for k, (values, _) in settings.items()},
                "additionalProperties": False,
            },
            config_defaults={k: default for k, (_, default) in settings.items()},
            owner=OWNER,
            # the pack's own name for it (the interface adds the packs' names over its catalogs)
            title_key=f"dashboard:packWidget.{look}",
            required_permission=PERMISSION,
            icon=(entry.get("economy") or {}).get("icon") or "sparkles",
            size=size_limits(payload.get("sizes")),
            refresh=Refresh("interval", int(refresh)) if isinstance(refresh, int) else Refresh(),
            component_id=COMPONENT,
        )

    def sync(self, entries: Iterable[Mapping[str, Any]]) -> None:
        """``entries``: the live widget elements (``pack``, ``sha``, ``look``, ``contracts``, ``payload``)."""
        wanted: dict[str, Mapping[str, Any]] = {}
        for entry in entries:
            if entry.get("look"):
                wanted.setdefault(pack_widget_key(str(entry["look"])), entry)
        for key in self._registered - set(wanted):
            self.registry.unregister(key)
        registered: set[str] = set()
        for key, entry in wanted.items():
            try:
                self.registry.register(
                    self.definition(entry),
                    PackWidgetProvider(entry, self.authorizer, self.registry),
                    owner=OWNER,
                )
                registered.add(key)
            except WidgetRegistryError:
                continue  # a key another module holds: the pack's widget stays off the dashboard
        self._registered = registered
