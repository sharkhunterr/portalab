"""#3, #4 — the Seerr connector: request limits read and written (an account's settings written back whole,
the defaults merged), a request's seasons, 4K and the bypass of a bought unit (``ignoreQuota``, else the
API key's own account when the service refuses), quota and duplicate refusals told apart; the titles one
can ask for (search, shelves, details with seasons asked for or there)."""

import json
from typing import Any
from uuid import uuid4

import httpx
import pytest

from portalab.capabilities.connector_http import ConnectorHttpClient
from portalab.capabilities.connector_sdk import ServiceHandle
from portalab.capabilities.media import (
    REQUEST_DISCOVERY,
    REQUEST_QUOTAS,
    REQUESTS,
    QuotaLimits,
    SourceDuplicate,
    SourceQuotaExceeded,
)
from portalab.connectors.seerr import SeerrConnector

SETTINGS = {
    "username": "zoe",
    "email": "zoe@home.lan",
    "locale": "fr",
    "movieQuotaLimit": 3,
    "movieQuotaDays": 7,
    "tvQuotaLimit": None,
    "tvQuotaDays": None,
    "globalMovieQuotaLimit": 5,
    "globalMovieQuotaDays": 7,
    "globalTvQuotaLimit": 2,
    "globalTvQuotaDays": 14,
}


class Seerr:
    """A tiny Seerr: answers by method and path, records what was sent."""

    def __init__(self) -> None:
        self.seen: list[httpx.Request] = []
        self.quota_full = False  # refuse requests that do not bypass the quota
        self.bypass_known = True  # Seerr 3 (``ignoreQuota``); False: Overseerr
        self.duplicate = False

    def respond(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        path, method = request.url.path, request.method
        body = json.loads(request.content) if request.content else {}
        if path == "/api/v1/request" and method == "POST":
            if self.duplicate:
                return httpx.Response(409, json={"message": "Request for this media already exists."})
            bypass = self.bypass_known and body.get("ignoreQuota")
            if self.quota_full and "userId" in body and not bypass:
                return httpx.Response(403, json={"message": "Movie Quota exceeded."})
            return httpx.Response(201, json={"id": 77, "status": 1, "media": {"status": 2}})
        if path == "/api/v1/user/7/quota":
            return httpx.Response(
                200,
                json={
                    "movie": {"days": 7, "limit": 3, "used": 3, "remaining": 0, "restricted": True},
                    "tv": {"days": 14, "limit": 0, "used": 0, "restricted": False},
                },
            )
        if path == "/api/v1/user/7/settings/main":
            return httpx.Response(200, json=SETTINGS if method == "GET" else {"username": "zoe"})
        if path == "/api/v1/user":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "displayName": "Owner", "permissions": 2},
                        {"id": 7, "displayName": "Zoé", "permissions": 32, "movieQuotaLimit": 3},
                    ]
                },
            )
        if path == "/api/v1/settings/main":
            return httpx.Response(
                200,
                json={"defaultQuotas": {"movie": {"quotaLimit": 5, "quotaDays": 7}, "tv": {}}},
            )
        if path in ("/api/v1/search", "/api/v1/discover/trending"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "mediaType": "person", "name": "Someone"},
                        {
                            "id": 438631,
                            "mediaType": "movie",
                            "title": "Dune",
                            "releaseDate": "2021-09-15",
                            "posterPath": "/dune.jpg",
                            "voteAverage": 7.8,
                            "mediaInfo": {"status": 5},
                        },
                        {"id": 83867, "mediaType": "tv", "name": "Andor", "firstAirDate": "2022-09-21"},
                    ]
                },
            )
        if path == "/api/v1/tv/83867":
            return httpx.Response(
                200,
                json={
                    "id": 83867,
                    "name": "Andor",
                    "firstAirDate": "2022-09-21",
                    "genres": [{"name": "Science-fiction"}],
                    "episodeRunTime": [45],
                    "externalIds": {"imdbId": "tt9253284", "tvdbId": 393189},
                    "productionCompanies": [{"name": "Lucasfilm"}],
                    "networks": [{"name": "Disney+"}],
                    "originCountry": ["US"],
                    "numberOfSeasons": 3,
                    "numberOfEpisodes": 36,
                    "createdBy": [{"name": "Tony Gilroy"}],
                    "contentRatings": {"results": [{"iso_3166_1": "FR", "rating": "12"}]},
                    "keywords": [{"name": "rebellion"}],
                    "credits": {
                        "cast": [{"name": "Diego Luna", "character": "Cassian", "profilePath": "/d.jpg"}]
                    },
                    "relatedVideos": [
                        {"site": "YouTube", "type": "Teaser", "key": "teaser"},
                        {"site": "YouTube", "type": "Trailer", "key": "trailer"},
                    ],
                    "seasons": [
                        {"seasonNumber": 0, "name": "Specials"},
                        {"seasonNumber": 1, "name": "Season 1", "episodeCount": 12},
                        {"seasonNumber": 2, "name": "Season 2", "episodeCount": 12},
                        {"seasonNumber": 3, "name": "Season 3", "episodeCount": 12},
                    ],
                    "mediaInfo": {
                        "status": 4,
                        "seasons": [{"seasonNumber": 1, "status": 5}],
                        "requests": [{"status": 2, "seasons": [{"seasonNumber": 2}]}],
                    },
                },
            )
        if path == "/api/v1/settings/sonarr":
            return httpx.Response(200, json=[{"id": 0, "is4k": False}, {"id": 1, "is4k": True}])
        if path == "/api/v1/settings/radarr":
            return httpx.Response(200, json=[{"id": 0, "is4k": False}])
        return httpx.Response(404, json={"message": "not found"})


