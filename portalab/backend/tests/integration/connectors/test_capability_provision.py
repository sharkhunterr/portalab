"""005 T009 — enabling a service provides its capabilities; consumers resolve them without naming the
service; two services for one capability are ordered by priority; disabling withdraws and keeps data."""

from portalab.capabilities.results import Available
from portalab.connectors.fake import CAPABILITY
from portalab.modules.connectors.sync.runner import source_ref
from tests.connectors_fixtures import ConnectorsHarness


async def test_enable_provides_and_disable_withdraws(cn: ConnectorsHarness) -> None:
    capabilities = cn.full.identity.capabilities
    service_id = await cn.configure()
    assert capabilities.system_providers(CAPABILITY) == []  # configured is not enough
    cn.remote.put("a", title="Alpha")
    await cn.module.manager.enable(cn.admin, service_id)
    [registration] = capabilities.system_providers(CAPABILITY)
    result = await registration.provider.list_items()  # the consumer never names the service
    assert isinstance(result, Available) and result.value == [{"id": "a", "title": "Alpha"}]

    await cn.module.runner.run(service_id, kind="manual", actor=cn.admin)
    await cn.module.manager.disable(cn.admin, service_id)
    assert capabilities.system_providers(CAPABILITY) == []
    async with cn.full.database.session() as session:
        row = await cn.module.manager._row(session, service_id)
    assert set(cn.sink.stored(source_ref(row))) == {"a"}  # disabling never deletes data


async def test_two_services_ordered_by_priority(cn: ConnectorsHarness) -> None:
    first = await cn.enabled("First")
    second = await cn.enabled("Second", base_url=cn.base_url)
    await cn.module.manager.update(cn.admin, second, capabilities={CAPABILITY: {"priority": 10}})
    refs = [reg.instance_ref for reg in cn.full.identity.capabilities.system_providers(CAPABILITY)]
    assert refs == [str(second), str(first)]


async def test_disabled_capability_is_not_provided(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    await cn.module.manager.update(cn.admin, service_id, capabilities={CAPABILITY: {"enabled": False}})
    assert cn.full.identity.capabilities.system_providers(CAPABILITY) == []


async def test_restore_rebuilds_providers_from_stored_state(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    cn.full.identity.capabilities.unregister(f"service:{service_id}")  # e.g. a fresh process
    assert await cn.module.start() == 1
    assert [r.instance_ref for r in cn.full.identity.capabilities.system_providers(CAPABILITY)] == [
        str(service_id)
    ]
