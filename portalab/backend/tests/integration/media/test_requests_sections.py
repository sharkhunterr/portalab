"""024 T016/T018/T025/T027 — availability, service health and sync state come back side by side and an
outage changes no catalog fact; each detail section answers independently ({state, as_of, data}) and a
failing source degrades only its own; requests go through the request service within the quota (base +
extra units credited idempotently), failures give the quota back, the source of truth updates the mirror;
search and discovery are permission/privacy bounded."""

from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.health import SERVICE_DIRECTORY, SERVICE_STATE, ServiceInfo, ServiceStateView
from portalab.capabilities.media.testkit import PNG_1PX, library_record
from portalab.capabilities.search.testkit import ProviderWorld, SearchProviderContractKit
from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

pytestmark = pytest.mark.integration
T0 = datetime(2026, 10, 1, tzinfo=UTC)


class Directory:
    def __init__(self, states: dict[str, str]) -> None:
        self.states = states

    async def services(self) -> list[ServiceInfo]:
        return [await self.service(s) for s in self.states]  # type: ignore[misc]

    async def service(self, service_id: str) -> ServiceInfo | None:
        return ServiceInfo(
            service_id, f"Service {service_id[-1]}", "fake", "enabled", "failed", T0, T0, "SyncError"
        )

    async def get(self, service_id: str) -> ServiceStateView | None:
        return ServiceStateView(service_id, self.states.get(service_id, "unknown"), T0, T0, 1.0, T0)  # type: ignore[arg-type]

    async def all(self) -> list[ServiceStateView]:
        return []


async def test_sections_and_availability(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "alex")
    one, two = media.service(1), media.service(2)
    directory = Directory({str(one.service_id): "unavailable", str(two.service_id): "operational"})
    caps = media.ev.full.identity.capabilities
    caps.provide(SERVICE_DIRECTORY, directory, instance_ref="test", owner="test")
    caps.provide(SERVICE_STATE, directory, instance_ref="test", owner="test")
    library = media.library(one)
    library.images["poster-1"] = PNG_1PX
    await media.module.library.upsert(
        [
            library_record(
                "a",
                title="Arrival",
                ids={"tmdb": "329865"},
                year=2016,
                genres=["Sci-Fi"],
                people=["Amy Adams"],
                image="poster-1",
            )
        ],
        one,
    )
    await media.module.library.upsert(
        [library_record("b", title="Arrival", ids={"tmdb": "329865"}, available=False)], two
    )
    object_id = (await media.module.catalog.browse(Principal(user_id=people["alex"])))[0][0][0].id
    assert await media.module.images.fetch(object_id)
    await login(client, "alex")
    detail = (await client.get(f"/api/v1/media/{object_id}")).json()
    assert detail["title"] == "Arrival" and detail["image_id"] and detail["ids"] == {"tmdb": "329865"}
    image = await client.get(f"/api/v1/media/images/{detail['image_id']}")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    sources = (await client.get(f"/api/v1/media/{object_id}/sections/sources")).json()
    assert sources["state"] == "partial" and sources["data"]["available"] is True
    facts = {s["service_id"]: s for s in sources["data"]["sources"]}
    down = facts[str(one.service_id)]
    assert (down["availability"], down["service_state"], down["sync_status"], down["sync_error"]) == (
        "available",
        "unavailable",
        "failed",
        True,
    )  # three separate facts; the outage changes nothing in the catalog
    assert facts[str(two.service_id)]["availability"] == "unavailable"
    for name in (
        "info",
        "history",
        "progress",
        "requests",
        "people",
        "statistics",
        "events",
        "actions",
        "links",
        "blocks",
    ):
        body = (await client.get(f"/api/v1/media/{object_id}/sections/{name}")).json()
        assert {"name", "state", "as_of", "data"} <= set(body), name
    assert (await client.get(f"/api/v1/media/{object_id}/sections/people")).json()["data"]["people"] == [
        "Amy Adams"
    ]
    links = (await client.get(f"/api/v1/media/{object_id}/sections/links")).json()["data"]["links"]
    assert links[0]["url"].startswith("https://www.themoviedb.org/movie/329865")
    stats = (await client.get(f"/api/v1/media/{object_id}/sections/statistics")).json()
    assert stats["state"] == "insufficient_data"
    # a plugin block that fails is isolated; a permission-gated one is hidden
    from portalab.capabilities.media_core import DetailBlock

    async def boom(object_id, viewer):  # type: ignore[no-untyped-def]
        raise RuntimeError("plugin down")

    async def facts_block(object_id, viewer):  # type: ignore[no-untyped-def]
        return {"rows": [["Rating", "8/10"]]}

    media.blocks.register(DetailBlock("radio.facts", "plugin:radio", "radio:facts", "facts", facts_block))
    media.blocks.register(DetailBlock("radio.boom", "plugin:radio", "radio:boom", "facts", boom))
    media.blocks.register(
        DetailBlock(
            "radio.secret", "plugin:radio", "radio:s", "facts", facts_block, required_permission="audit.read"
        )
    )
    blocks = (await client.get(f"/api/v1/media/{object_id}/sections/blocks")).json()["data"]["blocks"]
    assert [(b["key"], b["state"]) for b in blocks] == [
        ("radio.boom", "unavailable"),
        ("radio.facts", "available"),
    ]
    browse = (await client.get("/api/v1/media", params={"genre": "sci-fi"})).json()
    assert [i["title"] for i in browse["items"]] == ["Arrival"]
    assert (await client.get("/api/v1/media", params={"availability": "unavailable"})).json()["items"] == []
    assert (await client.get("/api/v1/media/discovery/new")).json()["items"][0]["title"] == "Arrival"
    empty = (await client.get("/api/v1/media/discovery/recommended")).json()
    assert empty["items"] == [] and empty["next_action"]
    assert (await client.get("/api/v1/media/discovery/nope")).status_code == 404
    assert (await client.get("/api/v1/media/00000000-0000-7000-8000-000000000000")).status_code == 404


