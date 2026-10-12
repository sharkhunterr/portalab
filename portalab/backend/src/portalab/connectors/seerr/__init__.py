"""``seerr`` connector: Overseerr, Jellyseerr and their forks (API v1).

* ``request.service`` (sync + live): every request with its state, synchronised so Media shows members
  where their requests stand; members' new requests are submitted here (``POST /api/v1/request``) — on
  their behalf (``userId``), the seasons of a series and 4K when asked (#4). A request paid with a unit
  bought in the shop bypasses the account's quota (``ignoreQuota``, Seerr 3); on a service without it
  (Overseerr), it is made by the API key's account — the portal keeps who asked.
* ``request.quotas`` (#3): each account's limits (films and series, per number of days), what it used
  and has left (``/user/{id}/quota``), set by the portal (``/user/{id}/settings/main``, read then
  written back whole) — and the service's defaults (``/settings/main``, merged).
* ``request.discovery`` (#4): the titles one can ask for — search, trending, popular and upcoming films
  and series, a title's details (cast, trailer, seasons and which are there or asked for).
* ``service.health_probe``: an authenticated request listing.

Authentication uses the API key of *Settings → General*, sent as ``X-Api-Key``.
"""

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import replace
from typing import Any

from portalab.capabilities.connector_http import ConnectorHttpError
from portalab.capabilities.connector_sdk import (
    CapabilityBinding,
    ServiceHandle,
    SourceRecord,
    SyncContext,
    SyncProgress,
)
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import (
    ACCOUNTS,
    REQUEST_DISCOVERY,
    REQUEST_QUOTAS,
    REQUESTS,
    QuotaAccount,
    QuotaLimits,
    QuotaWindow,
    RequestableDetails,
    RequestableSeason,
    RequestableStatus,
    RequestableTitle,
    RequestState,
    ServiceAccount,
    SourceDuplicate,
    SourceQuota,
    SourceQuotaExceeded,
    SourceRefused,
    SourceRequest,
)
from portalab.capabilities.results import InvalidPayload, ProviderAuthError
from portalab.connectors.http_base import HttpConnector, _Probe, binding, parse_time, safe_id

PAGE = 100
# request.status: 1 pending, 2 approved, 3 declined (4 failed, 5 completed in recent versions);
# media.status: 1 unknown, 2 pending, 3 processing, 4 partially available, 5 available (6 blacklisted).
REQUEST_STATES: dict[int, RequestState] = {
    1: "pending",
    2: "approved",
    3: "declined",
    4: "failed",
    5: "available",
}
MEDIA_STATES: dict[int, RequestState] = {3: "processing", 4: "available", 5: "available"}
KINDS = {"movie": "movie", "tv": "series"}


# media.status as a title's state for someone about to ask for it
TITLE_STATES: dict[int, RequestableStatus] = {2: "pending", 3: "processing", 4: "partial", 5: "available"}
MANAGE_USERS, ADMIN = 8, 2
SHELVES = {
    "trending": "/api/v1/discover/trending",
    "popular_movies": "/api/v1/discover/movies",
    "popular_series": "/api/v1/discover/tv",
    "upcoming_movies": "/api/v1/discover/movies/upcoming",
    "upcoming_series": "/api/v1/discover/tv/upcoming",
}


