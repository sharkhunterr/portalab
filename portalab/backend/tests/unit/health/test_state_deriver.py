"""006 T005 — state derivation table: probes, latency, failures, staleness, maintenance, breaker."""

from datetime import UTC, datetime, timedelta

import pytest

from portalab.modules.health.state.deriver import Inputs, Thresholds, derive

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
T = Thresholds(degraded_latency_ms=1000, unavailable_after_failures=3, stale_after_seconds=300)


def inputs(**overrides: object) -> Inputs:
    base: dict[str, object] = {
        "now": NOW,
        "connection_state": "enabled",
        "last_check_at": NOW - timedelta(seconds=30),
        "last_ok": True,
        "last_latency_ms": 50.0,
        "consecutive_failures": 0,
        "maintenance_active": False,
    }
    return Inputs(**(base | overrides))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "state", "reason"),
    [
        ({}, "operational", "probe"),
        ({"last_latency_ms": 2500.0}, "degraded", "latency"),
        ({"consecutive_failures": 1, "last_ok": False}, "degraded", "probe"),
        ({"consecutive_failures": 3, "last_ok": False}, "unavailable", "probe"),
        ({"last_check_at": None, "last_ok": None}, "unknown", "stale"),
        ({"last_check_at": NOW - timedelta(minutes=10)}, "unknown", "stale"),  # stale is never Operational
        ({"maintenance_active": True, "consecutive_failures": 5}, "maintenance", "maintenance"),
        ({"connection_state": "unavailable"}, "unavailable", "breaker"),
        ({"connection_state": "error"}, "degraded", "breaker"),
        ({"connection_state": "disabled"}, "unknown", "inactive"),
        ({"connection_state": None}, "unknown", "inactive"),
        ({"maintenance_active": True, "connection_state": "unavailable"}, "maintenance", "maintenance"),
    ],
)
def test_table(overrides: dict[str, object], state: str, reason: str) -> None:
    derived = derive(inputs(**overrides), T)
    assert (derived.state, derived.reason) == (state, reason)


def test_maintenance_reverts_after() -> None:
    assert derive(inputs(maintenance_active=True), T).state == "maintenance"
    assert derive(inputs(maintenance_active=False), T).state == "operational"


def test_deterministic() -> None:
    sample = inputs(consecutive_failures=2, last_ok=False)
    assert derive(sample, T) == derive(sample, T)
