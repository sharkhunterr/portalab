"""``radarr`` and ``sonarr`` connectors: the *arr download managers (API v3, Sonarr v3/v4, Radarr v3+).

* ``media.library`` (sync): what the manager tracks — Radarr movies, Sonarr series and their seasons —
  marked ``available`` when the files are on disk, with TMDB/IMDb/TVDB ids so Media merges them with what a
  media server reports.
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
from portalab.capabilities.media import CALENDAR, LIBRARY, SourceRelease
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import HttpConnector, _Probe, binding, parse_time, safe_id


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
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None

    def releases(self, item: Mapping[str, Any], start: datetime, end: datetime) -> list[SourceRelease]:
        return []


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
        movies = await self.get_json(ctx.service, "/api/v3/movie")
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
        series_list = await self.get_json(ctx.service, "/api/v3/series")
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
