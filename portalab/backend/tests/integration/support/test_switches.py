"""Issue 246 — tickets and incidents switched off apart (the arrival wizard's features): their addresses
answer nothing, their menu entries go at once, and switched on again they come back as they were."""

from uuid import UUID

import httpx
import pytest

from portalab.core.authz_port import Principal
from portalab.modules.administration.config.service import Change
from tests.integration.identity.helpers import login
from tests.integration.support.conftest import SupportHarness

pytestmark = pytest.mark.integration


async def switch(support: SupportHarness, key: str, value: bool) -> None:
    admin = Principal(user_id=support.people["boss"])
    await support.full.administration.config.apply([Change(key, value)], admin, reason="test")


async def test_tickets_and_incidents_switch_off_apart(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    await login(client, "ursula")
    assert (await client.get("/api/v1/me/tickets")).status_code == 200
    assert (await client.get("/api/v1/incidents")).status_code == 200

    await switch(support, "support.tickets.enabled", False)
    off = await client.get("/api/v1/me/tickets")
    assert off.status_code == 404 and off.json()["code"] == "support.tickets_off"
    created = await client.post("/api/v1/tickets", json={"type_key": "bug", "title": "Crash"})
    assert created.status_code == 404
    assert (await client.get("/api/v1/incidents")).status_code == 200  # the incidents stay

    await switch(support, "support.incidents.enabled", False)
    assert (await client.get("/api/v1/incidents")).json()["code"] == "support.incidents_off"

    await switch(support, "support.tickets.enabled", True)
    assert (await client.get("/api/v1/me/tickets")).status_code == 200
