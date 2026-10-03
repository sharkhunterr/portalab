"""023 T023 — plugin events are namespaced and validated by 007 (a secret-looking payload is
quarantined); plugin permissions are namespaced, listed for consent at install and enforced by 003; a
plugin capability is consumed through the 001 registry only; personal data requires an erasure
participant (refused otherwise)."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.core.errors import ValidationFailed
from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import SYSTEM, PlHarness

pytestmark = pytest.mark.integration


async def test_events_permissions_capabilities(pl: PlHarness, client: AsyncClient) -> None:
    await pl.installed(pl.hello())
    assert pl.registries.event_types.get("plugin.hello.greeted") is not None
    async with pl.database.unit_of_work() as uow:
        await pl.ev.publisher.publish(
            uow.session, "plugin.hello.greeted", {"count": 1}, occurred_at=pl.clock.now(), source="plugin"
        )
        await pl.ev.publisher.publish(
            uow.session,
            "plugin.hello.greeted",
            {"api_token": "s3cr3t"},
            occurred_at=pl.clock.now(),
            source="plugin",
        )
    async with pl.database.session() as session:
        stored = await session.scalar(
            text("SELECT count(*) FROM events.events WHERE type = 'plugin.hello.greeted'")
        )
        quarantined = await session.scalar(
            text("SELECT count(*) FROM events.quarantine WHERE event_type = 'plugin.hello.greeted'")
        )
    assert stored == 1 and quarantined == 1

    await login(client, "ursula")  # no plugin permission: the plugin's page and routes are closed
    assert (await client.get("/api/v1/plugins/hello/greetings/count")).status_code == 403
    await login(client, "boss")
    assert (await client.get("/api/v1/plugins/hello/greetings/count")).json()["value"] == 0

    [greeter] = pl.registries.capabilities.system_providers("plugin.hello.greeter")
    assert greeter.owner == "plugin:hello" and await greeter.provider.count() == 0
    with pytest.raises(ValidationFailed):
        await pl.module.lifecycle.install(
            SYSTEM, pl.package("hoarder", manifest={"personal_data": {"enabled": True}})
        )
