"""009 T005/T009 — schema in place; ``/widgets/{key}/data``: provider timeout ⇒ ``unavailable`` (HTTP 200);
exception ⇒ ``error``; partial ⇒ ``partial`` with reasons; stale from ``as_of``/``stale_after_s``;
permission denied ⇒ ``unauthorized`` without data; one slow widget never delays another request;
invalid stored config ⇒ defaults + ``config_invalid``."""

import asyncio
import time
from dataclasses import replace
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from tests.integration.dashboard.conftest import DashboardHarness
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.privacy.conftest import NOW
from tests.unit.dashboard.fakes import FakeWidget, definition

pytestmark = pytest.mark.integration


async def test_schema(dash: DashboardHarness) -> None:
    async with dash.full.database.session() as session:
        tables = set(
            (
                await session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'dashboard'"))
            ).scalars()
        )
        fks = set(
            (
                await session.execute(
                    text(
                        "SELECT confrelid::regclass::text FROM pg_constraint c JOIN pg_namespace n "
                        "ON n.oid = c.connamespace WHERE n.nspname = 'dashboard' AND contype = 'f'"
                    )
                )
            ).scalars()
        )
    assert tables == {"user_dashboards", "widget_instances"} and fks == {"identity.users"}


async def test_states(app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness) -> None:
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    widgets = {
        "t.ok": FakeWidget(),
        "t.slow": FakeWidget(delay=30.0),  # far beyond the budget: only the timeout can end it
        "t.down": FakeWidget("unavailable"),
        "t.crash": FakeWidget("crash"),
        "t.partial": FakeWidget("partial"),
        "t.old": FakeWidget(as_of=NOW - timedelta(hours=2)),
        "t.secret": FakeWidget(),
    }
    for key, widget in widgets.items():
        extra = {"stale_after_s": 600} if key == "t.old" else {}
        if key == "t.secret":
            extra["required_permission"] = "audit.read"
        dash.registry.register(definition(key, **extra), widget)
    dash.module.config = replace(dash.module.config, widget_timeout_ms=300)

    async def state(key: str) -> dict[str, object]:
        response = await client.get(f"/api/v1/widgets/{key}/data")
        assert response.status_code == 200, (key, response.text)
        return response.json()

    # #32: the budget ends the slow widget (not the wall clock of a loaded machine): the page answers
    # long before the widget would have
    started = time.perf_counter()
    slow, ok = await asyncio.gather(state("t.slow"), state("t.ok"))
    assert slow["state"] == "unavailable" and slow["partial_reasons"] == ["timeout"]
    assert ok["state"] == "available"
    assert time.perf_counter() - started < 15
    assert (await state("t.down"))["state"] == "unavailable"
    assert (await state("t.crash"))["state"] == "error"
    partial = await state("t.partial")
    assert partial["state"] == "partial" and partial["partial_reasons"] == ["one source down"]
    assert (await state("t.old"))["state"] == "stale"
    secret = await state("t.secret")
    assert secret == {**secret, "state": "unauthorized", "data": None} and widgets["t.secret"].calls == 0
    missing = await client.get("/api/v1/widgets/t.nothing/data")
    assert missing.status_code == 404 and missing.json()["code"] == "dashboard.widget_not_found"


async def test_invalid_stored_config_falls_back(
    app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness
) -> None:
    widget = FakeWidget()
    dash.registry.register(definition("t.cfg"), widget)
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    created = (
        await client.post("/api/v1/dashboard/widgets", json={"widget_key": "t.cfg", "config": {"limit": 2}})
    ).json()
    async with dash.full.database.unit_of_work() as uow:
        await uow.session.execute(
            text("UPDATE dashboard.widget_instances SET config = '{\"limit\": 99}' WHERE id = :id"),
            {"id": created["id"]},
        )
    payload = (await client.get("/api/v1/widgets/t.cfg/data", params={"instance": created["id"]})).json()
    assert payload["config_invalid"] is True and widget.last_config == {"limit": 5}
