"""023 T020 — raising, slow and oversized plugin hooks are contained (the request fails alone); errors
are counted and quarantine the plugin at ``plugins.errorThreshold`` with the Admin notified; other plugins
and core routes are unaffected; rate limits apply; plugin event handlers are worker consumers; a plugin
failing at startup is quarantined while the portal keeps starting."""

from dataclasses import replace

import pytest
from httpx import AsyncClient

from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import SYSTEM, PlHarness

pytestmark = pytest.mark.integration
SLOW = """
import asyncio

from portalab.sdk import PluginContext


def register(ctx: PluginContext) -> None:
    async def slow(principal, query, body):
        await asyncio.sleep(2)
        return {"state": "available"}

    async def fine(principal, query, body):
        return {"state": "available", "value": 1}

    ctx.route("GET", "slow", slow, permission="users.self.manage")
    ctx.route("GET", "fine", fine, permission="users.self.manage")
"""
BROKEN = """
from portalab.sdk import PluginContext


def register(ctx: PluginContext) -> None:
    raise RuntimeError("cannot start")
"""


async def test_failures_are_contained(pl: PlHarness, client: AsyncClient) -> None:
    pl.module.config = replace(pl.module.config, error_threshold=3, hook_timeout_seconds=0.2)
    await pl.installed(pl.hello())
    await pl.installed(pl.package("sleepy", code=SLOW))
    await login(client, "boss")
    for _ in range(2):
        failed = await client.get("/api/v1/plugins/hello/boom")
        assert failed.status_code == 502 and failed.json()["code"] == "plugin.hook_failed"
        assert "on purpose" not in failed.text
    timeout = await client.get("/api/v1/plugins/sleepy/slow")
    assert timeout.status_code == 502
    assert (await client.get("/api/v1/plugins/sleepy/fine")).json()["value"] == 1  # neighbour unaffected
    assert (await client.get("/api/v1/me")).status_code == 200  # core unaffected
    await client.get("/api/v1/plugins/hello/boom")  # third error: quarantine
    states = {p["key"]: p["state"] for p in (await client.get("/api/v1/admin/plugins")).json()}
    assert states == {"hello": "quarantined", "sleepy": "enabled"}
    assert (await client.get("/api/v1/plugins/hello/greetings/count")).status_code == 404
    assert pl.registries.consumers.get("plugin.hello.welcome") is None  # removed with the plugin

    pl.module.guard.rate_per_minute = 2
    await client.get("/api/v1/plugins/sleepy/fine")
    limited = await client.get("/api/v1/plugins/sleepy/fine")
    assert limited.status_code == 429


async def test_consumers_run_in_the_worker_and_startup_survives(pl: PlHarness) -> None:
    await pl.installed(pl.hello())
    consumer = pl.registries.consumers.get("plugin.hello.welcome")
    assert consumer is not None and consumer.types == frozenset({"user.verified"})  # dispatched by the worker
    await pl.installed(pl.package("broken", code=BROKEN), restart=False)
    loaded = await pl.module.lifecycle.load_enabled()
    assert "hello" in loaded and "broken" not in loaded
    assert (await pl.module.lifecycle.get("broken")).state == "quarantined"
    assert (await pl.module.lifecycle.get("hello")).state == "enabled"
    await pl.module.lifecycle.disable(SYSTEM, "hello")
