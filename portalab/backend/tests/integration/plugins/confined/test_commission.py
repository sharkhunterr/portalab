"""030 T050 (US4, SC-007) — a new kind of product from a confined plugin: the shop tells it (activation opens
the request, idempotently; a refund cancels it); when the plugin fails — an error, a hang, its process killed
mid-call — the activation fails cleanly (the shop then keeps the purchase pending and retries, spec 015: no
coin is ever lost) and the plugin comes back for the next one."""

import asyncio
import shutil
import textwrap
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import PlHarness

from portalab.capabilities.marketplace import OwnershipView
from portalab.core.confinement import probe
from portalab.modules.plugins.confined.host import ChildFailed

pytestmark = pytest.mark.skipif(not probe().ok, reason="kernel cannot confine")
COMMISSION = Path(__file__).resolve().parents[5] / "examples" / "plugins" / "commission"


def _h(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("__Host-portalab_csrf") or ""}


async def _enable(pl: PlHarness, client: httpx.AsyncClient, key: str) -> None:
    assert (
        await client.post("/api/v1/admin/plugins/install", json={"package": key}, headers=_h(client))
    ).status_code == 201
    assert (await client.post(f"/api/v1/admin/plugins/{key}/approve", headers=_h(client))).status_code == 200
    enabled = await client.post(f"/api/v1/admin/plugins/{key}/enable", headers=_h(client))
    assert enabled.status_code == 200, enabled.text


async def test_the_shop_tells_the_plugin(pl: PlHarness, client: httpx.AsyncClient) -> None:
    pl.module.config = replace(pl.module.config, hook_timeout_seconds=8.0)
    shutil.copytree(
        COMMISSION, pl.root / "available" / "commission", ignore=shutil.ignore_patterns("__pycache__")
    )
    await login(client, "boss")
    await _enable(pl, client, "commission")
    product = pl.registries.product_types.get("plugin:commission.avatar")
    assert product is not None and product.payload_fields == ("description",)
    view = OwnershipView(
        uuid4(), pl.people["boss"], "avatar-1", "plugin:commission.avatar", {"description": "a fox"}
    )
    result = await product.handler.activate(view)
    assert result.state == "active"
    assert (await product.handler.activate(view)).state == "active"  # retried: still one request
    mine = (await client.get("/api/v1/plugins/commission/mine")).json()
    assert [(i["product"], i["status"]) for i in mine["items"]] == [("avatar-1", "open")]
    await product.handler.deactivate(view)  # a refund
    mine = (await client.get("/api/v1/plugins/commission/mine")).json()
    assert [i["status"] for i in mine["items"]] == ["cancelled"]


FAULTY = """
schema_version = 2
key = "faulty"
name = "Faulty"
version = "1.0.0"
entry_point = "faulty_plugin:register"

[capabilities]
product_types = ["thing"]
"""
FAULTY_CODE = """
import asyncio, os
from portalab.sdk import ActivationResult, ProductType

def register(ctx):
    class Thing:
        async def activate(self, ownership):
            mode = (ownership.payload or {}).get("mode")
            if mode == "raise":
                raise RuntimeError("broken")
            if mode == "hang":
                await asyncio.sleep(60)
            if mode == "die":
                os._exit(9)
            return ActivationResult("active")
        async def deactivate(self, ownership):
            return None
    ctx.product_type(ProductType(key="plugin:faulty.thing", owner="plugin:faulty", handler=Thing()))
"""


async def test_a_failing_plugin_never_completes_an_activation(
    pl: PlHarness, client: httpx.AsyncClient
) -> None:
    pl.module.config = replace(pl.module.config, hook_timeout_seconds=1.0, error_threshold=100)
    target = pl.root / "available" / "faulty"
    (target / "faulty_plugin").mkdir(parents=True)
    (target / "plugin.toml").write_text(FAULTY)
    (target / "faulty_plugin" / "__init__.py").write_text(textwrap.dedent(FAULTY_CODE))
    await login(client, "boss")
    await _enable(pl, client, "faulty")
    product = pl.registries.product_types.get("plugin:faulty.thing")
    assert product is not None

    def view(mode: str) -> OwnershipView:
        return OwnershipView(uuid4(), pl.people["boss"], "thing", "plugin:faulty.thing", {"mode": mode})

    for mode in ("raise", "hang", "die"):
        with pytest.raises(ChildFailed):  # the shop catches it: activation_failed, retried, coins kept
            await product.handler.activate(view(mode))
    for _ in range(60):  # its process comes back (restart with backoff)
        try:
            assert (await product.handler.activate(view("ok"))).state == "active"
            break
        except ChildFailed:
            await asyncio.sleep(0.5)
    else:
        raise AssertionError("the plugin did not come back")
