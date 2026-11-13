"""``unraid`` connector: an Unraid server through its API (#50) — the array (state, parity, disks with their
space, temperature and errors), the cache pools, the processor and memory, the Docker containers with
their available updates, and the server's unread notifications (where Unraid says an update is out).

The API is GraphQL (``/graphql``), authenticated by an API key (*Settings → Management Access → API Keys*,
read access is enough) sent as ``x-api-key``. Unraid usually serves a self-signed certificate: untick
« Check the HTTPS certificate » for it.

* ``service.health_probe``: the array; the probe *warns* (degraded, not down) when the array is not
  started, a disk is not OK or has errors, or the array is almost full.
* ``infrastructure.metrics``: cpu (%), ram (%), storage (% of the array), temperature (the hottest disk or
  processor, °C).
* ``infrastructure.host``: the full picture (``HostReport``).
"""

import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle, TestResult
from portalab.capabilities.health import (
    HEALTH_PROBE,
    INFRA_HOST,
    INFRA_METRICS,
    Container,
    HostNotice,
    HostReport,
    MetricValue,
    NotAvailable,
    ParityCheck,
    ProbeResult,
    Sensor,
    Usage,
    Volume,
    host_warnings,
)
from portalab.capabilities.results import InvalidPayload, ProviderAuthError
from portalab.connectors.glances import describe_warnings
from portalab.connectors.http_base import HttpConnector, binding, parse_time

ENDPOINT = "/graphql"
KB = 1024  # the array's sizes are in kilobytes

# each part asked on its own when the server's API does not know a field (an older Unraid)
SECTIONS: dict[str, str] = {
    "info": """info {
      os { hostname uptime release distro }
      versions { core { unraid } }
      cpu { brand cores threads packages { temp totalPower } }
    }""",
    "metrics": "metrics { cpu { percentTotal } memory { total used free available percentTotal } }",
    "array": """array {
      state
      capacity { kilobytes { free used total } }
      parities { name status temp size numErrors }
      disks { name status temp size numErrors fsSize fsFree fsUsed isSpinning }
      caches { name status temp size numErrors fsSize fsFree fsUsed }
      parityCheckStatus { status progress running errors speed date duration paused correcting }
    }""",
    # the check under way, as the array driver counts it (parityCheckStatus may still tell the last one)
    # (not mdResync nor mdResyncSize: past 2^31 kilobytes the API cannot tell them — the parity disk's size
    # says how long the check is, the kilobytes done in the last sample whether it moves)
    "resync": "vars { mdResyncPos mdResyncDt mdResyncDb }",
    "docker": "docker { containers { names state status image isUpdateAvailable autoStart } }",
    "notifications": """notifications {
      list(filter: {type: UNREAD, offset: 0, limit: 20}) { title subject description importance timestamp }
    }""",
}
STATUS_QUERY = "query PortalabStatus { info { os { hostname } versions { core { unraid } } } }"
PROBE_QUERY = f"query PortalabProbe {{ {SECTIONS['array']} }}"


