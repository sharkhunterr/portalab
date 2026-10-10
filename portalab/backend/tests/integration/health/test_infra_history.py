"""#52 — the metrics over time: the sweep samples each service's metrics (once per slot), the history
averages them into buckets per metric, and « right now » asks the service without storing; the « Chart »
widget draws them (its other series sold in the shop)."""

from datetime import timedelta

from sqlalchemy import text

from portalab.capabilities.health import INFRA_HISTORY
from portalab.capabilities.i18n import LocaleContext
from portalab.core.time import FixedClock
from portalab.modules.dashboard.widgets.hosts import ChartProvider, HostReports
from portalab.modules.health.probes.scheduler import INFRA_JOB
from tests.health_fixtures import HealthHarness


async def test_samples_history_and_chart(hl: HealthHarness, clock: FixedClock) -> None:
    service_id = await hl.service()
    await hl.module.scheduler.sweep()
    async with hl.cn.full.database.session() as session:
        jobs = (
            await session.execute(text("SELECT count(*) FROM core.job WHERE kind = :k"), {"k": INFRA_JOB})
        ).scalar_one()
    assert jobs == 1
    for _ in range(3):
        await hl.module.scheduler.sample({"service_id": service_id})
    history = hl.module.infra_history
    assert history.services() == [service_id]
    series = await history.series(service_id, ["cpu", "ram", "gpu"], clock.now() - timedelta(hours=1))
    assert [v for _, v in series["cpu"]] == [12.5]  # three samples of the same minute: one point
    assert series["gpu"] == []  # not reported: no points, never zeros
    current = await history.current(service_id, ["cpu", "gpu"])
    assert current["cpu"] is not None and current["cpu"].value == 12.5 and current["gpu"] is None
    registration = hl.module.capabilities.system_providers(INFRA_HISTORY)[0]
    assert registration.provider is history
    chart = ChartProvider(hl.module.capabilities, HostReports(hl.module.capabilities), clock)
    payload = await chart.load(None, {"series": "cpu", "range": "1h", "live": True}, LocaleContext())  # type: ignore[arg-type]
    assert payload.state == "available" and payload.data is not None
    assert payload.data["metrics"] == ["cpu"] and payload.data["current"] == {"cpu": 12.5}
    assert payload.data["points"] and payload.data["points"][0]["cpu"] == 12.5
