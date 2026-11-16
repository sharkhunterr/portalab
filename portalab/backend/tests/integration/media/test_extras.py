"""Issue 465 — a title's videos and extra pictures: every service offering ``media.extras`` is asked (the one
holding the title by its own item), what they tell is merged and sorted (trailers first, the member's
language first, each YouTube video once), kept a while, and every picture is served by the portal, decoded
and saved afresh. Issue 466: an item played through a title must be the title, one of its episodes or one of
its extras."""

import io
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from PIL import Image
from sqlalchemy import text

from portalab.capabilities.media import EXTRAS, STREAMING, ExtraImage, ExtraVideo, MediaExtras
from portalab.capabilities.media.testkit import FakeExtras, FakeStreaming, library_record
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

pytestmark = pytest.mark.integration

TMDB_LIKE = MediaExtras(
    videos=[
        ExtraVideo(site="youtube", key="featurette1", kind="featurette", language="en"),
        ExtraVideo(site="youtube", key="trailerEN01", name="Trailer", kind="trailer", language="en"),
        ExtraVideo(site="youtube", key="trailerFR01", name="Bande-annonce", kind="trailer", language="fr"),
        ExtraVideo(site="youtube", key="not a youtube id", kind="trailer"),
    ],
    images=[ExtraImage(kind="still", ref="/still.jpg"), ExtraImage(kind="backdrop", ref="/back.jpg")],
)


async def _object(media: MediaHarness, title: str) -> str:
    async with media.database.session() as session:
        found = await session.execute(text("SELECT id FROM media.objects WHERE title = :t"), {"t": title})
        return str(found.scalar_one())


