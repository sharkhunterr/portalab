"""Issue 171 — ``media.status``: the assistant finds a title in the catalog, as the member it acts for, and
reads its journey — requested by them, approved, released, searched by Radarr, downloading (the torrent
client says it is stalled) — with the step it waits at, its page as source; an unknown title says so; the
catalog's own media tools are the assistant's too."""

import httpx
from fastapi import FastAPI

from portalab.capabilities.ai import AIToolRegistry
from portalab.capabilities.media import ACQUISITION, DOWNLOAD_CLIENTS, DOWNLOADS, SourceDownload
from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock
from portalab.modules.media.models import UserLink
from tests.integration.media.conftest import MediaHarness, users
from tests.integration.media.test_journey import HASH, _Client, _Queue, _Radarr
from tests.integration.media.test_request_insights import _request


async def test_media_status_tells_the_journey(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe")
    library, seerr = media.service(1), media.service(8, "seerr")
    media.library(library)
    await media.module.library.upsert(
        [
            library_record("h", title="Heat", ids={"tmdb": "949"}, available=False),
            library_record("h2", title="Heat Wave", ids={"tmdb": "950"}, available=True),
        ],
        library,
    )
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
    await media.module.request_sink.upsert([_request(clock, "2", "Heat", "949", "processing", "7")], seerr)
    queue = _Queue()
    queue.items = [
        SourceDownload(
            "q1", "movie", "Heat", "downloading", 0.4, ids={"tmdb": "949"}, download_id=HASH, client="qBit"
        )
    ]
    media.provide(ACQUISITION, media.service(4, "radarr"), _Radarr(clock))
    media.provide(DOWNLOADS, media.service(4, "radarr"), queue)
    media.provide(DOWNLOAD_CLIENTS, media.service(6, "qbittorrent"), _Client())

    registry = AIToolRegistry()
    media.module.ai_tools.register(registry)
    names = {t.name for t in registry.all()}
    assert names == {"media.search_catalog", "media.my_history", "media.recommendations", "media.status"}
    status = registry.get("media.status")
    assert status is not None
    zoe = Principal(channel="ai", acting_for=people["zoe"])
    answer = await status.handler(zoe, {"title": "heat"})
    data = answer.data
    assert answer.state == "ok" and data["found"] and data["title"] == "Heat" and data["available"] is False
    assert data["requested"] and data["other_matches"] == ["Heat Wave"]
    keys = [s["key"] for s in data["steps"]]
    assert keys[:5] == ["requested", "approved", "released", "searched", "downloading"]
    downloading = next(s for s in data["steps"] if s["key"] == "downloading")
    assert downloading["status"] in ("blocked", "current", "waiting")
    assert data["stuck_at"] == "downloading" or data["under_way"] == "downloading"
    assert answer.sources[0].url.startswith("/media/") and answer.sources[0].title == "Heat"
    assert "link" not in (data["download_manager"] or {})  # no service internals for the assistant

    heat_id = answer.sources[0].url.removeprefix("/media/")
    by_id = await status.handler(zoe, {"id": heat_id})  # the page the member is on names it
    assert by_id.data["title"] == "Heat" and by_id.data["steps"] == data["steps"]
    assert (await status.handler(zoe, {"id": "not-an-id"})).data["found"] is False
    assert "leaving_library" not in data  # no cleanup tool: nothing said
    assert data["my_viewing"] == {"watched": False, "plays": 0}  # zoe never played it

    class _Cleanup:  # Maintainerr put it on its deletion list
        def configured(self) -> bool:
            return True

        async def status(self, object_id: object, user: object) -> dict[str, object]:
            return {
                "leaving": [{"collection": "Films demandés non vus"}],
                "delete_at": "2026-11-01T00:00:00+00:00",
                "saved": None,
            }

    media.module.ai_tools.cleanup = _Cleanup()
    leaving = (await status.handler(zoe, {"id": heat_id})).data["leaving_library"]
    assert leaving == {
        "deletion_list": True,
        "rules": ["Films demandés non vus"],
        "delete_at": "2026-11-01T00:00:00+00:00",
        "saved": False,
        "can_be_rescued": True,
    }
    unknown = await status.handler(zoe, {"title": "Some film nobody asked for"})
    assert unknown.data["found"] is False and "requested" in unknown.data["hint"]
    history = registry.get("media.my_history")
    assert history is not None and "kind" in history.params_schema["properties"]  # « my last film »
    found = await registry.get("media.search_catalog").handler(zoe, {"q": "heat"})  # type: ignore[union-attr]
    assert {i["title"] for i in found.data["items"]} == {"Heat", "Heat Wave"}
