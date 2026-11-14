"""Issue 426 — each member's own account in the game library: the member authorises the portal there once
(a code approved in RomM), the token kept encrypted; their play sessions, saves and states then go to their
own account — a household profile's to its master's, labelled with the profile — and back to the service's
account once revoked or unlinked (the member asked to authorise again); only the master authorises."""

from datetime import timedelta
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock
from portalab.modules.retro.models import LibraryAccount
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users
from tests.integration.retro.conftest import FakeRetro
from tests.integration.retro.test_retro import _games, _sitting

SERVICE = str(UUID(int=1))


async def _authorise(client: httpx.AsyncClient, retro: FakeRetro) -> dict[str, object]:
    asked = await client.post(f"/api/v1/retro/accounts/{SERVICE}")
    assert asked.status_code == 200, asked.text
    body = asked.json()
    assert (body["state"], body["user_code"], body["interval"]) == ("pending", "ABCD-1234", 5)
    waiting = (await client.post(f"/api/v1/retro/accounts/{SERVICE}/check")).json()
    assert waiting["state"] == "pending"  # not approved yet
    retro.approved = True
    linked = (await client.post(f"/api/v1/retro/accounts/{SERVICE}/check")).json()
    assert (linked["state"], linked["username"], linked["user_code"]) == ("linked", "zoe-in-romm", None)
    return linked


async def test_a_member_writes_to_their_own_account(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe")
    ids = await _games(media)
    await login(client, "zoe")
    accounts = (await client.get("/api/v1/retro/accounts")).json()
    assert [(a["service_id"], a["state"]) for a in accounts] == [(SERVICE, "none")]
    await _authorise(client, retro)
    assert retro.links == [f"portalab-{people['zoe'].hex}"]
    async with media.database.session() as session:
        row = await session.scalar(select(LibraryAccount))
    assert row is not None and row.token and "member-token" not in row.token  # kept encrypted

    sitting = await _sitting(client, ids["Super Metroid"])
    await client.put(f"{sitting['saves_path']}states/1", content=b"STATE")
    assert retro.copies[-1]["account"] == "member-token"
    clock.advance(timedelta(seconds=40))
    await client.post(f"/api/v1/retro/sittings/{sitting['id']}/end")
    assert retro.accounts_used == ["member-token"]  # the play session in their own RomM

    assert (await client.delete(f"/api/v1/retro/accounts/{SERVICE}")).status_code == 204
    assert [a.device_id for a in retro.ended] == ["dev-9"]  # revoked in the library too
    assert (await client.get("/api/v1/retro/accounts")).json()[0]["state"] == "none"
    again = await _sitting(client, ids["Super Metroid"])
    await client.put(f"{again['saves_path']}states/1", content=b"STATE-2")
    assert retro.copies[-1]["account"] is None  # the service's account again


async def test_a_copy_moves_to_the_members_account(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro
) -> None:
    await users(app, media, "zoe")
    ids = await _games(media)
    await login(client, "zoe")
    saves = (await _sitting(client, ids["Super Metroid"]))["saves_path"]
    await client.put(f"{saves}states/2", content=b"OLD")
    first = retro.copies[-1]
    assert first["account"] is None
    await _authorise(client, retro)
    await client.put(f"{saves}states/2", content=b"NEW")
    moved = retro.copies[-1]
    assert (moved["account"], moved["replaces"]) == ("member-token", None)  # a new copy in their account
    assert retro.deleted == [("state", "101")]  # the service's old copy goes


async def test_a_revoked_token_falls_back_and_asks_again(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro, clock: FixedClock
) -> None:
    await users(app, media, "zoe")
    ids = await _games(media)
    await login(client, "zoe")
    await _authorise(client, retro)
    retro.revoked.add("member-token")  # revoked in RomM
    sitting = await _sitting(client, ids["Super Metroid"])
    clock.advance(timedelta(seconds=40))
    await client.post(f"/api/v1/retro/sittings/{sitting['id']}/end")
    assert retro.accounts_used == [None]  # told anyway, to the service's account
    again = await _sitting(client, ids["Super Metroid"])
    await client.put(f"{again['saves_path']}sram", content=b"SRAM")
    assert retro.copies[-1]["account"] is None  # kept anyway, in the service's account
    assert (await client.get("/api/v1/retro/accounts")).json()[0]["state"] == "expired"


async def test_a_refused_authorisation_and_profiles(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro
) -> None:
    people = await users(app, media, "zoe")
    ids = await _games(media)
    await login(client, "zoe")
    await client.post(f"/api/v1/retro/accounts/{SERVICE}")
    retro.refuse_link = True
    refused = (await client.post(f"/api/v1/retro/accounts/{SERVICE}/check")).json()
    assert refused["state"] == "none"
    retro.refuse_link = False
    await _authorise(client, retro)

    households = app.state.household_module.service
    created = await households.create(
        Principal(user_id=people["zoe"]), display_name="Léa", kind="standard", color=None, pin=None
    )
    await client.post("/api/v1/household/switch", json={"user_id": str(created["id"])})
    denied = await client.post(f"/api/v1/retro/accounts/{SERVICE}")
    assert denied.status_code == 403 and denied.json()["code"] == "retro.account_master_only"
    assert (await client.get("/api/v1/retro/accounts")).json()[0]["state"] == "linked"  # its master's
    saves = (await _sitting(client, ids["Super Metroid"]))["saves_path"]
    await client.put(f"{saves}states/1", content=b"LEA")
    assert (retro.copies[-1]["account"], retro.copies[-1]["labels"]) == ("member-token", ["Portalab", "Léa"])
