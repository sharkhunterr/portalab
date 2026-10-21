"""Service health contracts (spec 006): capabilities consumed from connectors, the directory of configured
services (provided by 005), the ``health.service_state`` read model (provided by 006) and the Support ports
(``support.incidents`` / ``support.service_tickets``, implemented by 016; empty until then).

Connector-provided capabilities are bound to one service (the provider instance is the service, its
``instance_ref`` the service id) and are called through the 001 isolation wrapper, so their methods return
:class:`~portalab.capabilities.results.CapabilityResult` values.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from portalab.capabilities.registry import CapabilitySpec

HEALTH_PROBE = "service.health_probe"
INFRA_METRICS = "infrastructure.metrics"
INFRA_HOST = "infrastructure.host"  # #49/#50: a server's full picture (Glances, Unraid)
INFRA_HISTORY = "health.infra_history"  # #52: the metrics over time (charts), provided by health
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
    # #49/#50: the service answers but reports a problem (an array degraded, a disk in error, little space
    # left): the service is « degraded », never counted as an outage
    warning: str | None = None


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


# --- a server's full picture (#49 Glances, #50 Unraid) ----------------------------------------------------
@dataclass(frozen=True, slots=True)
class Usage:
    used: float  # bytes
    total: float


@dataclass(frozen=True, slots=True)
class Volume:
    """A file system, a disk of an array, a cache pool or a share."""

    name: str
    kind: str = "filesystem"  # filesystem | array | parity | disk | cache | boot | pool | share
    used: float | None = None  # bytes
    total: float | None = None
    mount: str | None = None
    state: str | None = None  # the device's state as the server says it (e.g. DISK_OK)
    ok: bool = True
    temperature: float | None = None  # °C
    errors: int | None = None
    spinning: bool | None = None


@dataclass(frozen=True, slots=True)
class Sensor:
    label: str
    value: float
    unit: str = "°C"
    warning: float | None = None
    critical: float | None = None


@dataclass(frozen=True, slots=True)
class Interface:
    name: str
    rx_bps: float | None = None  # bytes per second
    tx_bps: float | None = None


@dataclass(frozen=True, slots=True)
class Container:
    name: str
    state: str  # running | exited | paused | …
    image: str | None = None
    cpu_percent: float | None = None
    memory_bytes: float | None = None
    update_available: bool | None = None


@dataclass(frozen=True, slots=True)
class ParityCheck:
    status: str  # running | paused | completed | …
    progress: float | None = None  # percent
    errors: int | None = None
    speed: str | None = None
    running: bool = False
    paused: bool = False
    correcting: bool | None = None
    started_at: str | None = None  # ISO
    elapsed_seconds: float | None = None
    remaining_seconds: float | None = None  # estimated from the pace so far


@dataclass(frozen=True, slots=True)
class HostNotice:
    """Something the server says needs attention (an unread alert, an update…)."""

    title: str
    importance: str = "info"  # info | warning | alert
    detail: str = ""


@dataclass(frozen=True, slots=True)
class HostReport:
    hostname: str | None = None
    os: str | None = None
    version: str | None = None
    uptime_seconds: float | None = None
    cpu_name: str | None = None
    cpu_cores: int | None = None
    cpu_percent: float | None = None
    load: tuple[float, float, float] | None = None
    memory: Usage | None = None
    swap: Usage | None = None
    storage: Usage | None = None  # the whole (array capacity, or the file systems together)
    array_state: str | None = None  # Unraid: STARTED, STOPPED…
    parity: ParityCheck | None = None
    volumes: tuple[Volume, ...] = ()
    sensors: tuple[Sensor, ...] = ()
    interfaces: tuple[Interface, ...] = ()
    containers: tuple[Container, ...] = ()
    notices: tuple[HostNotice, ...] = ()
    warnings: tuple[str, ...] = ()  # stable codes: storage_low, disk_errors, array_stopped, temperature_high…


@runtime_checkable
class HostReporter(Protocol):
    async def report(self) -> HostReport: ...


class ReportCache:
    """#52: servers answer slowly or one request at a time — a report a few seconds old is served at
    once (and refreshed in the background, once), callers asking together share one request, and a first
    ask waits at most ``wait`` seconds (the report keeps coming for the next ask)."""

    def __init__(self, fresh: float = 20.0, keep: float = 600.0, wait: float = 4.0) -> None:
        self.fresh, self.keep, self.wait = fresh, keep, wait
        self._values: dict[str, tuple[float, Any]] = {}
        self._running: dict[str, Any] = {}

    async def get(self, key: str, load: Any) -> Any:
        import asyncio
        import contextlib
        import time

        now = time.monotonic()
        cached = self._values.get(key)
        task = self._running.get(key)
        if task is None and (cached is None or now - cached[0] > self.fresh):

            async def run() -> None:
                try:
                    self._values[key] = (time.monotonic(), await load())
                finally:
                    self._running.pop(key, None)

            task = asyncio.ensure_future(run())
            self._running[key] = task
        if cached is not None and now - cached[0] <= self.keep:
            return cached[1]
        if task is not None:
            with contextlib.suppress(Exception):  # too slow or failed: said as « not there yet »
                await asyncio.wait_for(asyncio.shield(task), timeout=self.wait)
        found = self._values.get(key)
        return found[1] if found else None


def host_warnings(report: HostReport, *, storage_low: float = 95.0) -> tuple[str, ...]:
    """What deserves attention in a report (also what makes a probe warn): a volume almost full, a device
    not OK or with errors, the array not started, a sensor at its critical value."""
    codes: list[str] = []
    for volume in report.volumes:
        if volume.kind in ("share", "boot"):
            continue
        if volume.used is not None and volume.total and 100 * volume.used / volume.total >= storage_low:
            codes.append("storage_low")
        if not volume.ok:
            codes.append("disk_problem")
        if volume.errors:
            codes.append("disk_errors")
    if report.array_state and report.array_state.upper() not in ("STARTED", "STARTING"):
        codes.append("array_stopped")
    for sensor in report.sensors:
        if sensor.critical is not None and sensor.value >= sensor.critical:
            codes.append("temperature_high")
    return tuple(dict.fromkeys(codes))


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


# --- alerting (027): what an outage does, by importance --------------------------------------------------
IMPORTANCES: tuple[str, ...] = ("critical", "major", "minor", "internal")


@dataclass(frozen=True, slots=True)
class AlertRule:
    """What an outage (``unavailable``) of a service does. The administrator sets one rule per importance
    (``health.alertRules``); a service may override any field (``ServiceInfo.alerting``)."""

    incident: bool = True  # declare an incident when the outage lasts
    incident_after: int = 10  # minutes unavailable before the incident
    auto_resolve: bool = True  # the portal's incident is closed when the service is back
    notify_after: int = 5  # minutes unavailable before members and administrators are told (0: at once)
    notify_members: bool = True  # holders of services.read (administrators apart)
    notify_admins: bool = True  # holders of services.manage
    email_members: bool = False
    email_admins: bool = False
    degrades_portal: bool = True  # counts in the portal's health (header indicator, status page)
    banner: bool = False  # the incident is also a banner across the portal while it is open


ALERT_FLAGS: tuple[str, ...] = (
    "incident",
    "auto_resolve",
    "notify_members",
    "notify_admins",
    "email_members",
    "email_admins",
    "degrades_portal",
    "banner",
)
ALERT_DELAYS: tuple[str, ...] = ("incident_after", "notify_after")
MAX_ALERT_DELAY = 1440  # minutes (a day)

DEFAULT_ALERT_RULES: dict[str, AlertRule] = {
    "critical": AlertRule(incident_after=5, notify_after=0, email_admins=True, banner=True),
    "major": AlertRule(),
    "minor": AlertRule(incident_after=30, notify_after=15, notify_members=False),
    "internal": AlertRule(incident=False, notify_after=15, notify_members=False, degrades_portal=False),
}


def clean_alerting(values: Mapping[str, Any] | None) -> dict[str, Any]:
    """The known fields of a rule (or overrides), with their types — anything else is dropped."""
    out: dict[str, Any] = {}
    for name, value in (values or {}).items():
        if value is None:
            continue
        if name in ALERT_FLAGS and isinstance(value, bool):
            out[name] = value
        elif name in ALERT_DELAYS and isinstance(value, int) and not isinstance(value, bool):
            out[name] = max(0, min(MAX_ALERT_DELAY, value))
    return out


def alert_rule(
    rules: Mapping[str, Mapping[str, Any]] | None, importance: str, overrides: Mapping[str, Any] | None = None
) -> AlertRule:
    """The rule in force for a service: the default of its importance, then the administrator's rule for
    that importance, then the service's own overrides."""
    base = DEFAULT_ALERT_RULES.get(importance, DEFAULT_ALERT_RULES["major"])
    configured = clean_alerting((rules or {}).get(importance))
    return replace(base, **{**configured, **clean_alerting(overrides)})


