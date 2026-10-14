"""013 T029 — another user's progression only as their visibility (021) allows (404 otherwise, even for a
permission holder); ledger views owner-only or ``economy.manage`` (audited); events carry no PII."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.gamification.conftest import RULE, GamHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_visibility_and_ledger_access(gm: GamHarness, client: AsyncClient) -> None:
    await gm.rule("listen", RULE)
    user = gm.people["ursula"]
    await gm.emit(user)
    preferences = gm.module.capabilities.system_providers("privacy.visibility_preference")
    provider = next(p.provider for p in preferences if p.instance_ref == "gamification")
    await provider.set_preference(user, "progression", None, "private")  # issue 120: the default is shown
    await login(client, "ulrich")
    assert (await client.get(f"/api/v1/users/{user}/progression")).status_code == 404
    await login(client, "boss")
    assert (
        await client.get(f"/api/v1/users/{user}/progression")
    ).status_code == 404  # a permission is not consent
    await provider.set_preference(user, "progression", None, "community")
    await login(client, "ulrich")
    shown = await client.get(f"/api/v1/users/{user}/progression")
    assert shown.status_code == 200 and shown.json()["xp"] == 20
    await login(client, "boss")
    ledger = await client.get("/api/v1/admin/economy/transactions", params={"user": str(user)})
    assert ledger.status_code == 200 and len(ledger.json()["items"]) == 2
    async with gm.database.session() as session:
        viewed = await session.scalar(
            text("SELECT count(*) FROM audit.audit_entries WHERE action = 'economy.ledger_viewed'")
        )
        payloads = (
            (
                await session.execute(
                    text(
                        "SELECT payload::text FROM events.events "
                        "WHERE type LIKE 'reward.%' OR type LIKE 'economy.%'"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert viewed == 1
    assert all("ursula" not in p and str(user) not in p for p in payloads)
