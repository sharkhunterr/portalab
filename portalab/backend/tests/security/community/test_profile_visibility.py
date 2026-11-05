"""012 T005 — profile visibility matrix: owner / member / Admin / moderator by Public / Community /
Leaderboards-only / Private for identity, progression, achievements, activity and projects. A permission
alone never reveals Private; a Private section is absent (not "hidden"); non-Active accounts are not
profiles; each section fails independently (013 down ⇒ that section ``unavailable``)."""

from typing import Any

import pytest
from httpx import AsyncClient

from portalab.capabilities.visibility import Level
from portalab.modules.identity.domain.state_machine import AccountState
from tests.integration.community.conftest import CoHarness
from tests.integration.identity.helpers import login, module_of, set_state

pytestmark = pytest.mark.integration

DATA = {
    "identity": "member_listing",
    "progression": "progression",
    "achievements": "progression",
    "activity": "community_activity",
    "projects": "projects",
}


async def sections(client: AsyncClient, viewer: str, owner: Any) -> dict[str, str] | None:
    await login(client, viewer)
    response = await client.get(f"/api/v1/community/members/{owner}")
    if response.status_code == 404:
        return None
    assert response.status_code == 200, response.text
    return {s["key"]: s["state"] for s in response.json()["sections"]}


@pytest.mark.parametrize("level", ["public", "community", "leaderboard", "private"])
async def test_matrix(co: CoHarness, client: AsyncClient, level: Level) -> None:
    owner = co.people["ursula"]
    for datum in set(DATA.values()):
        await co.prefer("ursula", datum, level)
    expected_visible = level in ("public", "community")
    for viewer in ("ulrich", "boss", "mona"):  # member, Admin, moderator: permission is not consent
        seen = await sections(client, viewer, owner)
        if expected_visible:
            assert seen is not None and set(seen) == set(DATA), (viewer, seen)
        else:
            assert seen is None, (viewer, seen)  # nothing visible: 404 revealing nothing
    mine = await sections(client, "ursula", owner)
    assert mine is not None and set(mine) == set(DATA)  # the owner sees everything


async def test_sections_are_independent(co: CoHarness, client: AsyncClient) -> None:
    owner = co.people["ursula"]
    await co.prefer("ursula", "community_activity", "private")
    seen = await sections(client, "ulrich", owner)
    assert seen is not None and set(seen) == set(DATA) - {"activity"}
    absent = await client.get(f"/api/v1/community/members/{owner}/sections/activity")
    assert absent.status_code == 404  # absent, not "hidden"
    await co.prefer("ursula", "community_activity", "community")
    await co.prefer("ursula", "progression", "private")  # issue 347: anonymous — no profile for the others
    assert await sections(client, "ulrich", owner) is None
    assert await sections(client, "ursula", owner) is not None  # one knows oneself
    await login(client, "ulrich")
    await co.prefer("ursula", "progression", "community")
    await co.prefer("ursula", "member_listing", "private")
    body = (await client.get(f"/api/v1/community/members/{owner}")).json()
    assert body["display_name"] is None and "identity" not in {s["key"] for s in body["sections"]}
    progression = (await client.get(f"/api/v1/community/members/{owner}/sections/progression")).json()
    assert progression["state"] == "available" and progression["data"]["level"] == 3
    co.progression.down = True
    seen = await sections(client, "ulrich", owner)
    assert seen is not None and seen["progression"] == "unavailable" and seen["achievements"] == "unavailable"
    assert seen["activity"] == "no-data"  # the other sections still render


async def test_non_active_accounts_are_not_profiles(co: CoHarness, client: AsyncClient, app: Any) -> None:
    await set_state(module_of(app), co.people["vera"], AccountState.SUSPENDED)
    assert await sections(client, "ulrich", co.people["vera"]) is None
    assert await sections(client, "ulrich", "01900000-0000-7000-8000-00000000dead") is None
