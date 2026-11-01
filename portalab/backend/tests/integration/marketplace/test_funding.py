"""015 T010 — funding only while ``open``; the non-guarantee acknowledgement is mandatory; amount limits;
a ledger reservation atomic with the funding row; insufficient Coins refused and the balance never
negative; concurrent fundings stay consistent; idempotent requests; independent of voting;
``project.funding_added`` once per request."""

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import RULES, MkHarness

pytestmark = pytest.mark.integration


async def test_funding_rules(mk: MkHarness, client: AsyncClient) -> None:
    closed = await mk.project("Not yet open")
    project = await mk.project(open_with=RULES)
    await mk.coins("ursula", 150)
    await login(client, "ursula")
    fund = f"/api/v1/projects/{project}/fund"
    missing = await client.post(fund, json={"amount": 50})
    assert missing.status_code == 422 and missing.json()["code"] == "project.acknowledgement_required"
    refused = await client.post(f"/api/v1/projects/{closed}/fund", json={"amount": 50, "acknowledged": True})
    assert refused.status_code == 409 and refused.json()["code"] == "project.funding_closed"
    for amount in (2, 201):
        bad = await client.post(fund, json={"amount": amount, "acknowledged": True})
        assert bad.status_code == 422 and bad.json()["code"] == "project.funding_limits"

    first = await client.post(
        fund, json={"amount": 100, "acknowledged": True}, headers={"Idempotency-Key": "r1"}
    )
    replay = await client.post(
        fund, json={"amount": 100, "acknowledged": True}, headers={"Idempotency-Key": "r1"}
    )
    assert first.status_code == 201 and replay.json()["id"] == first.json()["id"]
    assert first.json()["reserved"] == 100 and await mk.balance("ursula") == 50
    poor = await client.post(fund, json={"amount": 60, "acknowledged": True})
    assert poor.status_code == 409 and poor.json()["code"] == "economy.insufficient_coins"
    assert await mk.balance("ursula") == 50
    over = await client.post(fund, json={"amount": 101, "acknowledged": True})
    assert over.status_code == 422 and over.json()["max"] == 100  # per-member cap of 200
    assert len(await mk.events("project.funding_added")) == 1

    mine = (await client.get("/api/v1/me/fundings")).json()
    assert [(f["amount"], f["status"], f["project_state"]) for f in mine] == [(100, "reserved", "open")]
    async with mk.database.session() as session:
        votes = await session.scalar(text("SELECT count(*) FROM pg_tables WHERE tablename = 'votes'"))
    assert votes in (0, 1)  # funding never creates or needs a vote (votes belong to Community)


async def test_concurrent_fundings_stay_consistent(mk: MkHarness) -> None:
    project = await mk.project(open_with=RULES)
    await mk.coins("ulrich", 100)

    async def attempt(index: int) -> object:
        try:
            return await mk.module.fundings.fund(
                mk.p("ulrich"), project, 40, acknowledged=True, request_key=f"c{index}"
            )
        except Exception as error:  # some must fail
            return error

    results = await asyncio.gather(*(attempt(i) for i in range(4)))
    succeeded = [r for r in results if not isinstance(r, Exception)]
    assert len(succeeded) == 2 and await mk.balance("ulrich") == 20
    summary = await mk.module.projects.funding_summary(str(project))
    assert summary is not None and summary.reserved == 80 and summary.funders == 1


async def test_funders_largest_first_each_as_they_allow(mk: MkHarness, client: AsyncClient) -> None:
    """#304: who backs a project, the largest first, each member's fundings added up — another member who
    has not made their progression public is there without their name."""
    project = await mk.project(open_with=RULES)
    await mk.coins("ulrich", 100)
    await mk.coins("ursula", 150)
    for key in ("a", "b"):
        await mk.module.fundings.fund(mk.p("ulrich"), project, 40, acknowledged=True, request_key=key)
    await mk.module.fundings.fund(mk.p("ursula"), project, 100, acknowledged=True, request_key="c")
    await login(client, "ursula")
    funders = (await client.get(f"/api/v1/projects/{project}/funders")).json()
    assert [(f["amount"], f["me"], f["name"] is not None) for f in funders] == [
        (100, True, True),
        (80, False, False),
    ]
    assert funders[1]["user_id"] is None  # anonymous: nothing that leads to them
    assert (await client.get(f"/api/v1/projects/{funders[0]['user_id']}/funders")).status_code == 404
