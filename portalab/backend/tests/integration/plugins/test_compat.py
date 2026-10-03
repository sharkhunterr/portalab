"""023 T010 — compatibility: the portal version range and required capability ranges are checked against
the 001 registry; an incompatible plugin becomes ``incompatible`` and cannot be enabled, with named
reasons; a satisfied minor range passes."""

import pytest
from httpx import AsyncClient

from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import PlHarness

pytestmark = pytest.mark.integration


async def test_compatibility(pl: PlHarness, client: AsyncClient) -> None:
    pl.package("future", manifest={"requires_portal": ">=9.0"})
    pl.package(
        "needy", manifest={"requires_capabilities": [{"name": "identity.directory", "range": ">=2.0"}]}
    )
    pl.package("missing", manifest={"requires_capabilities": [{"name": "teleport.service"}]})
    pl.package(
        "fine",
        manifest={
            "requires_portal": ">=0.1,<1",
            "requires_capabilities": [{"name": "identity.directory", "range": ">=1.0,<2"}],
        },
    )
    await login(client, "boss")
    for name in ("future", "needy", "missing", "fine"):
        assert (
            await client.post("/api/v1/admin/plugins/install", json={"package": f"{name}-1.0.0"})
        ).status_code == 201
        await client.post(f"/api/v1/admin/plugins/{name}/approve")
    reasons = {}
    for name in ("future", "needy", "missing"):
        refused = await client.post(f"/api/v1/admin/plugins/{name}/enable")
        assert refused.status_code == 409 and refused.json()["code"] == "plugin.incompatible"
        reasons[name] = refused.json()["reasons"]
    assert "needs portal >=9.0" in reasons["future"][0]
    assert "identity.directory >=2.0" in reasons["needy"][0]
    assert "not available" in reasons["missing"][0]
    states = {p["key"]: p["state"] for p in (await client.get("/api/v1/admin/plugins")).json()}
    assert states["future"] == "incompatible"
    assert (await client.post("/api/v1/admin/plugins/fine/enable")).json()["state"] == "enabled"
    discovery = {
        d["key"]: d for d in (await client.get("/api/v1/admin/plugins/discovery")).json() if d.get("valid")
    }
    assert discovery["future"]["compatibility"] and discovery["fine"]["compatibility"] == []