async def test_a_titles_extras_gathered_sorted_and_served(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    await users(app, media, "zoe")
    plex = media.service(3, "plex")
    await media.module.library.upsert(
        [library_record("m1", title="Film", year=2020, ids={"tmdb": "603"})], plex
    )
    object_id = await _object(media, "Film")
    metadata = media.provide(EXTRAS, media.service(4, "tmdb"), FakeExtras(told=TMDB_LIKE))
    server = media.provide(
        EXTRAS,
        plex,
        FakeExtras(
            held_only=True,
            told=MediaExtras(
                videos=[
                    ExtraVideo(
                        site="service", key="c1", name="Making of", kind="behind_the_scenes", picture="c1"
                    ),
                    ExtraVideo(site="service", key="c2", name="Trailer", kind="trailer"),
                    # the same YouTube video as the metadata's, without its name: told once, named
                    ExtraVideo(site="youtube", key="trailerFR01", kind="trailer", language="fr"),
                ]
            ),
        ),
    )
    broken = media.provide(EXTRAS, media.service(5, "fanart"), FakeExtras(fails=True))
    await login(client, "zoe")

    answer = await client.get(f"/api/v1/media/{object_id}/extras")
    assert answer.status_code == 200, answer.text
    body = answer.json()
    # each service asked by the title's ids — the one holding it also by its own item
    assert metadata.calls[-1][:3] == ("movie", {"tmdb": "603"}, None)
    assert server.calls[-1][2] == "m1" and broken.calls
    videos = body["videos"]
    # trailers first, then featurettes, then behind the scenes; the invalid id left out
    assert [v["kind"] for v in videos] == ["trailer", "trailer", "trailer", "featurette", "behind_the_scenes"]
    assert {v["youtube"] for v in videos if v["site"] == "youtube"} == {
        "trailerEN01",
        "trailerFR01",
        "featurette1",
    }
    named = next(v for v in videos if v["youtube"] == "trailerFR01")
    assert named["name"] == "Bande-annonce" and named["picture"].endswith("/picture")
    making = next(v for v in videos if v["name"] == "Making of")
    assert making["play"] == f"/media/{object_id}/watch?item=c1" and making["youtube"] is None
    assert next(v for v in videos if v["name"] == "Trailer" and v["site"] == "service")["picture"] is None
    # pictures: backdrops before stills
    assert [i["kind"] for i in body["images"]] == ["backdrop", "still"]

    # a picture: fetched once, decoded and saved afresh as a JPEG, served by the portal
    preview = await client.get(body["images"][0]["preview"])
    assert preview.status_code == 200 and preview.headers["content-type"] == "image/jpeg"
    assert preview.headers["content-security-policy"] == "default-src 'none'"
    assert Image.open(io.BytesIO(preview.content)).format == "JPEG"
    assert metadata.pictures[-1] == ("/back.jpg", True)
    await client.get(body["images"][0]["preview"])
    assert metadata.pictures.count(("/back.jpg", True)) == 1  # kept
    full = await client.get(body["images"][1]["full"])
    assert full.status_code == 200 and metadata.pictures[-1] == ("/still.jpg", False)
    assert (await client.get(f"/api/v1/media/{object_id}/extras/images/99")).status_code == 404

    # a media server's extra's picture, from that server
    picture = await client.get(making["picture"])
    assert picture.status_code == 200 and server.pictures[-1] == ("c1", True)

    # kept a while: the services are not asked again (but sooner when one of them did not answer)
    asked = len(metadata.calls)
    await client.get(f"/api/v1/media/{object_id}/extras")
    assert len(metadata.calls) == asked


async def test_a_picture_that_is_not_one_is_refused(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    await users(app, media, "zoe")
    plex = media.service(3, "plex")
    await media.module.library.upsert([library_record("m1", title="Film", year=2020)], plex)
    object_id = await _object(media, "Film")
    media.provide(
        EXTRAS, plex, FakeExtras(told=MediaExtras(images=[ExtraImage(kind="still", ref="bad.svg")]))
    )
    await login(client, "zoe")
    body = (await client.get(f"/api/v1/media/{object_id}/extras")).json()
    refused = await client.get(body["images"][0]["full"])
    assert refused.status_code == 503 and refused.json()["code"] == "media.image_unavailable"


async def test_only_the_title_its_episodes_or_its_extras_play_through_it(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "zoe")
    plex = media.service(3, "plex")
    await media.module.library.upsert(
        [
            library_record("m1", title="Film", year=2020),
            library_record("s1", kind="series", title="Series", year=2021),
        ],
        plex,
    )
    film, series = await _object(media, "Film"), await _object(media, "Series")
    media.provide(STREAMING, plex, FakeStreaming())
    extras = media.provide(EXTRAS, plex, FakeExtras(held_only=True))
    await media.module.links.claim(people["zoe"], UUID(int=3), "7", verified=True)
    await login(client, "zoe")

    # another film, an episode of another series, a clip that is not this film's: refused
    for item in ("m2", "e2", "c1"):
        refused = await client.get(f"/api/v1/media/{film}/player", params={"item": item})
        assert refused.status_code == 404, item
        started = await client.post(f"/api/v1/media/{film}/player/start", json={"item": item})
        assert started.status_code == 404, item
    reset = await client.post(f"/api/v1/media/{film}/player/reset", json={"item": "m2"})
    assert reset.status_code == 404

    # the series' own episode plays through it
    assert (await client.get(f"/api/v1/media/{series}/player", params={"item": "e2"})).status_code == 200
    # the film's extra, once the media server tells it is one
    media.module.extras._titles.clear()
    extras.told = MediaExtras(videos=[ExtraVideo(site="service", key="c1", kind="trailer")])
    info = await client.get(f"/api/v1/media/{film}/player", params={"item": "c1"})
    assert info.status_code == 200, info.text
    assert info.json()["item"]["kind"] == "clip"
    assert (await client.post(f"/api/v1/media/{film}/player/start", json={"item": "c1"})).status_code == 200
    # the title itself, as always
    assert (await client.get(f"/api/v1/media/{film}/player")).status_code == 200
