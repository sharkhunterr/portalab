"""#3, #4 — the request service's quota is the truth for a linked member: a request counts there (not
against the portal's own allowance); once it is used up, a unit bought in the shop lets one more through
(sent so the service does not count it), else « quota reached »; a film already asked for is not asked
again; administrators read and set every account's limits and the defaults (audited); the titles one can
ask for come with what the portal knows of them, and the search has an « Ask for it » section."""

from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, text

from portalab.capabilities.media import (
    REQUEST_DISCOVERY,
    REQUEST_QUOTAS,
    QuotaAccount,
    QuotaLimits,
    QuotaWindow,
    RequestableDetails,
    RequestableSeason,
    RequestableTitle,
    SourceQuota,
)
from portalab.capabilities.search import ParsedQuery
from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock
from portalab.modules.media.models import MediaRequest, UserLink
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

pytestmark = pytest.mark.integration


class FakeQuotas:
    def __init__(self) -> None:
        self.movie = QuotaWindow(limit=2, days=7, used=1, remaining=1)
        self.set: list[tuple[str, QuotaLimits]] = []
        self.default_limits = QuotaLimits(movie_limit=2, movie_days=7)

    async def quota(self, external_user: str) -> SourceQuota:
        return SourceQuota(movie=self.movie, tv=QuotaWindow())

    async def accounts(self) -> list[QuotaAccount]:
        return [
            QuotaAccount(
                "7", "Alex on Seerr", QuotaLimits(movie_limit=2, movie_days=7), await self.quota("7")
            ),
            QuotaAccount("9", "Stranger", QuotaLimits(), await self.quota("9")),
            QuotaAccount("1", "Owner", QuotaLimits(), None, exempt=True),
        ]

    async def set_limits(self, external_user: str, limits: QuotaLimits) -> None:
        self.set.append((external_user, limits))

    async def defaults(self) -> QuotaLimits:
        return self.default_limits

    async def set_defaults(self, limits: QuotaLimits) -> None:
        self.default_limits = limits


class FakeDiscovery:
    async def search(self, query: str, language: str, page: int = 1) -> list[RequestableTitle]:
        return [
            RequestableTitle("603", "movie", "The Matrix", 1999, poster="/matrix.jpg"),
            RequestableTitle("604", "movie", "The Matrix Reloaded", 2003, status="available"),
        ]

    async def shelf(self, name: str, language: str) -> list[RequestableTitle]:
        return [RequestableTitle("1399", "series", "Game of Thrones", 2011)] if name == "trending" else []

    async def details(self, kind: str, tmdb_id: str, language: str) -> RequestableDetails | None:
        if tmdb_id != "1399":
            return None
        return RequestableDetails(
            RequestableTitle("1399", "series", "Game of Thrones", 2011),
            seasons=(
                RequestableSeason(1, "Season 1", 10, status="available"),
                RequestableSeason(2, "Season 2", 10),
            ),
            trailer="abc",
        )


