"""Spec 032 — households: a member account holds profiles (members of their own without a login), picked on
« Who's there? » and used through the master's session; entering a profile asks its PIN (not for the master),
coming back to the master asks the master's PIN, wrong PINs slow down; a profile never reaches the account's
own routes nor manages the household; every member sees the household, the master manages it and decides on
its profiles' access requests; deleting a profile signs out the browsers using it, deleting the master
takes its profiles along; a profile kept out of the community is no member there."""

from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.identity_directory import MEMBERS
from portalab.core.authz_port import Principal
from portalab.modules.identity.models import User
from portalab.modules.identity.module import IdentityModule
from portalab.modules.identity.services.common import self_actor
from tests.integration.identity.helpers import PASSWORD, create_user, login, module_of


def households(app: FastAPI) -> Any:
    """032: the household module's service (the households are no longer identity's)."""
    return app.state.household_module.service


pytestmark = pytest.mark.integration


async def _profile(
    client: httpx.AsyncClient, name: str, kind: str = "standard", pin: str | None = None
) -> UUID:
    body = {"display_name": name, "kind": kind} | ({"pin": pin} if pin else {})
    response = await client.post("/api/v1/household/profiles", json=body)
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def _switch(client: httpx.AsyncClient, to: UUID, pin: str | None = None) -> httpx.Response:
    return await client.post(
        "/api/v1/household/switch", json={"user_id": str(to)} | ({"pin": pin} if pin else {})
    )


async def _me(client: httpx.AsyncClient) -> dict[str, object]:
    response = await client.get("/api/v1/me")
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


async def _family(app: FastAPI, client: httpx.AsyncClient) -> tuple[IdentityModule, UUID, UUID, UUID]:
    module = module_of(app)
    alice = await create_user(module, "alice")
    await login(client, "alice")
    lea = await _profile(client, "Léa", "child", pin="1234")
    tom = await _profile(client, "Tom")
    return module, alice, lea, tom


async def test_who_is_there_then_switch_with_pins(app: FastAPI, client: httpx.AsyncClient) -> None:
    module, alice, lea, tom = await _family(app, client)
    me = await _me(client)
    assert me["household_profiles"] == 2 and me["profile_of"] is None
    state = (await client.get("/api/v1/household/session")).json()
    assert state["must_choose"] is True and state["active_id"] == str(alice)
    assert [m["display_name"] for m in state["members"]] == ["alice", "Léa", "Tom"]
    assert [m["kind"] for m in state["members"]] == ["owner", "child", "standard"]
    assert [m["needs_pin"] for m in state["members"]] == [
        False,
        True,
        False,
    ]  # Léa's PIN, even for the master

    asked = await _switch(client, lea)
    assert asked.status_code == 403 and asked.json()["code"] == "household.wrong_pin"
    assert (await _switch(client, lea, "1234")).status_code == 200
    me = await _me(client)
    assert me["id"] == str(lea) and me["profile_of"] == str(alice) and me["login"] is None
    state = (await client.get("/api/v1/household/session")).json()
    assert state["must_choose"] is False and state["active_id"] == str(lea)

    assert (await _switch(client, tom)).status_code == 200
    wrong = await _switch(client, lea)
    assert wrong.status_code == 403 and wrong.json()["code"] == "household.wrong_pin"
    assert (await _switch(client, lea, "1234")).status_code == 200

    # the master's PIN guards the way back from a profile
    refused = await client.put(f"/api/v1/household/members/{alice}/pin", json={"pin": "9999"})
    assert refused.status_code == 403 and refused.json()["code"] == "household.owner_only"
    assert (await _switch(client, alice)).status_code == 200  # no master PIN yet
    assert (
        await client.put(f"/api/v1/household/members/{alice}/pin", json={"pin": "9999"})
    ).status_code == 204
    assert (await _switch(client, lea, "1234")).status_code == 200
    assert (await _switch(client, alice)).status_code == 403
    assert (await _switch(client, alice, "9999")).status_code == 200
    assert (await _me(client))["id"] == str(alice)

    stranger = await create_user(module, "bob")
    lost = await _switch(client, stranger)
    assert lost.status_code == 404 and lost.json()["code"] == "household.member_not_found"


