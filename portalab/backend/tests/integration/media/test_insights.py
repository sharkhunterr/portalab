"""027 — Telemetra-style statistics: the raw history of each service is backfilled page by page then followed
incrementally, tied to the catalog (episodes count for their series), attributed to members through their
linked accounts (even linked afterwards), de-duplicated when Tautulli reports the plays Plex reports too,
aggregated per day, and served — mine, or the server's anonymously — with erasure on account deletion."""

from datetime import timedelta
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.media import (
    ACCOUNTS,
    ACTIVITY_HISTORY,
    CALENDAR,
    METADATA,
    ActivityPage,
    MetadataPerson,
    MetadataRecord,
    ServiceAccount,
    SourceActivity,
    SourceRelease,
)
from portalab.capabilities.media.testkit import PNG_1PX, library_record
from portalab.core.time import FixedClock
from portalab.modules.media.insights.stats import window
from portalab.modules.media.models import Activity, ActivityCursor, MediaObject, UserLink
from portalab.modules.media.participant import MediaParticipant
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users


class _History:
    """A paged history (two plays per page), recording what the portal asked for."""

    def __init__(self, plays: list[SourceActivity]) -> None:
        self.plays = plays
        self.calls: list[tuple[Any, Any]] = []

    async def history(self, *, since: Any, cursor: str | None) -> ActivityPage:
        self.calls.append((since, cursor))
        rows = [p for p in self.plays if since is None or p.started_at >= since]
        start = int(cursor or 0)
        page = rows[start : start + 2]
        return ActivityPage(
            items=page,
            cursor=str(start + 2) if start + 2 < len(rows) else None,
            total=len(rows),
            position=start + len(page),
        )


class _Accounts:
    async def list_accounts(self) -> list[ServiceAccount]:
        return [ServiceAccount("1234", "zoe", "Zoé")]


def play(
    ref: str, at: Any, *, kind: str = "movie", item: str | None = "101", priority: int, **kw: Any
) -> SourceActivity:
    return SourceActivity(
        ref=ref,
        external_user_id=kw.pop("user", "1"),
        kind=kind,
        title=kw.pop("title", "Dune"),
        started_at=at,
        watched_s=kw.pop("watched", 5400.0),
        duration_s=kw.pop("duration", 9360.0),
        progress=kw.pop("progress", 0.95),
        item_external_id=item,
        family="plex",
        priority=priority,
        **kw,
    )


