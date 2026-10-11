"""027 (#31) — « playing on the server »: the sessions running now (not ended, seen in the last minutes), each
with its title and progress, the viewer's own marked and nobody named; « a year ago »: around this date a
year (or more) back, what the viewer watched (once per title) and what came into the library."""

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.modules.media.models import Activity, PlaybackSession
from portalab.modules.media.providers.insight_widgets import OnThisDayWidget, ServerPlayingWidget
from tests.integration.media.conftest import MediaHarness, users
from tests.integration.privacy.conftest import NOW

pytestmark = pytest.mark.integration


async def _objects(media: MediaHarness) -> dict[str, UUID]:
    async with media.database.session() as session:
        rows = (await session.execute(text("SELECT title, id FROM media.objects"))).all()
    return {title: id_ for title, id_ in rows}


def _session(key: str, user: UUID | None, work: UUID | None, **kw: Any) -> PlaybackSession:
    updated = kw.pop("updated", NOW - timedelta(seconds=20))
    return PlaybackSession(
        session_key=key,
        service_id=UUID(int=1),
        user_id=user,
        external_user_id=key,
        object_id=work,
        kind=kw.pop("kind", "movie"),
        state=kw.pop("state", "playing"),
        position_s=kw.pop("position", 1500.0),
        max_position_s=1500.0,
        duration_s=6000.0,
        device="TV",
        started_at=NOW - timedelta(minutes=25),
        updated_at=updated,
        as_of=updated,
        last_event_at=updated,
        state_seq=1,
        ended=kw.pop("ended", False),
        **kw,
    )


async def test_playing_on_the_server(app: FastAPI, media: MediaHarness) -> None:
    people = await users(app, media, "zoe", "max")
    await media.module.library.upsert(
        [
            library_record("m1", title="Alien", year=1979),
            library_record("m2", title="Heat", year=1995),
            library_record("m3", title="Gone", year=1999),
            library_record("m4", title="Old", year=1990),
        ],
        media.service(1, "plex"),
    )
    objects = await _objects(media)
    async with media.database.unit_of_work() as uow:
        uow.session.add_all(
            [
                _session("a", people["zoe"], objects["Alien"]),
                _session("b", people["max"], objects["Heat"], state="paused", position=3000.0),
                _session("c", people["max"], objects["Gone"], ended=True),  # over
                _session("d", people["max"], objects["Old"], updated=NOW - timedelta(minutes=10)),  # stale
            ]
        )

    widget = ServerPlayingWidget(media.database, media.module.clock)
    payload = await widget.load(Principal(user_id=people["zoe"]), {}, LocaleContext(locale="en"))
    data = payload.data or {}
    shown = {item["title"]: item for item in data["items"]}
    assert set(shown) == {"Alien", "Heat"} and data["count"] == 2
    assert shown["Alien"]["mine"] is True and shown["Heat"]["mine"] is False
    assert shown["Alien"]["progress"] == 0.25 and shown["Heat"]["state"] == "paused"
    assert str(people["max"]) not in str(data) and "TV" not in str(data)  # nobody named, no device
    # « mine » (what « now playing » was): the viewer's own streams only
    mine = (
        await widget.load(Principal(user_id=people["zoe"]), {"scope": "me"}, LocaleContext(locale="en"))
    ).data
    assert mine is not None and [i["title"] for i in mine["items"]] == ["Alien"] and mine["mine"] is True


async def test_live_tv_on_the_server(app: FastAPI, media: MediaHarness) -> None:
    """#47: a live TV programme is not in the library — it shows by its own title, episode and channel,
    live (no progress bar), never as its bare kind."""
    people = await users(app, media, "zoe")
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            _session(
                "live",
                people["zoe"],
                None,
                kind="live",
                title="Caméra café (Espagne)",
                subtitle="Episode 3",
                channel="5 Coffee TV",
            )
        )
    widget = ServerPlayingWidget(media.database, media.module.clock)
    data = (await widget.load(Principal(user_id=people["zoe"]), {}, LocaleContext(locale="en"))).data or {}
    [card] = data["items"]
    assert card["title"] == "Caméra café (Espagne)" and card["subtitle"] == "Episode 3"
    assert card["live"] is True and card["channel"] == "5 Coffee TV" and card["kind"] == "live"
    assert card["progress"] is None and card["remaining_s"] is None


async def _watched(media: MediaHarness, user: UUID, work: UUID, title: str, days: float) -> None:
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            Activity(
                service_id=UUID(int=3),
                ref=str(uuid4()),
                family="plex",
                priority=20,
                counted=True,
                external_user_id="zoe",
                user_id=user,
                kind="movie",
                title=title,
                object_id=work,
                work_id=work,
                ids={},
                started_at=NOW - timedelta(days=days),
                watched_s=6000.0,
                duration_s=6000.0,
                progress=1.0,
                received_at=NOW,
            )
        )


async def test_a_year_ago(app: FastAPI, media: MediaHarness) -> None:
    people = await users(app, media, "zoe", "max")
    await media.module.library.upsert(
        [
            library_record("m1", title="Alien", year=1979),
            library_record("m2", title="Heat", year=1995, at=NOW - timedelta(days=366)),  # came in then
            library_record("m3", title="Today", year=2026, at=NOW - timedelta(days=2)),
        ],
        media.service(3, "plex"),
    )
    objects = await _objects(media)
    await _watched(media, people["zoe"], objects["Alien"], "Alien", 365)
    await _watched(media, people["zoe"], objects["Alien"], "Alien", 364)  # once per title
    await _watched(media, people["zoe"], objects["Heat"], "Heat", 340)  # too far from the date
    await _watched(media, people["zoe"], objects["Heat"], "Heat", 365 * 2 + 1)  # two years back
    await _watched(media, people["max"], objects["Heat"], "Heat", 365)  # someone else's

    widget = OnThisDayWidget(media.database, media.module.clock, media.module.enricher)
    ctx = LocaleContext(locale="en")
    data = (await widget.load(Principal(user_id=people["zoe"]), {}, ctx)).data
    assert data is not None
    moments = {m["years"]: m for m in data["moments"]}
    assert sorted(moments) == [1, 2]
    one = moments[1]
    assert one["date"] == (NOW - timedelta(days=365)).date().isoformat()
    assert [w["title"] for w in one["watched"]] == ["Alien"]
    assert one["watched"][0]["route"] == f"/media/{objects['Alien']}"
    assert one["added"] == []  # Heat came in a year ago (the service's date), but has no poster to show
    assert [w["title"] for w in moments[2]["watched"]] == ["Heat"]

    lone = await users(app, media, "ana")
    nothing = await widget.load(Principal(user_id=lone["ana"]), {}, ctx)
    assert nothing.state == "no-data"  # nothing watched, nothing with a poster came in


async def test_detailed_cards_tell_about_their_title(media: MediaHarness) -> None:
    """027: a detailed card says its title's year, genres and overview (and the provider's rating)."""
    from portalab.modules.media.providers.insight_widgets import with_posters

    await media.module.library.upsert(
        [library_record("m1", title="Alien", year=1979, genres=["Sci-Fi", "Horror"], overview="In space.")],
        media.service(1, "plex"),
    )
    objects = await _objects(media)
    rows = [{"id": str(objects["Alien"]), "title": "Alien"}]
    [card] = await with_posters(media.database, None, rows, detailed=True)
    assert card["year"] == 1979 and card["genres"] == ["Sci-Fi", "Horror"] and card["overview"] == "In space."
    [plain] = await with_posters(media.database, None, [{"id": str(objects["Alien"]), "title": "Alien"}])
    assert "overview" not in plain  # only when asked
