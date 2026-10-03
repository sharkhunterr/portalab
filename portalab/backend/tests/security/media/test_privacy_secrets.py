"""024 T029/T030/T035 — no secrets or credential URLs in stored payloads, events or API answers; another
user's history, progress, links and requests are never visible; AI tools act as the acting principal;
community references show a public summary only; admin views are metadata only; export/erasure cover
the personal media data while catalog objects stay."""

import logging

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock
from portalab.modules.media.participant import MediaParticipant
from portalab.modules.media.providers.community import public_summary
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

pytestmark = pytest.mark.integration


async def test_media_privacy(
    app: FastAPI,
    client: httpx.AsyncClient,
    media: MediaHarness,
    clock: FixedClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    people = await users(app, media, "alex", "sam", admin="boss")
    svc = media.service(1)
    await media.module.library.upsert(
        [
            library_record(
                "m",
                title="Memento",
                ids={"tmdb": "77"},
                image="https://srv.local/p.jpg?api_key=SECRET123",
                duration_s=100,
            )
        ],
        svc,
    )
    link = await media.module.links.claim(people["alex"], svc.service_id, "alex-on-plex")
    playback = media.playback(svc)
    playback.play(
        "s",
        external_user_id="alex-on-plex",
        item_external_id="m",
        position_s=95,
        duration_s=100,
        device="Alex's TV",
    )
    await media.module.poller.tick()
    assert await media.module.poller.now_playing(people["alex"]) == []  # unverified link: never attributed
    await media.module.links.verify(None, link.id, None)
    clock.advance(__import__("datetime").timedelta(seconds=30))
    playback.play(
        "t",
        external_user_id="alex-on-plex",
        item_external_id="m",
        position_s=95,
        duration_s=100,
        device="Alex's TV",
    )
    await media.module.poller.tick()
    playback.stop("t")
    playback.stop("s")
    await media.module.poller.poll(svc.service_id, playback)
    await media.dispatch()
    object_id = (await media.module.catalog.browse(Principal(user_id=people["sam"])))[0][0][0].id
    async with media.database.session() as session:
        stored = " ".join(
            r[0] for r in await session.execute(text("SELECT payload::text FROM media.source_items"))
        )
        events = " ".join(
            r[0] for r in await session.execute(text("SELECT payload::text FROM events.events"))
        )
    assert "SECRET123" not in stored and "SECRET123" not in events
    assert "Memento" not in events and "Alex's TV" not in events and "alex-on-plex" not in events
    assert "SECRET123" not in caplog.text
    # sam sees the object but nothing personal of alex's
    await login(client, "sam")
    history = (await client.get(f"/api/v1/media/{object_id}/sections/history")).json()
    assert history["data"]["mine"] == [] and history["data"]["concerned_users"] == []
    assert (await client.get("/api/v1/me/media/history")).json() == []
    assert (await client.get("/api/v1/me/media/links")).json() == []
    assert (await client.delete(f"/api/v1/me/media/links/{link.id}")).status_code == 404
    assert (await client.get("/api/v1/admin/media/unlinked-activity")).status_code == 403
    assert "SECRET123" not in (await client.get(f"/api/v1/media/{object_id}")).text
    await login(client, "alex")
    assert [h["title"] for h in (await client.get("/api/v1/me/media/history")).json()] == ["Memento"]
    # AI tools run as the acting principal
    tools = {t.name: t for t in media.module.ai_tools.definitions()}
    as_sam = Principal(channel="ai", acting_for=people["sam"])
    assert (await tools["media.my_history"].run(as_sam, {}))["items"] == []
    assert (await tools["media.my_history"].run(Principal(channel="ai", acting_for=people["alex"]), {}))[
        "items"
    ]
    found = await tools["media.search_catalog"].run(as_sam, {"q": "memento"})
    assert found["items"][0]["title"] == "Memento" and "image" not in str(found)
    # community: public summary, never who watched
    summary = await public_summary(media.module.catalog_port, "tmdb:77", Principal(user_id=people["sam"]))
    assert summary is not None and set(summary) == {"id", "kind", "title", "year", "available", "route"}
    assert (
        await public_summary(media.module.catalog_port, "tmdb:999999", Principal(user_id=people["sam"]))
        is None
    )
    # admin unlinked view: counts only
    await login(client, "boss")
    unlinked = (await client.get("/api/v1/admin/media/unlinked-activity")).json()
    assert (
        unlinked and "alex" not in str(unlinked) and set(unlinked[0]) == {"service_id", "sessions", "last_at"}
    )
    # export / erasure
    participant = MediaParticipant(media.database)
    exported = await participant.export(people["alex"])
    assert {r.category for r in exported} >= {"media.history", "media.link"}
    await participant.erase(people["alex"], "delete")  # type: ignore[arg-type]
    await participant.erase(people["alex"], "delete")  # type: ignore[arg-type]
    assert await participant.export(people["alex"]) == []
    async with media.database.session() as session:
        assert (await session.execute(text("SELECT count(*) FROM media.objects"))).scalar_one() == 1
