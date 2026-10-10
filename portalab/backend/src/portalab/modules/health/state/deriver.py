"""StateDeriver (T007; R1, FR-001..003): Service State is derived, never set by hand.

A pure, deterministic function of its inputs (versioned rules, ``RULES_VERSION``), evaluated in this order:

1. an active maintenance window ⇒ **maintenance** (never Unavailable during planned work);
2. the service is not monitored (not enabled in Connectors) ⇒ **unknown**;
3. the service's circuit breaker is open (Connectors ``unavailable``) ⇒ **unavailable**;
4. no probe yet, or the last probe is older than ``stale_after`` ⇒ **unknown** (never Operational);
5. ``unavailable_after`` consecutive failed probes ⇒ **unavailable**;
6. a failed last probe (fewer failures), a connector-reported error, a latency above the threshold or a
   probe that answered with a warning (#49/#50) ⇒ **degraded**;
7. otherwise **operational**.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from portalab.capabilities.health import HealthState

RULES_VERSION = 1
Reason = Literal["probe", "breaker", "stale", "maintenance", "inactive", "latency", "warning"]
MONITORED = frozenset({"enabled", "error", "unavailable", "maintenance"})


@dataclass(frozen=True, slots=True)
class Inputs:
    now: datetime
    connection_state: str | None  # 005 state; None when the service is unknown to Connectors
    last_check_at: datetime | None
    last_ok: bool | None
    last_latency_ms: float | None
    consecutive_failures: int
    maintenance_active: bool
    last_warning: bool = False  # #49/#50: the last probe answered but reported a problem


@dataclass(frozen=True, slots=True)
class Thresholds:
    degraded_latency_ms: int = 1500
    unavailable_after_failures: int = 3
    stale_after_seconds: int = 300


@dataclass(frozen=True, slots=True)
class Derived:
    state: HealthState
    reason: Reason


def derive(inputs: Inputs, thresholds: Thresholds) -> Derived:
    if inputs.maintenance_active:
        return Derived("maintenance", "maintenance")
    if inputs.connection_state not in MONITORED:
        return Derived("unknown", "inactive")
    if inputs.connection_state == "unavailable":
        return Derived("unavailable", "breaker")
    if inputs.last_check_at is None or inputs.now - inputs.last_check_at > timedelta(
        seconds=thresholds.stale_after_seconds
    ):
        return Derived("unknown", "stale")
    if inputs.consecutive_failures >= thresholds.unavailable_after_failures:
        return Derived("unavailable", "probe")
    if inputs.consecutive_failures > 0 or inputs.last_ok is False:
        return Derived("degraded", "probe")
    if inputs.connection_state == "error":
        return Derived("degraded", "breaker")
    if inputs.last_latency_ms is not None and inputs.last_latency_ms > thresholds.degraded_latency_ms:
        return Derived("degraded", "latency")
    if inputs.last_warning:
        return Derived("degraded", "warning")
    return Derived("operational", "probe")
