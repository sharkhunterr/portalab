"""012 T006 — members directory: pagination, search by display name, visibility filtering (listing surface),
Active accounts only, ordering by display name only, an empty result offers a next action (client side:
the response is simply empty, never an error)."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from portalab.modules.identity.domain.state_machine import AccountState
from tests.integration.community.conftest import CoHarness
from tests.integration.identity.helpers import create_user, login, module_of, set_state

pytestmark = pytest.mark.integration


async def test_directory(co: CoHarness, client: AsyncClient, app: FastAPI) -> None:
    await login(client, "ursula")
    names = [m["display_name"] for m in (await client.get("/api/v1/community/members")).json()["items"]]
    assert names == ["Boss", "Mona", "Ulrich", "Ursula", "Vera"]  # Community default; by name only
    first = (await client.get("/api/v1/community/members", params={"limit": 2})).json()
    assert [m["display_name"] for m in first["items"]] == ["Boss", "Mona"] and first["next_cursor"]
    second = (
        await client.get("/api/v1/community/members", params={"limit": 2, "cursor": first["next_cursor"]})
    ).json()
    assert [m["display_name"] for m in second["items"]] == ["Ulrich", "Ursula"]
    found = (await client.get("/api/v1/community/members", params={"q": "ULR"})).json()["items"]
    assert [m["display_name"] for m in found] == ["Ulrich"]
    assert (await client.get("/api/v1/community/members", params={"q": "nobody"})).json() == {
        "items": [],
        "next_cursor": None,
        "anonymous": 0,  # issue 347: never counted in a search
    }

    await co.prefer("ulrich", "member_listing", "private")
    await co.prefer("mona", "member_listing", "private")
    page = (await client.get("/api/v1/community/members", params={"limit": 2})).json()
    assert [m["display_name"] for m in page["items"]] == ["Boss", "Ursula"]  # page still filled
    rest = (
        await client.get("/api/v1/community/members", params={"limit": 2, "cursor": page["next_cursor"]})
    ).json()
    assert [m["display_name"] for m in rest["items"]] == ["Vera"] and rest["next_cursor"] is None
    await login(client, "ulrich")  # a member always sees themself
    assert "Ulrich" in [
        m["display_name"] for m in (await client.get("/api/v1/community/members")).json()["items"]
    ]

    identity = module_of(app)
    await create_user(identity, "sleepy", state=AccountState.SUSPENDED)
    await set_state(identity, co.people["vera"], AccountState.SUSPENDED)
    await login(client, "ursula")
    listed = [m["display_name"] for m in (await client.get("/api/v1/community/members")).json()["items"]]
    assert "Vera" not in listed and "sleepy" not in listed
    assert (await client.get(f"/api/v1/community/members/{co.people['vera']}")).status_code == 404


async def test_anonymous_members_close_the_directory(co: CoHarness, client: AsyncClient) -> None:
    """Issue 347: an anonymous member (progression private) stays in the directory, counted at its end with no
    name nor profile, never found by a search; they still see themself."""
    await co.prefer("mona", "progression", "private")
    await login(client, "ursula")
    page = (await client.get("/api/v1/community/members")).json()
    assert [m["display_name"] for m in page["items"]] == ["Boss", "Ulrich", "Ursula", "Vera"]
    assert page["anonymous"] == 1
    first = (await client.get("/api/v1/community/members", params={"limit": 2})).json()
    assert first["anonymous"] == 0 and first["next_cursor"]  # counted on the last page only
    assert (await client.get("/api/v1/community/members", params={"q": "mon"})).json()["items"] == []
    assert (await client.get(f"/api/v1/community/members/{co.people['mona']}")).status_code == 404
    await co.prefer("ulrich", "member_listing", "private")  # kept out of the directory: not even counted
    await co.prefer("ulrich", "progression", "private")
    assert (await client.get("/api/v1/community/members")).json()["anonymous"] == 1
    await login(client, "mona")
    mine = (await client.get("/api/v1/community/members")).json()
    assert "Mona" in [m["display_name"] for m in mine["items"]] and mine["anonymous"] == 0


async def test_requires_sign_in(co: CoHarness, client: AsyncClient) -> None:
    assert (await client.get("/api/v1/community/members")).status_code == 401
