"""012 T022 — votes: free, no minimum level; one active vote per account (concurrent duplicates count
once); retract and re-cast while the lifecycle accepts votes; non-active accounts refused with
``community.not_active_account``; voting never requires funding; public counts, private voters;
``project.vote_added|vote_retracted`` with dedup."""

import asyncio
from dataclasses import replace
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text

from portalab.modules.identity.domain.state_machine import AccountState
from tests.integration.community.conftest import CoHarness, with_marketplace
from tests.integration.identity.helpers import login, module_of, set_state

pytestmark = pytest.mark.integration


async def test_votes(co: CoHarness, client: AsyncClient, app: FastAPI) -> None:
    co.module.config = replace(co.module.config, proposals_moderation=False)
    marketplace = with_marketplace(co)
    proposal = await co.module.proposals.create(co.p("ursula"), "project", "Dark mode", "")
    path = f"/api/v1/community/proposals/{proposal.id}/vote"
    await login(client, "ulrich")
    assert (await client.post(path)).json() == {"votes": 1, "my_vote": True}
    assert (await client.post(path)).json()["votes"] == 1  # one active vote
    assert (await client.delete(path)).json() == {"votes": 0, "my_vote": False}
    assert (await client.post(path)).json()["votes"] == 1  # re-cast
    results = await asyncio.gather(*(co.module.votes.cast(co.p("vera"), proposal.id) for _ in range(5)))
    assert max(results) == 2 and await co.module.proposals.count(proposal.id) == 2

    detail = (await client.get(f"/api/v1/community/proposals/{proposal.id}")).json()
    assert detail["votes"] == 2 and detail["my_vote"] is True
    assert str(co.people["vera"]) not in str(detail)  # voters are private

    await set_state(module_of(app), co.people["vera"], AccountState.SUSPENDED)
    from portalab.core.errors import Forbidden

    with pytest.raises(Forbidden) as refused:
        await co.module.votes.retract(co.p("vera"), proposal.id)
    assert refused.value.code == "community.not_active_account"

    assert proposal.lifecycle_ref is not None
    project = await marketplace.projects.get(UUID(proposal.lifecycle_ref))
    for state in ("proposal", "open", "validation"):
        await marketplace.transition(co.p("boss"), project.id, state)
    closed = await client.delete(path)
    assert closed.status_code == 409 and closed.json()["code"] == "community.voting_closed"

    async with co.database.session() as session:
        events = (
            await session.execute(
                text("SELECT type, payload FROM events.events WHERE type LIKE 'project.vote_%' ORDER BY seq")
            )
        ).all()
        fundings = await session.scalar(text("SELECT count(*) FROM marketplace.project_fundings"))
    assert [t for t, _ in events] == [
        "project.vote_added",
        "project.vote_retracted",
        "project.vote_added",
        "project.vote_added",
    ]
    assert all(set(p) == {"proposal", "count"} for _, p in events)
    assert fundings == 0  # voting never funds