class UnraidConnector(HttpConnector):
    key = "unraid"
    name = "Unraid"
    description = "The array, disks, space, temperatures, containers and updates of an Unraid server."
    icon = "database"
    category = "infrastructure"
    secret_fields: frozenset[str] = frozenset({"api_key"})
    provides: Sequence[CapabilityBinding] = (
        binding(HEALTH_PROBE),
        binding(INFRA_METRICS),
        binding(INFRA_HOST),
    )
    status_path = ENDPOINT

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        return {"x-api-key": service.secrets.get("api_key", "")}

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        if capability == INFRA_METRICS:
            return _Metrics(self, service)
        if capability == INFRA_HOST:
            return _Host(self, service)
        return None

    async def query(self, service: ServiceHandle, document: str) -> tuple[dict[str, Any], list[Any]]:
        """``(data, errors)`` of a GraphQL query; an unauthenticated answer raises ``ProviderAuthError``."""
        answer = await self.request(service, "POST", ENDPOINT, json_body={"query": document})
        if not isinstance(answer, Mapping):
            raise InvalidPayload("not a GraphQL answer")
        raw_errors = answer.get("errors")
        errors: list[Any] = list(raw_errors) if isinstance(raw_errors, list) else []
        codes = {str((e.get("extensions") or {}).get("code") or "") for e in errors if isinstance(e, Mapping)}
        if codes & {"UNAUTHENTICATED", "FORBIDDEN"}:
            raise ProviderAuthError("Unraid rejected the API key")
        data = _map(answer.get("data"))
        if not data and errors:
            raise InvalidPayload("; ".join(str(e.get("message")) for e in errors if isinstance(e, Mapping)))
        return dict(data), errors

    async def gather(self, service: ServiceHandle, sections: Sequence[str]) -> dict[str, Any]:
        """The asked parts in one query — or each on its own when the server does not know a field."""
        document = "query PortalabHost { " + " ".join(SECTIONS[s] for s in sections) + " }"
        try:
            data, errors = await self.query(service, document)
        except InvalidPayload:
            data, errors = {}, [{"retry": True}]
        if not errors:
            return data
        merged: dict[str, Any] = {}
        for section in sections:
            try:
                part, _ = await self.query(service, f"query PortalabPart {{ {SECTIONS[section]} }}")
            except ProviderAuthError:
                raise
            except Exception:  # noqa: S112 — a part the server cannot give is left out
                continue
            merged.update(part)
        if not merged:
            raise InvalidPayload("Unraid answered nothing usable")
        return merged

    async def report(self, service: ServiceHandle, sections: Sequence[str] | None = None) -> HostReport:
        return build_report(await self.gather(service, sections or tuple(SECTIONS)))

    async def test_connection(self, service: ServiceHandle) -> TestResult:
        try:
            data, _ = await self.query(service, STATUS_QUERY)
            info = _map(data.get("info"))
            os_ = _map(info.get("os"))
            core = _map(_map(info.get("versions")).get("core"))
            if not os_ and not core:
                raise InvalidPayload("not an Unraid server")
        except ProviderAuthError:
            return TestResult(
                ok=False,
                reachable=True,
                authenticated=False,
                detail="Unraid answered but refused the API key: check it (read access is enough).",
            )
        except InvalidPayload:
            return TestResult(
                ok=False,
                reachable=True,
                authenticated=False,
                compatible=False,
                detail="Something answered at this address, but not Unraid's API (/graphql).",
            )
        except (ConnectionError, OSError):
            return TestResult(
                ok=False,
                reachable=False,
                authenticated=False,
                detail="Cannot reach the server: check the address (https://…) and the certificate option.",
            )
        label = f"Unraid {core.get('unraid') or ''}".strip()
        if os_.get("hostname"):
            label = f"{label} ({os_['hostname']})"
        return TestResult(ok=True, reachable=True, authenticated=True, detail=f"Connected to {label}.")


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Mapping[str, Any]]:
    return [v for v in value if isinstance(v, Mapping)] if isinstance(value, list) else []


def _memory_used(memory: Mapping[str, Any], total: float) -> float:
    """What programs use: total - available (Unraid's « used » counts the disk cache too)."""
    available = _number(memory.get("available"))
    if available is not None and 0 <= available <= total:
        return total - available
    return _number(memory.get("used")) or 0.0


def _cpu_name(value: Any) -> str | None:
    """« Gen Intel® Core™ i5-13500 » (Unraid drops the generation) → « Intel Core i5-13500 »."""
    if not value:
        return None
    text = str(value).replace("®", "").replace("™", "").replace("(R)", "").replace("(TM)", "")
    text = " ".join(text.split())
    return text.removeprefix("Gen ")


def _resync(raw: Mapping[str, Any], resync: Mapping[str, Any]) -> Mapping[str, Any]:
    """The check under way as the array driver counts it (``vars.mdResync*``): Unraid's
    ``parityCheckStatus`` may still describe the last check while a new one runs — the counters win."""
    size = _number(resync.get("mdResyncSize")) or _number(resync.get("size"))
    position = _number(resync.get("mdResyncPos"))
    if not size or not position or position <= 0:
        return raw
    seconds, done = _number(resync.get("mdResyncDt")), _number(resync.get("mdResyncDb"))
    flag = _number(resync.get("mdResync"))  # an older API may still tell it (0: paused)
    active = bool(flag) if flag is not None else bool(seconds and done)
    progress = round(min(100.0, 100 * position / size), 1)
    speed = f"{done / seconds / 1024:.1f} MB/s" if active and seconds and done else raw.get("speed")
    return {
        **raw,
        # the time left at the driver's pace (kilobytes left over kilobytes a second)
        "_remaining": (size - position) / (done / seconds) if active and seconds and done else None,
        "status": "running" if active else "paused",
        "running": active,
        "paused": not active,
        "progress": progress,
        "speed": speed,
        # the last check's own dates are not this one's
        "date": None
        if str(raw.get("status") or "").lower() not in ("running", "paused")
        else raw.get("date"),
        "duration": None
        if str(raw.get("status") or "").lower() not in ("running", "paused")
        else raw.get("duration"),
    }


