"""Issue 474 — a household profile's shelves past the titles its age rating hides: the query itself
leaves them out, so the next allowed ones fill the shelf instead of leaving it nearly empty; « Leaving soon »
follows the profile like the others (hidden titles out, each card's age badge); the random draws of the
dashboard fill up with allowed titles. Issue 475 — « Recently requested » on the media home: newest first,
one card per title, a profile's age rating holding as on every shelf."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy import select, update

from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.modules.media.models import MediaObject, MediaRequest, ObjectMetadata, SourceItem
from portalab.modules.media.providers.insight_widgets import ShuffleWidget
from portalab.modules.media.restrictions import GatedWidget
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

NOW = datetime(2026, 11, 16, 12, tzinfo=UTC)
ADULT = [f"Thriller {n}" for n in range(20)]  # rated 16, added last: more than a shelf holds
FAMILY = ["Toy Story", "Coco", "Paddington"]  # for everyone, added before


def households(app: FastAPI) -> Any:
    return app.state.household_module.service


async def _library(media: MediaHarness) -> dict[str, UUID]:
    one = media.service(1)
    media.library(one)
    records = [library_record(f"a{n}", title=t, year=2020) for n, t in enumerate(ADULT)]
    records += [library_record(f"f{n}", title=t, year=2010) for n, t in enumerate(FAMILY)]
    await media.module.library.upsert(records, one)
    async with media.database.unit_of_work() as uow:
        ids = {t: i for t, i in (await uow.session.execute(select(MediaObject.title, MediaObject.id))).all()}
        for title, object_id in ids.items():
            uow.session.add(
                ObjectMetadata(
                    object_id=object_id,
                    provider="tmdb",
                    status="found",
                    language="fr",
                    data={"certification": "16" if title in ADULT else "Tous publics"},
                    fetched_at=NOW,
                )
            )
            # the adult films came in last: the newest shelf would be all of them
            at = NOW - (timedelta(hours=1) if title in ADULT else timedelta(days=3))
            await uow.session.execute(
                update(SourceItem).where(SourceItem.object_id == object_id).values(observed_at=at)
            )
    return ids


async def _child(app: FastAPI, client: httpx.AsyncClient, media: MediaHarness) -> tuple[UUID, UUID]:
    people = await users(app, media, "zoe")
    created = await households(app).create(
        Principal(user_id=people["zoe"]), display_name="Léa", kind="child", color=None, pin=None
    )
    await login(client, "zoe")
    return people["zoe"], UUID(str(created["id"]))


async def test_a_childs_newest_shelf_fills_past_what_it_hides(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    await _library(media)
    _, lea = await _child(app, client, media)
    shelf = (await client.get("/api/v1/media/discovery/new")).json()["items"]
    assert shelf and all(i["title"] in ADULT for i in shelf)  # the master's newest: the adult films only

    assert (await client.post("/api/v1/household/switch", json={"user_id": str(lea)})).status_code == 200
    shelf = await client.get("/api/v1/media/discovery/new")
    assert shelf.status_code == 200, shelf.text
    titles = [i["title"] for i in shelf.json()["items"]]
    # twenty newer titles hidden, the shelf still shows the three allowed ones (it once came back empty)
    assert sorted(titles) == sorted(FAMILY)
    assert all(i["age"] == 0 for i in shelf.json()["items"])


async def test_leaving_soon_follows_the_profile_with_its_badges(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, monkeypatch: Any
) -> None:
    ids = await _library(media)
    _, lea = await _child(app, client, media)
    leaving = [ids["Thriller 0"], ids["Coco"], ids["Thriller 1"], ids["Toy Story"]]

    class Cleanup:
        def configured(self) -> bool:
            return True

        async def soonest(
            self, limit: int = 12, hidden: frozenset[UUID] = frozenset()
        ) -> list[dict[str, Any]]:
            return [{"id": str(i), "delete_at": "2026-11-30"} for i in leaving if i not in hidden][:limit]

    monkeypatch.setattr(media.module, "cleanup", Cleanup())
    shelf = (await client.get("/api/v1/media/discovery/leaving")).json()["items"]
    assert [i["title"] for i in shelf] == ["Thriller 0", "Coco", "Thriller 1", "Toy Story"]
    assert {i["title"]: i["age"] for i in shelf}["Thriller 0"] == 16  # the badge, for everyone

    await client.post("/api/v1/household/switch", json={"user_id": str(lea)})
    shelf = (await client.get("/api/v1/media/discovery/leaving")).json()["items"]
    assert [(i["title"], i["age"]) for i in shelf] == [("Coco", 0), ("Toy Story", 0)]


async def test_the_shuffle_draws_only_allowed_titles_and_fills_up(app: FastAPI, media: MediaHarness) -> None:
    ids = await _library(media)
    people = await users(app, media, "zoe")
    created = await households(app).create(
        Principal(user_id=people["zoe"]), display_name="Léa", kind="child", color=None, pin=None
    )
    lea = Principal(user_id=UUID(str(created["id"])), profile_of=people["zoe"])
    widget = ShuffleWidget(media.database)
    widget.DRAW = 3
    gated = GatedWidget(widget, media.module.gate)
    assert widget.title_gate is media.module.gate  # the gate is handed to the widget
    hidden = await media.module.gate.hidden(lea)
    assert {ids[t] for t in ADULT} <= hidden
    # (no poster in the test library: the drawing itself is what counts)
    drawn = await widget.hidden(lea)
    assert drawn == hidden
    payload = await gated.load(lea, {}, None)
    for item in (payload.data or {}).get("items", []):
        assert UUID(item["id"]) not in hidden


async def test_recently_requested_follows_the_profile(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    ids = await _library(media)
    master, lea = await _child(app, client, media)
    service = uuid4()
    async with media.database.unit_of_work() as uow:
        coco = ids["Coco"]
        asked = [("Thriller 2", ids["Thriller 2"]), ("Dune 3", None), ("Coco", coco), ("Coco", coco)]
        for n, (title, object_id) in enumerate(asked):
            uow.session.add(
                MediaRequest(
                    object_id=object_id,
                    external_ref={"kind": "movie", "title": title, "ids": {"tmdb": [str(100 + n)]}},
                    requester_user_id=master,
                    service_id=service,
                    state="pending",
                    source_state="pending",
                    counted="base",
                    requested_at=NOW - timedelta(minutes=n),
                    updated_at=NOW,
                )
            )
    seen = (await client.get("/api/v1/media/requests/recent")).json()["items"]
    assert [i["title"] for i in seen] == ["Thriller 2", "Dune 3", "Coco"]  # one card per title, newest first
    assert seen[0]["state"] == "pending"

    await client.post("/api/v1/household/switch", json={"user_id": str(lea)})
    seen = (await client.get("/api/v1/media/requests/recent")).json()["items"]
    # the hidden film out, and the one outside the library (no known rating) too: rated titles only
    assert [i["title"] for i in seen] == ["Coco"]


class PagedDiscovery:
    """Issue 478: a request service's popular films, twenty a page — most rated for adults."""

    def __init__(self) -> None:
        self.pages: list[int] = []

    async def search(self, query: str, language: str, page: int = 1) -> list[Any]:
        return []

    async def shelf(self, name: str, language: str, page: int = 1) -> list[Any]:
        from portalab.capabilities.media import RequestableTitle

        self.pages.append(page)
        return [RequestableTitle(str(page * 100 + n), "movie", f"Film {page}-{n}", 2024) for n in range(20)]

    async def details(self, kind: str, tmdb_id: str, language: str) -> None:
        return None


