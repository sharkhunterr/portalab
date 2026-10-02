"""025 T030 — trends over periods from rollups; detailed samples expire before rollups; observability
data is separate from users' functional data (own schema, own retention targets)."""

from datetime import timedelta

from portalab.capabilities.retention import default_retention_targets
from portalab.core.metrics import Observation
from portalab.core.time import FixedClock
from portalab.modules.observability.trends import trends
from tests.observability_fixtures import ObsHarness


async def test_trends_and_retention(ob: ObsHarness, clock: FixedClock) -> None:
    start = clock.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=3)
    for hour in range(3):
        for _ in range(hour + 1):
            ob.hooks._push(
                Observation(
                    "counter", "jobs", "job.failed", 1.0, {}, at=start + timedelta(hours=hour, minutes=5)
                )
            )
    await ob.module.collector.flush()
    assert await ob.module.collector.rollup(clock.now()) >= 3
    hourly = await trends(ob.database, metric="job.failed", component="jobs", since=start, bucket="hour")
    assert [p["count"] for p in hourly["points"]] == [1, 2, 3]
    assert await ob.module.collector.rollup(clock.now()) == 0  # idempotent

    targets = {t.name: t for t in default_retention_targets.all() if t.owner == "module:observability"}
    config = ob.module.config
    assert targets["observability.samples"].action == "drop_partition"
    samples_window = targets["observability.samples"].window()  # type: ignore[misc]
    rollups_window = targets["observability.rollups"].window()  # type: ignore[misc]
    assert samples_window == timedelta(days=config.sample_retention_days) and samples_window < rollups_window
    assert all(t.table.startswith("obs.") and t.data_class == "technical" for t in targets.values())