def _limit(value: Any) -> int | None:
    return int(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def map_window(document: Any) -> QuotaWindow:
    """One kind of ``/user/{id}/quota``: ``{days, limit, used, remaining, restricted}`` (no limit: 0/None)."""
    doc = document if isinstance(document, Mapping) else {}
    limit = _limit(doc.get("limit")) or None
    return QuotaWindow(
        limit=limit,
        days=_limit(doc.get("days")) or None,
        used=_limit(doc.get("used")) or 0,
        remaining=_limit(doc.get("remaining")) if limit else None,
        restricted=bool(doc.get("restricted")) and bool(limit),
    )


def map_title(result: Mapping[str, Any]) -> RequestableTitle | None:
    """A search or discovery result (films and series only; people are left out)."""
    media_type = result.get("mediaType") or ("tv" if result.get("firstAirDate") is not None else "movie")
    if media_type not in ("movie", "tv") or result.get("id") is None:
        return None
    title = result.get("title") or result.get("name")
    if not title:
        return None
    date = str(result.get("releaseDate") or result.get("firstAirDate") or "")[:10] or None
    info = result.get("mediaInfo") or {}
    rating = result.get("voteAverage")
    return RequestableTitle(
        tmdb_id=str(result["id"]),
        kind="movie" if media_type == "movie" else "series",
        title=str(title)[:500],
        year=int(date[:4]) if date and date[:4].isdigit() else None,
        overview=(str(result["overview"])[:2000] if result.get("overview") else None),
        poster=result.get("posterPath") or None,
        backdrop=result.get("backdropPath") or None,
        rating=float(rating) if isinstance(rating, int | float) and rating else None,
        status=TITLE_STATES.get(int(info.get("status") or 1), "unknown"),
        release_date=date,
    )


CREW_JOBS = ("Director", "Screenplay", "Writer", "Original Music Composer", "Producer")


def _names_of(values: Any, key: str = "name") -> list[str]:
    return [str(v[key]) for v in values or [] if isinstance(v, Mapping) and v.get(key)]


def _certification(document: Mapping[str, Any], country: str) -> str | None:
    """The age rating in the member's country (else the US one): a film's release dates, a series'
    content ratings."""
    for wanted in (country, "US"):
        for entry in (document.get("releases") or {}).get("results") or []:
            if isinstance(entry, Mapping) and entry.get("iso_3166_1") == wanted:
                for date in entry.get("release_dates") or []:
                    if isinstance(date, Mapping) and date.get("certification"):
                        return str(date["certification"])[:20]
        for entry in (document.get("contentRatings") or {}).get("results") or []:
            if isinstance(entry, Mapping) and entry.get("iso_3166_1") == wanted and entry.get("rating"):
                return str(entry["rating"])[:20]
    return None


def map_metadata(document: Mapping[str, Any], kind: str, country: str = "FR") -> dict[str, Any]:
    """#4: Seerr's details (TMDB's, camel-cased) in the shape of the library's own metadata, so a title
    before it is asked for reads like one in the library."""
    credits = document.get("credits") or {}
    people: list[dict[str, Any]] = [
        {
            "name": str(c["name"]),
            "role": c.get("character") or None,
            "department": "cast",
            "image": c.get("profilePath"),
        }
        for c in (credits.get("cast") or [])[:20]
        if isinstance(c, Mapping) and c.get("name")
    ]
    for creator in document.get("createdBy") or []:
        if isinstance(creator, Mapping) and creator.get("name"):
            people.append(
                {
                    "name": str(creator["name"]),
                    "role": "Creator",
                    "department": "creator",
                    "image": creator.get("profilePath"),
                }
            )
    seen: set[tuple[str, str]] = set()
    for member in credits.get("crew") or []:
        if not isinstance(member, Mapping):
            continue
        job, name = member.get("job"), member.get("name")
        if job in CREW_JOBS and name and (name, job) not in seen:
            seen.add((name, job))
            people.append(
                {
                    "name": str(name),
                    "role": job,
                    "department": str(member.get("department") or "crew").lower(),
                    "image": member.get("profilePath"),
                }
            )
    collection = document.get("collection")
    runtime = document.get("runtime") or (document.get("episodeRunTime") or [None])[0]
    countries = [
        str(c.get("iso_3166_1") or c.get("name"))
        for c in document.get("productionCountries") or []
        if isinstance(c, Mapping) and (c.get("iso_3166_1") or c.get("name"))
    ] or [str(c) for c in document.get("originCountry") or []]
    return {
        "title": document.get("title") or document.get("name") or "",
        "tagline": document.get("tagline") or None,
        "overview": document.get("overview") or None,
        "genres": _names_of(document.get("genres")),
        "release_date": str(document.get("releaseDate") or document.get("firstAirDate") or "")[:10] or None,
        "runtime_min": _limit(runtime),
        "countries": countries,
        "languages": _names_of(document.get("spokenLanguages"), "englishName")
        or _names_of(document.get("spokenLanguages"), "english_name"),
        "studios": _names_of(document.get("productionCompanies")),
        "budget": _limit(document.get("budget")) or None,
        "revenue": _limit(document.get("revenue")) or None,
        "vote_average": document.get("voteAverage") or None,
        "vote_count": _limit(document.get("voteCount")),
        "status": document.get("status") or None,
        "certification": _certification(document, country),
        "collection": {
            "id": str(collection.get("id")),
            "name": str(collection.get("name") or ""),
            "poster": collection.get("posterPath"),
            "backdrop": collection.get("backdropPath"),
        }
        if isinstance(collection, Mapping) and collection.get("name")
        else None,
        "seasons": _limit(document.get("numberOfSeasons")) if kind == "series" else None,
        "episodes": _limit(document.get("numberOfEpisodes")) if kind == "series" else None,
        "networks": _names_of(document.get("networks")),
        "backdrop": document.get("backdropPath"),
        "people": people,
        "keywords": _names_of(document.get("keywords"))[:12],
    }


def map_details(document: Mapping[str, Any], kind: str) -> RequestableDetails | None:
    title = map_title({**document, "mediaType": "movie" if kind == "movie" else "tv"})
    if title is None:
        return None
    info = document.get("mediaInfo") or {}
    seasons_there = {
        int(s["seasonNumber"]): int(s.get("status") or 1)
        for s in info.get("seasons") or []
        if isinstance(s, Mapping) and s.get("seasonNumber") is not None
    }
    asked: set[int] = set()
    for request in info.get("requests") or []:
        if isinstance(request, Mapping) and int(request.get("status") or 1) in (1, 2):
            for season in request.get("seasons") or []:
                if isinstance(season, Mapping) and season.get("seasonNumber") is not None:
                    asked.add(int(season["seasonNumber"]))
    seasons = []
    for season in document.get("seasons") or []:
        number = season.get("seasonNumber") if isinstance(season, Mapping) else None
        if number is None or int(number) == 0:  # the specials are never asked for
            continue
        there = TITLE_STATES.get(seasons_there.get(int(number), 1), "unknown")
        seasons.append(
            RequestableSeason(
                number=int(number),
                name=season.get("name") or None,
                episodes=_limit(season.get("episodeCount")),
                air_date=str(season.get("airDate") or "")[:10] or None,
                status="pending" if there == "unknown" and int(number) in asked else there,
            )
        )
    videos = [
        v
        for v in document.get("relatedVideos") or []
        if isinstance(v, Mapping) and v.get("site") == "YouTube" and v.get("key")
    ]
    trailer = next((v for v in videos if v.get("type") == "Trailer"), videos[0] if videos else None)
    cast = tuple(
        (str(c["name"]), c.get("character") or None, c.get("profilePath") or None)
        for c in ((document.get("credits") or {}).get("cast") or [])[:12]
        if isinstance(c, Mapping) and c.get("name")
    )
    external = document.get("externalIds") or {}
    ids = {"tmdb": title.tmdb_id}
    imdb = document.get("imdbId") or external.get("imdbId")
    if imdb:
        ids["imdb"] = str(imdb)
    if external.get("tvdbId"):
        ids["tvdb"] = str(external["tvdbId"])
    runtime = document.get("runtime") or (document.get("episodeRunTime") or [None])[0]
    return RequestableDetails(
        title=title,
        genres=tuple(str(g["name"]) for g in document.get("genres") or [] if isinstance(g, Mapping)),
        runtime=_limit(runtime),
        tagline=document.get("tagline") or None,
        cast=cast,
        trailer=str(trailer["key"]) if trailer else None,
        seasons=tuple(seasons),
        ids=ids,
        metadata=map_metadata(document, kind),
    )


def state_of(request: Mapping[str, Any]) -> tuple[RequestState, str]:
    status = int(request.get("status") or 1)
    media_status = int((request.get("media") or {}).get("status") or 1)
    state: RequestState = REQUEST_STATES.get(status, "pending")
    if state == "approved":
        state = MEDIA_STATES.get(media_status, "approved")
    return state, f"request:{status}/media:{media_status}"


class SeerrConnector(HttpConnector):
    key = "seerr"
    name = "Seerr (Overseerr / Jellyseerr)"
    description = "Media requests: members ask for a film or a series, Seerr sends it to Radarr or Sonarr."
    icon = "inbox"
    category = "requests"
    provides: Sequence[CapabilityBinding] = (
        binding(REQUESTS, syncable=True),
        binding(HEALTH_PROBE),
        binding(ACCOUNTS),
        binding(REQUEST_QUOTAS),
        binding(REQUEST_DISCOVERY),
    )
    status_path = "/api/v1/settings/main"
    public_path = "/api/v1/status"

    def describe(self, status: Any) -> str:
        if not isinstance(status, Mapping) or "applicationTitle" not in status:
            raise InvalidPayload("not a Seerr settings document")
        return str(status.get("applicationTitle") or self.name)

    def looks_like_us(self, public: Any) -> bool:
        return isinstance(public, Mapping) and "version" in public and "commitTag" in public

    async def _title(self, service: ServiceHandle, kind: str, tmdb: Any, cache: dict[str, str]) -> str:
        key = f"{kind}:{tmdb}"
        if key not in cache:
            try:
                details = await self.get_json(service, f"/api/v1/{kind}/{safe_id(tmdb)}")
                cache[key] = str((details or {}).get("title") or (details or {}).get("name") or key)
            except (ConnectionError, InvalidPayload):
                cache[key] = key
        return cache[key]

    async def sync(
        self, ctx: SyncContext, cursor: Mapping[str, Any] | None
    ) -> AsyncIterator[SourceRecord | SyncProgress]:
        service = ctx.service
        titles: dict[str, str] = {}
        skip = 0
        while True:
            page = await self.get_json(service, "/api/v1/request", take=PAGE, skip=skip, sort="added")
            if not isinstance(page, Mapping) or not isinstance(page.get("results"), list):
                raise InvalidPayload("unexpected /request payload")
            if skip == 0 and (page.get("pageInfo") or {}).get("results"):
                yield SyncProgress(cursor={}, total=int(page["pageInfo"]["results"]))
            for request in page["results"]:
                media = request.get("media") or {}
                media_type = str(media.get("mediaType") or request.get("type") or "movie")
                tmdb = media.get("tmdbId")
                state, source_state = state_of(request)
                ids = {
                    "tmdb": str(tmdb) if tmdb else None,
                    "tvdb": str(media["tvdbId"]) if media.get("tvdbId") else None,
                }
                requester = (request.get("requestedBy") or {}).get("id")
                payload = {
                    "title": (await self._title(service, media_type, tmdb, titles)) if tmdb else "?",
                    "kind": KINDS.get(media_type, "movie"),
                    "ids": {k: v for k, v in ids.items() if v},
                    "state": state,
                    "source_state": source_state,
                    "requester": str(requester) if requester else None,
                    # 027: when it arrived in the library (time to availability on « My requests »)
                    "available_at": (
                        media.get("mediaAddedAt") or request.get("updatedAt")
                        if state == "available"
                        else None
                    ),
                }
                yield self.record(
                    service,
                    safe_id(request.get("id")),
                    "request",
                    payload,
                    parse_time(request.get("updatedAt") or request.get("createdAt")),
                )
            skip += len(page["results"])
            total = int((page.get("pageInfo") or {}).get("results") or 0)
            if not page["results"] or skip >= total:
                break
        yield SyncProgress(cursor={"items": skip})

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == REQUESTS:
            return _Requests(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        if capability == ACCOUNTS:
            return _Accounts(self, service)
        if capability == REQUEST_QUOTAS:
            return _Quotas(self, service)
        if capability == REQUEST_DISCOVERY:
            return _Discovery(self, service)
        return None

    async def post_request(self, service: ServiceHandle, body: Mapping[str, Any]) -> Mapping[str, Any]:
        """``POST /api/v1/request``, its refusals told apart: a used-up quota (403 « Quota exceeded »),
        a title already asked for (409)."""
        try:
            response = await self._http(service).request(
                "POST",
                "/api/v1/request",
                headers={"Accept": "application/json", **self.auth_headers(service)},
                json=dict(body),
            )
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        try:
            document = response.json() if response.content else {}
        except ValueError:
            document = {}
        message = str((document or {}).get("message") or "") if isinstance(document, Mapping) else ""
        if response.status_code == 403 and "quota" in message.lower():
            raise SourceQuotaExceeded(message[:200])
        if response.status_code == 409:
            raise SourceDuplicate(message[:200])
        if response.status_code == 401:
            raise ProviderAuthError("the service refused the credentials")
        if response.status_code == 403:
            raise SourceRefused(message[:200])
        if response.status_code >= 400:
            raise ConnectionError(f"the service answered HTTP {response.status_code}")
        if not isinstance(document, Mapping) or "id" not in document:
            raise InvalidPayload("unexpected answer to a request")
        return document


class _Requests:
    def __init__(self, connector: SeerrConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def submit(
        self, ids: Mapping[str, str], kind: str, title: str, requester: str | None, **options: Any
    ) -> SourceRequest:
        tmdb = ids.get("tmdb")
        if not tmdb:
            raise InvalidPayload("Seerr needs a TMDB id to request a title")
        media_type = "tv" if kind in ("series", "season", "episode") else "movie"
        body: dict[str, Any] = {"mediaType": media_type, "mediaId": int(safe_id(tmdb))}
        if media_type == "tv":
            seasons = [int(n) for n in options.get("seasons") or [] if int(n) > 0]
            body["seasons"] = sorted(set(seasons)) if seasons else "all"
            if ids.get("tvdb") and str(ids["tvdb"]).isdigit():
                body["tvdbId"] = int(ids["tvdb"])
        if options.get("is4k"):
            body["is4k"] = True
        if requester and requester.isdigit():
            body["userId"] = int(requester)
        if options.get("bypass_quota"):
            body["ignoreQuota"] = True  # Seerr 3: the request does not count against the account
        try:
            created = await self.connector.post_request(self.service, body)
        except SourceQuotaExceeded:
            if not options.get("bypass_quota") or "userId" not in body:
                raise
            # a service without ``ignoreQuota`` (Overseerr): the API key's account asks instead — it has no
            # quota; the portal keeps who asked
            body.pop("userId")
            created = await self.connector.post_request(self.service, body)
        state, source_state = state_of(created)
        return SourceRequest(external_request_id=str(created["id"]), state=state, source_state=source_state)

    async def decide(self, external_request_id: str, approve: bool) -> SourceRequest:
        """#4: an administrator approves (Seerr sends it to Radarr or Sonarr) or declines a request."""
        verb = "approve" if approve else "decline"
        request = await self.connector.request(
            self.service, "POST", f"/api/v1/request/{safe_id(external_request_id)}/{verb}"
        )
        if not isinstance(request, Mapping):
            raise InvalidPayload("unexpected answer to a decision")
        state, source_state = state_of(request)
        return SourceRequest(external_request_id=external_request_id, state=state, source_state=source_state)

    async def status(self, external_request_id: str) -> SourceRequest:
        request = await self.connector.get_json(
            self.service, f"/api/v1/request/{safe_id(external_request_id)}"
        )
        if not isinstance(request, Mapping):
            raise InvalidPayload("unexpected request payload")
        state, source_state = state_of(request)
        return SourceRequest(external_request_id=external_request_id, state=state, source_state=source_state)


class _Accounts:
    def __init__(self, connector: SeerrConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def list_accounts(self) -> Sequence[ServiceAccount]:
        page = await self.connector.get_json(self.service, "/api/v1/user", take=500, skip=0)
        if not isinstance(page, Mapping) or not isinstance(page.get("results"), list):
            raise InvalidPayload("unexpected /user payload")
        return [
            ServiceAccount(
                external_id=str(u["id"]),
                username=u.get("username") or u.get("plexUsername") or u.get("jellyfinUsername"),
                display_name=u.get("displayName"),
                email=u.get("email"),
            )
            for u in page["results"]
            if u.get("id")
        ]


class _Quotas:
    """#3: request limits of the service's accounts."""

    def __init__(self, connector: SeerrConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def quota(self, external_user: str) -> SourceQuota:
        document = await self.connector.get_json(self.service, f"/api/v1/user/{safe_id(external_user)}/quota")
        if not isinstance(document, Mapping):
            raise InvalidPayload("unexpected quota payload")
        return SourceQuota(movie=map_window(document.get("movie")), tv=map_window(document.get("tv")))

    async def accounts(self) -> Sequence[QuotaAccount]:
        page = await self.connector.get_json(self.service, "/api/v1/user", take=500, skip=0)
        if not isinstance(page, Mapping) or not isinstance(page.get("results"), list):
            raise InvalidPayload("unexpected /user payload")
        users = [u for u in page["results"] if isinstance(u, Mapping) and u.get("id")]
        gate = asyncio.Semaphore(6)

        async def one(user: Mapping[str, Any]) -> QuotaAccount:
            permissions = int(user.get("permissions") or 0)
            exempt = bool(permissions & (MANAGE_USERS | ADMIN))
            quota = None
            if not exempt:
                async with gate:
                    try:
                        quota = await self.quota(str(user["id"]))
                    except (ConnectionError, InvalidPayload):
                        quota = None
            return QuotaAccount(
                external_id=str(user["id"]),
                name=user.get("displayName")
                or user.get("username")
                or user.get("plexUsername")
                or user.get("jellyfinUsername"),
                own=QuotaLimits(
                    movie_limit=_limit(user.get("movieQuotaLimit")),
                    movie_days=_limit(user.get("movieQuotaDays")),
                    tv_limit=_limit(user.get("tvQuotaLimit")),
                    tv_days=_limit(user.get("tvQuotaDays")),
                ),
                quota=quota,
                exempt=exempt,
            )

        return list(await asyncio.gather(*(one(u) for u in users[:500])))

    async def set_limits(self, external_user: str, limits: QuotaLimits) -> None:
        # the settings are written back whole: Seerr takes the name, the e-mail and the preferences from
        # the same body, and only changes the limits of an account that does not manage users
        path = f"/api/v1/user/{safe_id(external_user)}/settings/main"
        current = await self.connector.get_json(self.service, path)
        if not isinstance(current, Mapping):
            raise InvalidPayload("unexpected user settings payload")
        body = {
            **{k: v for k, v in current.items() if not str(k).startswith("global")},
            "movieQuotaLimit": limits.movie_limit,
            "movieQuotaDays": limits.movie_days,
            "tvQuotaLimit": limits.tv_limit,
            "tvQuotaDays": limits.tv_days,
        }
        await self.connector.request(self.service, "POST", path, json_body=body)

    async def defaults(self) -> QuotaLimits:
        settings = await self.connector.get_json(self.service, "/api/v1/settings/main")
        quotas = (settings or {}).get("defaultQuotas") if isinstance(settings, Mapping) else None
        movie = (quotas or {}).get("movie") or {}
        tv = (quotas or {}).get("tv") or {}
        return QuotaLimits(
            movie_limit=_limit(movie.get("quotaLimit")),
            movie_days=_limit(movie.get("quotaDays")),
            tv_limit=_limit(tv.get("quotaLimit")),
            tv_days=_limit(tv.get("quotaDays")),
        )

    async def set_defaults(self, limits: QuotaLimits) -> None:
        # merged into the main settings by Seerr: 0 clears a limit (no limit), never ``None``
        body = {
            "defaultQuotas": {
                "movie": {"quotaLimit": limits.movie_limit or 0, "quotaDays": limits.movie_days or 0},
                "tv": {"quotaLimit": limits.tv_limit or 0, "quotaDays": limits.tv_days or 0},
            }
        }
        await self.connector.request(self.service, "POST", "/api/v1/settings/main", json_body=body)


class _Discovery:
    """#4: titles one can ask for, as Seerr sees them (TMDB, with what the library and requests hold)."""

    def __init__(self, connector: SeerrConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def _titles(self, path: str, **params: Any) -> list[RequestableTitle]:
        page = await self.connector.get_json(self.service, path, **params)
        results = page.get("results") if isinstance(page, Mapping) else None
        if not isinstance(results, list):
            raise InvalidPayload("unexpected discovery payload")
        return [t for r in results if isinstance(r, Mapping) and (t := map_title(r)) is not None]

    async def search(self, query: str, language: str, page: int = 1) -> Sequence[RequestableTitle]:
        text = " ".join(str(query).split())[:100]
        if not text:
            return []
        return await self._titles(
            "/api/v1/search", query=text, page=max(1, min(int(page), 20)), language=language
        )

    async def shelf(self, name: str, language: str) -> Sequence[RequestableTitle]:
        path = SHELVES.get(name)
        if path is None:
            return []
        # no ``language`` here: on the discovery lists Seerr also takes it as the titles' *original*
        # language (popular films would be French films only); the service's own language is used
        return await self._titles(path, page=1)

    async def details(self, kind: str, tmdb_id: str, language: str) -> RequestableDetails | None:
        media = "movie" if kind == "movie" else "tv"
        document = await self.connector.get_json(
            self.service, f"/api/v1/{media}/{safe_id(tmdb_id)}", language=language
        )
        if not isinstance(document, Mapping):
            raise InvalidPayload("unexpected details payload")
        found = map_details(document, "movie" if media == "movie" else "series")
        if found is None:
            return None
        country = "FR" if language.lower().startswith("fr") else "US"
        metadata = map_metadata(document, found.title.kind, country)
        return replace(found, four_k=await self._four_k(media), metadata=metadata)

    async def _four_k(self, media: str) -> bool:
        """Whether a 4K server (Radarr for films, Sonarr for series) takes requests — else no 4K asked."""
        try:
            servers = await self.connector.get_json(
                self.service, f"/api/v1/settings/{'radarr' if media == 'movie' else 'sonarr'}"
            )
        except (ConnectionError, InvalidPayload, ProviderAuthError):
            return False
        return any(isinstance(s, Mapping) and s.get("is4k") for s in servers or [])
