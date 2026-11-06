"""Issue 363 — the members' requests for titles no service asks for: refused when the library has the title
(by one of its identifiers, by its title and author), a second member's request turned into « me too », the
administrators' queue the most wanted first with who wants each, a refusal told why, the request passed on
when who asked withdraws, closed once the library has the title (each member who wanted it counted for the
reward rules); a quota and a price per request; a member's requests exported and erased with them; nothing
answered while the module is switched off."""

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.economy import ECONOMY
from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.modules.administration.config.service import Change
from portalab.modules.media.models import ExternalId, MediaObject
from portalab.modules.requests.models import Supporter, TitleRequest
from portalab.modules.requests.module import RequestsModule
from portalab.modules.requests.service import QuotaReached
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

pytestmark = pytest.mark.integration


async def _library(media: MediaHarness, *records: Any) -> None:
    one = media.service(1)
    await media.module.library.upsert(list(records), one)


async def _object(media: MediaHarness, title: str) -> UUID:
    async with media.database.session() as session:
        found: UUID = (
            await session.execute(select(MediaObject.id).where(MediaObject.title == title))
        ).scalar_one()
        return found


def _book(ref: str, title: str, author: str = "Robin Hobb") -> Any:
    return library_record(ref, kind="book", title=title, authors=[author], people=[author])


async def test_a_request_its_me_too_and_its_end(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, wishes: RequestsModule
) -> None:
    people = await users(app, media, "zoe", "leo", admin="ann")
    media.library(media.service(1))
    await _library(media, _book("b1", "L'Apprenti assassin"))
    async with media.database.unit_of_work() as uow:
        first = await _object(media, "L'Apprenti assassin")
        uow.session.add(ExternalId(scheme="isbn", value="9782290302512", object_id=first))

    await login(client, "zoe")
    options = (await client.get("/api/v1/requests/options")).json()
    assert options["kinds"] == ["book", "audiobook", "game"] and options["price"] == 0
    assert options["left"] == {"book": None, "audiobook": None, "game": None}  # no limit set

    # the library has it: by its title and author, by one of its identifiers (as it is written or not)
    there = await client.post(
        "/api/v1/requests", json={"kind": "book", "title": "l'apprenti  ASSASSIN", "creators": ["Robin Hobb"]}
    )
    assert there.status_code == 409 and there.json()["code"] == "requests.in_library"
    assert there.json()["route"] == f"/media/{first}"
    by_id = await client.post(
        "/api/v1/requests",
        json={"kind": "book", "title": "Assassin's Apprentice", "ids": {"isbn": ["978-2-290-30251-2"]}},
    )
    assert by_id.status_code == 409 and by_id.json()["code"] == "requests.in_library"
    # another author's book of that title is not it
    other = await client.post(
        "/api/v1/requests",
        json={"kind": "book", "title": "L'Apprenti assassin", "creators": ["Someone Else"]},
    )
    assert other.status_code == 201
    # a kind the administrators did not open (the films go to the request service)
    closed = await client.post("/api/v1/requests", json={"kind": "movie", "title": "Alien"})
    assert closed.status_code == 422 and closed.json()["code"] == "requests.kind_closed"

    asked = await client.post(
        "/api/v1/requests",
        json={
            "kind": "book",
            "title": "Le Prophète blanc",
            "creators": ["Robin Hobb"],
            "details": {"language": "fr", "format": "ebook"},
            "ids": {"hardcover": ["917"]},
            "note": "Le tome 7 de L'Assassin royal",
        },
    )
    assert asked.status_code == 201
    request = asked.json()
    assert request["status"] == "new" and request["supporters"] == 1 and request["asked"] and request["mine"]
    assert request["details"] == {"language": "fr", "format": "ebook"} and request["ids"] == {
        "hardcover": ["917"]
    }

    # another member asks for it again: « me too » instead of a second request
    await login(client, "leo")
    again = await client.post(
        "/api/v1/requests", json={"kind": "book", "title": "le prophete blanc", "creators": ["robin hobb"]}
    )
    assert again.status_code == 409 and again.json()["code"] == "requests.already_asked"
    assert again.json()["request_id"] == request["id"]
    supported = (await client.post(f"/api/v1/requests/{request['id']}/support")).json()
    assert supported["supporters"] == 2 and supported["mine"] and not supported["asked"]
    assert (await client.post(f"/api/v1/requests/{request['id']}/support")).json()["supporters"] == 2  # once
    listed = (await client.get("/api/v1/requests")).json()
    assert [r["title"] for r in listed["mine"]] == ["Le Prophète blanc"]
    assert listed["open"][0]["id"] == request["id"]  # the most wanted first
    assert "wanted_by" not in listed["open"][0]  # the members see how many, not who

    # the administrators' queue: who wants each; a refusal needs a reason
    await login(client, "ann")
    queue = (await client.get("/api/v1/admin/requests")).json()
    top = queue["requests"][0]
    assert top["id"] == request["id"] and top["requester"] == "zoe"
    assert [(w["name"], w["asked"]) for w in top["wanted_by"]] == [("zoe", True), ("leo", False)]
    assert queue["figures"] == {"new": 2}
    unreasoned = await client.post(
        f"/api/v1/admin/requests/{request['id']}/decision", json={"status": "refused"}
    )
    assert unreasoned.status_code == 422 and unreasoned.json()["code"] == "requests.no_reason"
    accepted = await client.post(
        f"/api/v1/admin/requests/{request['id']}/decision", json={"status": "accepted"}
    )
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"
    refused = (
        await client.post(
            f"/api/v1/admin/requests/{other.json()['id']}/decision",
            json={"status": "refused", "reason": "Introuvable"},
        )
    ).json()
    assert refused["status"] == "refused" and refused["reason"] == "Introuvable"
    await login(client, "leo")
    assert (await client.get("/api/v1/admin/requests")).status_code == 403

    # who asked withdraws: the request goes on in the name of who said « me too » first
    await login(client, "zoe")
    gone = (await client.delete(f"/api/v1/requests/{request['id']}/support")).json()
    assert gone["status"] == "accepted" and gone["supporters"] == 1 and not gone["mine"]
    async with media.database.session() as session:
        row = await session.get(TitleRequest, UUID(request["id"]))
        assert row is not None and row.requester_id == people["leo"]

    # the library gets it: the request closes, its page given; the reward rules told
    await _library(media, _book("b1", "L'Apprenti assassin"), _book("b7", "Le Prophète blanc"))
    assert await wishes.requests.sweep() == 1
    await login(client, "leo")
    mine = (await client.get("/api/v1/requests")).json()["mine"][0]
    prophet = await _object(media, "Le Prophète blanc")
    assert mine["status"] == "available" and mine["route"] == f"/media/{prophet}"
    fulfilled = [e for e in await media.events("requests.") if e[0] == "requests.fulfilled"]
    assert [(p["asked"], p["supporters"], s) for _, p, s in fulfilled] == [(False, 1, str(people["leo"]))]
    assert {t for t, _, _ in await media.events("requests.")} == {
        "requests.created",
        "requests.supported",
        "requests.fulfilled",
    }
    assert (await client.post(f"/api/v1/requests/{request['id']}/support")).status_code == 409  # closed

    # switched off from the module manager: nothing answers
    await media.ev.full.administration.toggles.set(Principal(channel="system"), "module", "requests", False)
    assert (await client.get("/api/v1/requests")).status_code == 503


