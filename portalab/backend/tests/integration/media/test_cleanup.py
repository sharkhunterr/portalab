"""#57 — the cleanup tool's deletions (Maintainerr): a title page says when it goes (a film by the
server's id, a series through its leaving seasons); a member spends a rescue bought in the shop to save
it — once per purchase credited, one spent per title, for everyone; the widget lists the first to go;
rescues are exported and erased with the member."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.media import CLEANUP, LeavingItem
from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.modules.media.models import MediaObject, RescueLedger
from portalab.modules.media.participant import MediaParticipant
from portalab.modules.media.providers.insight_widgets import LeavingWidget
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

GOES = datetime(2026, 11, 1, tzinfo=UTC)


class _Maintainerr:
    def __init__(self) -> None:
        self.kept: list[str] = []
        self.items = [
            LeavingItem("h1", "movie", "Old films", datetime(2026, 10, 1, tzinfo=UTC), GOES, {"tmdb": "949"}),
            LeavingItem("se1", "season", "Abandoned", datetime(2026, 10, 2, tzinfo=UTC), None),
            LeavingItem("zz", "movie", "Old films", datetime(2026, 10, 1, tzinfo=UTC), GOES),  # unknown
        ]

    async def leaving(self) -> list[LeavingItem]:
        return [i for i in self.items if i.external_id not in self.kept]

    async def keep(self, external_id: str) -> None:
        self.kept.append(external_id)


async def _ids(media: MediaHarness) -> dict[str, UUID]:
    async with media.database.session() as session:
        return {o.title: o.id for o in (await session.execute(select(MediaObject))).scalars()}


async def test_leaving_and_rescue(app: FastAPI, client: httpx.AsyncClient, media: MediaHarness) -> None:
    people = await users(app, media, "zoe", "max")
    library = media.service(1, "plex")
    media.library(library)
    await media.module.library.upsert(
        [
            library_record("h1", title="Heat", ids={"tmdb": "949"}),
            library_record("s1", kind="series", title="Lost"),
            library_record("se1", kind="season", title="Season 1", parent="s1", position=1),
        ],
        library,
    )
    tool = _Maintainerr()
    media.provide(CLEANUP, media.service(9, "maintainerr"), tool)
    ids = await _ids(media)
    await login(client, "zoe")

    heat = (await client.get(f"/api/v1/media/{ids['Heat']}/leaving")).json()
    assert heat["configured"] is True and heat["delete_at"] == GOES.isoformat()
    assert heat["leaving"][0]["collection"] == "Old films" and heat["saved"] is None and heat["credits"] == 0
    lost = (await client.get(f"/api/v1/media/{ids['Lost']}/leaving")).json()
    assert [i["kind"] for i in lost["leaving"]] == ["season"] and lost["delete_at"] is None

    widget = LeavingWidget(media.database, media.module.cleanup)
    cards = (await widget.load(Principal(user_id=people["zoe"]), {}, LocaleContext(locale="en"))).data or {}
    assert [c["title"] for c in cards["items"]] == ["Heat", "Season 1"]  # dated first

    # no rescue yet: refused, nothing excluded
    refused = await client.post(f"/api/v1/media/{ids['Heat']}/leaving/keep")
    assert refused.status_code == 409 and refused.json()["code"] == "media.no_rescue" and tool.kept == []

    # the shop credits rescues once per purchase
    assert await media.module.cleanup.grant(people["zoe"], 2, "marketplace:p1") == 2
    assert await media.module.cleanup.grant(people["zoe"], 2, "marketplace:p1") == 2
    saved = (await client.post(f"/api/v1/media/{ids['Lost']}/leaving/keep")).json()
    assert tool.kept == ["se1"] and saved["leaving"] == [] and saved["credits"] == 1
    assert saved["saved"]["me"] is True
    # saved for everyone: another member sees it saved, not by them; the season is saved too
    await login(client, "max")
    seen: dict[str, Any] = (await client.get(f"/api/v1/media/{ids['Lost']}/leaving")).json()
    assert seen["saved"]["me"] is False and seen["credits"] == 0
    season = (await client.get(f"/api/v1/media/{ids['Season 1']}/leaving")).json()
    assert season["leaving"] == [] and season["saved"] is not None
    gone = await client.post(f"/api/v1/media/{ids['Season 1']}/leaving/keep")
    assert gone.status_code == 404

    participant = MediaParticipant(media.database)
    exported = [r for r in await participant.export(people["zoe"]) if r.category == "media.rescue"]
    assert {r.data["reason"] for r in exported} == {"purchase", "rescue"}
    await participant.erase(people["zoe"], "final")
    async with media.database.session() as session:
        left = (
            await session.execute(select(RescueLedger).where(RescueLedger.user_id == people["zoe"]))
        ).all()
    assert left == []
