"""027 (#22) — a title's « viewing » section: the viewer's own plays (from the services' history, newest
first, with how far and on what), whether they saw it, and how many plays and members the title had — two
bare figures, shown only once enough people watched it (privacy floor), never who."""

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.media.testkit import library_record
from portalab.modules.media.models import Activity
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users
from tests.integration.privacy.conftest import NOW

pytestmark = pytest.mark.integration


async def _object(media: MediaHarness, title: str) -> UUID:
    async with media.database.session() as session:
        found: UUID = (
            await session.execute(text("SELECT id FROM media.objects WHERE title = :t"), {"t": title})
        ).scalar_one()
        return found


async def _play(
    media: MediaHarness, work: UUID, user: UUID | None, progress: float, days: float, **kw: Any
) -> None:
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            Activity(
                service_id=UUID(int=3),
                ref=str(uuid4()),
                family="plex",
                priority=20,
                counted=kw.pop("counted", True),
                external_user_id=kw.pop("account", str(uuid4())),
                user_id=user,
                kind="movie",
                title="Film",
                object_id=work,
                work_id=work,
                ids={},
                started_at=NOW - timedelta(days=days),
                watched_s=6000.0 * progress,
                duration_s=6000.0,
                progress=progress,
                device=kw.pop("device", None),
                received_at=NOW,
            )
        )


async def test_my_plays_seen_and_counts_past_the_floor(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "zoe", "max", "ana", "leo")
    await media.module.library.upsert(
        [library_record("m1", title="Film", year=2020), library_record("m2", title="Rare", year=2021)],
        media.service(3, "plex"),
    )
    film, rare = await _object(media, "Film"), await _object(media, "Rare")
    await _play(media, film, people["zoe"], 0.35, 1, device="Portalab")
    await _play(media, film, people["zoe"], 1.0, 10, device="Living room TV")
    await _play(media, film, people["zoe"], 1.0, 9, counted=False)  # Plex's copy of Tautulli's row
    for name in ("max", "ana", "leo"):
        await _play(media, film, people[name], 1.0, 3)
    await _play(media, film, None, 0.5, 4, account="guest")  # an unlinked account still counts as one
    await _play(media, rare, people["zoe"], 0.5, 2)
    await _play(media, rare, people["max"], 1.0, 2)

    await login(client, "zoe")
    body = (await client.get(f"/api/v1/media/{film}/sections/viewing")).json()
    data = body["data"]
    assert body["state"] == "available"
    assert [(p["progress"], p["device"]) for p in data["mine"]] == [
        (0.35, "Portalab"),
        (1.0, "Living room TV"),
    ]
    assert data["mine_total"] == 2 and data["status"] == "seen"
    assert data["community"] == {"plays": 6, "viewers": 5}  # zoe twice, max, ana, leo, the guest
    assert "user_id" not in str(data) and "max" not in str(data)  # no one named

    rare_data = (await client.get(f"/api/v1/media/{rare}/sections/viewing")).json()["data"]
    assert rare_data["status"] == "in_progress" and rare_data["percent"] == 0.5
    assert rare_data["community"] is None and rare_data["min_cohort_size"] == 5  # two viewers: hidden

    await login(client, "leo")
    leo = (await client.get(f"/api/v1/media/{rare}/sections/viewing")).json()
    assert leo["state"] == "no-data" and leo["data"]["mine"] == []
