"""012 T025 — participation and recognition: take part as contributor/tester/helper; the proposer (or a
moderator) recognizes once; self-recognition refused; per-recognizer daily and per-pair limits; the
``community.contribution_recognized`` event (dedup participation) becomes Contribution through a real 013
reward rule, credited to the contributor once."""

from dataclasses import replace
from datetime import timedelta

import pytest
from httpx import AsyncClient

from portalab.capabilities.ai import AIToolRegistry
from portalab.capabilities.automation_actions import ActionRegistry
from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.observability import ObservableRegistry
from portalab.core.authz_port import Principal
from portalab.modules.gamification.module import GamificationModule
from tests.integration.community.conftest import CoHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def economy(co: CoHarness) -> GamificationModule:
    module = GamificationModule(
        co.database,
        co.ev.publisher,
        co.ev.full.authz.audit,
        co.module.capabilities,
        co.ev.full.authz.engine,
        clock=co.clock,
        visibility=co.ev.full.privacy.filter,
        event_types=co.ev.types,
        consumers=co.ev.consumers,
        widgets=WidgetRegistry(),
        observables=ObservableRegistry(),
        actions=ActionRegistry(),
        tools=AIToolRegistry(),
    )
    module.register()
    await module.levels.ensure_default()
    rule = {
        "event_type": "community.contribution_recognized",
        "grants": [{"value": "contribution", "amount": 10}],
    }
    row = await module.rules.save(Principal(channel="system"), "recognized", rule)
    await module.rules.publish(Principal(channel="system"), "recognized", row.version)
    co.clock.advance(timedelta(minutes=1))
    return module


async def test_participation_and_recognition(co: CoHarness, client: AsyncClient) -> None:
    gam = await economy(co)
    co.module.config = replace(co.module.config, proposals_moderation=False, recognition_max_per_day=2)
    proposal = await co.module.proposals.create(co.p("ursula"), "project", "Dark mode", "")
    other = await co.module.proposals.create(co.p("ursula"), "feature", "Light mode", "")
    base = f"/api/v1/community/proposals/{proposal.id}"
    ids = {}
    for name, role in (
        ("ulrich", "tester"),
        ("vera", "contributor"),
        ("ursula", "helper"),
        ("boss", "helper"),
    ):
        await login(client, name)
        joined = await client.post(f"{base}/participation", json={"role": role, "note": "I can help"})
        assert joined.status_code == 201
        ids[name] = joined.json()["id"]
    await login(client, "ulrich")
    assert (
        await client.post(f"{base}/participations/{ids['vera']}/recognize")
    ).status_code == 403  # not proposer
    await login(client, "ursula")
    own = await client.post(f"{base}/participations/{ids['ursula']}/recognize")
    assert own.status_code == 403 and own.json()["code"] == "community.self_recognition"
    assert (await client.post(f"{base}/participations/{ids['ulrich']}/recognize")).json()[
        "recognized"
    ] is True
    twice = await client.post(f"{base}/participations/{ids['ulrich']}/recognize")
    assert twice.status_code == 409 and twice.json()["code"] == "community.already_recognized"
    await client.post(f"{base}/participations/{ids['vera']}/recognize")
    limited = await client.post(f"{base}/participations/{ids['boss']}/recognize")
    assert limited.status_code == 409 and limited.json()["code"] == "community.recognition_limit"  # 2 per day

    co.clock.advance(timedelta(days=2))
    await login(client, "ulrich")
    second = await client.post(
        f"/api/v1/community/proposals/{other.id}/participation", json={"role": "tester"}
    )
    await login(client, "ursula")
    pair = await client.post(
        f"/api/v1/community/proposals/{other.id}/participations/{second.json()['id']}/recognize"
    )
    assert (
        pair.status_code == 409 and pair.json()["code"] == "community.recognition_limit"
    )  # same pair, 30 days

    await co.dispatch()
    assert await gam.economy.balance(co.people["ulrich"], "contribution") == 10
    assert await gam.economy.balance(co.people["vera"], "contribution") == 10
    assert await gam.economy.balance(co.people["ursula"], "contribution") == 0

    await login(client, "vera")
    assert (await client.delete(f"{base}/participation")).status_code == 204
    listed = (await client.get(f"{base}/participations")).json()
    assert {p["role"] for p in listed} == {"tester", "helper"} and all("note" in p for p in listed)