def alert_rules(rules: Mapping[str, Mapping[str, Any]] | None) -> dict[str, AlertRule]:
    return {importance: alert_rule(rules, importance) for importance in IMPORTANCES}


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
    # 027: how much it matters, and its own overrides of that importance's alerting rules (``AlertRule``)
    importance: str = "major"
    alerting: Mapping[str, Any] = field(default_factory=dict)


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


# 027: the severity of the incident an outage declares, by the service's importance
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
        banner: bool = False,
    ) -> IncidentRef:
        """Idempotent per ``(source, dedup_key)`` (016): a repeated escalation returns the same incident.
        ``severity`` accepts ``minor|major|critical`` (or 025's ``info|warning|critical``); ``banner`` also
        shows it as a banner across the portal while it is open."""
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


# --- the metrics over time (#52, provided by health) ------------------------------------------------------
@runtime_checkable
class InfraHistory(Protocol):
    def services(self) -> list[str]:
        """The services that report metrics."""
        ...

    async def series(
        self, service_id: str, metrics: Sequence[str], since: datetime, *, points: int = 240
    ) -> Mapping[str, list[tuple[datetime, float]]]:
        """Each metric's samples since ``since``, averaged down to about ``points`` points."""
        ...

    async def current(self, service_id: str, metrics: Sequence[str]) -> Mapping[str, MetricValue | None]:
        """The values right now (asked to the service, not stored)."""
        ...


def _spec(name: str, protocol: type[Any], multi: bool, description: str) -> CapabilitySpec:
    return CapabilitySpec(
        name=name, version="1.0", protocol=protocol, multi_provider=multi, description=description
    )


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(HEALTH_PROBE, HealthProbe, True, "Health probe of one service (provided per service)"),
    _spec(INFRA_METRICS, InfrastructureMetrics, True, "Infrastructure metrics of one service's host"),
    _spec(INFRA_HOST, HostReporter, True, "A server's full picture: disks, array, containers, updates"),
    _spec(INFRA_HISTORY, InfraHistory, False, "Infrastructure metrics over time (charts)"),
    _spec(SERVER_OPERATIONS, ServerOperations, True, "Privileged server operations of one service"),
    _spec(SERVICE_DIRECTORY, ServiceDirectory, False, "Configured services and their sync state (005)"),
    _spec(SERVICE_STATE, ServiceStateReader, False, "Derived service health state (006)"),
    _spec(INCIDENTS, Incidents, False, "Incident lifecycle (Support 016)"),
    _spec(SERVICE_TICKETS, ServiceTickets, False, "Tickets about a service (Support 016)"),
)
