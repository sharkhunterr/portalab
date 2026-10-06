"""``radarr`` and ``sonarr`` connectors: the *arr download managers (API v3, Sonarr v3/v4, Radarr v3+).

* ``media.library`` (sync): what the manager tracks — Radarr movies, Sonarr series and their seasons —
  marked ``available`` when the files are on disk, with TMDB/IMDb/TVDB ids so Media merges them with what a
  media server reports.
* ``media.downloads`` (027): the download queue (``/api/v3/queue``) — progress, state and expected time.
* ``media.acquisition`` (027): where the manager stands on one title — followed, monitored, released,
  searchable, files, quality, its history (grabbed, failed, imported) — and an on-demand interactive search
  of the indexers (``/api/v3/release``), for the request journey of a title's page.
* ``media.calendar`` (027): upcoming releases — Radarr's cinema, digital and physical release dates,
  Sonarr's episode air dates (``/api/v3/calendar``).
* ``service.health_probe``: an authenticated ``/api/v3/system/status`` round trip.

Authentication uses the API key of *Settings → General*, sent as ``X-Api-Key``. Posters are served by
the manager itself (``/api/v3/mediacover/<id>/poster.jpg``), never fetched from the internet.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from typing import Any, ClassVar

from portalab.capabilities.connector_sdk import (
    CapabilityBinding,
    ServiceHandle,
    SourceRecord,
    SyncContext,
    SyncProgress,
)
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import (
    ACQUISITION,
    CALENDAR,
    DOWNLOADS,
    LIBRARY,
    AcquisitionEvent,
    FoundRelease,
    SourceAcquisition,
    SourceDownload,
    SourceRelease,
)
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import (
    LIBRARY_LISTING_BYTES,
    HttpConnector,
    _Probe,
    binding,
    parse_time,
    safe_id,
)


def _overview(item: Mapping[str, Any]) -> str | None:
    return (item.get("overview") or "")[:5000] or None


def _has_poster(item: Mapping[str, Any]) -> bool:
    return any(image.get("coverType") == "poster" for image in item.get("images") or [])


class _ArrConnector(HttpConnector):
    app: ClassVar[str]
    category = "downloads"
    provides: Sequence[CapabilityBinding] = (
        binding(LIBRARY, syncable=True),
        binding(CALENDAR),
        binding(DOWNLOADS),
        binding(ACQUISITION),
        binding(HEALTH_PROBE),
    )
    status_path = "/api/v3/system/status"
    public_path = None

    def describe(self, status: Any) -> str:
        if not isinstance(status, Mapping) or "version" not in status:
            raise InvalidPayload("not an *arr system status")
        app = str(status.get("appName") or self.app)
        if app.lower() != self.app.lower():
            raise InvalidPayload(f"this is {app}, not {self.app}")
        return f"{status.get('instanceName') or app} ({app} {status['version']})"

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == LIBRARY:
            return _Covers(self, service)
        if capability == CALENDAR:
            return _Calendar(self, service)
        if capability == DOWNLOADS:
            return _Queue(self, service)
        if capability == ACQUISITION:
            return _Acquisition(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None

    def releases(self, item: Mapping[str, Any], start: datetime, end: datetime) -> list[SourceRelease]:
        return []

    def download(self, record: Mapping[str, Any]) -> SourceDownload | None:
        return None

    # --- 027: one title's acquisition ---------------------------------------------------------------
    async def find(
        self, service: ServiceHandle, kind: str, ids: Mapping[str, str]
    ) -> Mapping[str, Any] | None:
        return None

    def acquisition(
        self, service: ServiceHandle, item: Mapping[str, Any], history: Sequence[Mapping[str, Any]]
    ) -> SourceAcquisition:
        raise NotImplementedError

    async def history(self, service: ServiceHandle, item: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        return []

    async def releases_found(self, service: ServiceHandle, item: Mapping[str, Any]) -> Any:
        return []


def queue_attention(record: Mapping[str, Any]) -> str | None:
    """Why a download waits (027): an import someone must confirm, a failed one, a client warning."""
    tracked = str(record.get("trackedDownloadState") or "").lower()
    status = str(record.get("trackedDownloadStatus") or "").lower()
    if tracked == "importblocked":
        return "import_blocked"
    if tracked in ("failedpending", "failed"):
        return "failed"
    if tracked == "importpending":
        return "import_pending"
    if status in ("warning", "error"):
        return "warning"
    return None


def queue_messages(record: Mapping[str, Any]) -> tuple[str, ...]:
    out: list[str] = []
    if record.get("errorMessage"):
        out.append(str(record["errorMessage"])[:300])
    for message in record.get("statusMessages") or []:
        if isinstance(message, Mapping):
            for line in message.get("messages") or []:
                if isinstance(line, str) and line.strip():
                    out.append(line.strip()[:300])
    return tuple(dict.fromkeys(out))[:5]


def queue_extra(record: Mapping[str, Any]) -> dict[str, Any]:
    """What every *arr queue record tells about the transfer behind it (027)."""
    size = record.get("size")
    return {
        "download_id": str(record["downloadId"]).lower()[:80] if record.get("downloadId") else None,
        "client": str(record["downloadClient"])[:100] if record.get("downloadClient") else None,
        "release": str(record["title"])[:300] if record.get("title") else None,
        "attention": queue_attention(record),
        "messages": queue_messages(record),
        "size": int(size) if isinstance(size, int | float) else None,
    }


EVENTS = {
    "grabbed": "grabbed",
    "downloadfailed": "failed",
    "downloadfolderimported": "imported",
    "episodefileimported": "imported",
    "moviefileimported": "imported",
    "moviefiledeleted": "deleted",
    "episodefiledeleted": "deleted",
    "moviefilerenamed": "renamed",
    "episodefilerenamed": "renamed",
    "downloadignored": "ignored",
    "downloadimportfailed": "failed",
}


def acquisition_events(records: Sequence[Mapping[str, Any]]) -> tuple[AcquisitionEvent, ...]:
    out = []
    for record in records:
        event = EVENTS.get(str(record.get("eventType") or "").lower())
        at = parse_time(record.get("date"))
        if event is None or at is None:
            continue
        data = record.get("data") if isinstance(record.get("data"), Mapping) else {}
        detail = (data or {}).get("message") or (data or {}).get("reason")
        out.append(
            AcquisitionEvent(
                event=event,
                at=at,
                release=str(record.get("sourceTitle"))[:300] if record.get("sourceTitle") else None,
                client=str((data or {}).get("downloadClient"))[:100]
                if (data or {}).get("downloadClient")
                else None,
                detail=str(detail)[:300] if detail else None,
            )
        )
    return tuple(sorted(out, key=lambda e: e.at, reverse=True)[:12])


def found_release(record: Mapping[str, Any]) -> FoundRelease | None:
    if not record.get("title"):
        return None
    quality = (
        (record.get("quality") or {}).get("quality") if isinstance(record.get("quality"), Mapping) else None
    )
    size = record.get("size")
    seeders = record.get("seeders")
    return FoundRelease(
        title=str(record["title"])[:300],
        indexer=str(record["indexer"])[:100] if record.get("indexer") else None,
        size=int(size) if isinstance(size, int | float) else None,
        quality=str(quality.get("name"))[:60]
        if isinstance(quality, Mapping) and quality.get("name")
        else None,
        seeders=int(seeders) if isinstance(seeders, int) else None,
        approved=bool(record.get("approved")),
        rejections=tuple(str(r)[:200] for r in (record.get("rejections") or []) if r)[:5],
    )


def page_link(service: ServiceHandle, path: str) -> str | None:
    base = str(service.config.get("base_url") or "").rstrip("/")
    return f"{base}{path}" if base else None


def queue_state(record: Mapping[str, Any]) -> str:
    tracked = str(record.get("trackedDownloadState") or "").lower()
    status = str(record.get("status") or "").lower()
    if tracked in ("importpending", "importing", "imported"):
        return "importing"
    if str(record.get("trackedDownloadStatus") or "").lower() in ("warning", "error"):
        return "warning"
    if status in ("paused", "failed", "queued", "delay", "downloadclientunavailable"):
        return {"delay": "queued", "downloadclientunavailable": "warning"}.get(status, status)
    return "downloading"


def queue_progress(record: Mapping[str, Any]) -> float:
    size, left = record.get("size"), record.get("sizeleft")
    if isinstance(size, int | float) and size > 0 and isinstance(left, int | float):
        return round(max(0.0, min(1.0, 1 - left / size)), 4)
    return 0.0


class _Queue:
    def __init__(self, connector: _ArrConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def queue(self) -> Sequence[SourceDownload]:
        page = await self.connector.get_json(
            self.service,
            "/api/v3/queue",
            pageSize=200,
            includeMovie="true",
            includeSeries="true",
            includeEpisode="true",
        )
        records = page.get("records") if isinstance(page, Mapping) else page
        if not isinstance(records, list):
            raise InvalidPayload("unexpected /queue payload")
        out = []
        for record in records:
            if isinstance(record, Mapping):
                item = self.connector.download(record)
                if item is not None:
                    out.append(item)
        return out


class _Acquisition:
    def __init__(self, connector: _ArrConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def status(self, kind: str, ids: Mapping[str, str]) -> SourceAcquisition | None:
        item = await self.connector.find(self.service, kind, ids)
        if item is None:
            return None
        return self.connector.acquisition(
            self.service, item, await self.connector.history(self.service, item)
        )

    async def search(self, kind: str, ids: Mapping[str, str]) -> Sequence[FoundRelease]:
        item = await self.connector.find(self.service, kind, ids)
        if item is None:
            return []
        records = await self.connector.releases_found(self.service, item)
        if not isinstance(records, list):
            raise InvalidPayload("unexpected /release payload")
        found = [f for r in records if isinstance(r, Mapping) and (f := found_release(r)) is not None]
        return sorted(found, key=lambda f: (not f.approved, -(f.seeders or 0)))[:30]


class _Calendar:
    def __init__(self, connector: _ArrConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def upcoming(self, start: datetime, end: datetime) -> Sequence[SourceRelease]:
        items = await self.connector.get_json(
            self.service,
            "/api/v3/calendar",
            start=start.isoformat(),
            end=end.isoformat(),
            unmonitored="false",
            includeSeries="true",
        )
        if not isinstance(items, list):
            raise InvalidPayload("unexpected /calendar payload")
        out: list[SourceRelease] = []
        for item in items:
            if isinstance(item, Mapping):
                out.extend(self.connector.releases(item, start, end))
        return sorted(out, key=lambda r: r.release_at)


class _Covers:
    def __init__(self, connector: _ArrConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def fetch_image(self, ref: str) -> bytes:
        item_id = safe_id(ref.split(":")[-1])
        return await self.connector.get_bytes(self.service, f"/api/v3/mediacover/{item_id}/poster.jpg")


class RadarrConnector(_ArrConnector):
    key = "radarr"
    name = "Radarr"
    app = "Radarr"
    description = "The films Radarr follows, and whether they are downloaded."
    icon = "film"

    def download(self, record: Mapping[str, Any]) -> SourceDownload | None:
        nested = record.get("movie")
        movie: Mapping[str, Any] = nested if isinstance(nested, Mapping) else {}
        if record.get("id") is None:
            return None
        ids = {"tmdb": str(movie["tmdbId"]) if movie.get("tmdbId") else "", "imdb": movie.get("imdbId") or ""}
        return SourceDownload(
            external_id=f"queue:{safe_id(record['id'])}",
            kind="movie",
            title=str(movie.get("title") or record.get("title") or "?")[:500],
            status=queue_state(record),
            progress=queue_progress(record),
            ids={k: v for k, v in ids.items() if v},
            eta=parse_time(record.get("estimatedCompletionTime")),
            **queue_extra(record),
        )

    async def find(
        self, service: ServiceHandle, kind: str, ids: Mapping[str, str]
    ) -> Mapping[str, Any] | None:
        if kind not in ("movie", "film"):
            return None
        if ids.get("tmdb"):
            found = await self.get_json(service, "/api/v3/movie", tmdbId=ids["tmdb"])
            if isinstance(found, list) and found and isinstance(found[0], Mapping):
                return found[0]
        if ids.get("imdb"):
            found = await self.get_json(service, "/api/v3/movie/lookup", term=f"imdb:{ids['imdb']}")
            for item in found if isinstance(found, list) else []:
                if isinstance(item, Mapping) and item.get("id"):
                    return item
        return None

    async def history(self, service: ServiceHandle, item: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        found = await self.get_json(service, "/api/v3/history/movie", movieId=safe_id(item["id"]))
        return [r for r in found if isinstance(r, Mapping)] if isinstance(found, list) else []

    async def releases_found(self, service: ServiceHandle, item: Mapping[str, Any]) -> Any:
        return await self.request(service, "GET", "/api/v3/release", params={"movieId": safe_id(item["id"])})

    def acquisition(
        self, service: ServiceHandle, item: Mapping[str, Any], history: Sequence[Mapping[str, Any]]
    ) -> SourceAcquisition:
        file = item.get("movieFile") if isinstance(item.get("movieFile"), Mapping) else {}
        quality = ((file or {}).get("quality") or {}).get("quality") or {}
        releases = {
            name: at
            for name, field in (
                ("cinema", "inCinemas"),
                ("digital", "digitalRelease"),
                ("physical", "physicalRelease"),
            )
            if (at := parse_time(item.get(field))) is not None
        }
        size = (file or {}).get("size") or item.get("sizeOnDisk")
        slug = item.get("titleSlug") or item.get("tmdbId")
        return SourceAcquisition(
            service_name=service.name,
            tracked=True,
            monitored=bool(item.get("monitored")),
            has_file=bool(item.get("hasFile")),
            status=str(item.get("status") or "") or None,
            searchable=item.get("isAvailable") if isinstance(item.get("isAvailable"), bool) else None,
            added_at=parse_time(item.get("added")),
            releases=releases,
            files=1 if item.get("hasFile") else 0,
            expected=1,
            size=int(size) if isinstance(size, int | float) and size else None,
            quality=str(quality.get("name"))[:60]
            if isinstance(quality, Mapping) and quality.get("name")
            else None,
            link=page_link(service, f"/movie/{slug}") if slug else None,
            history=acquisition_events(history),
        )

    def releases(self, item: Mapping[str, Any], start: datetime, end: datetime) -> list[SourceRelease]:
        if not item.get("title") or item.get("id") is None:
            return []
        ids = {"tmdb": str(item["tmdbId"]) if item.get("tmdbId") else "", "imdb": item.get("imdbId") or ""}
        out = []
        for field, release_type in (
            ("inCinemas", "cinema"),
            ("digitalRelease", "digital"),
            ("physicalRelease", "physical"),
        ):
            at = parse_time(item.get(field))
            if at is not None and start <= at <= end:
                out.append(
                    SourceRelease(
                        external_id=f"movie:{safe_id(item['id'])}",
                        kind="movie",
                        title=str(item["title"])[:500],
                        release_at=at,
                        release_type=release_type,
                        ids={k: v for k, v in ids.items() if v},
                        available=bool(item.get("hasFile")),
                        overview=_overview(item),
                    )
                )
        return out

    async def sync(
        self, ctx: SyncContext, cursor: Mapping[str, Any] | None
    ) -> AsyncIterator[SourceRecord | SyncProgress]:
        movies = await self.request(ctx.service, "GET", "/api/v3/movie", max_bytes=LIBRARY_LISTING_BYTES)
        if not isinstance(movies, list):
            raise InvalidPayload("unexpected /movie payload")
        yield SyncProgress(cursor={}, total=len(movies))
        for movie in movies:
            if not movie.get("title"):
                continue
            movie_id = safe_id(movie.get("id"))
            ids = {
                "tmdb": str(movie["tmdbId"]) if movie.get("tmdbId") else None,
                "imdb": movie.get("imdbId"),
            }
            payload = {
                "title": str(movie["title"])[:500],
                "original_title": movie.get("originalTitle"),
                "ids": {k: v for k, v in ids.items() if v},
                "year": movie.get("year") or None,
                "overview": _overview(movie),
                "genres": list(movie.get("genres") or [])[:30],
                "duration_s": float(movie["runtime"]) * 60 if movie.get("runtime") else None,
                "image": f"movie:{movie_id}" if _has_poster(movie) else None,
                "available": bool(movie.get("hasFile")),
            }
            yield self.record(
                ctx.service, f"movie:{movie_id}", "movie", payload, parse_time(movie.get("added"))
            )
        yield SyncProgress(cursor={"items": len(movies)})


class SonarrConnector(_ArrConnector):
    key = "sonarr"
    name = "Sonarr"
    app = "Sonarr"
    description = "The series Sonarr follows, season by season, and what is downloaded."
    icon = "film"

    def download(self, record: Mapping[str, Any]) -> SourceDownload | None:
        nested = record.get("series")
        series: Mapping[str, Any] = nested if isinstance(nested, Mapping) else {}
        episode_doc = record.get("episode")
        episode: Mapping[str, Any] = episode_doc if isinstance(episode_doc, Mapping) else {}
        if record.get("id") is None:
            return None
        ids = {
            "tvdb": str(series["tvdbId"]) if series.get("tvdbId") else "",
            "tmdb": str(series["tmdbId"]) if series.get("tmdbId") else "",
            "imdb": series.get("imdbId") or "",
        }
        return SourceDownload(
            external_id=f"queue:{safe_id(record['id'])}",
            kind="episode",
            title=str(episode.get("title") or record.get("title") or "?")[:500],
            status=queue_state(record),
            progress=queue_progress(record),
            ids={k: v for k, v in ids.items() if v},
            parent_title=str(series.get("title"))[:500] if series.get("title") else None,
            season=episode.get("seasonNumber"),
            episode=episode.get("episodeNumber"),
            eta=parse_time(record.get("estimatedCompletionTime")),
            **queue_extra(record),
        )

    async def find(
        self, service: ServiceHandle, kind: str, ids: Mapping[str, str]
    ) -> Mapping[str, Any] | None:
        if kind not in ("series", "season", "episode", "tv"):
            return None
        if ids.get("tvdb"):
            found = await self.get_json(service, "/api/v3/series", tvdbId=ids["tvdb"])
            if isinstance(found, list) and found and isinstance(found[0], Mapping):
                return found[0]
        everything = await self.request(service, "GET", "/api/v3/series", max_bytes=LIBRARY_LISTING_BYTES)
        for item in everything if isinstance(everything, list) else []:
            if not isinstance(item, Mapping):
                continue
            if (ids.get("tmdb") and str(item.get("tmdbId")) == ids["tmdb"]) or (
                ids.get("imdb") and item.get("imdbId") == ids["imdb"]
            ):
                return item
        return None

    async def history(self, service: ServiceHandle, item: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        found = await self.get_json(service, "/api/v3/history/series", seriesId=safe_id(item["id"]))
        return [r for r in found if isinstance(r, Mapping)] if isinstance(found, list) else []

    async def releases_found(self, service: ServiceHandle, item: Mapping[str, Any]) -> Any:
        seasons: list[int] = [
            int(s["seasonNumber"])
            for s in item.get("seasons") or []
            if isinstance(s, Mapping) and isinstance(s.get("seasonNumber"), int) and s["seasonNumber"] > 0
        ]
        params: dict[str, Any] = {"seriesId": safe_id(item["id"])}
        if seasons:
            params["seasonNumber"] = max(seasons)  # the latest season: what a request usually waits for
        return await self.request(service, "GET", "/api/v3/release", params=params)

    def acquisition(
        self, service: ServiceHandle, item: Mapping[str, Any], history: Sequence[Mapping[str, Any]]
    ) -> SourceAcquisition:
        stats = item.get("statistics") if isinstance(item.get("statistics"), Mapping) else {}
        files = int((stats or {}).get("episodeFileCount") or 0)
        releases = {
            name: at
            for name, field in (("first_aired", "firstAired"), ("next_airing", "nextAiring"))
            if (at := parse_time(item.get(field))) is not None
        }
        size = (stats or {}).get("sizeOnDisk")
        return SourceAcquisition(
            service_name=service.name,
            tracked=True,
            monitored=bool(item.get("monitored")),
            has_file=files > 0,
            status=str(item.get("status") or "") or None,
            added_at=parse_time(item.get("added")),
            releases=releases,
            files=files,
            expected=int((stats or {}).get("episodeCount") or 0),
            size=int(size) if isinstance(size, int | float) and size else None,
            link=page_link(service, f"/series/{item['titleSlug']}") if item.get("titleSlug") else None,
            history=acquisition_events(history),
        )

    def releases(self, item: Mapping[str, Any], start: datetime, end: datetime) -> list[SourceRelease]:
        at = parse_time(item.get("airDateUtc"))
        nested = item.get("series")
        series: Mapping[str, Any] = nested if isinstance(nested, Mapping) else {}
        if at is None or item.get("id") is None or not (start <= at <= end):
            return []
        ids = {
            "tvdb": str(series["tvdbId"]) if series.get("tvdbId") else "",
            "tmdb": str(series["tmdbId"]) if series.get("tmdbId") else "",
            "imdb": series.get("imdbId") or "",
        }
        return [
            SourceRelease(
                external_id=f"episode:{safe_id(item['id'])}",
                kind="episode",
                title=str(item.get("title") or "?")[:500],
                release_at=at,
                release_type="air",
                parent_title=str(series.get("title"))[:500] if series.get("title") else None,
                season=item.get("seasonNumber"),
                episode=item.get("episodeNumber"),
                ids={k: v for k, v in ids.items() if v},
                available=bool(item.get("hasFile")),
                overview=_overview(item),
            )
        ]

    async def sync(
        self, ctx: SyncContext, cursor: Mapping[str, Any] | None
    ) -> AsyncIterator[SourceRecord | SyncProgress]:
        series_list = await self.request(
            ctx.service, "GET", "/api/v3/series", max_bytes=LIBRARY_LISTING_BYTES
        )
        if not isinstance(series_list, list):
            raise InvalidPayload("unexpected /series payload")
        seasons = sum(
            1
            for series in series_list
            for season in (series.get("seasons") or [])
            if isinstance(season.get("seasonNumber"), int) and season["seasonNumber"] >= 0
        )
        yield SyncProgress(cursor={}, total=len(series_list) + seasons)
        for series in series_list:
            if not series.get("title"):
                continue
            series_id = safe_id(series.get("id"))
            stats = series.get("statistics") or {}
            ids = {
                "tvdb": str(series["tvdbId"]) if series.get("tvdbId") else None,
                "tmdb": str(series["tmdbId"]) if series.get("tmdbId") else None,
                "imdb": series.get("imdbId"),
            }
            observed = parse_time(series.get("added"))
            yield self.record(
                ctx.service,
                f"series:{series_id}",
                "series",
                {
                    "title": str(series["title"])[:500],
                    "ids": {k: v for k, v in ids.items() if v},
                    "year": series.get("year") or None,
                    "overview": _overview(series),
                    "genres": list(series.get("genres") or [])[:30],
                    "image": f"series:{series_id}" if _has_poster(series) else None,
                    "available": int(stats.get("episodeFileCount") or 0) > 0,
                },
                observed,
            )
            for season in series.get("seasons") or []:
                number = season.get("seasonNumber")
                if not isinstance(number, int) or number < 0:
                    continue
                season_stats = season.get("statistics") or {}
                yield self.record(
                    ctx.service,
                    f"season:{series_id}:{number}",
                    "season",
                    {
                        "title": f"{series['title']} — Season {number}"[:500],
                        "parent": f"series:{series_id}",
                        "position": number,
                        "available": int(season_stats.get("episodeFileCount") or 0) > 0,
                    },
                    observed,
                )
        yield SyncProgress(cursor={"items": len(series_list)})
