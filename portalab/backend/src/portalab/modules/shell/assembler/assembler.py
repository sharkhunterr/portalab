"""``NavigationAssembler`` (T012; R2 to R6, FR-005..010, FR-029).

Merges registered contributions, keeps those whose owner (and ``visible_when`` module/plugin/setting) is
enabled, filters them **server side** through ``authorize()`` (one decision per distinct permission per
request), applies the layout precedence and returns a ``NavigationView``. Entries the principal may not use
are simply absent — their names never leak. A contribution failing at runtime is isolated; an authorization
failure yields a minimal, empty navigation flagged ``degraded`` — never more rights. Views are cached per
``(user, permission epoch, module epoch, registry version, preference fingerprint)``.
"""

import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from portalab.capabilities.administration import EXTENSION_STATE_CAPABILITY
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.navigation import NavigationContribution, NavigationRegistry, Rejection
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.metrics import default_metrics
from portalab.core.time import Clock, utc_now
from portalab.modules.shell.assembler.epochs import Epochs
from portalab.modules.shell.assembler.layout import arrange
from portalab.modules.shell.observability import log, metrics

CACHE_SIZE = 512


class NavigationAssembler:
    def __init__(
        self,
        registry: NavigationRegistry,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        epochs: Epochs,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.registry = registry
        self.authorizer = authorizer
        self.capabilities = capabilities
        self.epochs = epochs
        self.clock = clock
        self._cache: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
        self.runtime_rejections: list[Rejection] = []

    def _provider(self, name: str) -> Any:
        providers = self.capabilities.system_providers(name)
        return providers[0].provider if providers else None

    async def _setting(self, key: str, principal: Principal, fallback: Any) -> Any:
        reader = self._provider(CONFIG)
        if reader is None:
            return fallback
        try:
            return (await reader.get(key, user_id=principal.user_id)).value
        except Exception:
            return fallback

    async def _enabled(self, contribution: NavigationContribution, memo: dict[tuple[str, str], bool]) -> bool:
        state = self._provider(EXTENSION_STATE_CAPABILITY)
        checks: list[tuple[str, str]] = []
        kind, ref = contribution.owner.split(":", 1)
        checks.append((kind, ref))
        if contribution.visible_when:
            if contribution.visible_when.module:
                checks.append(("module", contribution.visible_when.module))
            if contribution.visible_when.plugin:
                checks.append(("plugin", contribution.visible_when.plugin))
        for check in checks:
            if check not in memo:
                memo[check] = bool(await state.enabled(*check)) if state else True
            if not memo[check]:
                return False
        if contribution.visible_when and contribution.visible_when.setting:
            reader = self._provider(CONFIG)
            if reader is not None and not bool((await reader.get(contribution.visible_when.setting)).value):
                return False
        return True

    async def build(self, principal: Principal) -> dict[str, Any]:
        started = time.monotonic()
        layout = await self._setting("shell.navigation.layout", principal, {})
        allow_user = bool(await self._setting("shell.navigation.allowUserOrdering", principal, True))
        user_order = list(await self._setting("shell.navigation.userOrder", principal, []))
        epochs = await self.epochs.current()
        fingerprint = hashlib.sha256(
            json.dumps([layout, allow_user, user_order], sort_keys=True, default=str).encode()
        ).hexdigest()
        key = (
            principal.user_id,
            principal.channel,
            principal.acting_for,
            *epochs,
            self.registry.version,
            fingerprint,
        )
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            metrics.increment("shell.cache_hits")
            return cached
        metrics.increment("shell.cache_misses")
        try:
            view = await self._assemble(principal, layout, user_order, allow_user)
        except Exception:
            log.warning("navigation assembly failed; minimal navigation served")
            metrics.increment("shell.assembly_failures")
            return self._minimal()
        self._cache[key] = view
        if len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        default_metrics.histogram(
            "shell", "navigation.assembly", (time.monotonic() - started) * 1000, {"phase": "internal"}
        )
        return view

    def _minimal(self) -> dict[str, Any]:
        view: dict[str, Any] = {"groups": [], "commands": [], "related": {}, "crumbs": {}, "degraded": True}
        return {**view, "version": _version(view), "generated_at": utc_now(self.clock).isoformat()}

    async def _assemble(
        self, principal: Principal, layout: Mapping[str, Any], user_order: list[str], allow_user: bool
    ) -> dict[str, Any]:
        enabled_memo: dict[tuple[str, str], bool] = {}
        allowed_memo: dict[str, bool] = {}
        usable: list[NavigationContribution] = []
        for contribution in self.registry.all():
            try:
                if not await self._enabled(contribution, enabled_memo):
                    continue
            except Exception as exc:
                self.runtime_rejections.append(
                    Rejection(
                        contribution.owner,
                        contribution.key,
                        "runtime",
                        f"enablement check failed ({type(exc).__name__})",
                    )
                )
                continue
            permission = contribution.required_permission
            if permission not in allowed_memo:
                allowed_memo[permission] = await self.authorizer.is_allowed(principal, permission, None)
            if allowed_memo[permission]:
                usable.append(contribution)
        entries = [c for c in usable if c.kind == "entry"]
        entry_keys = {c.key for c in entries}
        groups = [
            {"key": g["key"], "label_key": g["label_key"], "entries": [_entry(e) for e in g["entries"]]}
            for g in arrange(entries, layout=layout, user_order=user_order, allow_user_ordering=allow_user)
        ]
        commands = [_command(c) for c in usable if c.kind == "command"] + [
            {**_entry(e), "kind": "navigate"} for e in entries
        ]
        related: dict[str, list[dict[str, Any]]] = {}
        crumbs: dict[str, dict[str, Any]] = {}
        for contribution in usable:
            if contribution.target_entry_key not in entry_keys:
                continue
            target = self.registry.get(contribution.target_entry_key or "")
            if target is None or target.route is None:
                continue
            if contribution.kind == "related_link":
                related.setdefault(target.route, []).append(_entry(contribution))
            elif contribution.kind == "crumb_parent":
                crumbs[target.route] = {"label_key": contribution.label_key, "route": contribution.route}
        view: dict[str, Any] = {
            "groups": [g for g in groups if g["entries"]],
            "commands": sorted(commands, key=lambda c: c["key"]),
            "related": related,
            "crumbs": crumbs,
            "degraded": False,
        }
        return {**view, "version": _version(view), "generated_at": utc_now(self.clock).isoformat()}

    def drain_runtime_rejections(self) -> list[Rejection]:
        drained, self.runtime_rejections = self.runtime_rejections, []
        return drained


def _entry(c: NavigationContribution) -> dict[str, Any]:
    return {
        "key": c.key,
        "label_key": c.label_key,
        "icon": c.icon,
        "route": c.route,
        "existence_sensitive": c.existence_sensitive,
        "keywords": list(c.keywords),
    }


def _command(c: NavigationContribution) -> dict[str, Any]:
    return {
        **_entry(c),
        "kind": "action" if c.action_id else "navigate",
        "action_id": c.action_id,
        "sensitivity": c.sensitivity,
        "confirmation_required": c.confirmation_required,
    }


def _version(view: Mapping[str, Any]) -> str:
    stable = {k: v for k, v in view.items() if k != "generated_at"}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, default=str).encode()).hexdigest()[:20]


def as_of(view: Mapping[str, Any]) -> datetime:
    return datetime.fromisoformat(str(view["generated_at"]))
