"""#354: a title's technical sheet for the team — asked of each media server holding it (its files and
streams), a server that fails left out; the download manager's side when one follows the title."""

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media import TECHNICAL, TechnicalFile, TechnicalSheet, TechnicalStream
from portalab.capabilities.media.testkit import library_record
from portalab.capabilities.media_core import TECHNICAL_SHEETS
from portalab.core.authz_port import Principal
from portalab.modules.media.models import MediaObject
from tests.integration.media.conftest import MediaHarness, users

ADDED = datetime(2026, 10, 6, tzinfo=UTC)


class Plex:
    def __init__(self) -> None:
        self.asked: list[tuple[str, str]] = []

    async def technical(self, external_id: str, kind: str) -> TechnicalSheet:
        self.asked.append((external_id, kind))
        stream = TechnicalStream(kind="audio", codec="eac3", language="Français", channels="5.1")
        return TechnicalSheet(ADDED, (TechnicalFile("/m/Alien.mkv", 4_000, "mkv", 7000.0, 9000, (stream,)),))


class Broken:
    async def technical(self, external_id: str, kind: str) -> Any:
        raise RuntimeError("down")


async def test_a_title_s_technical_sheet(app: FastAPI, media: MediaHarness) -> None:
    people = await users(app, media, admin="sam")
    one, two = media.service(1), media.service(2)
    for service in (one, two):
        media.library(service)
        await media.module.library.upsert([library_record("m1", title="Alien", year=1979, ids={"tmdb": "348"})], service)
    plex = media.provide(TECHNICAL, one, Plex())
    media.provide(TECHNICAL, two, Broken())
    async with media.database.session() as session:
        alien = (
            await session.execute(select(MediaObject.id).where(MediaObject.title == "Alien"))
        ).scalar_one()
    [provider] = media.ev.full.identity.capabilities.system_providers(TECHNICAL_SHEETS)
    sheet = await provider.provider.sheet(Principal(user_id=people["sam"]), alien)
    assert plex.asked == [("m1", "movie")]
    [server] = sheet["servers"]  # the broken one left out
    assert server["added_at"] == ADDED.isoformat()
    [file] = server["files"]
    assert file["path"] == "/m/Alien.mkv" and file["duration_s"] == 7000.0
    assert file["streams"][0] | {} == {**file["streams"][0], "language": "Français", "channels": "5.1"}
    assert sheet["acquisition"] is None  # no download manager follows it
