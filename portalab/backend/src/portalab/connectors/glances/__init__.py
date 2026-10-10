"""``glances`` connector: Glances, the system monitor (#49) — a server's processor, memory, temperatures,
file systems, network and containers, read from its REST API (``/api/4``, Glances 4).

* ``service.health_probe``: ``/api/4/status``; the probe *warns* (the service is degraded, not down) when a
  file system is almost full or a sensor reaches its critical value.
* ``infrastructure.metrics``: cpu (%), ram (%), storage (% of the file systems), network (Mbit/s, in and
  out together), temperature (the hottest sensor, °C).
* ``infrastructure.host``: the full picture (``HostReport``).

Glances usually runs without authentication on the LAN; when it is started with ``--password``, give the
username and the password (HTTP basic).
"""

import asyncio
import base64
import re
import time
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field

from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle
from portalab.capabilities.health import (
    HEALTH_PROBE,
    INFRA_HOST,
    INFRA_METRICS,
    Container,
    HostReport,
    Interface,
    MetricValue,
    NotAvailable,
    ProbeResult,
    Sensor,
    Usage,
    Volume,
    host_warnings,
)
from portalab.capabilities.results import InvalidPayload, ProviderAuthError
from portalab.connectors.http_base import BaseConfig, HttpConnector, binding

API = "/api/4"
PARALLEL = 2  # more requests at once and Glances times out
# file systems that say nothing about the storage: images, overlays, virtual ones
IGNORED_FS = frozenset(
    {"squashfs", "tmpfs", "devtmpfs", "overlay", "proc", "sysfs", "cgroup", "nsfs", "ramfs"}
)
IGNORED_MOUNTS = re.compile(r"^/(var/lib/docker|run|dev|sys|proc|boot/efi|snap|etc)(/|$)|/docker/")
IGNORED_DEVICES = re.compile(r"^/dev/(loop|zram)")  # images (docker.img) and memory, not storage
IGNORED_INTERFACES = re.compile(r"^(lo|veth|docker|br-|virbr|vnet|tun|tap|shim)")
UPTIME = re.compile(r"(?:(\d+)\s+days?,\s*)?(\d+):(\d+):(\d+)")


class GlancesConfig(BaseConfig):
    username: str | None = Field(
        default=None,
        max_length=120,
        title="Username",
        description="Only when Glances is protected by a password (started with --password).",
    )


def parse_uptime(value: Any) -> float | None:
    """« 17 days, 11:16:45 », « 1 day, 2:03:04 » or « 11:16:45 » → seconds."""
    if isinstance(value, int | float):
        return float(value)
    match = UPTIME.search(str(value or ""))
    if not match:
        return None
    days, hours, minutes, seconds = (int(g or 0) for g in match.groups())
    return float(((days * 24 + hours) * 60 + minutes) * 60 + seconds)


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


