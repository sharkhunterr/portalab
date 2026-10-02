"""025 T020 — a slow external call is attributed to ``external_wait``, a slow handler to ``internal``,
timeouts are counted; views list the dominant phase; "slow" comes from configuration."""

from dataclasses import replace
from datetime import timedelta

from portalab.core.metrics import Timer, phase_scope, record_request
from portalab.core.time import FixedClock
from portalab.modules.observability.components.performance import performance
from tests.observability_fixtures import ObsHarness


async def test_phase_attribution(ob: ObsHarness, clock: FixedClock) -> None:
    hooks = ob.hooks
    for _ in range(3):  # /media: mostly waiting on the external service
        record_request(
            "portal", "http.request", 2.0, {"external_wait": 1.8}, {"route": "/api/v1/media"}, registry=hooks
        )
    for _ in range(3):  # /search: slow in our own code
        record_request("portal", "http.request", 1.6, {}, {"route": "/api/v1/search"}, registry=hooks)
    record_request(
        "portal", "http.request", 5.0, {}, {"route": "/api/v1/widget"}, timed_out=True, registry=hooks
    )
    with phase_scope():
        try:
            with Timer("external_wait", "connectors", "http.request", {"method": "GET"}, registry=hooks):
                raise TimeoutError
        except TimeoutError:
            pass
    for observation in hooks._queue:  # all observations of this test happened "now" on the fixed clock
        object.__setattr__(observation, "at", clock.now())
    await ob.module.collector.flush()
    ob.module.config = replace(ob.module.config, slow_request_ms=1_000)
    views = {
        v["target"]: v
        for v in await performance(ob.database, clock.now() - timedelta(hours=1), slow_ms=1_000)
    }
    assert views["/api/v1/media"]["dominant_phase"] == "external_wait" and views["/api/v1/media"]["slow"]
    assert views["/api/v1/search"]["dominant_phase"] == "internal"
    assert views["/api/v1/widget"]["timeouts"] == 1 and views["/api/v1/widget"]["dominant_phase"] == "timeout"
    assert views["GET"]["timeouts"] == 1
    relaxed = {
        v["target"]: v
        for v in await performance(ob.database, clock.now() - timedelta(hours=1), slow_ms=10_000)
    }
    assert not relaxed["/api/v1/media"]["slow"]  # the threshold is configuration, not code