async def test_a_profile_never_reaches_the_account(app: FastAPI, client: httpx.AsyncClient) -> None:
    _, _, lea, _ = await _family(app, client)
    await _switch(client, lea, "1234")
    for method, path, body in (
        ("POST", "/api/v1/me/password", {"current_password": PASSWORD, "new_password": "x" * 16}),
        ("POST", "/api/v1/me/mfa/setup", {"password": PASSWORD}),
        ("POST", "/api/v1/me/deletion", {"password": PASSWORD}),
        ("POST", "/api/v1/household/profiles", {"display_name": "Max"}),
    ):
        response = await client.request(method, path, json=body)
        assert response.status_code == 403, (path, response.text)
        assert response.json()["code"] == "household.owner_only", path


async def test_wrong_pins_slow_down(app: FastAPI, client: httpx.AsyncClient) -> None:
    _, _, lea, tom = await _family(app, client)
    await _switch(client, tom)
    codes = [(await _switch(client, lea, "0000")).status_code for _ in range(7)]
    assert codes[:5] == [403] * 5 and codes[-1] == 429
    throttled = await _switch(client, lea, "1234")  # even the right one waits
    assert throttled.status_code == 429 and throttled.json()["code"] == "household.pin_throttled"


async def test_everyone_sees_the_household_the_master_manages_it(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    _, alice, lea, tom = await _family(app, client)
    view = (await client.get("/api/v1/household")).json()
    assert view["can_manage"] is True and view["owner_id"] == str(alice) and view["totals"] is not None
    child = next(m for m in view["members"] if m["id"] == str(lea))
    assert child["restrictions"] == {
        "max_age": 12,
        "allow_unrated": False,
        "blocked": ["ai", "community", "requests", "shop"],
        "birth_date": None,
        "mode": "hide",
        "requests": True,
        "genres": ["crime", "horror", "thriller", "war"],  # issue 432: at least these for a child
        "types": [],
        "titles": [],
        "daily_minutes": None,
        "services": False,
        "week_minutes": None,
        "hours_from": None,
        "hours_to": None,
        "slots": [],
        "screen_scope": "media",  # issue 439: its media only, unless its master counts all of Portalab
    }
    assert child["community_visible"] is False and child["has_pin"] is True

    changed = await client.patch(
        f"/api/v1/household/profiles/{lea}",
        json={
            "restrictions": {"max_age": 16, "allow_unrated": True, "blocked": ["shop"]},
            "color": "#10B981",
        },
    )
    assert changed.status_code == 204, changed.text
    restrictions = await households(app).restrictions_of(lea)
    assert (
        restrictions is not None
        and restrictions.max_age == 16
        and restrictions.withholds("marketplace.purchase")
    )
    assert not restrictions.withholds("media.request")
    assert await households(app).owner_of(lea) == alice and await households(app).owner_of(alice) is None
    bad = await client.patch(f"/api/v1/household/profiles/{lea}", json={"restrictions": {"max_age": 13}})
    assert bad.status_code == 422

    await _switch(client, tom)
    seen = (await client.get("/api/v1/household")).json()
    assert seen["can_manage"] is False and seen["me"] == str(tom)
    by_id = {m["id"]: m for m in seen["members"]}
    assert "restrictions" not in by_id[str(lea)] or by_id[str(lea)]["restrictions"] is None
    assert by_id[str(tom)]["restrictions"]["max_age"] is None  # its own
    assert {m["id"] for m in seen["members"]} == {str(alice), str(lea), str(tom)}


async def test_access_requests(app: FastAPI, client: httpx.AsyncClient) -> None:
    _, _, lea, _ = await _family(app, client)
    owner_ask = await client.post("/api/v1/household/requests", json={"ref": "x", "title": "X"})
    assert owner_ask.status_code == 403 and owner_ask.json()["code"] == "household.not_a_profile"
    await _switch(client, lea, "1234")
    body = {"ref": "0190a6d2-0000-7000-8000-000000000001", "title": "Alien", "rating": "16"}
    first = (await client.post("/api/v1/household/requests", json=body)).json()
    again = (await client.post("/api/v1/household/requests", json=body)).json()
    assert first["created"] is True and again == {"id": first["id"], "status": "pending", "created": False}
    assert len((await client.get("/api/v1/household/requests")).json()) == 1
    refused = await client.post(f"/api/v1/household/requests/{first['id']}/decision", json={"approve": True})
    assert refused.status_code == 403  # a profile decides nothing

    await _switch(client, (await _me(client))["profile_of"])  # type: ignore[arg-type]
    from portalab.modules.household.service import HouseholdAttention

    badge = HouseholdAttention(households(app))
    master = (await _me(client))["id"]
    assert await badge.counts(Principal(user_id=UUID(str(master)))) == {"shell.household.requests": 1}
    assert await badge.counts(Principal(user_id=lea, profile_of=UUID(str(master)))) == {}
    pending = (await client.get("/api/v1/household/requests")).json()
    assert pending[0]["profile_name"] == "Léa" and pending[0]["status"] == "pending"
    assert not await households(app).granted(lea, "media", body["ref"])
    decided = await client.post(
        f"/api/v1/household/requests/{first['id']}/decision", json={"approve": True, "days": 2}
    )
    assert decided.status_code == 204, decided.text
    assert await households(app).granted(lea, "media", body["ref"])
    twice = await client.post(f"/api/v1/household/requests/{first['id']}/decision", json={"approve": False})
    assert twice.status_code == 409
    activity = (await client.get(f"/api/v1/household/profiles/{lea}/activity")).json()
    assert activity["requests"][0]["status"] == "approved" and activity["requests"][0]["expires_at"]


async def test_deleting_a_profile_signs_its_browsers_out(app: FastAPI, client: httpx.AsyncClient) -> None:
    module, _, lea, tom = await _family(app, client)
    other = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://portal.test")
    async with other:
        await login(other, "alice")
        await _switch(other, tom)
        assert (await _me(other))["id"] == str(tom)
        assert (await client.delete(f"/api/v1/household/profiles/{tom}")).status_code == 204
        assert (await other.get("/api/v1/me")).status_code == 401
    async with module.ctx.database.session() as session:
        assert (await session.get(User, tom)).state == "pending_deletion"  # type: ignore[union-attr]
    state = (await client.get("/api/v1/household/session")).json()
    assert [m["id"] for m in state["members"]][1:] == [str(lea)]


async def test_hidden_profiles_are_no_members_and_follow_their_master(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    module, alice, lea, tom = await _family(app, client)
    listing = module.ctx.capabilities.system_providers(MEMBERS)[0].provider
    listed = {entry.id for entry in (await listing.active_members(limit=50)).items}
    # issue 443: a common pot (the default) — the master stands for the household, its profiles stay out
    assert alice in listed and tom not in listed and lea not in listed
    assert await households(app).hidden() == frozenset({lea, tom})
    await households(app).set_economy(Principal(user_id=alice), "dispatch")
    listed = {entry.id for entry in (await listing.active_members(limit=50)).items}
    assert {alice, tom, lea} <= listed  # dispatched: each profile in the community
    assert await households(app).anonymous() == frozenset({lea})  # a child, anonymously

    await module.deletion.request(self_actor(Principal(user_id=alice)), alice, reason="test")
    async with module.ctx.database.session() as session:
        states = {u: (await session.get(User, u)).state for u in (lea, tom)}  # type: ignore[union-attr]
    assert states == {lea: "pending_deletion", tom: "pending_deletion"}
    await module.deletion.cancel(self_actor(Principal(user_id=alice)), alice)
    async with module.ctx.database.session() as session:
        assert (await session.get(User, lea)).state == "active"  # type: ignore[union-attr]


async def test_an_account_holds_a_bounded_number_of_profiles(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    await create_user(module, "carol")
    await login(client, "carol")
    for number in range(8):
        await _profile(client, f"P{number}")
    full = await client.post("/api/v1/household/profiles", json={"display_name": "One more"})
    assert full.status_code == 409 and full.json()["code"] == "household.limit"


async def test_the_master_gives_time_in_a_few_taps(app: FastAPI, client: httpx.AsyncClient) -> None:
    """Issue 432: minutes more today, no limits for a while, the limits back — the master only."""
    _, _, lea, tom = await _family(app, client)
    week = [30, 30, 30, 30, 60, 120, 120]
    changed = await client.patch(
        f"/api/v1/household/profiles/{lea}",
        json={
            "restrictions": {"max_age": 12, "week_minutes": week, "hours_from": "08:00", "hours_to": "20:00"}
        },
    )
    assert changed.status_code == 204, changed.text
    base = await households(app).restrictions_of(lea)
    assert base is not None and base.week_minutes == tuple(week) and base.hours == ("08:00", "20:00")

    minutes, free = f"/api/v1/household/profiles/{lea}/minutes", f"/api/v1/household/profiles/{lea}/free"
    assert (await client.post(minutes, json={"minutes": 30})).status_code == 204
    assert (await client.post(minutes, json={"minutes": 15})).status_code == 204
    given = await households(app).restrictions_of(lea)
    assert given is not None and given.bonus_minutes == 45
    odd = await client.post(minutes, json={"minutes": 7})
    assert odd.status_code == 409 and odd.json()["code"] == "household.invalid_minutes"
    tile = next(m for m in (await client.get("/api/v1/household")).json()["members"] if m["id"] == str(lea))
    assert tile["bonus_minutes"] == 45

    assert (await client.post(free, json={"minutes": 60})).status_code == 204
    assert await households(app).restrictions_of(lea) is None  # no limits for an hour
    tile = next(m for m in (await client.get("/api/v1/household")).json()["members"] if m["id"] == str(lea))
    assert tile["free_until"] is not None
    assert (await client.post(free, json={})).status_code == 204
    assert await households(app).restrictions_of(lea) is not None  # the limits back

    await _switch(client, tom)
    refused = await client.post(minutes, json={"minutes": 30})
    assert refused.status_code == 403  # a profile gives no time


async def test_a_master_makes_its_household_or_undoes_an_empty_one(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    """Issue 445: a member is in no household until it makes one (with its economy) or a profile; a household
    without profiles may be undone, one with profiles not."""
    module = module_of(app)
    await create_user(module, "dora")
    await login(client, "dora")

    async def made() -> bool:
        return bool((await client.get("/api/v1/household/session")).json()["made"])

    assert await made() is False
    response = await client.post("/api/v1/household/made", json={"economy": "dispatch"})
    assert response.status_code == 204, response.text
    assert await made() is True
    assert (await client.get("/api/v1/household")).json()["economy"] == "dispatch"
    assert (await client.delete("/api/v1/household/made")).status_code == 204
    assert await made() is False
    await _profile(client, "Zoé")  # a profile makes the household too
    assert await made() is True
    refused = await client.delete("/api/v1/household/made")
    assert refused.status_code == 409 and refused.json()["code"] == "household.not_empty"
    (zoe,) = await households(app).profiles_of(UUID(str((await client.get("/api/v1/me")).json()["id"])))
    assert (await client.delete(f"/api/v1/household/profiles/{zoe}")).status_code == 204
    assert (await client.delete("/api/v1/household/made")).status_code == 204  # its removed profile gone too
    assert await made() is False


async def test_a_removed_profile_leaves_no_request_behind(app: FastAPI, client: httpx.AsyncClient) -> None:
    """Issue 450: a removed profile's access requests go with it (they waited, unnamed, for its master), and
    its household takes part in the erasure of an account (its row, its requests)."""
    from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY

    module, alice, lea, tom = await _family(app, client)
    service = households(app)
    for profile in (lea, tom):
        await service.ask(
            Principal(user_id=profile, profile_of=alice),
            kind="media",
            ref=str(uuid4()),
            title="Alien",
            rating="16",
            note=None,
        )
    assert len(await service.requests(Principal(user_id=alice))) == 2
    assert (await client.delete(f"/api/v1/household/profiles/{tom}")).status_code == 204
    assert [r["profile_id"] for r in await service.requests(Principal(user_id=alice))] == [lea]

    participants = module.ctx.capabilities.system_providers(ERASURE_CAPABILITY)
    household = next(p.provider for p in participants if p.instance_ref == "household")
    await household.erase(lea, "final")
    assert await service.requests(Principal(user_id=alice)) == []
    assert await service.exists(lea) is False
