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
                },
                {  # #47: a live TV programme — a guide entry, not a library item
                    "sessionKey": "8",
                    "ratingKey": "9001",
                    "live": 1,
                    "type": "episode",
                    "grandparentTitle": "Caméra café (Espagne)",
                    "title": "Episode 3",
                    "viewOffset": 0,
                    "duration": 1_800_000,
                    "Media": [{"channelCallSign": "5COF", "channelTitle": "5 Coffee TV"}],
                    "User": {"id": "2", "title": "thibaut"},
                    "Player": {"state": "playing"},
                },
            ]
        }
    },
}

RADARR: Routes = {
    "/api/v3/system/status": {"appName": "Radarr", "version": "5.14.0", "instanceName": "Radarr"},
    "/api/v3/calendar": lambda request: CALENDAR_RADARR,
    "/api/v3/queue": lambda request: {
        "records": [
            {
                "id": 31,
                "movie": {"title": "Dune: Part Three", "tmdbId": 1170608},
                "size": 1000,
                "sizeleft": 250,
                "status": "downloading",
                "trackedDownloadState": "downloading",
                "estimatedCompletionTime": "2026-10-05T12:00:00Z",
            },
            {
                "id": 32,
                "movie": {"title": "Heat", "tmdbId": 949},
                "size": 10,
                "sizeleft": 0,
                "status": "completed",
                "trackedDownloadState": "importPending",
            },
        ]
    },
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
    "/api/v3/calendar": lambda request: CALENDAR_SONARR,
    "/api/v3/queue": lambda request: {
        "records": [
            {
                "id": 41,
                "series": {"title": "Andor", "tvdbId": 393189},
                "episode": {"title": "Premiere", "seasonNumber": 3, "episodeNumber": 1},
                "size": 0,
                "status": "queued",
            }
        ]
    },
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


def _tautulli(request: httpx.Request) -> Any:
    if request.url.params.get("apikey") != "tautulli-secret-key":
        return {"response": {"result": "error", "message": "Invalid apikey", "data": {}}}
    cmd = request.url.params.get("cmd")
    if cmd == "get_tautulli_info":
        return {"response": {"result": "success", "data": {"tautulli_version": "v2.15.0"}}}
    if cmd == "get_users":
        return {
            "response": {
                "result": "success",
                "data": [
                    {"user_id": 0, "username": "Local"},
                    {"user_id": 1234, "username": "jo", "friendly_name": "Jo", "email": "jo@home.lan"},
                ],
            }
        }
    if cmd == "get_history":
        rows = [
            {
                "id": 1,
                "started": 1_700_000_000,
                "stopped": 1_700_009_000,
                "play_duration": 8_400,
                "percent_complete": 96,
                "user_id": 1234,
                "media_type": "movie",
                "rating_key": 101,
                "title": "Dune",
                "year": 2021,
                "guid": "plex://movie/5d77",
                "guids": ["tmdb://438631", "imdb://tt1160419"],
                "player": "Living room TV",
                "platform": "Android",
            },
            {
                "id": 2,
                "started": 1_700_100_000,
                "stopped": 1_700_102_000,
                "play_duration": 2_000,
                "percent_complete": 40,
                "user_id": 1234,
                "media_type": "episode",
                "rating_key": 202,
                "title": "Kassa",
                "grandparent_title": "Andor",
            },
            {
                "id": 3,
                "started": 1_700_200_000,
                "play_duration": 3_600,
                "user_id": 1234,
                "media_type": "episode",
                "live": 1,
                "title": "Journal",
                "grandparent_title": "Le 20h",
            },
            {"id": 4, "started": None, "user_id": 1234, "media_type": "movie"},
        ]
        start = int(request.url.params.get("start", "0"))
        return {"response": {"result": "success", "data": {"data": rows[start:]}}}
    return {"response": {"result": "error", "message": "Unknown command"}}


TAUTULLI: Routes = {"/api/v2": _tautulli}

GRIMMORY_BOOKS = [
    {
        "id": 1,
        "libraryId": 1,
        "primaryFile": {"bookType": "EPUB"},
        "lastReadTime": "2024-03-01T10:00:00Z",
        "metadata": {
            "title": "Dune",
            "authors": ["Frank Herbert"],
            "categories": ["Science Fiction"],
            "publishedDate": "1965-08-01",
            "isbn13": "9780441172719",
            "pageCount": 688,
            "seriesName": "Dune",
            "seriesNumber": 1,
        },
    },
    {
        "id": 2,
        "libraryId": 2,
        "primaryFile": {"bookType": "AUDIOBOOK"},
        "metadata": {
            "title": "Project Hail Mary",
            "authors": [{"name": "Andy Weir"}],
            "narrator": "Ray Porter",
        },
    },
    {"id": 3, "metadata": {}},
]


def _grimmory_sessions(request: httpx.Request) -> Any:
    book = request.url.path.rsplit("/", 1)[-1]
    if book != "1" or request.url.params.get("page", "0") != "0":
        return []
    return [
        {
            "id": 77,
            "bookId": 1,
            "bookType": "EPUB",
            "startTime": "2024-03-01T09:00:00Z",
            "endTime": "2024-03-01T10:00:00Z",
            "durationSeconds": 3600,
            "startProgress": 10.0,
            "endProgress": 25.0,
        }
    ]


GRIMMORY: Routes = {
    "/api/v1/auth/login": {"accessToken": "grimmory-access", "refreshToken": "r", "expires": 3600},
    "/api/v1/healthcheck": {"status": "UP"},
    "/api/v1/libraries": [{"id": 1, "name": "Books"}, {"id": 2, "name": "Audio"}],
    "/api/v1/books": GRIMMORY_BOOKS,
    "/api/v1/users": [{"id": 9, "username": "portal", "name": "Portal", "email": "p@home.lan"}],
    "/api/v1/reading-sessions/book/1": _grimmory_sessions,
    "/api/v1/reading-sessions/book/2": _grimmory_sessions,
    "/api/v1/reading-sessions/book/3": _grimmory_sessions,
}

TMDB_MOVIE = {
    "id": 438631,
    "imdb_id": "tt1160419",
    "title": "Dune",
    "original_title": "Dune",
    "tagline": "Beyond fear, destiny awaits.",
    "overview": "Paul Atreides…",
    "genres": [{"id": 878, "name": "Science-Fiction"}],
    "release_date": "2021-09-15",
    "runtime": 156,
    "budget": 165_000_000,
    "revenue": 402_027_830,
    "vote_average": 7.8,
    "vote_count": 12000,
    "status": "Released",
    "production_countries": [{"iso_3166_1": "US"}],
    "spoken_languages": [{"english_name": "English"}],
    "production_companies": [{"name": "Legendary Pictures"}],
    "belongs_to_collection": {"id": 726871, "name": "Dune - Saga", "poster_path": "/coll.jpg"},
    "poster_path": "/poster.jpg",
    "backdrop_path": "/backdrop.jpg",
    "credits": {
        "cast": [
            {"id": 1190668, "name": "Timothée Chalamet", "character": "Paul", "profile_path": "/tc.jpg"}
        ],
        "crew": [{"id": 137427, "name": "Denis Villeneuve", "job": "Director", "department": "Directing"}],
    },
    "keywords": {"keywords": [{"name": "desert"}]},
    "release_dates": {
        "results": [{"iso_3166_1": "FR", "release_dates": [{"certification": "Tous publics"}]}]
    },
}

TMDB: Routes = {
    "/3/configuration": {"images": {"secure_base_url": "https://image.tmdb.org/t/p/"}},
    "/3/movie/438631": TMDB_MOVIE,
    "/3/find/tt1160419": {"movie_results": [{"id": 438631}], "tv_results": []},
    "/3/search/movie": {"results": [{"id": 438631}]},
}

CALENDAR_RADARR = [
    {
        "id": 3,
        "title": "Dune: Part Three",
        "tmdbId": 1170608,
        "inCinemas": "2026-12-18T00:00:00Z",
        "digitalRelease": "2027-02-01T00:00:00Z",
        "hasFile": False,
    }
]
CALENDAR_SONARR = [
    {
        "id": 40,
        "seriesId": 5,
        "seasonNumber": 3,
        "episodeNumber": 1,
        "title": "Premiere",
        "airDateUtc": "2026-11-02T02:00:00Z",
        "hasFile": False,
        "series": {"title": "Andor", "tvdbId": 393189},
    }
]

# 027: Authentik — the single sign-on; users and groups (a POST answers as Authentik does)
AUTHENTIK = {
    "/api/v3/core/users/me/": {"user": {"pk": 1, "username": "portal"}},
    "/api/v3/core/users/": lambda request: (
        {"pk": 42, "username": "ursula"}
        if request.method == "POST"
        else {
            "pagination": {"next": 0},
            "results": [{"pk": 7, "username": "ada", "email": "ada@example.org"}]
            if request.url.params.get("email") in (None, "ada@example.org")
            else [],
        }
    ),
    "/api/v3/core/groups/": {"pagination": {"next": 0}, "results": [{"pk": "g-uuid", "name": "romm-users"}]},
    "/api/v3/core/groups/g-uuid/add_user/": {},
    "/api/v3/core/groups/g-uuid/remove_user/": {},
    "/api/v3/core/users/42/recovery/": {"link": "https://sso.example.org/recovery/abc"},
}

# #57: Maintainerr — a film collection deleting after 30 days, a show collection without a delay, an
# inactive collection (skipped); the status is a JSON document encoded as a string
MAINTAINERR: Routes = {
    "/api/app/status": '{"status": 1, "version": "2.19.0", "commitTag": "v2.19.0", "updateAvailable": false}',
    "/api/collections": [
        {"id": 1, "title": "Old films", "isActive": True, "deleteAfterDays": 30, "type": "movie"},
        {"id": 2, "title": "Abandoned shows", "isActive": True, "deleteAfterDays": None, "type": "show"},
        {"id": 3, "title": "Paused", "isActive": False, "deleteAfterDays": 7, "type": "movie"},
    ],
    "/api/collections/media/": lambda request: {
        "1": [
            {"mediaServerId": "101", "tmdbId": 949, "addDate": "2026-10-01T10:00:00.000Z", "sizeBytes": 4000},
            {"plexId": 102, "addDate": "2026-10-02T10:00:00.000Z"},  # Maintainerr 1.x
            {"mediaServerId": "103"},  # no date: skipped
        ],
        "2": [{"mediaServerId": "201", "tvdbId": 77, "addDate": "2026-09-01T00:00:00.000Z"}],
        "3": [{"mediaServerId": "301", "addDate": "2026-09-01T00:00:00.000Z"}],
    }.get(request.url.params.get("collectionId", ""), []),
    "/api/rules/exclusion": {"code": 1, "result": "Success", "message": "Success"},
}

# issue 169: Ollama — a chat model in memory, another on disk (an older server: no « capabilities »), an
# embedding model
OLLAMA: Routes = {
    "/api/version": {"version": "0.34.3"},
    "/api/tags": {
        "models": [
            {
                "name": "qwen3:8b",
                "size": 5225388164,
                "details": {"family": "qwen3", "parameter_size": "8.2B", "quantization_level": "Q4_K_M"},
                "capabilities": ["completion", "tools", "thinking"],
            },
            {
                "name": "mistral:7b",
                "size": 4372824384,
                "details": {"family": "llama", "parameter_size": "7.2B"},
            },
            {
                "name": "nomic-embed-text:latest",
                "size": 274302450,
                "details": {"family": "nomic-bert", "families": ["nomic-bert"]},
            },
            {"size": 1},  # no name: skipped
        ]
    },
    "/api/ps": {"models": [{"name": "qwen3:8b", "size": 6295440588, "size_vram": 6295440588}]},
}

SECRETS = {
    "jellyfin": {"api_key": "jf-secret-key"},
    "plex": {"token": "plex-secret-token"},
    "radarr": {"api_key": "radarr-secret-key"},
    "sonarr": {"api_key": "sonarr-secret-key"},
    "seerr": {"api_key": "seerr-secret-key"},
    "romm": {"password": "romm-secret-pass"},
    "tautulli": {"api_key": "tautulli-secret-key"},
    "grimmory": {"password": "grimmory-secret-pass"},
    "tmdb": {"api_key": "tmdb-secret-key"},
    "authentik": {"api_token": "authentik-secret-token"},
    "maintainerr": {},
    "ollama": {},
}
ROUTES = {
    "jellyfin": JELLYFIN,
    "plex": PLEX,
    "radarr": RADARR,
    "sonarr": SONARR,
    "seerr": SEERR,
    "romm": ROMM,
    "tautulli": TAUTULLI,
    "grimmory": GRIMMORY,
    "tmdb": TMDB,
    "authentik": AUTHENTIK,
    "maintainerr": MAINTAINERR,
    "ollama": OLLAMA,
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
        if request.url.path.endswith(
            ("/thumb", "/Images/Primary", "/poster.jpg", ".png", "/cover", "/audiobook-cover")
        ):
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
    user = {"username": "portal"} if key in ("romm", "grimmory") else {}
    settings = {"base_url": base, **user, **(config or {})}
    return ServiceHandle(service_id=uuid4(), name=key, config=settings, secrets=secrets, http=http)


Factory = Callable[[], Any]