def _parity(raw: Mapping[str, Any], resync: Mapping[str, Any] | None = None) -> ParityCheck | None:
    """The parity check: its state, progress, time so far and (when running) the time left at its pace."""
    raw = _resync(raw, resync or {})
    if not raw:
        return None
    running = raw.get("running") is True
    paused = raw.get("paused") is True
    status = str(raw.get("status") or ("running" if running else "idle")).lower()
    progress = _number(raw.get("progress"))
    elapsed = _number(raw.get("duration"))
    started = parse_time(raw.get("date"))
    if elapsed is None and started is not None and (running or paused):
        elapsed = max(0.0, (datetime.now(UTC) - started).total_seconds())
    remaining = _number(raw.get("_remaining"))
    if remaining is None and (running or paused) and progress and 0 < progress < 100 and elapsed:
        remaining = elapsed * (100 - progress) / progress
    return ParityCheck(
        status=status,
        progress=progress,
        errors=int(_number(raw.get("errors")) or 0),
        speed=str(raw.get("speed")) if raw.get("speed") not in (None, "", "0", 0) else None,
        running=running,
        paused=paused,
        correcting=raw.get("correcting") if isinstance(raw.get("correcting"), bool) else None,
        started_at=started.isoformat() if started else None,
        elapsed_seconds=elapsed,
        remaining_seconds=remaining,
    )


def _uptime(value: Any) -> float | None:
    """Seconds — Unraid gives the boot time (ISO) or a number of seconds."""
    number = _number(value)
    if number is not None:
        return number
    booted = parse_time(value)
    return max(0.0, (datetime.now(UTC) - booted).total_seconds()) if booted else None


def _device(item: Mapping[str, Any], kind: str) -> Volume | None:
    status = str(item.get("status") or "")
    if status in ("DISK_NP", "DISK_NP_DSBL"):  # an empty slot
        return None
    total = _number(item.get("fsSize"))
    used = _number(item.get("fsUsed"))
    if total is None and item.get("size") is not None:
        total = _number(item.get("size"))
    temp = _number(item.get("temp"))
    return Volume(
        name=str(item.get("name") or kind),
        kind=kind,
        used=used * KB if used is not None and kind != "parity" else None,
        total=total * KB if total is not None else None,
        state=status or None,
        ok=status in ("", "DISK_OK"),
        temperature=temp if temp and temp > 0 else None,
        errors=int(_number(item.get("numErrors")) or 0) or None,
        spinning=item.get("isSpinning") if isinstance(item.get("isSpinning"), bool) else None,
    )