class Briefs:
    """What TMDB says of each film: one in five « tous publics », the others -16 (one with a warning, one
    about a serial killer)."""

    async def brief(self, kind: str, ids: dict[str, str], title: str, year: int | None) -> dict[str, Any]:
        n = int(ids["tmdb"]) % 100
        family = n % 5 == 0
        releases = [{"country": "FR", "type": "cinema", "certification": "TP" if family else "16"}]
        if n == 5:
            releases[0]["descriptors"] = ["violence"]
        keywords = ["serial killer", "investigation"] if n == 10 else ["friendship"]
        return {"poster": None, "rated": {"releases": releases, "genres": [], "keywords": keywords}}


async def test_a_childs_request_shelf_is_rated_and_fills_from_the_next_pages(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    from portalab.capabilities.media import REQUEST_DISCOVERY
    from portalab.modules.household.rules import RestrictionSettings

    await media.configure("i18n.defaultLanguage", "fr")
    seerr = media.service(5, "seerr")
    media.requests(seerr)
    discovery = PagedDiscovery()
    media.provide(REQUEST_DISCOVERY, seerr, discovery)
    media.module.gate.briefs = Briefs()
    master, lea = await _child(app, client, media)
    await households(app).change(
        Principal(user_id=master),
        lea,
        restrictions=RestrictionSettings(
            max_age=12, allow_unrated=False, genres=[], avoid_warnings=["violence"], keywords=["Killer"]
        ),
    )
    shelf = (await client.get("/api/v1/media/discover/shelves/popular_movies")).json()["items"]
    assert len(shelf) == 20  # the master: the first page as it is

    await client.post("/api/v1/household/switch", json={"user_id": str(lea)})
    discovery.pages.clear()
    shelf = (await client.get("/api/v1/media/discover/shelves/popular_movies")).json()["items"]
    titles = [i["title"] for i in shelf]
    # rated on TMDB instead of left out as unrated: the « tous publics » ones of five pages, but « Film n-5 »
    # (its violence kept away) and « Film n-10 » (its serial killer: a keyword kept away)
    assert titles and all(int(t.split("-")[1]) % 5 == 0 and not t.endswith(("-5", "-10")) for t in titles)
    assert discovery.pages == [2, 3, 4, 5]  # the next pages, looked for to fill the shelf
    assert len(titles) == 2 * 5


class TmdbExtras:
    """TMDB's videos and pictures of a film, by its id."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, dict[str, str]]] = []

    async def extras(self, kind: str, ids: dict[str, str], external_id: str | None, language: str) -> Any:
        from portalab.capabilities.media import ExtraImage, ExtraVideo, MediaExtras

        self.asked.append((kind, dict(ids)))
        return MediaExtras(
            videos=[ExtraVideo(site="youtube", key="abcdefghijk", name="Bande-annonce", kind="trailer")],
            images=[ExtraImage(kind="backdrop", ref="/b1.jpg"), ExtraImage(kind="still", ref="/s2.jpg")],
        )

    async def extra_image(self, ref: str, preview: bool = False) -> bytes:
        from portalab.capabilities.media.testkit import PNG_1PX

        return PNG_1PX


async def test_a_film_the_library_lacks_shows_its_videos_and_pictures_as_its_profile_allows(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    """Issue 503: a film's page before asking for it has its videos and pictures as a library title's, by
    its TMDB id — and a household profile its age rating keeps from the film gets nothing of them."""
    from portalab.capabilities.media import EXTRAS
    from portalab.modules.household.rules import RestrictionSettings

    await media.configure("i18n.defaultLanguage", "fr")  # rated as in France
    told = TmdbExtras()
    media.provide(EXTRAS, media.service(9, "tmdb"), told)
    media.module.gate.briefs = Briefs()
    master, lea = await _child(app, client, media)
    extras = (
        await client.get("/api/v1/media/discover-extras", params={"kind": "movie", "tmdb": "101"})
    ).json()
    assert told.asked == [("movie", {"tmdb": "101"})]
    assert [(v["youtube"], v["kind"], v["play"]) for v in extras["videos"]] == [
        ("abcdefghijk", "trailer", None)
    ]
    assert extras["images"][0]["preview"] == (
        "/api/v1/media/discover-extras/images/0?kind=movie&tmdb=101&preview=true"
    )
    picture = await client.get(extras["images"][1]["full"])
    assert picture.status_code == 200 and picture.headers["content-type"] == "image/jpeg"
    assert (await client.get(extras["videos"][0]["picture"])).status_code in (200, 503)
    bad = await client.get("/api/v1/media/discover-extras", params={"kind": "book", "tmdb": "101"})
    assert bad.status_code == 422
    assert (
        await client.get("/api/v1/media/discover-extras", params={"kind": "movie", "tmdb": "../x"})
    ).status_code == 422

    await households(app).change(
        Principal(user_id=master),
        lea,
        restrictions=RestrictionSettings(
            max_age=12, allow_unrated=False, genres=[], avoid_warnings=[], keywords=[]
        ),
    )
    await client.post("/api/v1/household/switch", json={"user_id": str(lea)})
    kept = await client.get("/api/v1/media/discover-extras", params={"kind": "movie", "tmdb": "101"})
    assert kept.status_code == 404  # rated 16: nothing of it for a 12-year-old's profile
    hidden = await client.get(
        "/api/v1/media/discover-extras/images/0", params={"kind": "movie", "tmdb": "101"}
    )
    assert hidden.status_code == 404
    family = await client.get("/api/v1/media/discover-extras", params={"kind": "movie", "tmdb": "100"})
    assert family.status_code == 200 and len(family.json()["images"]) == 2  # « tous publics »
