"""027 — service accounts ↔ members: each service lists its accounts, unlinked ones get a suggestion (same
e-mail, else same login/name ignoring accents and case), the administrator applies them or links by hand (one
account per member and service), and the account's past activity is attributed to the member."""

from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.identity_directory import AccountSummary
from portalab.capabilities.media import ACCOUNTS, ServiceAccount
from portalab.modules.media.links.accounts import normalize, suggest
from portalab.modules.media.models import MediaRequest, PlaybackSession
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

T0 = datetime(2026, 10, 1, 20, tzinfo=UTC)


class _Accounts:
    async def list_accounts(self) -> list[ServiceAccount]:
        return [
            ServiceAccount("1", username="Zoé", display_name="Zoé"),
            ServiceAccount("2", username="BOSS"),
            ServiceAccount("3", username="ghost"),
        ]


def test_suggestions_ignore_accents_and_prefer_email() -> None:
    members = [
        AccountSummary(UUID(int=1), "zoe", "Zoé Martin", "zoe@home.lan"),
        AccountSummary(UUID(int=2), "max", "Max", None),
    ]
    assert normalize("Zoé-M.") == "zoem"
    assert suggest(ServiceAccount("a", username="ZOE"), members) == (UUID(int=1), "name")
    assert suggest(ServiceAccount("b", username="x", email="ZOE@home.lan"), members) == (UUID(int=1), "email")
    assert suggest(ServiceAccount("c", username="nobody"), members) is None
    assert suggest(ServiceAccount("d", username="ma"), members) is None  # too short to be meaningful


async def test_mapping_flow(app: FastAPI, client: httpx.AsyncClient, media: MediaHarness) -> None:
    people = await users(app, media, "zoe", admin="boss")
    service = media.service(7)
    media.provide(ACCOUNTS, service, _Accounts())
    async with media.ev.full.database.unit_of_work() as uow:
        uow.session.add(
            PlaybackSession(
                session_key="s-1",
                service_id=service.service_id,
                user_id=None,
                external_user_id="2",
                object_id=None,
                kind="movie",
                state="stopped",
                position_s=10,
                max_position_s=10,
                duration_s=100,
                device=None,
                started_at=T0,
                updated_at=T0,
                as_of=T0,
                last_event_at=T0,
                state_seq=1,
                ended=True,
            )
        )
    await login(client, "boss")
    overview = (await client.get("/api/v1/admin/media/accounts")).json()
    accounts = {a["external_id"]: a for a in overview["services"][0]["accounts"]}
    assert accounts["1"]["suggestion"] == {"user_id": str(people["zoe"]), "reason": "name"}
    assert accounts["2"]["suggestion"]["user_id"] == str(people["boss"])
    assert accounts["2"]["unlinked_sessions"] == 1 and accounts["3"]["suggestion"] is None

    applied = (await client.post("/api/v1/admin/media/accounts/apply-suggestions", json={})).json()
    assert applied == {"linked": 2}
    async with media.ev.full.database.session() as session:
        row = await session.get(PlaybackSession, "s-1")
    assert row is not None and row.user_id == people["boss"]  # past activity attributed

    # one account per member and service: linking "ghost" to Zoé replaces her previous account
    moved = await client.put(
        f"/api/v1/admin/media/accounts/{service.service_id}",
        json={"external_user_id": "3", "user_id": str(people["zoe"])},
    )
    assert moved.status_code == 200
    accounts = {
        a["external_id"]: a
        for a in (await client.get("/api/v1/admin/media/accounts")).json()["services"][0]["accounts"]
    }
    assert accounts["3"]["linked_user_id"] == str(people["zoe"]) and accounts["3"]["verified"]
    assert accounts["1"]["linked_user_id"] is None
    assert await media.module.links.resolve(service.service_id, "3") == people["zoe"]

    unlinked = await client.put(
        f"/api/v1/admin/media/accounts/{service.service_id}", json={"external_user_id": "2", "user_id": None}
    )
    assert unlinked.json()["linked"] is False
    assert await media.module.links.resolve(service.service_id, "2") is None

    await login(client, "zoe")
    assert (await client.get("/api/v1/admin/media/accounts")).status_code == 403


class _SeerrAccounts:
    async def list_accounts(self) -> list[ServiceAccount]:
        return [ServiceAccount("7", username="zoe")]


def _request(external_id: str, requester: str | None, state: str = "pending") -> SourceRecord:
    payload = {"title": f"Film {external_id}", "kind": "movie", "ids": {}, "state": state}
    if requester:
        payload["requester"] = requester
    return SourceRecord(
        source_system="seerr",
        external_id=external_id,
        kind="request",
        payload=payload,
        observed_at=T0,
    )


async def test_requests_synced_before_the_mapping_are_attributed(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    """027: Seerr requests imported before the account was linked reach the member once it is linked."""
    people = await users(app, media, "zoe", admin="boss")
    seerr = media.service(8, "seerr")
    media.provide(ACCOUNTS, seerr, _SeerrAccounts())
    sink = media.module.request_sink
    await sink.upsert([_request("1", "7"), _request("2", "7", "available"), _request("3", "9")], seerr)
    # an older import that did not keep who asked: the next sync fills it in, without notifying anyone
    async with media.database.unit_of_work() as uow:
        row = (
            await uow.session.execute(select(MediaRequest).where(MediaRequest.external_request_id == "1"))
        ).scalar_one()
        row.external_ref = {k: v for k, v in row.external_ref.items() if k != "requester"}
    before = len(await media.events("media.request_updated"))
    again = await sink.upsert([_request("1", "7")], seerr)
    assert again.modified == 1 and len(await media.events("media.request_updated")) == before

    await login(client, "zoe")
    assert (await client.get("/api/v1/me/media/requests")).json()["items"] == []
    await login(client, "boss")
    linked = await client.put(
        f"/api/v1/admin/media/accounts/{seerr.service_id}",
        json={"external_user_id": "7", "user_id": str(people["zoe"])},
    )
    assert linked.status_code == 200
    await login(client, "zoe")
    mine = (await client.get("/api/v1/me/media/requests")).json()["items"]
    assert sorted(r["state"] for r in mine) == ["available", "pending"]  # request 3 is someone else's

    await login(client, "boss")
    await client.put(
        f"/api/v1/admin/media/accounts/{seerr.service_id}", json={"external_user_id": "7", "user_id": None}
    )
    await login(client, "zoe")
    assert (await client.get("/api/v1/me/media/requests")).json()["items"] == []
