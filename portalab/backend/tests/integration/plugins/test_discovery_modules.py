"""023 T028 — discovery lists the packages in ``plugins/available`` with a compatibility preview, maturity
and deprecation notices (never downloading anything); first-party modules are disabled through 020 toggles
with their dependents respected and their contributions removed by the same sweep."""

import pytest
from httpx import AsyncClient

from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import PlHarness

pytestmark = pytest.mark.integration


async def test_discovery(pl: PlHarness, client: AsyncClient) -> None:
    pl.hello()
    pl.package("old", manifest={"maturity": "deprecated", "deprecation_notice": "Use hello instead"})
    pl.package("needs_base", manifest={"requires_plugins": [{"key": "base", "range": ">=1.0"}]})
    (pl.root / "available" / "junk").mkdir()
    await login(client, "boss")
    found = {
        d.get("key") or d["package"]: d for d in (await client.get("/api/v1/admin/plugins/discovery")).json()
    }
    assert found["hello"]["maturity"] == "beta" and found["hello"]["state"] is None
    assert found["old"]["deprecation_notice"] == "Use hello instead"
    assert found["needs_base"]["dependencies"] == ["needs_base needs base"]
    assert found["junk"]["valid"] is False


async def test_modules(pl: PlHarness, client: AsyncClient) -> None:
    removed: list[str] = []

    async def spy(owner: str) -> dict[str, int]:
        # the sweep itself is proven by test_clean_removal; here only that disabling a module runs it —
        # without wiping first-party declarations from the process-wide registries other tests use
        removed.append(owner)
        return {}

    pl.module.modules.remove = spy
    await login(client, "ursula")
    assert (await client.get("/api/v1/admin/modules")).status_code == 403
    await login(client, "boss")
    modules = {m["key"]: m for m in (await client.get("/api/v1/admin/modules")).json()}
    assert modules["gamification"]["enabled"] and modules["campaigns"]["requires"] == ["gamification"]
    blocked = await client.post("/api/v1/admin/modules/gamification/disable", json={})
    assert blocked.status_code == 409 and set(blocked.json()["dependents"]) >= {
        "campaigns",
        "community",
        "marketplace",
    }
    assert (await client.post("/api/v1/admin/modules/identity/disable", json={})).status_code == 409
    cascade = (await client.post("/api/v1/admin/modules/gamification/disable", json={"cascade": True})).json()
    assert cascade["changed"][-1] == "gamification" and "module:gamification" in removed
    states = {m["key"]: m["enabled"] for m in (await client.get("/api/v1/admin/modules")).json()}
    assert not states["gamification"] and not states["campaigns"]
    refused = await client.post("/api/v1/admin/toggles/module/campaigns", json={"enabled": True})
    assert (
        refused.status_code in (409, 422) and "gamification" in refused.text
    )  # ToggleHook: dependency first
    enabled = await client.post("/api/v1/admin/modules/gamification/enable")
    assert enabled.json()["enabled"] is True
    assert {m["key"]: m["needs_restart"] for m in (await client.get("/api/v1/admin/modules")).json()}[
        "gamification"
    ]
