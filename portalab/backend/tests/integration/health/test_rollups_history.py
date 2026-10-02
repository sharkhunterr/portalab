"""006 T012 — hourly rollups compute availability and downtime with gaps marked; history follows
``occurred_at``; health history stays apart from incidents and sync history."""

from datetime import timedelta

from portalab.core.time import FixedClock
from tests.health_fixtures import HealthHarness


async def test_rollups_availability_gaps(hl: HealthHarness, clock: FixedClock) -> None:
    service_id = await hl.service()
    start = clock.now().replace(minute=0, second=0, microsecond=0)
    clock.set(start + timedelta(minutes=5))
    await hl.module.runner.probe(service_id)
    hl.cn.remote.mode = "error"
    for minute in (10, 20, 30):
        clock.set(start + timedelta(minutes=minute))
        await hl.module.runner.probe(service_id)  # 2 failures ⇒ unavailable at minute 20
    hl.cn.remote.mode = "ok"
    clock.set(start + timedelta(minutes=50))
    await hl.module.runner.probe(service_id)
    # hour 2 has no sample at all (monitoring gap); hour 3 one OK sample
    clock.set(start + timedelta(hours=2, minutes=10))
    await hl.module.runner.probe(service_id)
    clock.set(start + timedelta(hours=3, minutes=1))
    assert await hl.module.rollups.run() == 3
    assert await hl.module.rollups.run() == 0  # nothing new to roll

    history = await hl.module.history.history(service_id, start, start + timedelta(hours=3))
    buckets = history["buckets"]
    assert buckets[0]["gap"] is False and buckets[0]["availability"] == 2 / 5
    assert buckets[0]["downtime_seconds"] == 30 * 60  # unavailable from :20 to :50
    assert buckets[1]["gap"] is True  # no sample ⇒ gap, never counted as uptime
    assert buckets[2]["gap"] is False and buckets[2]["availability"] == 1.0
    assert [t["to"] for t in history["transitions"]] == [
        "operational",
        "degraded",
        "unavailable",
        "operational",
    ]
    assert history["transitions"][2]["occurred_at"] == (start + timedelta(minutes=20)).isoformat()
    assert "metrics" not in history  # standard shape
    assert set(history) == {"transitions", "buckets"}  # no incidents or sync runs mixed in