async def test_service_quota_bought_units_and_duplicates(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "alex", "max", admin="boss")
    seerr = media.service(5, "seerr")
    fake = media.requests(seerr)
    quotas = FakeQuotas()
    media.provide(REQUEST_QUOTAS, seerr, quotas)
    await media.configure("media.requests.quotaPerPeriod", 0)  # the portal's own allowance is not used
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            UserLink(
                user_id=people["alex"],
                service_id=seerr.service_id,
                external_user_id="7",
                verified=True,
                created_at=clock.now(),
            )
        )
    await login(client, "alex")
    mine = (await client.get("/api/v1/me/media/requests/quota")).json()
    assert mine["service"]["linked"] is True
    assert (mine["service"]["movie"]["remaining"], mine["service"]["movie"]["limit"]) == (1, 2)

    body = {"ids": {"tmdb": "603"}, "kind": "movie", "title": "The Matrix", "idempotency_key": "seerr-q-0001"}
    first = await client.post("/api/v1/media/requests", json=body)
    assert first.status_code == 201 and "bypass_quota" not in fake.submitted[-1]
    async with media.database.session() as session:
        counted = await session.scalar(
            select(MediaRequest.counted).where(MediaRequest.id == UUID(first.json()["id"]))
        )
    assert counted == "service"  # the service counts it, not the portal's own allowance

    # the same film again: already asked for — follow that request instead
    again = await client.post("/api/v1/media/requests", json={**body, "idempotency_key": "seerr-q-0002"})
    assert again.status_code == 409 and again.json()["code"] == "media.request_duplicate"

    # the service's quota used up: refused, unless a unit bought in the shop lets one more through
    quotas.movie = QuotaWindow(limit=2, days=7, used=2, remaining=0, restricted=True)
    media.module.requests.service_quotas.forget()
    other = {
        "ids": {"tmdb": "680"},
        "kind": "movie",
        "title": "Pulp Fiction",
        "idempotency_key": "seerr-q-0003",
    }
    refused = await client.post("/api/v1/media/requests", json=other)
    assert refused.status_code == 429 and refused.json()["code"] == "media.request_quota_exceeded"
    await media.module.quota.add_units(people["alex"], 1, "order:9", "purchase:order:9")
    paid = await client.post("/api/v1/media/requests", json={**other, "idempotency_key": "seerr-q-0004"})
    assert paid.status_code == 201 and fake.submitted[-1]["bypass_quota"] is True
    assert (await media.module.quota.available(people["alex"]))["extra_units"] == 0

    # a series with its seasons
    series = {"ids": {"tmdb": "1399"}, "kind": "series", "title": "Game of Thrones", "seasons": [2, 3]}
    await media.module.quota.add_units(people["alex"], 1, "order:10", "purchase:order:10")
    asked = await client.post("/api/v1/media/requests", json={**series, "idempotency_key": "seerr-q-0005"})
    assert asked.status_code == 201 and fake.submitted[-1]["seasons"] == [2, 3]

    # a member without a linked account keeps the portal's own allowance (0 here)
    await login(client, "max")
    theirs = (await client.get("/api/v1/me/media/requests/quota")).json()
    assert theirs["service"] == {"linked": False} and theirs["base_remaining"] == 0

    # administrators: every account, the member it is, its limits; changes go to the service, audited
    assert (await client.get("/api/v1/admin/media/quotas")).status_code == 403
    await login(client, "boss")
    overview = (await client.get("/api/v1/admin/media/quotas")).json()
    rows = {r["account"]: r for r in overview["accounts"]}
    assert rows["7"]["member"]["id"] == str(people["alex"]) and rows["9"]["member"] is None
    assert rows["1"]["exempt"] is True and overview["defaults"]["movie"] == {"limit": 2, "days": 7}
    changed = await client.put(
        "/api/v1/admin/media/quotas/accounts/7", json={"movie": {"limit": 4, "days": 7}, "tv": {}}
    )
    assert changed.status_code == 200 and quotas.set[-1] == ("7", QuotaLimits(4, 7, None, None))
    bulk = {"accounts": ["7", "9"], "movie": {"limit": 1, "days": 30}, "tv": {"limit": 1, "days": 30}}
    assert (await client.put("/api/v1/admin/media/quotas/accounts", json=bulk)).status_code == 200
    assert [a for a, _ in quotas.set[-2:]] == ["7", "9"]
    defaults = {"movie": {"limit": 3, "days": 7}, "tv": {"limit": 0, "days": None}}
    assert (await client.put("/api/v1/admin/media/quotas/defaults", json=defaults)).status_code == 200
    assert quotas.default_limits == QuotaLimits(3, 7, 0, None)
    async with media.database.session() as session:
        audited = (
            (
                await session.execute(
                    text("SELECT action FROM audit.audit_entries WHERE action LIKE 'media.quota%'")
                )
            )
            .scalars()
            .all()
        )
    assert sorted(set(audited)) == ["media.quota_changed", "media.quota_defaults_changed"]


