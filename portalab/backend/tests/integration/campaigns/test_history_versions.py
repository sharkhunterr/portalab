"""014 T026 — editing an active campaign publishes a new version effective now (confirmation required);
earlier grants keep the old version; history never rewritten; the history lists versions, occurrences,
intervals and overrides; simulation writes nothing."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.campaigns.conftest import HALLOWEEN, SYSTEM, CampHarness, later, paris
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_versions_and_history(cm: CampHarness, client: AsyncClient) -> None:
    campaign = await cm.create()
    rule = await cm.gamification.rules.save(
        SYSTEM, "watch", {"event_type": "media.played", "grants": [{"value": "xp", "amount": 10}]}
    )
    await cm.gamification.rules.publish(SYSTEM, "watch", rule.version)
    await cm.at(later(paris(10, 20, 0), minutes=1))
    user = cm.people["ursula"]
    await cm.play(user, "m1", paris(10, 21, 20))
    cm.clock.set(paris(10, 22, 12))
    await login(client, "boss")
    edited = {**HALLOWEEN, "modifiers": [{"id": "everything", "value": "xp", "factor": 3}]}
    first = await client.put(f"/api/v1/admin/campaigns/{campaign}", json={"definition": edited})
    assert first.status_code == 409
    done = await client.put(
        f"/api/v1/admin/campaigns/{campaign}",
        json={"definition": edited, "confirmation": first.json()["confirmation"]},
    )
    assert done.json()["current_version"] == 2
    await cm.play(user, "m2", paris(10, 23, 20))
    await cm.play(user, "m1", paris(10, 21, 22))  # a late event from before the edit: version 1 applies
    async with cm.database.session() as session:
        refs = (
            (
                await session.execute(
                    text("SELECT modifiers::text FROM gamification.transactions ORDER BY seq")
                )
            )
            .scalars()
            .all()
        )
    assert "campaign:halloween:1:" in refs[0] and "campaign:halloween:2:everything" in refs[1]
    assert "campaign:halloween:1:" in refs[2]
    simulated = await client.post(
        f"/api/v1/admin/campaigns/{campaign}/simulate",
        json={"event_type": "media.played", "payload": {"media_id": "m2"}},
    )
    assert [(s["modifier"], s["verdict"], s["version"]) for s in simulated.json()] == [
        ("everything", "match", 2)
    ]
    history = (await client.get(f"/api/v1/admin/campaigns/{campaign}/history")).json()
    assert [v["version"] for v in history["versions"]] == [1, 2]
    assert history["intervals"][0]["closed_at"] is None and history["occurrences"][0]["status"] == "active"
    async with cm.database.session() as session:
        published = await session.scalar(
            text("SELECT count(*) FROM events.events WHERE type = 'campaign.version_published'")
        )
    assert published == 1
