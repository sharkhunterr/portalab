"""014 T012 — manual activation/deactivation: recorded with actor, reason, confirmation and audit; wins over
the schedule until the occurrence end / next start / ``until``; the schedule resumes; conflicting overrides
are rejected; paused within a window; only ``campaigns.manage`` may do it."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.campaigns.conftest import CampHarness, later, paris
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def confirm(client: AsyncClient, path: str, body: dict[str, object]) -> object:
    first = await client.post(path, json=body)
    assert first.status_code == 409 and first.json()["code"] == "authz.confirmation_required", first.text
    return await client.post(path, json={**body, "confirmation": first.json()["confirmation"]})


async def test_override_lifecycle(cm: CampHarness, client: AsyncClient) -> None:
    campaign = await cm.create()
    await cm.at(paris(10, 22, 12))
    cm.clock.set(paris(10, 22, 14))  # active for two hours before the deactivation
    await login(client, "ursula")
    denied = await client.post(f"/api/v1/admin/campaigns/{campaign}/deactivate", json={"reason": "nope"})
    assert denied.status_code == 403
    await login(client, "boss")
    paused = await confirm(
        client, f"/api/v1/admin/campaigns/{campaign}/deactivate", {"reason": "Server load"}
    )
    assert paused.status_code == 200 and paused.json()["state"] == "paused"  # type: ignore[attr-defined]
    again = await client.post(
        f"/api/v1/admin/campaigns/{campaign}/deactivate", json={"reason": "twice", "confirmation": "x"}
    )
    assert again.status_code in (403, 409)
    from portalab.modules.campaigns.overrides.service import OverrideConflict

    with pytest.raises(OverrideConflict):
        await cm.campaigns.overrides.apply(cm.p("boss"), campaign, "deactivate", "twice")
    await cm.at(paris(10, 25, 12))
    assert (await client.get(f"/api/v1/admin/campaigns/{campaign}")).json()[
        "state"
    ] == "paused"  # until next start
    resumed = await confirm(
        client, f"/api/v1/admin/campaigns/{campaign}/activate", {"reason": "Load is fine"}
    )
    assert resumed.json()["state"] == "active"  # type: ignore[attr-defined]
    await cm.at(later(paris(11, 1, 0), minutes=1))  # the manual activation ends with the occurrence
    history = (await client.get(f"/api/v1/admin/campaigns/{campaign}/history")).json()
    causes = [(i["cause"], i["reason"]) for i in history["intervals"]]
    assert causes == [("schedule", None), ("manual", "Load is fine")]
    assert [o["kind"] for o in history["overrides"]] == ["deactivate", "activate"]
    await cm.at(later(paris(10, 20, 0, year=2027), minutes=1))  # schedule resumed next year
    await login(client, "boss")  # a year later the session has expired
    assert (await client.get(f"/api/v1/admin/campaigns/{campaign}")).json()["state"] == "active"
    async with cm.database.session() as session:
        audits = (
            (
                await session.execute(
                    text("SELECT action FROM audit.audit_entries WHERE action LIKE 'campaign.%' ORDER BY seq")
                )
            )
            .scalars()
            .all()
        )
        lifecycle = (
            (
                await session.execute(
                    text(
                        "SELECT type FROM events.events WHERE type IN ('campaign.paused', 'campaign.resumed')"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert {"campaign.created", "campaign.deactivated", "campaign.activated"} <= set(audits)
    assert lifecycle == ["campaign.paused", "campaign.resumed"]


async def test_activation_outside_a_window_needs_an_end(cm: CampHarness) -> None:
    from portalab.core.errors import ValidationFailed

    campaign = await cm.create()
    with pytest.raises(ValidationFailed):
        await cm.campaigns.overrides.apply(cm.p("boss"), campaign, "activate", "early bird")
    await cm.campaigns.overrides.apply(cm.p("boss"), campaign, "activate", "early bird", until=paris(10, 3))
    async with cm.database.session() as session:
        assert await session.scalar(text("SELECT cause FROM campaigns.open_intervals")) == "manual"
    await cm.at(paris(10, 3, 13))
    async with cm.database.session() as session:
        assert await session.scalar(text("SELECT count(*) FROM campaigns.open_intervals")) == 0
        assert await session.scalar(text("SELECT state FROM campaigns.campaigns")) == "scheduled"