async def test_history_is_ingested_deduplicated_attributed_and_served(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe", admin="boss")
    now = clock.now()
    plex, tautulli = media.service(1, "plex"), media.service(2, "tautulli")
    media.library(plex)
    await media.module.library.upsert(
        [
            library_record(
                "101", title="Dune", ids={"tmdb": "438631"}, year=2021, genres=["Sci-Fi"], duration_s=9360.0
            ),
            library_record("s1", kind="series", title="Andor", year=2022),
            library_record("se1", kind="season", title="Season 1", parent="s1", position=1),
            library_record("e1", kind="episode", title="Kassa", parent="se1", position=1),
        ],
        plex,
    )
    async with media.database.unit_of_work() as uow:  # Zoé's Plex account is already linked
        uow.session.add(
            UserLink(
                user_id=people["zoe"],
                service_id=plex.service_id,
                external_user_id="1",
                verified=True,
                created_at=now,
            )
        )
    plex_history = media.provide(
        ACTIVITY_HISTORY,
        plex,
        _History(
            [
                play("p1", now - timedelta(days=10), priority=10),
                play("p9", now - timedelta(days=12), priority=10, watched=0.0, duration=None, progress=None),
                play("p2", now - timedelta(days=2), priority=10),
                play(
                    "p3",
                    now - timedelta(days=1, hours=1),
                    priority=10,
                    kind="episode",
                    item="e1",
                    title="Kassa",
                ),
            ]
        ),
    )
    tautulli_history = media.provide(
        ACTIVITY_HISTORY,
        tautulli,
        _History(
            [
                play(
                    "t1", now - timedelta(days=2), priority=20, user="1234", device="TV", platform="Android"
                ),
                play(
                    "t2",
                    now - timedelta(days=1),
                    priority=20,
                    user="1234",
                    kind="episode",
                    item="e1",
                    title="Kassa",
                    parent_title="Andor",
                ),
                play(
                    "t3",
                    now - timedelta(hours=5),
                    priority=20,
                    user="1234",
                    kind="live",
                    item=None,
                    title="Journal",
                ),
            ]
        ),
    )
    media.provide(ACCOUNTS, tautulli, _Accounts())

    assert await media.module.ingestor.run() == 7
    while await media.module.aggregator.run():
        pass
    async with media.database.session() as session:
        rows = {a.ref: a for a in (await session.execute(select(Activity))).scalars()}
        cursors = {c.service_id: c for c in (await session.execute(select(ActivityCursor))).scalars()}
        dune = await session.scalar(select(MediaObject.id).where(MediaObject.title == "Dune"))
        andor = await session.scalar(select(MediaObject.id).where(MediaObject.title == "Andor"))
    # backfilled over pages, then incremental
    assert [c[1] for c in plex_history.calls] == [None, "2"] and cursors[
        plex.service_id
    ].mode == "incremental"
    assert cursors[tautulli.service_id].backfilled_at is not None
    # from Tautulli's first play on, Plex's rows of the same plays stop counting
    assert rows["p1"].counted and not rows["p2"].counted and not rows["p3"].counted
    assert rows["t1"].counted and rows["t1"].object_id == dune == rows["p1"].work_id
    assert rows["t2"].work_id == andor  # an episode counts for its series (resolved through the Plex library)
    # Plex plays were attributed at once; Tautulli's wait for the account to be linked
    assert rows["p1"].user_id == people["zoe"] and rows["t1"].user_id is None
    # Plex's history gives no length: the catalog's duration is used for the time spent
    assert rows["p9"].watched_s == 9360.0 and rows["p9"].duration_s == 9360.0

    await login(client, "boss")
    linked = await client.put(
        f"/api/v1/admin/media/accounts/{tautulli.service_id}",
        json={"external_user_id": "1234", "user_id": str(people["zoe"])},
    )
    assert linked.status_code == 200
    while await media.module.aggregator.run():
        pass
    server = (await client.get("/api/v1/media/insights", params={"scope": "all", "period": "30d"})).json()
    assert server["manager"] and server["totals"]["plays"] == 5 and server["totals"]["members"] == 1
    assert server["members"][0]["name"] == "zoe" and server["unattributed"] == 0
    ran = await client.post("/api/v1/admin/media/insights/run", json={"what": "metadata"})
    assert ran.status_code == 202 and ran.json() == {"state": "scheduled"}
    assert (await client.post("/api/v1/admin/media/insights/run", json={"what": "x"})).status_code == 422
    sources = (await client.get("/api/v1/admin/media/insights/sources")).json()
    assert {s["mode"] for s in sources["sources"]} == {"incremental"}
    # live progress: nothing runs now; the last run went to the end of each history
    assert not any(s["progress"]["running"] for s in sources["sources"])
    assert sorted((s["progress"]["done"], s["progress"]["total"]) for s in sources["sources"]) == [
        (3, 3),
        (4, 4),
    ]
    assert sources["metadata"]["eligible"] == 2 and sources["metadata"]["progress"]["running"] is False

    await login(client, "zoe")
    mine = (await client.get("/api/v1/media/insights", params={"period": "30d", "tz": "Europe/Paris"})).json()
    totals = mine["totals"]
    assert totals["plays"] == 5 and totals["works"] == 3 and totals["seconds"] == 4 * 5400 + 9360
    assert mine["top_works"][0]["id"] == str(dune) and mine["top_works"][0]["plays"] == 3
    assert {w["title"] for w in mine["top_works"]} == {"Dune", "Andor", "Journal"}
    assert mine["genres"][0]["name"] == "Sci-Fi" and mine["platforms"][0]["name"] == "Android"
    assert mine["records"]["best_streak"] >= 1 and len(mine["timeline"]["points"]) == 30
    assert sum(cell["plays"] for cell in mine["heatmap"]) == 5
    movies = (await client.get("/api/v1/media/insights", params={"category": "movies"})).json()
    assert movies["totals"]["plays"] == 3 and movies["requests"] is None
    anonymous = (await client.get("/api/v1/media/insights", params={"scope": "all"})).json()
    assert anonymous["members"] is None and anonymous["recent"] is None and anonymous["platforms"] is None
    assert (await client.get("/api/v1/media/insights", params={"tz": "Mars/Base"})).status_code == 422
    assert (await client.get("/api/v1/admin/media/insights/sources")).status_code == 403
    assert (
        await client.post("/api/v1/admin/media/insights/run", json={"what": "history"})
    ).status_code == 403

    # incremental: only what is new since the latest play (with an overlap) is asked for
    tautulli_history.plays.append(play("t4", now + timedelta(minutes=1), priority=20, user="1234"))
    assert await media.module.ingestor.run() >= 1
    assert tautulli_history.calls[-1][0] is not None

    await MediaParticipant(media.database).erase(people["zoe"], "final")
    async with media.database.session() as session:
        left = (await session.execute(select(Activity).where(Activity.user_id == people["zoe"]))).all()
    assert left == []


def test_periods() -> None:
    from datetime import UTC, datetime

    now = datetime(2026, 10, 4, 15, tzinfo=UTC)
    assert window("7d", now).start == datetime(2026, 9, 28, tzinfo=UTC)
    assert window("2025", now).start == datetime(2025, 1, 1, tzinfo=UTC)
    assert window("all", now).start is None and window("all", now).previous() is None
    previous = window("30d", now).previous()
    assert previous is not None and previous.end == window("30d", now).start


class _Tmdb:
    def __init__(self) -> None:
        self.asked: list[tuple[str, dict[str, str], str]] = []

    async def lookup(
        self, kind: str, ids: Any, title: str, year: Any, language: str
    ) -> MetadataRecord | None:
        self.asked.append((kind, dict(ids), language))
        if title != "Dune":
            return None
        return MetadataRecord(
            ids={"tmdb": "438631"},
            title="Dune",
            tagline="Beyond fear, destiny awaits.",
            genres=["Science-Fiction"],
            budget=165_000_000,
            revenue=402_027_830,
            collection={"id": "726871", "name": "Dune - Saga", "poster": None, "backdrop": None},
            backdrop="/backdrop.jpg",
            poster="/poster.jpg",
            people=[MetadataPerson("Timothée Chalamet", "Paul", image="/tc.jpg")],
        )

    async def fetch_image(self, ref: str, size: str) -> bytes:
        return b"\xff\xd8jpeg" + ref.encode()


class _Calendar:
    async def upcoming(self, start: Any, end: Any) -> list[SourceRelease]:
        return [
            SourceRelease(
                "movie:3", "movie", "Dune", start + timedelta(days=3), "digital", ids={"tmdb": "438631"}
            ),
            SourceRelease("movie:4", "movie", "Far Away", end + timedelta(days=30), "cinema"),
        ]


async def test_metadata_enrichment_and_upcoming(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    await users(app, media, "zoe")
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            library_record("101", title="Dune", ids={"tmdb": "438631"}, year=2021),
            library_record("102", title="Nowhere", year=1999),
        ],
        one,
    )
    tmdb = media.provide(METADATA, media.service(9, "tmdb"), _Tmdb())
    media.provide(CALENDAR, media.service(3, "radarr"), _Calendar())
    assert await media.module.enricher.run() == 2
    assert await media.module.enricher.run() == 0  # nothing due until the retry delay
    assert {(kind, ids.get("tmdb")) for kind, ids, _ in tmdb.asked} == {("movie", "438631"), ("movie", None)}
    async with media.database.session() as session:
        dune = await session.scalar(select(MediaObject.id).where(MediaObject.title == "Dune"))
        nowhere = await session.scalar(select(MediaObject.id).where(MediaObject.title == "Nowhere"))

    await login(client, "zoe")
    details = (await client.get(f"/api/v1/media/{dune}/metadata")).json()
    assert details["budget"] == 165_000_000 and details["collection"]["name"] == "Dune - Saga"
    assert details["people"][0]["name"] == "Timothée Chalamet" and details["backdrop"] == "/backdrop.jpg"
    assert (await client.get(f"/api/v1/media/{nowhere}/metadata")).status_code == 404
    image = await client.get(
        "/api/v1/media/metadata-images", params={"ref": "/backdrop.jpg", "size": "w1280"}
    )
    assert image.status_code == 200 and image.content.endswith(b"/backdrop.jpg")
    assert "immutable" in image.headers["cache-control"]
    bad = await client.get("/api/v1/media/metadata-images", params={"ref": "https://evil.example/x.jpg"})
    assert bad.status_code == 422
    upcoming = (await client.get("/api/v1/media/upcoming", params={"days": 14})).json()["items"]
    assert [(u["title"], u["type"], u["object_id"]) for u in upcoming] == [("Dune", "digital", str(dune))]