class GlancesConnector(HttpConnector):
    key = "glances"
    name = "Glances"
    description = "A server's processor, memory, temperatures, disks, network and containers."
    icon = "cpu"
    category = "infrastructure"
    config_schema: type[BaseModel] = GlancesConfig
    secret_fields: frozenset[str] = frozenset({"password"})
    provides: Sequence[CapabilityBinding] = (
        binding(HEALTH_PROBE),
        binding(INFRA_METRICS),
        binding(INFRA_HOST),
    )
    status_path = f"{API}/status"

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        username = str(service.config.get("username") or "")
        if not username:
            return {}
        token = base64.b64encode(f"{username}:{service.secrets.get('password', '')}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    def describe(self, status: Any) -> str:
        if not isinstance(status, Mapping) or "version" not in status:
            raise InvalidPayload("not a Glances status")
        return f"Glances {status['version']}"

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        if capability == INFRA_METRICS:
            return _Metrics(self, service)
        if capability == INFRA_HOST:
            return _Host(self, service)
        return None

    async def _get(self, service: ServiceHandle, plugin: str) -> Any:
        """One plugin's answer, or ``None`` when that plugin is off or fails (the others still count)."""
        try:
            return await self.get_json(service, f"{API}/{plugin}")
        except ProviderAuthError:
            raise
        except Exception:
            return None

    async def report(self, service: ServiceHandle, plugins: Sequence[str] | None = None) -> HostReport:
        wanted = plugins or (
            "system",
            "uptime",
            "core",
            "quicklook",
            "mem",
            "memswap",
            "load",
            "sensors",
            "fs",
            "network",
            "containers",
        )
        gate = asyncio.Semaphore(PARALLEL)  # Glances' web server answers one request at a time

        async def one(plugin: str) -> Any:
            async with gate:
                return await self._get(service, plugin)

        results = await asyncio.gather(*(one(p) for p in wanted))
        answers = dict(zip(wanted, results, strict=True))
        if all(answer is None for answer in answers.values()):
            raise ConnectionError("Glances did not answer")
        return build_report(answers)


def build_report(answers: Mapping[str, Any]) -> HostReport:
    """A ``HostReport`` from the plugins' answers (each may be missing)."""
    system = _map(answers.get("system"))
    cpu = _map(answers.get("cpu"))
    core = _map(answers.get("core"))
    quick = _map(answers.get("quicklook"))
    mem = _map(answers.get("mem"))
    swap = _map(answers.get("memswap"))
    load = _map(answers.get("load"))
    volumes = []
    for fs in _list(answers.get("fs")):
        mount = str(fs.get("mnt_point") or "")
        if (
            str(fs.get("fs_type") or "") in IGNORED_FS
            or IGNORED_MOUNTS.search(mount)
            or IGNORED_DEVICES.match(str(fs.get("device_name") or ""))
        ):
            continue
        total = _number(fs.get("size"))
        if not total:
            continue
        volumes.append(
            Volume(
                name=mount or str(fs.get("device_name") or "?"),
                kind="filesystem",
                used=_number(fs.get("used")),
                total=total,
                mount=mount or None,
            )
        )
    sensors = tuple(
        Sensor(
            label=str(s.get("label") or "?"),
            value=float(s["value"]),
            unit="°C" if str(s.get("unit") or "C") == "C" else str(s.get("unit")),
            warning=_number(s.get("warning")),
            critical=_number(s.get("critical")),
        )
        for s in _list(answers.get("sensors"))
        if _number(s.get("value")) is not None
    )
    interfaces = tuple(
        Interface(
            name=str(i.get("interface_name")),
            rx_bps=_number(i.get("bytes_recv_rate_per_sec")),
            tx_bps=_number(i.get("bytes_sent_rate_per_sec")),
        )
        for i in _list(answers.get("network"))
        if i.get("interface_name") and not IGNORED_INTERFACES.match(str(i.get("interface_name")))
    )
    containers = []
    for c in _list(answers.get("containers")):
        image = c.get("image")
        cpu_block = _map(c.get("cpu"))
        containers.append(
            Container(
                name=str(c.get("name") or "?"),
                state=str(c.get("status") or "unknown").lower(),
                image=str(image[0]) if isinstance(image, list) and image else (str(image) if image else None),
                cpu_percent=_number(c.get("cpu_percent")) or _number(cpu_block.get("total")),
                memory_bytes=_number(c.get("memory_usage")),
            )
        )
    used = sum(v.used or 0 for v in volumes)
    total = sum(v.total or 0 for v in volumes)
    mem_total = _number(mem.get("total"))
    swap_total = _number(swap.get("total"))
    loads = tuple(_number(load.get(k)) for k in ("min1", "min5", "min15"))
    report = HostReport(
        hostname=str(system.get("hostname")) if system.get("hostname") else None,
        os=str(system.get("hr_name") or system.get("os_name") or "") or None,
        version=str(system.get("os_version")) if system.get("os_version") else None,
        uptime_seconds=parse_uptime(answers.get("uptime")),
        cpu_name=str(quick.get("cpu_name")) if quick.get("cpu_name") else None,
        cpu_cores=int(core["log"]) if isinstance(core.get("log"), int) else None,
        # « quicklook » averages over Glances' own refresh; « cpu » reads 0 when asked too often
        cpu_percent=_number(quick.get("cpu"))
        if _number(quick.get("cpu")) is not None
        else _number(cpu.get("total")),
        load=(loads[0], loads[1], loads[2]) if all(x is not None for x in loads) else None,  # type: ignore[arg-type]
        memory=Usage(used=_number(mem.get("used")) or 0, total=mem_total) if mem_total else None,
        swap=Usage(used=_number(swap.get("used")) or 0, total=swap_total) if swap_total else None,
        storage=Usage(used=used, total=total) if total else None,
        volumes=tuple(volumes),
        sensors=sensors,
        interfaces=interfaces,
        containers=tuple(sorted(containers, key=lambda c: (c.state != "running", c.name.lower()))),
    )
    return HostReport(**{**_fields(report), "warnings": host_warnings(report)})


def _fields(report: HostReport) -> dict[str, Any]:
    return {name: getattr(report, name) for name in HostReport.__dataclass_fields__}


def metrics_of(report: HostReport, wanted: Sequence[str]) -> dict[str, MetricValue | NotAvailable]:
    """``infrastructure.metrics`` values from a report — a metric the host does not report says so."""
    out: dict[str, MetricValue | NotAvailable] = {}
    for metric in wanted:
        value: MetricValue | None = None
        if metric == "cpu" and report.cpu_percent is not None:
            value = MetricValue(round(report.cpu_percent, 1), "%")
        elif metric == "ram" and report.memory and report.memory.total:
            value = MetricValue(round(100 * report.memory.used / report.memory.total, 1), "%")
        elif metric == "storage" and report.storage and report.storage.total:
            value = MetricValue(round(100 * report.storage.used / report.storage.total, 1), "%")
        elif metric == "network" and report.interfaces:
            total = sum((i.rx_bps or 0) + (i.tx_bps or 0) for i in report.interfaces)
            value = MetricValue(round(total * 8 / 1_000_000, 2), "Mbit/s")
        elif metric == "temperature":
            temps = [s.value for s in report.sensors if s.unit == "°C"]
            if temps:
                value = MetricValue(max(temps), "°C")
        out[metric] = value if value is not None else NotAvailable("not reported by the host")
    return out


class _Host:
    def __init__(self, connector: GlancesConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def report(self) -> HostReport:
        return await self.connector.report(self.service)


class _Metrics:
    def __init__(self, connector: GlancesConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def fetch(self, metrics: list[str]) -> dict[str, MetricValue | NotAvailable]:
        plugins = ("quicklook", "mem", "fs", "network", "sensors")
        return metrics_of(await self.connector.report(self.service, plugins), metrics)


class _Probe:
    """Answers? Then warns on a nearly full file system or a sensor at its critical value."""

    def __init__(self, connector: GlancesConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def probe(self) -> ProbeResult:
        started = time.monotonic()
        try:
            await self.connector.get_json(self.service, self.connector.status_path)
        except ProviderAuthError:
            return ProbeResult(reachable=True, error_code="auth", detail="Glances rejected the credentials.")
        except InvalidPayload:
            return ProbeResult(reachable=True, error_code="invalid_response", detail="Unexpected answer.")
        except (ConnectionError, OSError):
            return ProbeResult(reachable=False, error_code="unreachable", detail="Glances cannot be reached.")
        latency = round((time.monotonic() - started) * 1000, 1)
        try:
            report = await self.connector.report(self.service, ("fs", "sensors"))
        except Exception:
            return ProbeResult(reachable=True, latency_ms=latency)
        if not report.warnings:
            return ProbeResult(reachable=True, latency_ms=latency)
        return ProbeResult(
            reachable=True,
            latency_ms=latency,
            warning=report.warnings[0],
            detail=describe_warnings(report),
        )


def describe_warnings(report: HostReport) -> str:
    parts = []
    for volume in report.volumes:
        if volume.used is not None and volume.total and volume.used / volume.total >= 0.95:
            parts.append(f"{volume.name} is {round(100 * volume.used / volume.total)} % full")
        if not volume.ok:
            parts.append(f"{volume.name}: {volume.state or 'problem'}")
        if volume.errors:
            parts.append(f"{volume.name}: {volume.errors} errors")
    if "array_stopped" in report.warnings:
        parts.append(f"the array is {str(report.array_state or 'stopped').lower()}")
    parts.extend(
        f"{s.label} at {s.value:g} {s.unit}"
        for s in report.sensors
        if s.critical is not None and s.value >= s.critical
    )
    return "; ".join(parts)[:480] or "The server reports a problem."