def handle(seerr: Seerr) -> ServiceHandle:
    base = f"http://seerr-{uuid4().hex[:6]}.lan:5055"
    secrets = {"api_key": "seerr-secret-key"}
    http = ConnectorHttpClient(
        base, timeout_seconds=1, retries=0, secrets=secrets, transport=httpx.MockTransport(seerr.respond)
    )
    return ServiceHandle(
        service_id=uuid4(), name="seerr", config={"base_url": base}, secrets=secrets, http=http
    )


def sent(seerr: Seerr, path: str) -> list[dict[str, Any]]:
    return [
        json.loads(r.content) for r in seerr.seen if r.url.path == path and r.method == "POST" and r.content
    ]


async def test_quotas_read_and_written() -> None:
    seerr = Seerr()
    quotas = SeerrConnector().provider(REQUEST_QUOTAS, handle(seerr))
    quota = await quotas.quota("7")
    assert (quota.movie.limit, quota.movie.remaining, quota.movie.restricted) == (3, 0, True)
    assert (quota.tv.limit, quota.tv.restricted, quota.tv.remaining) == (None, False, None)  # 0: no limit

    accounts = {a.external_id: a for a in await quotas.accounts()}
    assert accounts["1"].exempt and accounts["1"].quota is None  # the owner has no quota
    assert accounts["7"].own.movie_limit == 3 and accounts["7"].quota is not None

    await quotas.set_limits("7", QuotaLimits(movie_limit=5, movie_days=7, tv_limit=None, tv_days=None))
    [written] = sent(seerr, "/api/v1/user/7/settings/main")
    # written back whole (Seerr takes the name and the e-mail from the same body), the defaults left out
    assert written["username"] == "zoe" and written["email"] == "zoe@home.lan" and written["locale"] == "fr"
    assert (written["movieQuotaLimit"], written["tvQuotaLimit"]) == (5, None)
    assert not any(key.startswith("global") for key in written)

    assert (await quotas.defaults()).movie_limit == 5
    await quotas.set_defaults(QuotaLimits(movie_limit=4, movie_days=7))
    [merged] = sent(seerr, "/api/v1/settings/main")
    assert merged == {
        "defaultQuotas": {"movie": {"quotaLimit": 4, "quotaDays": 7}, "tv": {"quotaLimit": 0, "quotaDays": 0}}
    }


async def test_request_options_and_refusals() -> None:
    seerr = Seerr()
    requests = SeerrConnector().provider(REQUESTS, handle(seerr))
    await requests.submit(
        {"tmdb": "83867", "tvdb": "393189"}, "series", "Andor", "7", seasons=[2, 3, 2], is4k=True
    )
    assert sent(seerr, "/api/v1/request")[-1] == {
        "mediaType": "tv",
        "mediaId": 83867,
        "seasons": [2, 3],
        "tvdbId": 393189,
        "is4k": True,
        "userId": 7,
    }

    seerr.quota_full = True
    with pytest.raises(SourceQuotaExceeded):
        await requests.submit({"tmdb": "438631"}, "movie", "Dune", "7")
    # a bought unit: Seerr 3 takes ``ignoreQuota`` for the member…
    made = await requests.submit({"tmdb": "438631"}, "movie", "Dune", "7", bypass_quota=True)
    assert made.external_request_id == "77" and sent(seerr, "/api/v1/request")[-1]["ignoreQuota"] is True
    # …Overseerr does not: the API key's own account asks instead
    seerr.bypass_known = False
    await requests.submit({"tmdb": "438631"}, "movie", "Dune", "7", bypass_quota=True)
    assert "userId" not in sent(seerr, "/api/v1/request")[-1]

    seerr.duplicate = True
    with pytest.raises(SourceDuplicate):
        await requests.submit({"tmdb": "438631"}, "movie", "Dune", "7")


async def test_titles_to_ask_for() -> None:
    seerr = Seerr()
    discovery = SeerrConnector().provider(REQUEST_DISCOVERY, handle(seerr))
    found = await discovery.search("dune", "fr")
    assert [(t.kind, t.title, t.year, t.status) for t in found] == [
        ("movie", "Dune", 2021, "available"),
        ("series", "Andor", 2022, "unknown"),
    ]  # people left out
    assert found[0].poster == "/dune.jpg" and found[0].rating == 7.8
    assert [t.title for t in await discovery.shelf("trending", "fr")] == ["Dune", "Andor"]
    # the discovery lists take no language (Seerr would filter by the titles' original language)
    assert all(
        "language" not in r.url.params for r in seerr.seen if r.url.path.startswith("/api/v1/discover")
    )
    assert await discovery.shelf("nonsense", "fr") == []
    andor = await discovery.details("series", "83867", "fr")
    assert andor is not None
    assert [(s.number, s.status) for s in andor.seasons] == [(1, "available"), (2, "pending"), (3, "unknown")]
    assert andor.trailer == "trailer" and andor.cast[0][0] == "Diego Luna" and andor.runtime == 45
    assert andor.ids == {"tmdb": "83867", "imdb": "tt9253284", "tvdb": "393189"}
    assert andor.four_k is True  # a 4K Sonarr takes series
    # the enriched details, in the library's own shape: studios, networks, countries, rating, creators…
    facts = andor.metadata
    assert (facts["studios"], facts["networks"], facts["countries"]) == (["Lucasfilm"], ["Disney+"], ["US"])
    assert (facts["seasons"], facts["episodes"], facts["certification"]) == (3, 36, "12")
    assert ("Tony Gilroy", "creator") in [(p["name"], p["department"]) for p in facts["people"]]
    assert facts["release_date"] == "2022-09-21" and facts["keywords"] == ["rebellion"]