async def test_dashboard_widgets(app: FastAPI, media: MediaHarness, clock: FixedClock) -> None:
    from portalab.capabilities.i18n import LocaleContext
    from portalab.core.authz_port import Principal

    people = await users(app, media, "zoe")
    one = media.service(1)
    media.library(one).images["p"] = PNG_1PX
    await media.module.library.upsert(
        [library_record("101", title="Dune", ids={"tmdb": "438631"}, year=2021, image="p")], one
    )
    async with media.database.session() as session:
        dune = await session.scalar(select(MediaObject.id).where(MediaObject.title == "Dune"))
    assert dune is not None and await media.module.images.fetch(dune)
    media.provide(CALENDAR, media.service(3, "radarr"), _Calendar())
    media.provide(
        ACTIVITY_HISTORY,
        media.service(2),
        _History([play("x", clock.now(), priority=10, ids={"tmdb": "438631"})]),
    )
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            UserLink(
                user_id=people["zoe"],
                service_id=media.service(2).service_id,
                external_user_id="1",
                verified=True,
                created_at=clock.now(),
            )
        )
    await media.module.ingestor.run()
    await media.module.aggregator.run()
    zoe, ctx = Principal(user_id=people["zoe"]), LocaleContext()
    keys = {w.definition.key for w in media.widgets.widgets()}
    assert {"media.stats", "media.recently_added", "media.upcoming", "media.top"} <= keys
    added = await _widget(media, "media.recently_added").load(zoe, {}, ctx)
    assert added.state == "available" and added.data["items"][0]["image_id"]
    stats = await _widget(media, "media.stats").load(zoe, {"scope": "me"}, ctx)
    assert stats.data["totals"]["plays"] == 1 and stats.data["top"][0]["route"] == f"/media/{dune}"
    shaped = await _widget(media, "media.stats").load(
        zoe, {"chart": "donut", "metric": "plays", "category": "movies", "period": "90d"}, ctx
    )
    assert (shaped.data["chart"], shaped.data["metric"], shaped.data["category"]) == (
        "donut",
        "plays",
        "movies",
    )
    assert shaped.data["period"] == "90d" and shaped.data["timeline"][-1]["plays"] >= 0
    odd = await _widget(media, "media.stats").load(zoe, {"chart": "pie3d", "period": "10y"}, ctx)
    assert odd.data["chart"] == "bars" and odd.data["period"] == "30d"  # unknown choices fall back
    top = await _widget(media, "media.top").load(zoe, {}, ctx)
    assert top.data["items"][0]["title"] == "Dune"
    upcoming = await _widget(media, "media.upcoming").load(zoe, {}, ctx)
    assert upcoming.data["items"][0]["type"] == "digital"
    requested = await _widget(media, "media.recently_requested").load(zoe, {}, ctx)
    assert requested.state == "no-data"
    # a request the library does not have gets the metadata provider's poster
    media.provide(METADATA, media.service(9, "tmdb"), _Tmdb())
    seerr = media.service(8, "seerr")
    await media.module.request_sink.upsert(
        [
            SourceRecord(
                source_system="seerr",
                external_id="r1",
                kind="request",
                payload={"title": "Dune", "kind": "movie", "ids": {}, "state": "pending"},
                observed_at=clock.now(),
            )
        ],
        seerr,
    )
    requested = await _widget(media, "media.recently_requested").load(zoe, {}, ctx)
    card = requested.data["items"][0]
    assert card["image_id"] is None and card["poster_ref"] == "/poster.jpg" and card["state"] == "pending"