async def test_requests_and_quota(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "alex")
    seerr = media.service(5, "seerr")
    fake = media.requests(seerr)
    await media.configure("media.requests.quotaPerPeriod", 1)
    await login(client, "alex")
    body = {"ids": {"tmdb": "603"}, "kind": "movie", "title": "The Matrix", "idempotency_key": "req-key-0001"}
    first = await client.post("/api/v1/media/requests", json=body)
    again = await client.post("/api/v1/media/requests", json=body)
    assert first.status_code == 201 and again.json()["id"] == first.json()["id"] and len(fake.submitted) == 1
    over = await client.post("/api/v1/media/requests", json={**body, "idempotency_key": "req-key-0002"})
    assert over.status_code == 429 and over.json()["code"] == "media.request_quota_exceeded"
    quota = media.module.quota
    assert await quota.add_units(people["alex"], 2, "order:1", "purchase:order:1") == 2
    assert await quota.add_units(people["alex"], 2, "order:1", "purchase:order:1") == 2  # idempotent
    fake.down = True
    failed = await client.post("/api/v1/media/requests", json={**body, "idempotency_key": "req-key-0003"})
    assert (
        failed.status_code == 503 and (await quota.available(people["alex"]))["extra_units"] == 2
    )  # given back
    fake.down = False
    third = await client.post("/api/v1/media/requests", json={**body, "idempotency_key": "req-key-0004"})
    assert third.status_code == 201 and (await quota.available(people["alex"]))["extra_units"] == 1
    mine = (await client.get("/api/v1/me/media/requests")).json()
    assert [i["state"] for i in mine["items"]].count("pending") == 2 and mine["quota"]["base_remaining"] == 0
    # the source of truth moves the mirror (and a request never jumps the queue: no priority anywhere)
    external = fake.submitted and "req-1"
    await media.module.request_sink.upsert(
        [
            SourceRecord(
                "seerr",
                external,
                "request",
                {"title": "The Matrix", "kind": "movie", "state": "available"},
                clock.now(),
            )
        ],
        seerr,
    )
    states = {i["id"]: i["state"] for i in (await client.get("/api/v1/me/media/requests")).json()["items"]}
    assert states[first.json()["id"]] == "available"
    assert "media.request_available" in [e[0] for e in await media.events("media.request")]
    cancel = await client.post(f"/api/v1/media/requests/{third.json()['id']}/cancel")
    assert cancel.json()["state"] == "cancelled" and fake.states["req-2"] == "cancelled"
    assert (await client.post(f"/api/v1/media/requests/{first.json()['id']}/cancel")).status_code == 422
    async with media.database.session() as session:
        assert (
            "priority"
            not in (
                await session.execute(text("SELECT external_ref::text FROM media.requests LIMIT 1"))
            ).scalar_one()
        )


class TestMediaSearch(SearchProviderContractKit):
    harness: MediaHarness
    app: FastAPI

    @pytest.fixture(autouse=True)
    def _bind(self, media: MediaHarness, app: FastAPI) -> None:
        TestMediaSearch.harness, TestMediaSearch.app = media, app

    async def make_world(self) -> ProviderWorld:
        media = self.harness
        await media.ev.full.authz.catalog.sync()
        people = await users(self.app, media, f"u{id(self) % 10000}")
        user = next(iter(people.values()))
        await media.module.library.upsert(
            [
                library_record(
                    "z", title="Zodiac Searchable", ids={"tmdb": "1949"}, overview="A searchable thriller"
                )
            ],
            media.service(9),
        )

        async def hide(term: str) -> None:
            async with media.database.unit_of_work() as uow:
                await uow.session.execute(text("UPDATE media.objects SET status = 'hidden'"))

        provider = media.search.provider("media")
        assert provider is not None
        return ProviderWorld(
            provider, Principal(user_id=user), Principal(channel="anonymous"), "searchable", hide
        )
