"""Fake HTTP servers for the shipped connectors: canned answers of each API, served through an
``httpx.MockTransport`` so the real ``ConnectorHttpClient`` (headers, redirects, size cap) is exercised."""

import asyncio
from collections.abc import Callable, Mapping
from typing import Any
from uuid import uuid4

import httpx

from portalab.capabilities.connector_http import ConnectorHttpClient
from portalab.capabilities.connector_sdk import ServiceHandle

Scenario = str
Routes = Mapping[str, Any]  # path -> JSON body, or a callable(request) -> JSON body

JELLYFIN: Routes = {
    "/System/Info": {"ServerName": "Home", "Version": "10.10.7", "Id": "abc"},
    "/System/Info/Public": {"ServerName": "Home", "Version": "10.10.7", "Id": "abc"},
    "/Items": {
        "Items": [
            {
                "Id": "m1",
                "Name": "Dune",
                "Type": "Movie",
                "ProductionYear": 2021,
                "ProviderIds": {"Tmdb": "438631", "Imdb": "tt1160419"},
                "RunTimeTicks": 93_600_000_000,
                "ImageTags": {"Primary": "x"},
                "Genres": ["Science Fiction"],
                "DateCreated": "2024-01-02T03:04:05.1234567Z",
            },
            {"Id": "s1", "Name": "Andor", "Type": "Series", "ProviderIds": {"Tvdb": "393189"}},
            {"Id": "se1", "Name": "Season 1", "Type": "Season", "SeriesId": "s1", "IndexNumber": 1},
            {
                "Id": "e1",
                "Name": "Kassa",
                "Type": "Episode",
                "SeriesId": "s1",
                "SeasonId": "se1",
                "IndexNumber": 1,
            },
            {"Id": "x1", "Name": "Folder", "Type": "Folder"},
        ],
        "TotalRecordCount": 5,
    },
    "/Sessions": [
        {
            "Id": "sess",
            "UserId": "u1",
            "DeviceName": "TV",
            "NowPlayingItem": {"Id": "m1", "Name": "Dune", "Type": "Movie", "RunTimeTicks": 93_600_000_000},
            "PlayState": {"PositionTicks": 600_000_000, "IsPaused": False},
        },
        {"Id": "idle", "UserId": "u2"},
    ],
}


def _plex_all(request: httpx.Request) -> Any:
    start = int(request.headers.get("X-Plex-Container-Start", "0"))
    kind = request.url.params.get("type")
    items = {
        "1": [
            {
                "ratingKey": "101",
                "title": "Dune",
                "type": "movie",
                "year": 2021,
                "duration": 9_360_000,
                "thumb": "/library/metadata/101/thumb/1",
                "Guid": [{"id": "tmdb://438631"}],
                "addedAt": 1_700_000_000,
            },
            {"ratingKey": "102", "title": "Arrival", "type": "movie", "year": 2016},
            {"ratingKey": "103", "title": "Heat", "type": "movie", "year": 1995},
        ],
    }.get(kind or "", [])
    page = items[start : start + 2]  # pages of two to exercise paging
    return {"MediaContainer": {"size": len(page), "totalSize": len(items), "Metadata": page}}


PLEX: Routes = {
    "/": {"MediaContainer": {"friendlyName": "Home", "version": "1.41.0"}},
    "/identity": {"MediaContainer": {"machineIdentifier": "abc", "version": "1.41.0"}},
    "/library/sections": {"MediaContainer": {"Directory": [{"key": "1", "type": "movie", "title": "Films"}]}},
    "/library/sections/1/all": _plex_all,
    "/status/sessions": {
        "MediaContainer": {
            "Metadata": [
                {
                    "sessionKey": "7",
                    "ratingKey": "101",
                    "title": "Dune",
                    "type": "movie",
                    "viewOffset": 60_000,
                    "duration": 9_360_000,
                    "User": {"id": "1", "title": "jo"},
                    "Player": {"state": "paused"},
                }
            ]
        }
    },
}

RADARR: Routes = {
    "/api/v3/system/status": {"appName": "Radarr", "version": "5.14.0", "instanceName": "Radarr"},
    "/api/v3/movie": [
        {
            "id": 1,
            "title": "Dune",
            "year": 2021,
            "tmdbId": 438631,
            "imdbId": "tt1160419",
            "hasFile": True,
            "runtime": 156,
            "images": [{"coverType": "poster"}],
            "added": "2024-01-01T00:00:00Z",
        },
        {"id": 2, "title": "Heat", "year": 1995, "tmdbId": 949, "hasFile": False},
    ],
}

