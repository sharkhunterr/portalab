"""005 T038 (F20) — every connector-related registration is owner-tagged and removed with its owner."""

from portalab.capabilities.automation_actions import ActionRegistry, ActionType
from portalab.capabilities.connector_sdk import ConnectorRegistry
from portalab.capabilities.record_sink import SinkRegistry
from portalab.capabilities.record_sink_testkit import InMemoryRecordSink
from portalab.capabilities.registry import CapabilityRegistry
from portalab.connectors.fake import SPEC, FakeConnector


class _Items:
    async def list_items(self) -> list[dict[str, str]]:
        return []


async def _noop(params: object, principal: object) -> dict[str, str]:
    return {}


def test_unregister_owner_removes_all_contributions() -> None:
    owner = "plugin:demo"
    connectors, sinks, actions, capabilities = (
        ConnectorRegistry(),
        SinkRegistry(),
        ActionRegistry(),
        CapabilityRegistry(),
    )
    connectors.register(FakeConnector(key="demo"), owner=owner)
    connectors.register(FakeConnector(key="kept"), owner="core")
    sinks.register("demo.items", InMemoryRecordSink(), owner=owner)
    actions.register(ActionType("demo.go", "go", "services.manage", "idempotent", _noop, owner=owner))
    capabilities.declare(SPEC)
    capabilities.provide(SPEC.name, _Items(), instance_ref="svc", owner=owner)

    assert (connectors.unregister(owner), sinks.unregister(owner), actions.unregister(owner)) == (1, 1, 1)
    assert capabilities.unregister(owner) == 1
    assert [c.key for c in connectors.all()] == ["kept"]
    assert sinks.get("demo.items") is None and actions.get("demo.go") is None
    assert capabilities.system_providers(SPEC.name) == []
