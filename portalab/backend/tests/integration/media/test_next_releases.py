"""027 — « next releases »: the coming releases that concern the viewer — a title they asked for, or the next
episode of a series they watched this past year — one per title, the soonest first, each with why it is
there; nothing that concerns someone else, nothing already out."""

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.media import CALENDAR, SourceRelease
from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock
from portalab.modules.media.models import Activity, UserLink
from portalab.modules.media.providers.insight_widgets import NextReleasesWidget
from tests.integration.media.conftest import MediaHarness, users
from tests.integration.media.test_request_insights import _request


class _Calendar:
    async def upcoming(self, start: Any, end: Any) -> list[SourceRelease]:
        now = start + timedelta(days=1)

        def episode(n: int, at: Any) -> SourceRelease:
            return SourceRelease(
                f"e{n}", "episode", f"Chapter {n}", at, "air", "Severance", 2, n, ids={"tvdb": "371980"}
            )

        return [
            episode(4, now - timedelta(hours=2)),  # already out
            episode(5, now + timedelta(days=2)),
            episode(6, now + timedelta(days=9)),  # the same series: once
            SourceRelease(
                "m1", "movie", "Arrival", now + timedelta(days=5), "digital", ids={"tmdb": "329865"}
            ),
            SourceRelease("m2", "movie", "Unasked", now + timedelta(days=1), "cinema", ids={"tmdb": "1"}),
        ]


async def test_next_releases_of_what_i_asked_for_and_follow(
    app: FastAPI, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe", "max")
    seerr = media.service(8, "seerr")
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            UserLink(
                user_id=people["zoe"],
                service_id=seerr.service_id,
                external_user_id="7",
                verified=True,
                created_at=clock.now(),
            )
        )
        uow.session.add(
            Activity(
                service_id=UUID(int=3),
                ref=str(uuid4()),
                family="plex",
                priority=20,
                counted=True,
                external_user_id="zoe",
                user_id=people["zoe"],
                kind="episode",
                title="Chapter 3",
                parent_title="Severance",
                ids={},
                started_at=clock.now() - timedelta(days=30),
                watched_s=3000.0,
                duration_s=3000.0,
                progress=1.0,
                received_at=clock.now(),
            )
        )
    await media.module.request_sink.upsert(
        [_request(clock, "3", "Arrival", "329865", "approved", "7")], seerr
    )
    media.provide(CALENDAR, media.service(5, "sonarr"), _Calendar())

    widget = NextReleasesWidget(media.database, media.module.upcoming, media.module.clock)
    ctx = LocaleContext(locale="en")
    data = (await widget.load(Principal(user_id=people["zoe"]), {}, ctx)).data or {}
    shown = [(i["title"], i["reason"], i.get("episode")) for i in data["items"]]
    assert shown == [("Severance", "watching", 5), ("Arrival", "requested", None)]
    assert data["items"][0]["subtitle"] == "Chapter 5" and data["items"][0]["type"] == "air"

    other = (await widget.load(Principal(user_id=people["max"]), {}, ctx)).data or {}
    assert other["items"] == []  # nothing max asked for or follows