SONARR: Routes = {
    "/api/v3/system/status": {"appName": "Sonarr", "version": "4.0.10"},
    "/api/v3/series": [
        {
            "id": 5,
            "title": "Andor",
            "year": 2022,
            "tvdbId": 393189,
            "statistics": {"episodeFileCount": 3},
            "seasons": [
                {"seasonNumber": 0, "statistics": {"episodeFileCount": 0}},
                {"seasonNumber": 1, "statistics": {"episodeFileCount": 3}},
            ],
        },
    ],
}


def _seerr_requests(request: httpx.Request) -> Any:
    results = [
        {
            "id": 11,
            "status": 2,
            "type": "movie",
            "media": {"mediaType": "movie", "tmdbId": 438631, "status": 5},
            "requestedBy": {"id": 3},
            "updatedAt": "2024-02-02T00:00:00.000Z",
        },
        {
            "id": 12,
            "status": 1,
            "type": "tv",
            "media": {"mediaType": "tv", "tmdbId": 83867, "tvdbId": 393189, "status": 2},
        },
    ]
    skip = int(request.url.params.get("skip", "0"))
    return {"pageInfo": {"pages": 1, "results": len(results)}, "results": results[skip : skip + 100]}


SEERR: Routes = {
    "/api/v1/settings/main": {"applicationTitle": "Requests"},
    "/api/v1/status": {"version": "2.5.0", "commitTag": "v2.5.0"},
    "/api/v1/request": _seerr_requests,
    "/api/v1/movie/438631": {"title": "Dune"},
    "/api/v1/tv/83867": {"name": "Andor"},
}

ROMM: Routes = {
    "/api/users/me": {"username": "portal"},
    "/api/heartbeat": {"SYSTEM": {"VERSION": "4.0.0"}},
    "/api/roms": {
        "items": [
            {
                "id": 1,
                "name": "Super Metroid",
                "igdb_id": 1103,
                "platform_name": "SNES",
                "first_release_date": 763_084_800_000,
                "path_cover_large": "roms/2/1/cover/big.png?ts=1",
            },
            {"id": 2, "fs_name_no_ext": "Unknown Game", "platform_display_name": "GBA"},
        ],
        "total": 2,
    },
}

SECRETS = {
    "jellyfin": {"api_key": "jf-secret-key"},
    "plex": {"token": "plex-secret-token"},
    "radarr": {"api_key": "radarr-secret-key"},
    "sonarr": {"api_key": "sonarr-secret-key"},
    "seerr": {"api_key": "seerr-secret-key"},
    "romm": {"password": "romm-secret-pass"},
}
ROUTES = {
    "jellyfin": JELLYFIN,
    "plex": PLEX,
    "radarr": RADARR,
    "sonarr": SONARR,
    "seerr": SEERR,
    "romm": ROMM,
}


def transport(
    routes: Routes, scenario: Scenario, seen: list[httpx.Request] | None = None
) -> httpx.MockTransport:
    async def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if scenario == "down":
            raise httpx.ConnectError("connection refused", request=request)
        if scenario == "slow":
            await asyncio.sleep(5)
        if scenario == "auth_error":
            return httpx.Response(401, json={"error": "unauthorized"})
        if scenario == "garbage":
            return httpx.Response(
                200, content=b"<html>login page</html>", headers={"content-type": "text/html"}
            )
        if request.url.path.endswith(("/thumb", "/Images/Primary", "/poster.jpg", ".png")):
            return httpx.Response(200, content=b"\x89PNG-image")
        body = routes.get(request.url.path)
        if body is None:
            return httpx.Response(404, json={"error": "not found"})
        value = body(request) if callable(body) else body
        return httpx.Response(200, json=value)

    return httpx.MockTransport(handle)


def handle_for(
    key: str,
    scenario: Scenario = "ok",
    *,
    config: Mapping[str, Any] | None = None,
    seen: list[httpx.Request] | None = None,
    routes: Routes | None = None,
) -> ServiceHandle:
    base = f"http://{key}-{uuid4().hex[:6]}.lan:8080"
    secrets = SECRETS[key]
    http = ConnectorHttpClient(
        base,
        timeout_seconds=1,
        retries=0,
        secrets=secrets,
        transport=transport(routes or ROUTES[key], scenario, seen),
    )
    settings = {"base_url": base, **({"username": "portal"} if key == "romm" else {}), **(config or {})}
    return ServiceHandle(service_id=uuid4(), name=key, config=settings, secrets=secrets, http=http)


Factory = Callable[[], Any]
