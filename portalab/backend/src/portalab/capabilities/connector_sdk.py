"""Connector SDK (spec 005 R1, contracts/connector-contracts.md).

A *connector* is a code package (``portalab.connectors.<key>`` or a plugin) registered at start-up; a
*service* is a configured instance of it. Connectors declare the capabilities they provide, test
connections, discover candidates on operator-supplied targets only, and yield normalized
:class:`SourceRecord`s that consuming modules ingest through their ``RecordSink``. Connectors never write
module tables.
"""

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel

from portalab.capabilities.registry import CapabilitySpec


@dataclass(frozen=True, slots=True)
class Manifest:
    version: str
    requires_portal: str = ">=0.1"  # comma-separated bounds: ">=0.1,<2"
    requires_capabilities: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityBinding:
    spec: CapabilitySpec
    syncable: bool = False  # True when ``sync`` produces records for this capability


@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_system: str
    external_id: str
    kind: str
    payload: Mapping[str, Any]
    observed_at: datetime
    removed: bool = False


@dataclass(frozen=True, slots=True)
class SyncProgress:
    """A checkpoint (``cursor``, empty to only report progress) and, when the source knows it, how many
    records the run will yield in all (``total``, 027: shown as a progress bar)."""

    cursor: Mapping[str, Any]
    total: int | None = None


@dataclass(frozen=True, slots=True)
class TestResult:
    ok: bool
    reachable: bool
    authenticated: bool
    compatible: bool = True
    detail: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Candidate:
    target: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ServiceHandle:
    """What a connector receives about one service instance (secrets already decrypted, never logged)."""

    service_id: UUID
    name: str
    config: Mapping[str, Any]
    secrets: Mapping[str, str]
    http: Any = None  # ConnectorHttpClient bound to the configured base URL


class SyncContext(Protocol):
    @property
    def service(self) -> ServiceHandle: ...

    @property
    def capability(self) -> str: ...

    @property
    def kind(self) -> Literal["scheduled", "manual", "resync_partial", "resync_full"]: ...


@runtime_checkable
class Connector(Protocol):
    key: str
    name: str
    manifest: Manifest
    config_schema: type[BaseModel]
    secret_fields: frozenset[str]
    provides: Sequence[CapabilityBinding]

    async def test_connection(self, service: ServiceHandle) -> TestResult: ...

    async def discover(self, targets: Sequence[str]) -> list[Candidate]: ...

    def sync(
        self, ctx: SyncContext, cursor: Mapping[str, Any] | None
    ) -> AsyncIterator[SourceRecord | SyncProgress]: ...

    def provider(self, capability: str, service: ServiceHandle) -> Any: ...

    def actions(self) -> Mapping[str, Callable[[ServiceHandle, Mapping[str, Any]], Any]]: ...


class ConnectorRegistryError(ValueError):
    pass


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, tuple[Connector, str]] = {}

    def register(self, connector: Connector, *, owner: str = "core") -> Connector:
        if not connector.key or not connector.key.replace("-", "").replace("_", "").isalnum():
            raise ConnectorRegistryError(f"invalid connector key {connector.key!r}")
        if connector.key in self._connectors:
            raise ConnectorRegistryError(f"connector {connector.key!r} is already registered")
        if set(connector.secret_fields) & set(connector.config_schema.model_fields):
            raise ConnectorRegistryError(
                f"{connector.key}: secrets must not appear in the non-secret config schema"
            )
        self._connectors[connector.key] = (connector, owner)
        return connector

    def get(self, key: str) -> Connector | None:
        entry = self._connectors.get(key)
        return entry[0] if entry else None

    def all(self) -> list[Connector]:
        return [self._connectors[key][0] for key in sorted(self._connectors)]

    def unregister(self, owner: str) -> int:
        doomed = [key for key, (_, who) in self._connectors.items() if who == owner]
        for key in doomed:
            del self._connectors[key]
        return len(doomed)


default_connectors = ConnectorRegistry()


def register_connector(connector: Connector, *, owner: str = "core") -> Connector:
    if default_connectors.get(connector.key) is connector:
        return connector
    return default_connectors.register(connector, owner=owner)
