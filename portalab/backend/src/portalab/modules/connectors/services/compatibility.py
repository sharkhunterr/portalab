"""Compatibility checks (T017; FR-029, US9).

Before a connector's service is enabled, its manifest is checked against the running portal: portal
version bounds, capabilities it requires (must be declared) and permissions it needs (must exist).
Incompatible ⇒ refuse with reasons; a version-bound warning on an *already enabled* service keeps its prior
working state (no silent change). The check is also registered as an ``admin.toggle_hook`` so the 020
toggle service vetoes enabling an incompatible connector/service.
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

from portalab import __version__
from portalab.capabilities.connector_sdk import Connector, ConnectorRegistry
from portalab.capabilities.registry import CapabilityError, CapabilityRegistry
from portalab.core.permissions import PermissionRegistry, default_permissions

ServiceConnectorLookup = Callable[[str], Awaitable[str | None]]
Verdict = Literal["compatible", "warning", "incompatible"]
_BOUND = re.compile(r"^\s*(>=|<=|==|!=|>|<)\s*([0-9]+(?:\.[0-9]+)*)\s*$")


def _version(text: str) -> tuple[int, ...]:
    parts = [int(part) for part in re.findall(r"[0-9]+", text)[:3]]
    return tuple(parts + [0] * (3 - len(parts)))


def satisfies(version: str, spec: str) -> bool | None:
    """``True``/``False`` for a well-formed comma-separated spec (``">=0.1,<2"``), ``None`` if malformed."""
    current = _version(version)
    for clause in filter(None, (part.strip() for part in spec.split(","))):
        match = _BOUND.match(clause)
        if match is None:
            return None
        op, bound = match.group(1), _version(match.group(2))
        ok = {
            ">=": current >= bound,
            "<=": current <= bound,
            "==": current == bound,
            "!=": current != bound,
            ">": current > bound,
            "<": current < bound,
        }[op]
        if not ok:
            return False
    return True


@dataclass(frozen=True, slots=True)
class Compatibility:
    result: Verdict
    reasons: list[str] = field(default_factory=list)

    @property
    def compatible(self) -> bool:
        return self.result != "incompatible"


class CompatibilityChecker:
    def __init__(
        self,
        connectors: ConnectorRegistry,
        capabilities: CapabilityRegistry,
        *,
        permissions: PermissionRegistry = default_permissions,
        portal_version: str = __version__,
    ) -> None:
        self.connectors = connectors
        self.capabilities = capabilities
        self.permissions = permissions
        self.portal_version = portal_version

    def check(self, connector: Connector) -> Compatibility:
        reasons: list[str] = []
        manifest = connector.manifest
        verdict = satisfies(self.portal_version, manifest.requires_portal)
        if verdict is None:
            reasons.append(f"manifest version range {manifest.requires_portal!r} is malformed")
        elif not verdict:
            reasons.append(f"requires portal {manifest.requires_portal}, running {self.portal_version}")
        for capability in manifest.requires_capabilities:
            try:
                self.capabilities.spec(capability)
            except CapabilityError:
                reasons.append(f"requires capability {capability!r}, which is not available")
        known = self.permissions.keys()
        for permission in manifest.permissions:
            if permission not in known:
                reasons.append(f"requires permission {permission!r}, which is not declared")
        return Compatibility("incompatible" if reasons else "compatible", reasons)


class CompatibilityToggleHook:
    """``admin.toggle_hook`` provider: vetoes enabling an incompatible connector (020 toggles)."""

    def __init__(self, checker: CompatibilityChecker, connector_of_service: ServiceConnectorLookup) -> None:
        self.checker = checker
        self.connector_of_service = connector_of_service

    async def check_enable(self, kind: str, ref: str) -> list[str]:
        if kind == "connector":
            key: str | None = ref
        elif kind == "service":
            key = await self.connector_of_service(ref)
        else:
            return []
        if key is None:
            return []
        connector = self.checker.connectors.get(key)
        if connector is None:
            return [f"connector {key!r} is not installed"]
        return self.checker.check(connector).reasons
