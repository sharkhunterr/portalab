"""Rule-based anomaly detectors (T024; R4, FR-017): pure functions over numeric series, parameters from
configuration. A finding is an *observation that something is abnormal* — never an incident by itself;
escalation decides what happens next."""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["info", "warning", "critical"]


@dataclass(frozen=True, slots=True)
class Finding:
    detector: str
    component: str
    severity: Severity
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        return f"{self.detector}:{self.component}"[:64]


def error_spike(
    component: str, current: int, baseline: Sequence[int], *, factor: float, min_count: int
) -> Finding | None:
    """Errors in the current window far above the rolling baseline (mean of previous windows)."""
    mean = statistics.fmean(baseline) if baseline else 0.0
    if current >= min_count and current > factor * max(mean, 1.0):
        severity: Severity = "critical" if current > 2 * factor * max(mean, 1.0) else "warning"
        return Finding(
            "error_spike",
            component,
            severity,
            f"{current} errors vs a usual {mean:.1f}",
            {"current": current, "baseline_mean": round(mean, 2)},
        )
    return None


def long_sync(
    component: str, latest_ms: float, history_ms: Sequence[float], *, factor: float
) -> Finding | None:
    """A synchronization much longer than its median (needs some history)."""
    if len(history_ms) < 3:
        return None
    median = statistics.median(history_ms)
    if median > 0 and latest_ms > factor * median:
        return Finding(
            "long_sync",
            component,
            "warning",
            f"sync took {latest_ms / 1000:.1f}s vs a usual {median / 1000:.1f}s",
            {"latest_ms": latest_ms, "median_ms": median},
        )
    return None


def repeated_automation(component: str, executions: int, *, threshold: int) -> Finding | None:
    """One rule executed abnormally often in the window (possible loop)."""
    if executions >= threshold:
        return Finding(
            "repeated_automation",
            component,
            "warning",
            f"{executions} executions in the window",
            {"executions": executions, "threshold": threshold},
        )
    return None


def stuck_consumer(
    component: str, lag: int, oldest_failure_age_s: float | None, *, minutes: int
) -> Finding | None:
    """A consumer that stopped advancing: pending events and a failure older than the limit."""
    if lag > 0 and oldest_failure_age_s is not None and oldest_failure_age_s >= minutes * 60:
        return Finding(
            "stuck_consumer",
            component,
            "critical",
            f"{lag} events waiting for {oldest_failure_age_s / 60:.0f} min",
            {"lag": lag, "oldest_failure_minutes": round(oldest_failure_age_s / 60, 1)},
        )
    return None


def latency_spike(
    component: str, current_p95: float | None, baseline_p95: Sequence[float], *, factor: float
) -> Finding | None:
    if current_p95 is None or len(baseline_p95) < 3:
        return None
    median = statistics.median(baseline_p95)
    if median > 0 and current_p95 > factor * median:
        return Finding(
            "latency_spike",
            component,
            "warning",
            f"p95 {current_p95:.0f} ms vs a usual {median:.0f} ms",
            {"current_p95_ms": current_p95, "baseline_p95_ms": median},
        )
    return None


def repeated_failure(component: str, error_id: str, occurrences: int, *, count: int) -> Finding | None:
    """The same (fingerprinted) failure keeps happening."""
    if occurrences >= count:
        return Finding(
            "repeated_failure",
            component,
            "warning",
            f"the same error happened {occurrences} times",
            {"error_id": error_id, "occurrences": occurrences},
        )
    return None
