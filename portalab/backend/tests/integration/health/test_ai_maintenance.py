"""Issue 171 — the assistant reads the maintenance schedule: the window under way and the one planned, the
service it concerns (or the whole portal), when, and what about."""

from datetime import timedelta

from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock
from portalab.modules.health.ai_tools import HealthAiTools
from tests.health_fixtures import HealthHarness


async def test_maintenance_windows(hl: HealthHarness, clock: FixedClock) -> None:
    service_id = await hl.service("Plex")
    now = clock.now()
    await hl.module.maintenance.create(
        hl.cn.admin,
        service_id=None,
        title="Power cut",
        starts_at=now - timedelta(minutes=5),
        ends_at=now + timedelta(hours=1),
        description="The building's power is cut.",
    )
    await hl.module.maintenance.reconcile()
    await hl.module.maintenance.create(
        hl.cn.admin,
        service_id=service_id,
        title="Disk upgrade",
        starts_at=now + timedelta(hours=3),
        ends_at=now + timedelta(hours=4),
    )
    [tool] = HealthAiTools(hl.module, clock).tools()
    answer = await tool.handler(Principal(channel="ai", acting_for=hl.cn.admin.user_id), {})
    windows = {w["title"]: w for w in answer.data["windows"]}
    assert (
        windows["Power cut"]["status"] == "active" and windows["Power cut"]["service"] == "the whole portal"
    )
    assert windows["Power cut"]["about"] == "The building's power is cut."
    assert windows["Disk upgrade"]["status"] == "scheduled"
    assert answer.data["summary"] == "1 maintenance(s) under way. 1 planned."
    assert {s.title for s in answer.sources} == {"Power cut", "Disk upgrade"}