class Coins:
    def __init__(self) -> None:
        self.spent: list[tuple[UUID, int, str]] = []
        self.refunded: list[UUID] = []

    async def spend(self, user: UUID, amount: int, **kw: Any) -> Any:
        self.spent.append((user, amount, kw["source_kind"]))
        return SimpleNamespace(id=uuid4())

    async def refund(self, transaction_id: UUID, **kw: Any) -> Any:
        self.refunded.append(transaction_id)
        return SimpleNamespace(id=uuid4())

    async def balance(self, user: UUID, value: Any) -> int:
        return 100

    async def history(self, user: UUID, **kw: Any) -> Any:
        return None

    async def reserve(self, user: UUID, amount: int, **kw: Any) -> Any:
        return None

    async def release(self, reservation_id: UUID, **kw: Any) -> Any:
        return None

    async def consume(self, reservation_id: UUID, **kw: Any) -> Any:
        return None

    async def reservations(self, ids: Any) -> list[Any]:
        return []


async def test_a_quota_a_price_and_a_member_s_data(
    app: FastAPI, media: MediaHarness, wishes: RequestsModule
) -> None:
    people = await users(app, media, "zoe", "leo", admin="ann")
    coins = Coins()
    media.ev.full.identity.capabilities.provide(ECONOMY, coins, instance_ref="t", owner="test")
    config = {"kinds": ["book", "game"], "quotas": {"game": {"limit": 1, "days": 30}}, "price": 5}
    await media.ev.full.administration.config.apply(
        [Change("requests.config", config)], Principal(channel="system"), admin_change=True
    )
    await wishes.refresh_config()
    service = wishes.requests
    assert (await service.options(people["zoe"]))["left"] == {"book": None, "game": 1}

    game = await service.create(
        people["zoe"], kind="game", title="Chrono Trigger", details={"platform": "SNES"}
    )
    assert coins.spent == [(people["zoe"], 5, "requests")]
    with pytest.raises(QuotaReached):
        await service.create(people["zoe"], kind="game", title="Secret of Mana")
    assert (await service.options(people["zoe"]))["left"]["game"] == 0
    # refused: its Coins given back
    await service.decide(people["ann"], UUID(game["id"]), "refused", reason="Pas de ROM")
    assert len(coins.refunded) == 1

    book = await service.create(people["zoe"], kind="book", title="Fool's Errand", note="mon mot")
    await service.support(people["leo"], UUID(book["id"]))
    exported = await wishes.requests.export(people["zoe"])
    assert {(e["title"], e["asked"], e["status"]) for e in exported} == {
        ("Chrono Trigger", True, "refused"),
        ("Fool's Errand", True, "new"),
    }
    # erased: the request passes to the next member who wants it, without their words
    await wishes.requests.erase(people["zoe"])
    async with media.database.session() as session:
        row = await session.get(TitleRequest, UUID(book["id"]))
        assert row is not None and row.requester_id == people["leo"] and row.note is None
        left = (await session.execute(select(Supporter.user_id))).scalars().all()
        assert left == [people["leo"]]
    # the last one withdraws: cancelled, its Coins given back (nobody took it in hand)
    await service.withdraw(people["leo"], UUID(book["id"]))
    assert (await service.one(people["leo"], UUID(book["id"])))["status"] == "cancelled"
    assert len(coins.refunded) == 2
