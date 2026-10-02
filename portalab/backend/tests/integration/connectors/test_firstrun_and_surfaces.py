"""005 T037 — the optional, skippable ``services`` first-run step (Admin wizard) and the admin surface."""

from portalab.capabilities.administration import FIRST_RUN_STEP_CAPABILITY, default_admin_surfaces
from tests.connectors_fixtures import TOKEN, ConnectorsHarness


async def test_services_step(cn: ConnectorsHarness) -> None:
    [registration] = [
        r
        for r in cn.full.identity.capabilities.system_providers(FIRST_RUN_STEP_CAPABILITY)
        if r.metadata.get("step") == "services"
    ]
    assert registration.metadata["skippable"] is True
    assert cn.admin.user_id is not None
    listing = await registration.provider.run({}, cn.admin.user_id)
    assert [c["key"] for c in listing["connectors"]] == ["fake"]
    done = await registration.provider.run(
        {
            "services": [
                {
                    "connector": "fake",
                    "name": "Home",
                    "config": {"base_url": cn.base_url},
                    "secrets": {"api_token": TOKEN},
                }
            ]
        },
        cn.admin.user_id,
    )
    [service_id] = done["configured"]
    views = await cn.module.manager.list()
    assert [(str(v.id), v.state) for v in views] == [(service_id, "configured")]  # never auto-enabled
    steps = [s["step"] for s in cn.full.administration.first_run.steps()]
    assert "services" in steps
    assert "services" in {surface.key for surface in default_admin_surfaces.all()}


async def test_toggle_hook_refuses_incompatible_connector(cn: ConnectorsHarness) -> None:
    import pytest

    from portalab.capabilities.connector_sdk import Manifest
    from portalab.connectors.fake import FakeConnector
    from portalab.modules.administration.toggles.service import EnableRefused
    from portalab.modules.connectors.services.common import ConnectorIncompatible

    cn.connectors.register(
        FakeConnector(key="legacy", manifest=Manifest(version="0.1", requires_portal="<0.0.1"))
    )
    service_id = await cn.module.manager.configure(
        cn.admin,
        connector_key="legacy",
        name="Old",
        config={"base_url": cn.base_url},
        secrets={"api_token": TOKEN},
    )
    with pytest.raises(EnableRefused):
        await cn.full.administration.toggles.set(cn.admin, "service", str(service_id), True)
    with pytest.raises(ConnectorIncompatible):
        await cn.module.manager.enable(cn.admin, service_id)
    assert (await cn.module.manager.get(service_id)).state == "configured"  # prior state preserved
    assert [e["result"] for e in await cn.outbox("connector.compatibility_checked")] == ["incompatible"]
