"""025 T004 — kernel hooks are non-blocking: a full queue drops the oldest and counts it; hooks never raise;
phase timers split external and internal time."""

import time

import pytest

from portalab.core.metrics import MetricsRegistry, Timer, phase_scope, record_request


def test_full_queue_drops_oldest_and_counts() -> None:
    registry = MetricsRegistry(capacity=3)
    for value in range(5):
        registry.counter("c", "m", value)
    drained = registry.drain()
    assert [o.value for o in drained] == [2.0, 3.0, 4.0]
    assert registry.dropped == 2 and registry.stats()["depth"] == 0


def test_hooks_never_raise() -> None:
    registry = MetricsRegistry()

    class Exploding:
        def __str__(self) -> str:
            raise RuntimeError("boom")

    registry.counter("c", "m", labels={"bad": Exploding()})  # swallowed
    registry.histogram("c", "m", "not a number")  # type: ignore[arg-type]
    registry.error("c", "cat", Exploding())  # type: ignore[arg-type]
    assert registry.depth() <= 1


def test_labels_and_errors_are_redacted() -> None:
    registry = MetricsRegistry()
    registry.counter("c", "m", labels={"token": "abc123456", "route": "/x"})
    registry.error("c", "db", RuntimeError("password=hunter22 failed"), context={"api_key": "zzz"})
    counter, error = registry.drain()
    assert counter.labels == {"token": "***", "route": "/x"} or "abc123456" not in str(counter.labels)
    assert error.error is not None and "hunter22" not in error.error["message"]
    assert error.error["context"]["api_key"] != "zzz"


def test_timer_phases() -> None:
    registry = MetricsRegistry()
    with phase_scope() as phases, Timer("external_wait", "connectors", "http.request", registry=registry):
        time.sleep(0.02)
    assert phases["external_wait"] >= 0.02
    record_request("portal", "http.request", 0.05, phases, {"route": "/r"}, registry=registry)
    by_phase = {
        o.labels.get("phase"): o.value
        for o in registry.drain()
        if o.metric == "http.request" and o.component == "portal"
    }
    assert by_phase["external_wait"] >= 20 and by_phase["internal"] == pytest.approx(
        50 - by_phase["external_wait"], abs=1
    )


def test_timeout_phase() -> None:
    registry = MetricsRegistry()
    with pytest.raises(TimeoutError), Timer("external_wait", "connectors", "http.request", registry=registry):
        raise TimeoutError
    assert registry.drain()[0].labels["phase"] == "timeout"
