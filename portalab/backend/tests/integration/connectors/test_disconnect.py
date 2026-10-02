"""005 T029 — disconnect withdraws capabilities, stops sync, keeps history (historical/stale); purge only
via the 021 ``services.purge`` action, which erases this service's imported rows only."""

from sqlalchemy import func, select

from portalab.connectors.fake import CAPABILITY
from portalab.modules.connectors.models import SyncRun, SyncState
from portalab.modules.connectors.sync.runner import source_ref
from tests.connectors_fixtures import ConnectorsHarness


async def test_disconnect_keeps_history_and_purge_is_separate(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    cn.remote.put("a", at=1)
    await cn.module.runner.run(service_id, kind="manual")
    async with cn.full.database.session() as session:
        ref = source_ref(await cn.module.manager._row(session, service_id))

    view = await cn.module.manager.disconnect(cn.admin, service_id)
    assert view.state == "disconnected" and view.historical and view.stale
    assert cn.full.identity.capabilities.system_providers(CAPABILITY) == []
    assert await cn.module.runner.run(service_id) is None  # scheduled syncs stop
    assert await cn.module.scheduler.enqueue_due() == 0
    assert set(cn.sink.stored(ref)) == {"a"}  # data kept
    async with cn.full.database.session() as session:
        assert await session.scalar(select(func.count()).select_from(SyncRun)) == 1  # history kept

    assert await cn.module.data.has_service(str(service_id))
    assert await cn.module.data.purge_service_data(str(service_id)) == 1  # what 021's purge calls
    assert cn.sink.stored(ref) == {}
    async with cn.full.database.session() as session:
        state = await session.get(SyncState, service_id)
    assert state is not None and state.cursor is None
    assert [e["type"] for e in await cn.outbox("connector.data_purged")] == ["connector.data_purged"]


async def test_privacy_purge_uses_the_connectors_provider(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    cn.remote.put("a", at=1)
    await cn.module.runner.run(service_id, kind="manual")
    await cn.module.manager.disconnect(cn.admin, service_id)
    removed = await cn.full.privacy.purge.run(str(service_id))
    assert removed == 1
