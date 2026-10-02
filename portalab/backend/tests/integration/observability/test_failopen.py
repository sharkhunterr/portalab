"""025 T008/T009 — the collector writes minute samples and fingerprinted errors (50 occurrences ⇒ one row,
count 50); when the store is down requests keep working and the dropped batch is counted."""

from sqlalchemy import select

from portalab.modules.observability.models import ErrorRecord, MetricSample
from tests.observability_fixtures import ObsHarness


async def test_collect_samples_and_errors(ob: ObsHarness) -> None:
    for _ in range(3):
        ob.hooks.counter("jobs", "job.succeeded", labels={"kind": "x"})
    ob.hooks.histogram("portal", "http.request", 120.0, {"route": "/a", "phase": "internal"})
    for index in range(50):
        ob.hooks.error(
            "sync",
            "timeout",
            TimeoutError(f"service {index} timed out after {index}s"),
            context={"service": "s1", "password": "never-stored"},
            user_ref="not-a-uuid",
        )
    assert await ob.module.collector.flush() == 54
    async with ob.database.session() as session:
        samples = {
            (s.component, s.metric): s for s in (await session.execute(select(MetricSample))).scalars()
        }
        error = (await session.execute(select(ErrorRecord))).scalar_one()
    assert samples[("jobs", "job.succeeded")].count == 3
    assert samples[("portal", "http.request")].p95 == 120.0
    assert samples[("sync", "errors.recorded")].count == 50
    assert error.count == 50 and error.component == "sync" and error.category == "timeout"
    assert error.context["password"] != "never-stored" and error.user_ref is None
    assert len(await ob.outbox("observability.error_recorded")) == 1  # first occurrence only


async def test_store_down_is_fail_open(ob: ObsHarness) -> None:
    async def broken(batch: object) -> None:
        raise ConnectionError("database down")

    ob.module.collector._write = broken  # type: ignore[method-assign]
    ob.hooks.counter("portal", "x")
    ob.hooks.counter("portal", "y")
    assert await ob.module.collector.flush() == 0  # no exception reaches the caller
    assert ob.module.collector.stats.failures == 1 and ob.hooks.dropped == 2
    evaluations = {e.component: e for e in await ob.module.evaluator.evaluate_all()}
    assert evaluations["observability"].functional == "degraded"  # the self-component reports it