def build_report(data: Mapping[str, Any]) -> HostReport:
    info = _map(data.get("info"))
    os_ = _map(info.get("os"))
    cpu = _map(info.get("cpu"))
    metrics = _map(data.get("metrics"))
    array = _map(data.get("array"))
    capacity = _map(_map(array.get("capacity")).get("kilobytes"))
    volumes = [
        volume
        for kind, items in (
            ("parity", array.get("parities")),
            ("disk", array.get("disks")),
            ("cache", array.get("caches")),
        )
        for volume in (_device(item, kind) for item in _list(items))
        if volume is not None
    ]
    memory = _map(metrics.get("memory"))
    mem_total = _number(memory.get("total"))
    cap_total = _number(capacity.get("total"))
    parity_size = max((_number(p.get("size")) or 0 for p in _list(array.get("parities"))), default=0)
    parity = _parity(_map(array.get("parityCheckStatus")), {"size": parity_size, **_map(data.get("vars"))})
    packages = (
        _list(cpu.get("packages")) if isinstance(cpu.get("packages"), list) else [_map(cpu.get("packages"))]
    )
    sensors: list[Sensor] = []
    for index, package in enumerate(p for p in packages if p):
        temps = package.get("temp")
        for core_index, temp in enumerate(temps if isinstance(temps, list) else [temps]):
            value = _number(temp)
            if value and value > 0:
                label = (
                    "CPU" if len(packages) == 1 and core_index == 0 else f"CPU {index + 1}.{core_index + 1}"
                )
                sensors.append(Sensor(label=label, value=value))
    sensors.extend(
        Sensor(label=v.name, value=v.temperature, warning=50, critical=60)
        for v in volumes
        if v.temperature is not None
    )
    containers = []
    for c in _list(_map(data.get("docker")).get("containers")):
        names = c.get("names")
        name = names[0] if isinstance(names, list) and names else names
        containers.append(
            Container(
                name=str(name or "?").lstrip("/"),
                state=str(c.get("state") or "unknown").lower(),
                image=str(c.get("image")) if c.get("image") else None,
                update_available=c.get("isUpdateAvailable")
                if isinstance(c.get("isUpdateAvailable"), bool)
                else None,
            )
        )
    notices = tuple(
        HostNotice(
            title=str(n.get("title") or n.get("subject") or "Notification"),
            importance=str(n.get("importance") or "info").lower(),
            detail=str(n.get("description") or n.get("subject") or "")[:300],
        )
        for n in _list(_map(data.get("notifications")).get("list"))
    )
    version = _map(_map(info.get("versions")).get("core")).get("unraid")
    report = HostReport(
        hostname=str(os_.get("hostname")) if os_.get("hostname") else None,
        os=f"Unraid {version}" if version else (str(os_.get("distro")) if os_.get("distro") else "Unraid"),
        version=str(version) if version else (str(os_.get("release")) if os_.get("release") else None),
        uptime_seconds=_uptime(os_.get("uptime")),
        cpu_name=_cpu_name(cpu.get("brand")),
        cpu_cores=int(_number(cpu.get("threads")) or _number(cpu.get("cores")) or 0) or None,
        cpu_percent=_number(_map(metrics.get("cpu")).get("percentTotal")),
        memory=Usage(used=_memory_used(memory, mem_total), total=mem_total) if mem_total else None,
        storage=Usage(used=(_number(capacity.get("used")) or 0) * KB, total=cap_total * KB)
        if cap_total
        else None,
        array_state=str(array.get("state")) if array.get("state") else None,
        parity=parity,
        volumes=tuple(volumes),
        sensors=tuple(sensors),
        containers=tuple(
            sorted(
                containers,
                key=lambda c: (c.update_available is not True, c.state != "running", c.name.lower()),
            )
        ),
        notices=notices,
    )
    return HostReport(**{**_fields(report), "warnings": host_warnings(report)})


def _fields(report: HostReport) -> dict[str, Any]:
    return {name: getattr(report, name) for name in HostReport.__dataclass_fields__}


class _Host:
    def __init__(self, connector: UnraidConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def report(self) -> HostReport:
        return await self.connector.report(self.service)


class _Metrics:
    def __init__(self, connector: UnraidConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def fetch(self, metrics: list[str]) -> dict[str, MetricValue | NotAvailable]:
        report = await self.connector.report(self.service, ("info", "metrics", "array"))
        out: dict[str, MetricValue | NotAvailable] = {}
        for metric in metrics:
            value: MetricValue | None = None
            if metric == "cpu" and report.cpu_percent is not None:
                value = MetricValue(round(report.cpu_percent, 1), "%")
            elif metric == "ram" and report.memory and report.memory.total:
                value = MetricValue(round(100 * report.memory.used / report.memory.total, 1), "%")
            elif metric == "storage" and report.storage and report.storage.total:
                value = MetricValue(round(100 * report.storage.used / report.storage.total, 1), "%")
            elif metric == "temperature" and report.sensors:
                value = MetricValue(max(s.value for s in report.sensors), "°C")
            out[metric] = value if value is not None else NotAvailable("not reported by Unraid")
        return out


class _Probe:
    """The array: started, every disk OK and without errors, space left — or a warning."""

    def __init__(self, connector: UnraidConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def probe(self) -> ProbeResult:
        started = time.monotonic()
        try:
            data, _ = await self.connector.query(self.service, PROBE_QUERY)
        except ProviderAuthError:
            return ProbeResult(reachable=True, error_code="auth", detail="Unraid rejected the API key.")
        except InvalidPayload:
            return ProbeResult(reachable=True, error_code="invalid_response", detail="Unexpected answer.")
        except (ConnectionError, OSError):
            return ProbeResult(reachable=False, error_code="unreachable", detail="Unraid cannot be reached.")
        latency = round((time.monotonic() - started) * 1000, 1)
        report = build_report(data)
        if not report.warnings:
            return ProbeResult(reachable=True, latency_ms=latency)
        return ProbeResult(
            reachable=True, latency_ms=latency, warning=report.warnings[0], detail=describe_warnings(report)
        )
