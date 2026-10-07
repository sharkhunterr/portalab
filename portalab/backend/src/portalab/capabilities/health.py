"""Service health contracts (spec 006): capabilities consumed from connectors, the directory of configured
services (provided by 005), the ``health.service_state`` read model (provided by 006) and the Support ports
(``support.incidents`` / ``support.service_tickets``, implemented by 016; empty until then).

Connector-provided capabilities are bound to one service (the provider instance is the service, its
``instance_ref`` the service id) and are called through the 001 isolation wrapper, so their methods return
:class:`~portalab.capabilities.results.CapabilityResult` values.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from portalab.capabilities.registry import CapabilitySpec

HEALTH_PROBE = "service.health_probe"
INFRA_METRICS = "infrastructure.metrics"
SERVER_OPERATIONS = "server.operations"
SERVICE_DIRECTORY = "connectors.directory"
SERVICE_STATE = "health.service_state"
INCIDENTS = "support.incidents"
SERVICE_TICKETS = "support.service_tickets"

HealthState = Literal["operational", "degraded", "unavailable", "maintenance", "unknown"]
METRICS = ("cpu", "ram", "storage", "gpu", "network", "temperature", "transcoding")


# --- consumed from connectors ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ProbeResult:
    reachable: bool
    latency_ms: float | None = None
    detail: str = ""
    error_code: str | None = None  # stable code, e.g. "timeout", "http_503", "auth"


@runtime_checkable
class HealthProbe(Protocol):
    async def probe(self) -> ProbeResult: ...


@dataclass(frozen=True, slots=True)
class MetricValue:
    value: float
    unit: str


@dataclass(frozen=True, slots=True)
class NotAvailable:
    """A metric the provider cannot report right now — rendered as "not available", never as zero."""

    reason: str = "not reported"


@runtime_checkable
class InfrastructureMetrics(Protocol):
    async def fetch(self, metrics: list[str]) -> Mapping[str, MetricValue | NotAvailable]: ...


@dataclass(frozen=True, slots=True)
class Operation:
    key: str
    label: str
    description: str = ""
    sensitive: bool = True


@runtime_checkable
class ServerOperations(Protocol):
    async def list_operations(self) -> list[Operation]: ...

    async def execute(self, operation: str, params: Mapping[str, Any]) -> Mapping[str, Any]: ...


# --- provided by connectors (005) ----------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ServiceInfo:
    id: str
    name: str
    connector: str
    state: str  # connection state from 005 (configured|enabled|error|unavailable|maintenance|disabled|…)
    sync_status: str = "idle"
    last_sync_success_at: datetime | None = None
    last_sync_attempt_at: datetime | None = None
    last_sync_error: str | None = None
    link: str | None = None  # 027: where members open it (its public URL, or its https address)
    # 027: how much it matters and when its outage becomes an incident (minutes; None: never)
    importance: str = "major"
    incident_after_minutes: int | None = None
    incident_auto_resolve: bool = True


@runtime_checkable
class ServiceDirectory(Protocol):
    async def services(self) -> list[ServiceInfo]: ...

    async def service(self, service_id: str) -> ServiceInfo | None: ...


# --- provided by health (006) --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ServiceStateView:
    service_id: str
    state: HealthState
    since: datetime
    last_check_at: datetime | None
    availability: float | None  # share of OK probes over the last 24 h, None without data
    as_of: datetime


@runtime_checkable
class ServiceStateReader(Protocol):
    async def get(self, service_id: str) -> ServiceStateView | None: ...

    async def all(self) -> list[ServiceStateView]: ...


# --- Support ports (016) -------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class IncidentRef:
    id: str
    title: str
    status: str
    opened_at: datetime
    extra: Mapping[str, Any] = field(default_factory=dict)


# 027: minutes of outage before an incident is declared, by the service's importance (None: never)
INCIDENT_AFTER: dict[str, int | None] = {"critical": 5, "major": 10, "minor": 30, "internal": None}
INCIDENT_SEVERITY: dict[str, str] = {
    "critical": "critical",
    "major": "major",
    "minor": "minor",
    "internal": "minor",
}


@runtime_checkable
class Incidents(Protocol):
    """Support's incident lifecycle (016): create → notify → track → resolve stays there."""

    async def open_for_service(self, service_id: str) -> list[IncidentRef]: ...

    async def link(self, service_id: str, incident_id: str) -> None: ...

    async def create(
        self,
        *,
        title: str,
        source: str,
        severity: str,
        evidence: Mapping[str, Any],
        service_ids: Sequence[str] = (),
        dedup_key: str | None = None,
        summary: str | None = None,
    ) -> IncidentRef:
        """Idempotent per ``(source, dedup_key)`` (016): a repeated escalation returns the same incident.
        ``severity`` accepts ``minor|major|critical`` (or 025's ``info|warning|critical``)."""
        ...

    async def attach(self, incident_id: str, evidence: Mapping[str, Any]) -> IncidentRef | None:
        """Add evidence to an incident; ``None`` when it is no longer open."""
        ...

    async def get(self, incident_id: str) -> IncidentRef | None: ...


@dataclass(frozen=True, slots=True)
class TicketRef:
    id: str
    title: str
    status: str


@runtime_checkable
class ServiceTickets(Protocol):
    async def open_for_service(self, service_id: str) -> list[TicketRef]: ...


def _spec(name: str, protocol: type[Any], multi: bool, description: str) -> CapabilitySpec:
    return CapabilitySpec(
        name=name, version="1.0", protocol=protocol, multi_provider=multi, description=description
    )


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(HEALTH_PROBE, HealthProbe, True, "Health probe of one service (provided per service)"),
    _spec(INFRA_METRICS, InfrastructureMetrics, True, "Infrastructure metrics of one service's host"),
    _spec(SERVER_OPERATIONS, ServerOperations, True, "Privileged server operations of one service"),
    _spec(SERVICE_DIRECTORY, ServiceDirectory, False, "Configured services and their sync state (005)"),
    _spec(SERVICE_STATE, ServiceStateReader, False, "Derived service health state (006)"),
    _spec(INCIDENTS, Incidents, False, "Incident lifecycle (Support 016)"),
    _spec(SERVICE_TICKETS, ServiceTickets, False, "Tickets about a service (Support 016)"),
)
