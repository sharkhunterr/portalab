"""027 — service accounts ↔ members: each service lists its accounts, unlinked ones get a suggestion (same
e-mail, else same login/name ignoring accents and case), the administrator applies them or links by hand (one
account per member and service), and the account's past activity is attributed to the member."""

from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import FastAPI

from portalab.capabilities.identity_directory import AccountSummary
from portalab.capabilities.media import ACCOUNTS, ServiceAccount
from portalab.modules.media.links.accounts import normalize, suggest
from portalab.modules.media.models import PlaybackSession
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
