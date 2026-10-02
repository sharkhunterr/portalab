"""Kernel observability hooks (spec 025 T006; R2, R7, R8): counters, histograms, phase timers and error
records, all **non-blocking and fail-open**.

Every hook appends an :class:`Observation` to a bounded in-memory queue; when the queue is full the oldest
observation is dropped and the drop is counted. Hooks never raise into callers. The Observability module's
collector drains the queue (in each process) into its own store.

Performance is attributed to phases (``portal_wait``, ``external_wait``, ``internal``, ``timeout``): a
request scope accumulates the time spent waiting on external services (``Timer("external_wait")`` in the
connector HTTP client) so the middleware can split a request into external and internal time.
Labels and messages are redacted; observations carry ids and technical facts only.
"""

import threading
import time
from collections import deque
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from portalab.core.logging import redact, redact_text

Kind = Literal["counter", "histogram", "error"]
Phase = Literal["portal_wait", "external_wait", "internal", "timeout"]
PHASES: tuple[Phase, ...] = ("portal_wait", "external_wait", "internal", "timeout")
DEFAULT_CAPACITY = 20_000
MAX_LABELS = 8


@dataclass(frozen=True, slots=True)
class Observation:
    kind: Kind
    component: str
    metric: str
    value: float
    labels: Mapping[str, str] = field(default_factory=dict)
    at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: Mapping[str, Any] | None = None  # for kind == "error": category, level, message, context, refs


def _labels(labels: Mapping[str, Any] | None) -> dict[str, str]:
    if not labels:
        return {}
    clean = {}
    for key, value in list(labels.items())[:MAX_LABELS]:
        clean[str(key)[:64]] = redact_text(str(value))[:128]
    redacted = redact(clean)
    return {k: str(v) for k, v in redacted.items()}


class MetricsRegistry:
    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        self._queue: deque[Observation] = deque()
        self._capacity = capacity
        self._lock = threading.Lock()
        self.dropped = 0
        self.recorded = 0

    # --- hooks (never raise) -------------------------------------------------------------------------
    def _push(self, observation: Observation) -> None:
        with self._lock:
            if len(self._queue) >= self._capacity:
                self._queue.popleft()
                self.dropped += 1
            self._queue.append(observation)
            self.recorded += 1

    def counter(
        self, component: str, metric: str, value: float = 1, labels: Mapping[str, Any] | None = None
    ) -> None:
        with suppress(Exception):  # hooks are fail-open by contract
            self._push(Observation("counter", component, metric, float(value), _labels(labels)))

    def histogram(
        self, component: str, metric: str, value: float, labels: Mapping[str, Any] | None = None
    ) -> None:
        with suppress(Exception):  # hooks are fail-open by contract
            self._push(Observation("histogram", component, metric, float(value), _labels(labels)))

    def error(
        self,
        component: str,
        category: str,
        error: BaseException | str,
        *,
        level: str = "error",
        context: Mapping[str, Any] | None = None,
        service_ref: str | None = None,
        plugin_ref: str | None = None,
        event_ref: str | None = None,
        user_ref: str | None = None,
    ) -> None:
        """Record a structured error (``errors.record``); the message and context are redacted here."""
        try:
            if isinstance(error, BaseException):
                error_type, message = type(error).__name__, str(error)
            else:
                error_type, message = "error", error
            self._push(
                Observation(
                    "error",
                    component,
                    category,
                    1.0,
                    error={
                        "category": category,
                        "type": error_type,
                        "level": level,
                        "message": redact_text(message)[:2000],
                        "context": redact(dict(context or {})),
                        "service_ref": service_ref,
                        "plugin_ref": plugin_ref,
                        "event_ref": event_ref,
                        "user_ref": user_ref,
                    },
                )
            )
        except Exception:  # noqa: S110 — hooks are fail-open by contract
            pass

    # --- collector side ------------------------------------------------------------------------------
    def drain(self, limit: int = 10_000) -> list[Observation]:
        with self._lock:
            count = min(limit, len(self._queue))
            return [self._queue.popleft() for _ in range(count)]

    def depth(self) -> int:
        with self._lock:
            return len(self._queue)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "depth": len(self._queue),
                "dropped": self.dropped,
                "recorded": self.recorded,
                "capacity": self._capacity,
            }

    def reset(self) -> None:
        with self._lock:
            self._queue.clear()
            self.dropped = 0
            self.recorded = 0


default_metrics = MetricsRegistry()


# --- phase attribution -----------------------------------------------------------------------------------
_phases: ContextVar[dict[str, float] | None] = ContextVar("portalab_phases", default=None)


@contextmanager
def phase_scope() -> Iterator[dict[str, float]]:
    """Accumulate phase durations (seconds) for one request/job; nested scopes share the outer one."""
    current = _phases.get()
    if current is not None:
        yield current
        return
    accumulator: dict[str, float] = {}
    token = _phases.set(accumulator)
    try:
        yield accumulator
    finally:
        _phases.reset(token)


class Timer:
    """``with Timer("external_wait", "connectors", "http"):`` — records a histogram (ms) labelled with the
    phase and adds the duration to the surrounding :func:`phase_scope`. A ``TimeoutError`` inside is counted
    as the ``timeout`` phase."""

    def __init__(
        self,
        phase: Phase,
        component: str,
        metric: str,
        labels: Mapping[str, Any] | None = None,
        registry: MetricsRegistry | None = None,
    ) -> None:
        self.phase: Phase = phase
        self.component = component
        self.metric = metric
        self.labels = dict(labels or {})
        self.registry = registry or default_metrics
        self.started = 0.0
        self.elapsed = 0.0

    def __enter__(self) -> "Timer":
        self.started = time.monotonic()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: object) -> None:
        try:
            self.elapsed = time.monotonic() - self.started
            phase: Phase = (
                "timeout" if exc_type is not None and issubclass(exc_type, TimeoutError) else self.phase
            )
            accumulator = _phases.get()
            if accumulator is not None:
                accumulator[phase] = accumulator.get(phase, 0.0) + self.elapsed
            self.registry.histogram(
                self.component, self.metric, self.elapsed * 1000, {**self.labels, "phase": phase}
            )
        except Exception:  # noqa: S110 — hooks are fail-open by contract
            pass


def record_request(
    component: str,
    metric: str,
    total_seconds: float,
    phases: Mapping[str, float],
    labels: Mapping[str, Any] | None = None,
    *,
    timed_out: bool = False,
    registry: MetricsRegistry | None = None,
) -> None:
    """Split one request/job into phases: external/portal waits as measured, the rest is ``internal``."""
    target = registry or default_metrics
    waits = phases.get("external_wait", 0.0) + phases.get("portal_wait", 0.0)
    split = {
        "external_wait": phases.get("external_wait", 0.0),
        "portal_wait": phases.get("portal_wait", 0.0),
        "internal": max(total_seconds - waits, 0.0),
    }
    if timed_out:
        split = {"timeout": total_seconds}
    for phase, seconds in split.items():
        if seconds > 0 or phase == "internal":
            target.histogram(component, metric, seconds * 1000, {**dict(labels or {}), "phase": phase})
