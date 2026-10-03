"""015 T012 — reject/abandon release every reservation (new transactions, ``funding_released``); release
consumes per rules (at release, or per milestone percentages); never partial without a rule; idempotent
re-runs; zero reconciliation drift; a funder's deletion destroys their reservations in every project state
(R6) and the project totals drop."""

import pytest
from sqlalchemy import text

from portalab.modules.gamification.privacy.participant import GamificationParticipant
from portalab.modules.marketplace.privacy.participant import MarketplaceParticipant
from tests.integration.marketplace.conftest import RULES, MkHarness

pytestmark = pytest.mark.integration
MILESTONES = {**RULES, "consume_at": [{"state": "beta", "percent": 40}, {"state": "released", "percent": 60}]}


async def fund(mk: MkHarness, name: str, project: object, amount: int) -> None:
    await mk.module.fundings.fund(
        mk.p(name), project, amount, acknowledged=True, request_key=f"{name}{amount}"
    )  # type: ignore[arg-type]


async def test_reject_releases_everything(mk: MkHarness) -> None:
    project = await mk.project(open_with=RULES)
    for name in ("ursula", "ulrich"):
        await mk.coins(name, 100)
        await fund(mk, name, project, 70)
    await mk.module.transition(mk.p("boss"), project, "rejected", reason="Out of scope")
    assert await mk.balance("ursula") == 100 and await mk.balance("ulrich") == 100
    assert sorted(e["amount"] for e in await mk.events("project.funding_released")) == [70, 70]
    assert await mk.module.resolution.reconcile() == {"tranches": 2, "drift": 0}
    async with mk.database.session() as session:
        assert (
            await mk.module.resolution.settle(session, await mk.module.projects.get(project), None) == 0
        )  # idempotent


async def test_milestones_and_deletion(mk: MkHarness) -> None:
    project = await mk.project(open_with=MILESTONES)
    for name in ("ursula", "ulrich", "vera"):
        await mk.coins(name, 100)
        await fund(mk, name, project, 100)
    for name in ("ursula", "ulrich", "vera"):
        assert await mk.balance(name) == 0
    await mk.module.transition(mk.p("boss"), project, "validation")
    vera = mk.people["vera"]
    await MarketplaceParticipant(mk.database, clock=mk.clock).erase(vera, "final")
    await GamificationParticipant(mk.database, mk.economy.writer, clock=mk.clock).erase(vera, "final")
    summary = await mk.module.projects.funding_summary(str(project))
    assert summary is not None and summary.reserved == 200 and summary.funders == 2  # vera's 100 destroyed

    await mk.module.transition(mk.p("boss"), project, "development")
    await mk.module.transition(mk.p("boss"), project, "beta")
    summary = await mk.module.projects.funding_summary(str(project))
    assert summary is not None and (summary.consumed, summary.reserved) == (80, 120)
    await mk.module.transition(mk.p("boss"), project, "abandoned", reason="Stalled")  # remainder released
    assert await mk.balance("ursula") == 60 and await mk.balance("ulrich") == 60
    summary = await mk.module.projects.funding_summary(str(project))
    assert summary is not None and (summary.consumed, summary.reserved) == (80, 0)
    assert sorted(e["amount"] for e in await mk.events("project.funding_consumed")) == [40, 40]
    assert sorted(e["amount"] for e in await mk.events("project.funding_released")) == [60, 60]
    assert (await mk.module.resolution.reconcile())["drift"] == 0
    async with mk.database.session() as session:
        statuses = (
            (
                await session.execute(
                    text("SELECT status FROM marketplace.project_fundings ORDER BY created_at")
                )
            )
            .scalars()
            .all()
        )
        vera_balance = await session.scalar(
            text("SELECT coalesce(sum(amount), 0) FROM gamification.balances WHERE user_id = :u"), {"u": vera}
        )
    assert sorted(statuses) == ["consumed", "consumed", "destroyed_on_deletion"]
    assert vera_balance == 0


async def test_release_consumes_everything(mk: MkHarness) -> None:
    project = await mk.project(open_with=RULES)
    await mk.coins("ursula", 50)
    await fund(mk, "ursula", project, 50)
    for state in ("validation", "development", "released"):
        await mk.module.transition(mk.p("boss"), project, state)
    assert await mk.balance("ursula") == 0
    summary = await mk.module.projects.funding_summary(str(project))
    assert summary is not None and summary.consumed == 50 and summary.reserved == 0