def _widget(media: MediaHarness, key: str) -> Any:
    registered = media.widgets.get(key)
    assert registered is not None
    return registered.provider


async def test_media_home_journal_and_posters_of_titles_outside_the_library(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    """027 — the media home's own rows come from the services' history: what I am in the middle of (not
    finished, live TV left out) and what I opened lately (a series once); Statistics gives a title the
    library does not hold — live TV's show — the metadata provider's poster."""
    from portalab.capabilities.i18n import LocaleContext
    from portalab.core.authz_port import Principal

    people = await users(app, media, "zoe")
    now = clock.now()
    history = media.service(2, "tautulli")
    media.provide(METADATA, media.service(9, "tmdb"), _Tmdb())
    media.provide(
        ACTIVITY_HISTORY,
        history,
        _History(
            [
                play("a", now - timedelta(hours=9), priority=20, title="Arrival", progress=0.4, item=None),
                play(
                    "b",
                    now - timedelta(hours=8),
                    priority=20,
                    kind="episode",
                    item=None,
                    title="Kassa",
                    parent_title="Andor",
                    progress=0.97,
                ),
                play(
                    "c",
                    now - timedelta(hours=7),
                    priority=20,
                    kind="episode",
                    item=None,
                    title="Aldhani",
                    parent_title="Andor",
                    progress=0.96,
                ),
                play(
                    "d",
                    now - timedelta(hours=6),
                    priority=20,
                    kind="live",
                    item=None,
                    title="Morituri",
                    parent_title="Dune",
                    progress=None,
                ),
            ]
        ),
    )
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            UserLink(
                user_id=people["zoe"],
                service_id=history.service_id,
                external_user_id="1",
                verified=True,
                created_at=now,
            )
        )
    await media.module.ingestor.run()
    while await media.module.aggregator.run():
        pass

    await login(client, "zoe")
    journal = (await client.get("/api/v1/me/media/journal")).json()
    assert [(i["title"], i["progress"]) for i in journal["continue"]] == [("Arrival", 0.4)]
    assert journal["continue"][0]["route"] is None  # not in the library: nothing to open
    assert [(i["kind"], i["title"]) for i in journal["recent"]] == [
        ("episode", "Andor"),
        ("movie", "Arrival"),
    ]
    continuing = await _widget(media, "media.continue").load(
        Principal(user_id=people["zoe"]), {}, LocaleContext()
    )
    assert [i["title"] for i in continuing.data["items"]] == ["Arrival"]

    stats = (await client.get("/api/v1/media/insights", params={"period": "30d"})).json()
    live = next(w for w in stats["top_works"] if w["kind"] == "live")
    assert live["title"] == "Dune" and live["poster_ref"] == "/poster.jpg"  # grouped by the show
    latest = stats["recent"][0]
    assert (
        latest["kind"] == "live"
        and latest["parent_title"] == "Dune"
        and latest["poster_ref"] == "/poster.jpg"
    )
