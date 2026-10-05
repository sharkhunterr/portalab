"""027 — the statistics and metadata connectors: Tautulli and Plex histories (one ``plex`` family, Tautulli
wins), Grimmory books, audiobooks and reading sessions, TMDB enrichment, Radarr/Sonarr release calendars."""

from datetime import UTC, datetime

import pytest

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.media import ACCOUNTS, ACTIVITY_HISTORY, CALENDAR, DOWNLOADS, LIBRARY, METADATA
from portalab.capabilities.results import InvalidPayload, ProviderAuthError
from portalab.connectors.arr import RadarrConnector, SonarrConnector
from portalab.connectors.grimmory import GrimmoryConnector
from portalab.connectors.plex import map_history
from portalab.connectors.tautulli import TautulliConnector
from portalab.connectors.tmdb import TmdbConnector, image_ref
from tests.contract.connectors.builtin_fixtures import handle_for


class _Ctx:
    def __init__(self, service: object) -> None:
        self.service, self.capability, self.kind = service, LIBRARY, "manual"


async def test_tautulli_history_and_accounts() -> None:
    connector = TautulliConnector()
    handle = handle_for("tautulli")
    page = await connector.provider(ACTIVITY_HISTORY, handle).history(since=None, cursor=None)
    assert [a.kind for a in page.items] == ["movie", "episode", "live"]  # the row without a time is skipped
    dune, kassa, _live = page.items
    assert dune.ids == {"tmdb": "438631", "imdb": "tt1160419"} and dune.watched_s == 8400
    assert dune.progress == pytest.approx(0.96) and dune.device == "Living room TV"
    assert dune.family == "plex" and dune.priority == 20 and dune.external_user_id == "1234"
    assert kassa.parent_title == "Andor" and page.cursor is None
    later = await connector.provider(ACTIVITY_HISTORY, handle).history(
        since=datetime.fromtimestamp(1_700_050_000, UTC), cursor=None
    )
    assert [a.ref for a in later.items] == ["2", "3"]
    accounts = await connector.provider(ACCOUNTS, handle).list_accounts()
    assert [(a.external_id, a.display_name, a.email) for a in accounts] == [("1234", "Jo", "jo@home.lan")]


async def test_tautulli_refused_key_in_the_body_is_an_auth_error() -> None:
    handle = handle_for("tautulli")
    object.__setattr__(handle, "secrets", {"api_key": "wrong"})
    with pytest.raises(ProviderAuthError):
        await TautulliConnector().command(handle, "get_tautulli_info")


def test_plex_history_rows() -> None:
    row = {
        "historyKey": "/status/sessions/history/991",
        "ratingKey": "202",
        "title": "Kassa",
        "grandparentTitle": "Andor",
        "type": "episode",
        "viewedAt": 1_700_100_000,
        "accountID": 1,
        "duration": 2_400_000,
    }
    activity = map_history(row)
    assert activity is not None and activity.ref == "991" and activity.parent_title == "Andor"
    assert activity.family == "plex" and activity.priority == 10 and activity.watched_s == 2400
    assert map_history({**row, "type": "photo"}) is None and map_history({**row, "accountID": None}) is None


async def test_grimmory_books_sessions_and_accounts() -> None:
    connector = GrimmoryConnector()
    handle = handle_for("grimmory")
    found = [r async for r in connector.sync(_Ctx(handle), None) if isinstance(r, SourceRecord)]
    assert [(r.external_id, r.kind) for r in found] == [("1", "book"), ("2", "audiobook")]
    dune = found[0].payload
    assert dune["ids"] == {"isbn": "9780441172719"} and dune["people"] == ["Frank Herbert"]
    assert dune["year"] == 1965 and dune["pages"] == 688 and dune["genres"] == ["Science Fiction"]
    assert found[1].payload["people"] == ["Andy Weir", "Ray Porter"]
    page = await connector.provider(ACTIVITY_HISTORY, handle).history(since=None, cursor=None)
    (session,) = page.items
    assert session.external_user_id == "9" and session.kind == "book" and session.watched_s == 3600
    assert session.progress == pytest.approx(0.25) and session.parent_title == "Frank Herbert"
    assert (await connector.provider(LIBRARY, handle).fetch_image("1")).startswith(b"\x89PNG")
    with pytest.raises(InvalidPayload):
        await connector.provider(LIBRARY, handle).fetch_image("../../etc")
    accounts = await connector.provider(ACCOUNTS, handle).list_accounts()
    assert [(a.external_id, a.username) for a in accounts] == [("9", "portal")]


async def test_tmdb_metadata() -> None:
    provider = TmdbConnector().provider(METADATA, handle_for("tmdb"))
    record = await provider.lookup("movie", {"imdb": "tt1160419"}, "Dune", 2021, "fr")
    assert record is not None and record.ids["tmdb"] == "438631" and record.budget == 165_000_000
    assert record.revenue == 402_027_830 and record.genres == ["Science-Fiction"]
    assert record.collection and record.collection["name"] == "Dune - Saga"
    assert record.backdrop == "/backdrop.jpg" and record.certification == "Tous publics"
    cast = [p for p in record.people if p.department == "cast"]
    assert cast[0].name == "Timothée Chalamet" and cast[0].image == "/tc.jpg"
    assert any(p.role == "Director" for p in record.people)
    assert await provider.lookup("book", {}, "Dune", None, "fr") is None
    assert image_ref("https://evil.example/x.jpg") is None and image_ref("/../x.jpg") is None
    with pytest.raises(InvalidPayload):
        await provider.fetch_image("/poster.jpg", "w9999")


async def test_release_calendars() -> None:
    start, end = datetime(2026, 10, 1, tzinfo=UTC), datetime(2027, 3, 1, tzinfo=UTC)
    movies = await RadarrConnector().provider(CALENDAR, handle_for("radarr")).upcoming(start, end)
    assert [(r.release_type, r.release_at.month) for r in movies] == [("cinema", 12), ("digital", 2)]
    episodes = await SonarrConnector().provider(CALENDAR, handle_for("sonarr")).upcoming(start, end)
    (premiere,) = episodes
    assert premiere.parent_title == "Andor" and (premiere.season, premiere.episode) == (3, 1)
    assert premiere.ids == {"tvdb": "393189"}


def test_continuous_connectors_have_nothing_to_sync_now() -> None:
    """« Sync now » runs library syncs only: history and metadata services are read continuously."""
    syncable = {
        c.key: [b.spec.name for b in c.provides if b.syncable]
        for c in (TautulliConnector(), GrimmoryConnector(), TmdbConnector(), RadarrConnector())
    }
    assert syncable["tautulli"] == [] and syncable["tmdb"] == []
    assert syncable["grimmory"] == [LIBRARY] and syncable["radarr"] == [LIBRARY]


async def test_download_queues() -> None:
    movies = await RadarrConnector().provider(DOWNLOADS, handle_for("radarr")).queue()
    assert [(d.title, d.status, d.progress) for d in movies] == [
        ("Dune: Part Three", "downloading", 0.75),
        ("Heat", "importing", 1.0),
    ]
    assert movies[0].ids == {"tmdb": "1170608"} and movies[0].eta is not None
    (episode,) = await SonarrConnector().provider(DOWNLOADS, handle_for("sonarr")).queue()
    assert (episode.parent_title, episode.season, episode.episode, episode.status) == (
        "Andor",
        3,
        1,
        "queued",
    )
