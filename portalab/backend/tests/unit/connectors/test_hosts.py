"""#49/#50 — the server connectors read what Glances and Unraid answer into one ``HostReport``: storage
without the images and the container's own mounts, the processor from Glances' averaged reading,
containers and their updates, an array and its disks; what deserves attention becomes warnings (which
make a probe warn: the service is degraded, never counted as down)."""

import json
from pathlib import Path

from portalab.capabilities.health import HostReport, Sensor, Volume, host_warnings
from portalab.connectors.glances import build_report as glances_report
from portalab.connectors.glances import metrics_of, parse_uptime
from portalab.connectors.unraid import build_report as unraid_report
from portalab.modules.health.state.deriver import Inputs, Thresholds, derive

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "glances_unraid.json").read_text())


def test_glances_report_from_a_real_server() -> None:
    report = glances_report(FIXTURE)
    assert report.hostname == "Tower" and report.cpu_cores == 20
    assert report.cpu_name and "i5" in report.cpu_name
    assert report.uptime_seconds and report.uptime_seconds > 86400
    mounts = [v.mount for v in report.volumes]
    assert "/mnt/disk1" in mounts and "/mnt/cache" in mounts
    assert "/" not in mounts and not any(m and m.startswith("/etc/") for m in mounts)  # images, own mounts
    assert report.storage and report.storage.total == sum(v.total or 0 for v in report.volumes)
    assert [i.name for i in report.interfaces] == ["br0", "wg0"]  # no loopback, no veth
    assert report.containers[-1].state == "exited"  # running first
    metrics = metrics_of(report, ["cpu", "ram", "storage", "temperature", "gpu"])
    assert metrics["ram"].unit == "%" and metrics["temperature"].unit == "°C"  # type: ignore[union-attr]
    assert type(metrics["gpu"]).__name__ == "NotAvailable"


def test_uptime_and_warnings() -> None:
    assert parse_uptime("17 days, 11:16:45") == ((17 * 24 + 11) * 60 + 16) * 60 + 45
    assert parse_uptime("1 day, 0:00:01") == 86401 and parse_uptime("2:00:00") == 7200
    full = HostReport(
        volumes=(Volume("disk1", "disk", used=96, total=100), Volume("disk2", "disk", ok=False, errors=3)),
        sensors=(Sensor("Core 0", 101, critical=100),),
        array_state="STOPPED",
    )
    assert host_warnings(full) == (
        "storage_low",
        "disk_problem",
        "disk_errors",
        "array_stopped",
        "temperature_high",
    )
    assert host_warnings(HostReport(volumes=(Volume("share", "share", used=99, total=100),))) == ()


def test_unraid_report() -> None:
    data = {
        "info": {
            "os": {"hostname": "Tower", "uptime": 3600},
            "versions": {"core": {"unraid": "7.2.0"}},
            "cpu": {
                "brand": "Gen Intel® Core™ i5-13500",
                "cores": 14,
                "threads": 20,
                "packages": {"temp": [45], "totalPower": 30},
            },
        },
        "metrics": {
            "cpu": {"percentTotal": 12.5},
            "memory": {"total": 1000, "used": 980, "available": 400, "percentTotal": 98},
        },
        "array": {
            "state": "STARTED",
            "capacity": {"kilobytes": {"free": "100", "used": "900", "total": "1000"}},
            "parities": [{"name": "parity", "status": "DISK_OK", "temp": 35, "size": 1000, "numErrors": 0}],
            "disks": [
                {
                    "name": "disk1",
                    "status": "DISK_OK",
                    "temp": 33,
                    "fsSize": 500,
                    "fsUsed": 490,
                    "numErrors": 0,
                },
                {"name": "disk2", "status": "DISK_NP"},
            ],
            "caches": [{"name": "cache", "status": "DISK_OK", "fsSize": 100, "fsUsed": 10, "numErrors": 2}],
            "parityCheckStatus": {
                "status": "RUNNING",
                "progress": 25,
                "errors": 0,
                "running": True,
                "duration": 3600,
                "speed": "180 MB/s",
            },
        },
        "docker": {
            "containers": [
                {"names": ["/plex"], "state": "RUNNING", "image": "plex", "isUpdateAvailable": False},
                {"names": ["/sonarr"], "state": "RUNNING", "image": "sonarr", "isUpdateAvailable": True},
            ]
        },
        "notifications": {
            "list": [{"title": "Unraid OS", "subject": "7.2.1 is out", "importance": "WARNING"}]
        },
    }
    report = unraid_report(data)
    assert report.os == "Unraid 7.2.0" and report.cpu_cores == 20 and report.cpu_percent == 12.5
    assert report.cpu_name == "Intel Core i5-13500"
    assert report.memory is not None and report.memory.used == 600  # total - available, not the cache
    assert report.storage is not None and report.storage.total == 1000 * 1024
    assert [v.name for v in report.volumes] == ["parity", "disk1", "cache"]  # the empty slot is left out
    assert report.volumes[0].used is None  # a parity disk holds no files
    assert report.parity is not None and report.parity.progress == 25 and report.parity.running
    assert report.parity.elapsed_seconds == 3600 and report.parity.remaining_seconds == 3 * 3600
    assert report.containers[0].name == "sonarr" and report.containers[0].update_available  # updates first
    assert report.notices[0].importance == "warning"
    assert report.warnings == ("storage_low", "disk_errors")  # disk1 98 % full; the cache has errors


def test_a_warning_degrades_without_counting_as_an_outage() -> None:
    from datetime import UTC, datetime

    now = datetime(2026, 10, 10, tzinfo=UTC)
    base = {
        "now": now,
        "connection_state": "enabled",
        "last_check_at": now,
        "last_ok": True,
        "last_latency_ms": 20.0,
        "consecutive_failures": 0,
        "maintenance_active": False,
    }
    assert derive(Inputs(**base), Thresholds()).state == "operational"
    assert derive(Inputs(**base, last_warning=True), Thresholds()).state == "degraded"
