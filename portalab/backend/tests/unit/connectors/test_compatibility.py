"""005 T015 — incompatible portal version / capability / permission ⇒ refused with reasons."""

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.connector_sdk import ConnectorRegistry, Manifest
from portalab.connectors.fake import FakeConnector
from portalab.core.permissions import PermissionRegistry
from portalab.modules.connectors.services.compatibility import (
    CompatibilityChecker,
    CompatibilityToggleHook,
    satisfies,
)


def checker(version: str = "0.1.0") -> CompatibilityChecker:
    permissions = PermissionRegistry()
    permissions.declare("services.read", "read", owner="core")
    return CompatibilityChecker(
        ConnectorRegistry(), new_registry(), permissions=permissions, portal_version=version
    )


def test_version_ranges() -> None:
    assert satisfies("0.1.0", ">=0.1,<2") is True
    assert satisfies("2.0.0", ">=0.1,<2") is False
    assert satisfies("1.2.3", "==1.2.3") is True
    assert satisfies("1.0", "~>1") is None


def test_compatible_fake() -> None:
    result = checker().check(FakeConnector())
    assert result.result == "compatible" and result.reasons == []


def test_incompatible_reasons() -> None:
    connector = FakeConnector(
        key="future",
        manifest=Manifest(
            version="9.0",
            requires_portal=">=5",
            requires_capabilities=("future.library",),
            permissions=("future.read", "services.read"),
        ),
    )
    result = checker().check(connector)
    assert not result.compatible
    assert any("requires portal >=5" in r for r in result.reasons)
    assert any("future.library" in r for r in result.reasons)
    assert any("future.read" in r for r in result.reasons) and not any(
        "services.read" in r for r in result.reasons
    )


async def test_toggle_hook_vetoes_incompatible_connector() -> None:
    check = checker()
    check.connectors.register(FakeConnector())
    check.connectors.register(
        FakeConnector(key="old", manifest=Manifest(version="1", requires_portal="<0.1"))
    )

    async def lookup(service_id: str) -> str | None:
        return {"s1": "fake", "s2": "old"}.get(service_id)

    hook = CompatibilityToggleHook(check, lookup)
    assert await hook.check_enable("connector", "fake") == []
    assert await hook.check_enable("service", "s2") != []
    assert await hook.check_enable("connector", "missing") == ["connector 'missing' is not installed"]
    assert await hook.check_enable("module", "anything") == []
