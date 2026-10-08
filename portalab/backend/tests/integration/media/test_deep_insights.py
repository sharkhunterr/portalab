"""027 — statistics in depth (Telemetra-style tabs), compared with the previous period: the directors and
actors met most; what the films cost and earned (most expensive, most profitable, budget ranges, successes
and flops), their years and countries; how they were played (direct play, transcoded, resolution,
platforms; devices only where allowed); the genres (new, rising, always, gone) and the viewing footprint.
Tautulli's rows say how each play was streamed and in which resolution."""

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI

from portalab.connectors.tautulli import map_history_row
from portalab.modules.media.models import Activity, MediaObject, ObjectMetadata, ObjectTag
from tests.integration.media.conftest import NOW, MediaHarness, users


async def _film(media: MediaHarness, title: str, genres: list[str], **data: Any) -> UUID:
    object_id = uuid4()
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            MediaObject(
                id=object_id,
                kind="movie",
                title=title,
                sort_title=title.lower(),
                available=True,
                effective={},
                field_provenance={},
                status="active",
                first_seen_at=NOW,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await uow.session.flush()
        uow.session.add_all([ObjectTag(object_id=object_id, tag_kind="genre", value=g) for g in genres])
        uow.session.add(
            ObjectMetadata(
                object_id=object_id,
                provider="tmdb",
                status="found",
                language="fr",
                data={"title": title, **data},
                fetched_at=NOW,
            )
        )
    return object_id


async def _play(media: MediaHarness, work: UUID, days_ago: float, user: UUID, **kw: Any) -> None:
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            Activity(
                service_id=uuid4(),
                ref=str(uuid4()),
                family="plex",
                priority=20,
                counted=True,
                external_user_id="1",
                user_id=user,
                kind="movie",
                title="x",
                object_id=work,
                work_id=work,
                ids={},
                started_at=NOW - timedelta(days=days_ago),
                watched_s=6000.0,
                duration_s=6000.0,
                progress=1.0,
                received_at=NOW,
                **kw,
            )
        )


def _director(name: str) -> dict[str, Any]:
    return {"name": name, "role": "Director", "department": "directing", "image": f"/{name}.jpg"}


def _actor(name: str) -> dict[str, Any]:
    return {"name": name, "role": "Hero", "department": "cast", "ids": {"tmdb": name}}


async def test_sections_compare_with_the_previous_period(app: FastAPI, media: MediaHarness) -> None:
    me = (await users(app, media, "zoe"))["zoe"]
    dune = await _film(
        media,
        "Dune",
        ["Science-Fiction", "Aventure"],
        budget=190_000_000,
        revenue=714_000_000,
        release_date="2024-02-27",
        countries=["US", "CA"],
        people=[_director("Villeneuve"), _actor("Chalamet"), _actor("Zendaya")],
    )
    flop = await _film(
        media,
        "Tron Ares",
        ["Science-Fiction"],
        budget=220_000_000,
        revenue=142_000_000,
        release_date="2025-10-08",
        countries=["US"],
        people=[_director("Rønning"), _actor("Leto")],
    )
    small = await _film(
        media,
        "Heredity",
        ["Horreur"],
        budget=10_000_000,
        revenue=87_800_000,
        release_date="2018-06-08",
        countries=["US"],
        people=[_director("Aster"), _actor("Collette"), _actor("Zendaya")],
    )
    await _play(media, dune, 3, me, stream="direct", quality="4k", platform="Android", device="MIBOX3")
    await _play(media, flop, 5, me, stream="transcode", quality="1080p", platform="Chrome", device="Pixel")
    await _play(media, small, 10, me, stream="direct", quality=None, platform="Android", device="MIBOX3")
    await _play(media, small, 45, me, stream="direct", quality="1080p", platform="Android")  # previous
    deep = media.module.deep_insights

    casting = await deep.section("casting", period="30d", category="movies", user=me, detailed=True)
    assert [a["name"] for a in casting["actors"]][:1] == ["Zendaya"]  # two films
    assert casting["actors"][0]["works"] == 2 and casting["actors"][0]["previous"] == 1
    assert {d["name"] for d in casting["directors"]} == {"Villeneuve", "Rønning", "Aster"}

    production = await deep.section("production", period="30d", category="movies", user=me, detailed=True)
    assert production["films"] == 3
    assert production["most_expensive"]["title"] == "Tron Ares"
    assert production["cheapest"]["title"] == "Heredity"
    assert (
        production["most_profitable"]["title"] == "Heredity" and production["most_profitable"]["roi"] == 8.78
    )
    assert [f["title"] for f in production["flops"]][:1] == ["Tron Ares"]
    ranges = {b["range"]: (b["count"], b["previous"]) for b in production["budgets"]}
    assert ranges["<25"] == (1, 1) and ranges["150-250"] == (2, 0)
    assert {c["code"]: c["count"] for c in production["countries"]} == {"US": 3, "CA": 1}
    assert production["year_average"] == round((2024 + 2025 + 2018) / 3, 1)

    playback = await deep.section("playback", period="30d", category="movies", user=me, detailed=True)
    streams = {s["key"]: (s["count"], s["previous"]) for s in playback["streams"]["totals"]}
    assert streams == {"direct": (2, 1), "transcode": (1, 0)}
    assert {q["key"]: q["count"] for q in playback["qualities"]["totals"]} == {
        "4k": 1,
        "1080p": 1,
        "unknown": 1,
    }
    assert playback["platforms"][0] == {"name": "Android", "count": 2}
    assert playback["devices"][0]["name"] == "MIBOX3"
    anonymous = await deep.section("playback", period="30d", category="movies", user=None, detailed=False)
    assert anonymous["devices"] is None  # device names stay private

    profile = await deep.section("profile", period="30d", category="movies", user=me, detailed=True)
    assert profile["summary"]["new"] == ["Science-Fiction", "Aventure"]
    assert profile["summary"]["always"] == ["Horreur"] and profile["summary"]["gone"] == []
    assert sum(profile["hours"]) == 3 and sum(profile["weekdays"]) == 3
    assert sum(a["plays"] for a in profile["activity"]) == 3
    assert sum(a["previous_plays"] for a in profile["activity"]) == 1
    assert profile["unit"] == "day" and len(profile["buckets"]) == 30


def test_tautulli_rows_tell_the_stream_and_resolution() -> None:
    row = {
        "id": 7,
        "user_id": 1,
        "media_type": "movie",
        "started": 1760000000,
        "title": "Dune",
        "transcode_decision": "transcode",
        "stream_video_resolution": "1080",
        "video_resolution": "4k",
    }
    played = map_history_row(row)
    assert played is not None and (played.stream, played.quality) == ("transcode", "1080p")
    direct = map_history_row({**row, "transcode_decision": "direct play", "stream_video_resolution": None})
    assert direct is not None and (direct.stream, direct.quality) == ("direct", "4k")