async def test_titles_to_ask_for_and_search(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "alex")
    seerr = media.service(5, "seerr")
    media.requests(seerr)
    media.provide(REQUEST_DISCOVERY, seerr, FakeDiscovery())
    await login(client, "alex")
    body = {"ids": {"tmdb": "603"}, "kind": "movie", "title": "The Matrix", "idempotency_key": "seerr-d-0001"}
    assert (await client.post("/api/v1/media/requests", json=body)).status_code == 201

    found = (await client.get("/api/v1/media/discover/search", params={"q": "matrix"})).json()
    matrix, reloaded = found["items"]
    # one page per title: a title the catalog has opens its library page
    assert matrix["request"] == {"mine": True} and matrix["route"] == f"/media/{matrix['object_id']}"
    assert reloaded["status"] == "available" and reloaded["request"] is None
    assert reloaded["route"] == "/media/discover/movie/604"  # the library does not have it
    shelf = (await client.get("/api/v1/media/discover/shelves/trending")).json()
    assert [i["title"] for i in shelf["items"]] == ["Game of Thrones"]
    got = (await client.get("/api/v1/media/discover/series/1399")).json()
    assert [s["status"] for s in got["seasons"]] == ["available", "unknown"] and got["trailer"] == "abc"
    assert (await client.get("/api/v1/media/discover/series/1")).status_code == 404

    # #267: asked for, and in the catalog under its TVDB id only (a series from Sonarr) — still its page
    body = {"ids": {"tmdb": "1399", "tvdb": "121361"}, "kind": "series", "title": "Game of Thrones"}
    asked = await client.post("/api/v1/media/requests", json={**body, "idempotency_key": "seerr-d-0002"})
    assert asked.status_code == 201
    async with media.database.session() as session, session.begin():
        page = await session.scalar(
            select(MediaRequest.object_id).where(MediaRequest.id == UUID(asked.json()["id"]))
        )
        await session.execute(
            text("DELETE FROM media.external_ids WHERE object_id = :o AND scheme = 'tmdb'"), {"o": page}
        )
    got = (await client.get("/api/v1/media/discover/series/1399")).json()
    assert got["object_id"] == str(page) and got["request"] == {"mine": True}

    provider = media.module.search.provider("request")
    assert provider is not None
    query = ParsedQuery(text="matrix", normalized="matrix", terms=("matrix",))
    items = (
        await provider.search(query, Principal(user_id=people["alex"]), None, limit=10, cursor=None)
    ).items  # type: ignore[arg-type]
    # the available title is left to the library's own results; the asked one says so
    assert [(i.title, i.url_ref, i.facets.get("status")) for i in items] == [
        ("The Matrix (1999)", matrix["route"], "requested")
    ]
    assert items[0].facets["poster"] == "/matrix.jpg"


async def test_administrators_approve_and_decline(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    """#4: the queue shows who asked; a decision goes to the request service, keeps its reason, gives
    back a bought unit when declined, and is audited."""
    people = await users(app, media, "alex", admin="boss")
    seerr = media.service(5, "seerr")
    fake = media.requests(seerr)
    await media.configure("media.requests.quotaPerPeriod", 0)
    await media.module.quota.add_units(people["alex"], 2, "order:1", "purchase:order:1")
    await login(client, "alex")
    for tmdb, title in (("603", "The Matrix"), ("680", "Pulp Fiction")):
        body = {"ids": {"tmdb": tmdb}, "kind": "movie", "title": title, "idempotency_key": f"mod-{tmdb}-0001"}
        assert (await client.post("/api/v1/media/requests", json=body)).status_code == 201
    assert (await media.module.quota.available(people["alex"]))["extra_units"] == 0
    assert (await client.get("/api/v1/admin/media/requests")).status_code == 403

    await login(client, "boss")
    queue = (await client.get("/api/v1/admin/media/requests")).json()["items"]
    by_title = {i["title"]: i for i in queue}
    assert set(by_title) == {"The Matrix", "Pulp Fiction"} and all(i["decidable"] for i in queue)
    assert by_title["The Matrix"]["requester"]["id"] == str(people["alex"])
    # one member's requests only (their admin card)
    alex = (await client.get(f"/api/v1/admin/media/requests?user_id={people['alex']}")).json()["items"]
    boss = (await client.get(f"/api/v1/admin/media/requests?user_id={people['boss']}")).json()["items"]
    assert len(alex) == 2 and boss == []

    approved = await client.post(
        f"/api/v1/admin/media/requests/{by_title['The Matrix']['id']}/approve", json={}
    )
    assert approved.json() == {"state": "approved"} and fake.states["req-1"] == "approved"
    declined = await client.post(
        f"/api/v1/admin/media/requests/{by_title['Pulp Fiction']['id']}/decline",
        json={"reason": "Already in 4K on the server"},
    )
    assert declined.json() == {"state": "declined"} and fake.states["req-2"] == "declined"
    assert (await media.module.quota.available(people["alex"]))["extra_units"] == 1  # given back
    again = await client.post(
        f"/api/v1/admin/media/requests/{by_title['Pulp Fiction']['id']}/approve", json={}
    )
    assert again.status_code == 422  # no longer waiting
    every = {
        i["title"]: i for i in (await client.get("/api/v1/admin/media/requests?state=all")).json()["items"]
    }
    assert every["Pulp Fiction"]["decision"]["reason"] == "Already in 4K on the server"
    assert every["Pulp Fiction"]["decision"]["approved"] is False
    async with media.database.session() as session:
        audited = (
            (
                await session.execute(
                    text("SELECT action FROM audit.audit_entries WHERE action LIKE 'media.request_%'")
                )
            )
            .scalars()
            .all()
        )
    assert sorted(audited) == ["media.request_approved", "media.request_declined"]
