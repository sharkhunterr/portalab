"""``WidgetGateway`` (T011; R2): ``GET /widgets/{key}/data`` serves one widget's ``WidgetPayload``
under its own time budget. Provider failures become states (``unavailable``, ``error``,
``unauthorized``) — never a 5xx — so one widget's outage never affects another. Data is re-authorized on
every call (hiding a widget in the UI is not security): widget permission, module/plugin enablement and
Marketplace entitlement."""

import asyncio
import time
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import timedelta
from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator

from portalab.capabilities.administration import EXTENSION_STATE_CAPABILITY
from portalab.capabilities.dashboard import (
    ENTITLEMENTS,
    RegisteredWidget,
    WidgetPayload,
    WidgetRegistry,
    WidgetUnauthorized,
    WidgetUnavailable,
)
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import COSMETICS
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.dashboard.observability import log, metric_part, metrics
from portalab.modules.dashboard.settings import DashboardConfig

# 027: the frame's own settings, kept with a widget's but never part of its schema — « hide when empty »,
# « no title », « no box » (the raw content on the page)
FRAME_KEYS = frozenset({"_hide_empty", "_hide_title", "_no_box"})


def config_errors(widget: RegisteredWidget, config: Mapping[str, Any]) -> list[str]:
    validator = Draft202012Validator(dict(widget.definition.config_schema))
    own = {k: v for k, v in config.items() if k not in FRAME_KEYS}
    errors = [error.message for error in validator.iter_errors(own)]
    for key in sorted(FRAME_KEYS):
        if key in config and not isinstance(config[key], bool):
            errors.append(f"{key} must be true or false")
    return errors


def resolved_config(
    widget: RegisteredWidget, stored: Mapping[str, Any] | None
) -> tuple[dict[str, Any], bool]:
    """Stored config over defaults; an invalid stored config falls back to defaults (flagged)."""
    merged = {**widget.definition.config_defaults, **(stored or {})}
    if config_errors(widget, merged):
        return dict(widget.definition.config_defaults), True
    return merged, False


def module_of(owner: str) -> tuple[str, str]:
    kind, _, ref = owner.partition(":")
    return ("plugin" if kind == "plugin" else "module"), ref


class WidgetGateway:
    def __init__(
        self,
        registry: WidgetRegistry,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        config: Callable[[], DashboardConfig],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.registry = registry
        self.authorizer = authorizer
        self.capabilities = capabilities
        self.config = config
        self.clock = clock
        self._sold_cache: dict[tuple[str, str], tuple[float, frozenset[str]]] = {}

    def _provider(self, name: str) -> Any | None:
        try:
            providers = self.capabilities.system_providers(name)
        except Exception:
            return None
        return providers[0].provider if providers else None

    async def allowed(self, widget: RegisteredWidget, principal: Principal, *, preview: bool = False) -> bool:
        """Permission, owner enabled, and entitlement for Marketplace widget products (015 F9). 027: a preview
        (the shop's and the catalog's miniature) needs the permission, not the purchase."""
        try:
            if not await self.authorizer.is_allowed(principal, widget.definition.required_permission):
                return False
            extensions = self._provider(EXTENSION_STATE_CAPABILITY)
            if extensions is not None and not await extensions.enabled(*module_of(widget.owner)):
                return False
            product = widget.definition.product
            if preview:
                return True
            if product is not None:
                entitlements = self._provider(ENTITLEMENTS)
                user = principal.acting_for or principal.user_id
                if entitlements is None or user is None or not await entitlements.owns(user, product):
                    return False
            elif widget.definition.key in await self.sold_widgets():
                # 027: an existing widget sold by a ``widget`` product is for its owners only
                user = principal.acting_for or principal.user_id
                shop = self._provider(COSMETICS)
                if shop is None or user is None:
                    return False
                if widget.definition.key not in await shop.owned(user, "widget", "widget"):
                    return False
        except Exception:
            return False  # fail closed
        return True

    async def sold_widgets(self) -> frozenset[str]:
        """027: widget keys sold by available ``widget`` products (read at most every 10 s)."""
        return await self._sold("widget", "widget")

    async def locked_options(self, principal: Principal) -> frozenset[str]:
        """027: widget setting values sold in the shop (``widget_option``: ``<widget>:<field>=<value>``)
        that this member does not own."""
        sold = await self._sold("widget_option", "option")
        if not sold:
            return frozenset()
        shop = self._provider(COSMETICS)
        user = principal.acting_for or principal.user_id
        if shop is None or user is None:
            return sold
        try:
            return frozenset(sold - await shop.owned(user, "widget_option", "option"))
        except Exception:
            return sold  # fail closed

    async def _sold(self, kind: str, field: str) -> frozenset[str]:
        now = time.monotonic()
        cached = self._sold_cache.get((kind, field))
        if cached is not None and now - cached[0] < 10:
            return cached[1]
        shop = self._provider(COSMETICS)
        try:
            sold = frozenset(await shop.sold(kind, field)) if shop is not None else frozenset()
        except Exception:
            sold = frozenset()
        self._sold_cache[(kind, field)] = (now, sold)
        return sold

    async def load(
        self,
        key: str,
        principal: Principal,
        ctx: LocaleContext,
        stored_config: Mapping[str, Any] | None = None,
        *,
        preview: bool = False,
    ) -> WidgetPayload | None:
        """``None`` when no such widget is registered (the router answers 404)."""
        widget = self.registry.get(key)
        if widget is None:
            return None
        if not await self.allowed(widget, principal, preview=preview):
            return WidgetPayload("unauthorized")
        config, invalid = resolved_config(widget, stored_config)
        budget = max(0.1, self.config().widget_timeout_ms / 1000)
        started = time.perf_counter()
        name = metric_part(key)
        try:
            payload = await asyncio.wait_for(widget.provider.load(principal, config, ctx), timeout=budget)
        except TimeoutError:
            metrics.increment(f"dashboard.widget.{name}.timeouts")
            return WidgetPayload("unavailable", as_of=utc_now(self.clock), partial_reasons=("timeout",))
        except WidgetUnavailable:
            metrics.increment(f"dashboard.widget.{name}.unavailable")
            return WidgetPayload("unavailable", as_of=utc_now(self.clock))
        except WidgetUnauthorized:
            return WidgetPayload("unauthorized")
        except Exception:
            log.warning("widget provider failed", extra={"widget": key})
            metrics.increment(f"dashboard.widget.{name}.errors")
            return WidgetPayload("error", as_of=utc_now(self.clock))
        metrics.gauge(f"dashboard.widget.{name}.latency_ms", int((time.perf_counter() - started) * 1000))
        stale_after = payload.stale_after_s or widget.definition.stale_after_s
        if payload.stale_after_s is None and stale_after is not None:
            payload = replace(payload, stale_after_s=stale_after)
        if (
            payload.state == "available"
            and stale_after is not None
            and payload.as_of is not None
            and utc_now(self.clock) - payload.as_of > timedelta(seconds=stale_after)
        ):
            payload = replace(payload, state="stale")
        if invalid:
            payload = replace(payload, config_invalid=True)
        return payload

    async def has_data(self, key: str, principal: Principal) -> bool:
        payload = await self.load(key, principal, LocaleContext())
        return payload is not None and payload.state in ("available", "partial", "stale")

    @staticmethod
    def owner_user(principal: Principal) -> UUID | None:
        return principal.acting_for or principal.user_id
