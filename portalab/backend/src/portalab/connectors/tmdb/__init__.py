"""``tmdb`` connector: The Movie Database, a metadata provider (API v3).

* ``media.metadata``: what TMDB knows about a film or a series — tagline, overview, genres, release date,
  runtime, countries, languages, studios, budget, revenue, rating, certification, collection (saga),
  seasons and networks, keywords, cast and crew with their photos, poster and backdrop. Found by TMDB id,
  else by IMDb/TVDB id (``/find``), else by title and year. Text comes in the portal's language.
* Images (posters, backdrops, portraits) are fetched from TMDB's image server by the portal, cached, and
  served from the portal itself: members' browsers never call TMDB.
* ``service.health_probe``: an authenticated ``/3/configuration`` round trip.

Authentication: the *API Read Access Token* (v4, sent as a bearer) or the v3 *API key* (``api_key``
parameter) of https://www.themoviedb.org/settings/api.
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field

from portalab.capabilities.connector_http import ConnectorHttpClient, ConnectorHttpError
from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import METADATA, MetadataPerson, MetadataRecord
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import BaseConfig, HttpConnector, _Probe, binding

IMAGE_HOST = "https://image.tmdb.org"
IMAGE_PATH = re.compile(r"^/[A-Za-z0-9_-]{1,64}\.(jpg|jpeg|png|svg)$")
SIZES = frozenset({"w92", "w154", "w185", "w300", "w342", "w500", "w780", "w1280", "h632", "original"})
CAST = 20
CREW_JOBS = ("Director", "Screenplay", "Writer", "Original Music Composer", "Producer", "Creator")


class TmdbConfig(BaseConfig):
    base_url: str = Field(
        default="https://api.themoviedb.org",
        min_length=8,
        max_length=512,
        pattern=r"^https?://[^\s/$.?#].[^\s]*$",
        title="Address",
        description="Leave https://api.themoviedb.org unless you use a proxy.",
    )
    language: str = Field(
        default="",
        max_length=16,
        pattern=r"^$|^[a-z]{2}(-[A-Z]{2})?$",
        title="Language",
        description="e.g. fr-FR; empty = the portal's language.",
    )


def image_ref(path: Any) -> str | None:
    return path if isinstance(path, str) and IMAGE_PATH.fullmatch(path) else None


def _names(values: Any, key: str = "name") -> list[str]:
    return [str(v[key])[:120] for v in values or [] if isinstance(v, Mapping) and v.get(key)]


def _int(value: Any) -> int | None:
    return int(value) if isinstance(value, int | float) and value > 0 else None


def _certification(document: Mapping[str, Any], country: str) -> str | None:
    for result in (document.get("release_dates") or {}).get("results") or []:
        if result.get("iso_3166_1") == country:
            for release in result.get("release_dates") or []:
                if release.get("certification"):
                    return str(release["certification"])[:16]
    for result in (document.get("content_ratings") or {}).get("results") or []:
        if result.get("iso_3166_1") == country and result.get("rating"):
            return str(result["rating"])[:16]
    return None


def map_document(document: Mapping[str, Any], kind: str, country: str = "FR") -> MetadataRecord:
    """A TMDB movie or tv document (with ``credits``, ``keywords``, ``external_ids``…) as a record."""
    series = kind != "movie"
    external = document.get("external_ids") or {}
    ids = {"tmdb": str(document["id"])}
    imdb = document.get("imdb_id") or external.get("imdb_id")
    if imdb:
        ids["imdb"] = str(imdb)
    if external.get("tvdb_id"):
        ids["tvdb"] = str(external["tvdb_id"])
    credits = document.get("aggregate_credits") or document.get("credits") or {}
    people: list[MetadataPerson] = []
    for person in (credits.get("cast") or [])[:CAST]:
        role = person.get("character") or next(
            (r.get("character") for r in person.get("roles") or [] if r.get("character")), None
        )
        people.append(
            MetadataPerson(
                name=str(person.get("name") or "?")[:120],
                role=str(role)[:120] if role else None,
                department="cast",
                image=image_ref(person.get("profile_path")),
                ids={"tmdb": str(person["id"])} if person.get("id") else {},
            )
        )
    for creator in document.get("created_by") or []:
        people.append(
            MetadataPerson(
                name=str(creator.get("name") or "?")[:120],
                role="Creator",
                department="creator",
                image=image_ref(creator.get("profile_path")),
                ids={"tmdb": str(creator["id"])} if creator.get("id") else {},
            )
        )
    seen: set[tuple[str, str]] = set()
    for member in credits.get("crew") or []:
        jobs = [member.get("job")] + [j.get("job") for j in member.get("jobs") or []]
        job = next((j for j in jobs if j in CREW_JOBS), None)
        name = member.get("name")
        if job and name and (name, job) not in seen:
            seen.add((name, job))
            people.append(
                MetadataPerson(
                    name=str(name)[:120],
                    role=job,
                    department=str(member.get("department") or "crew").lower()[:40],
                    image=image_ref(member.get("profile_path")),
                    ids={"tmdb": str(member["id"])} if member.get("id") else {},
                )
            )
    collection = document.get("belongs_to_collection")
    keywords = document.get("keywords") or {}
    runtime = document.get("runtime") or next(iter(document.get("episode_run_time") or []), None)
    return MetadataRecord(
        ids=ids,
        title=str(document.get("title") or document.get("name") or "?")[:500],
        original_title=document.get("original_title") or document.get("original_name"),
        tagline=document.get("tagline") or None,
        overview=document.get("overview") or None,
        genres=_names(document.get("genres")),
        release_date=document.get("release_date") or document.get("first_air_date") or None,
        runtime_min=_int(runtime),
        countries=[
            c.get("iso_3166_1") for c in document.get("production_countries") or [] if c.get("iso_3166_1")
        ]
        or list(document.get("origin_country") or []),
        languages=_names(document.get("spoken_languages"), "english_name")
        or ([document["original_language"]] if document.get("original_language") else []),
        studios=_names(document.get("production_companies"))[:10],
        budget=_int(document.get("budget")),
        revenue=_int(document.get("revenue")),
        vote_average=float(document["vote_average"]) if document.get("vote_average") else None,
        vote_count=_int(document.get("vote_count")),
        status=document.get("status") or None,
        certification=_certification(document, country),
        collection=(
            {
                "id": str(collection.get("id")),
                "name": collection.get("name"),
                "poster": image_ref(collection.get("poster_path")),
                "backdrop": image_ref(collection.get("backdrop_path")),
            }
            if isinstance(collection, Mapping)
            else None
        ),
        seasons=_int(document.get("number_of_seasons")) if series else None,
        episodes=_int(document.get("number_of_episodes")) if series else None,
        networks=_names(document.get("networks")) if series else [],
        poster=image_ref(document.get("poster_path")),
        backdrop=image_ref(document.get("backdrop_path")),
        people=people,
        keywords=_names(keywords.get("keywords") or keywords.get("results"))[:20],
        backdrops=_artwork(document, "backdrops", 12),
        posters=_artwork(document, "posters", 8),
    )


def _artwork(document: Mapping[str, Any], key: str, limit: int) -> list[str]:
    """027: the best-rated other images (textless backdrops first), without the main one."""
    images = (document.get("images") or {}).get(key) or []
    ranked = sorted(
        (i for i in images if isinstance(i, Mapping)),
        key=lambda i: (i.get("iso_639_1") is not None, -(i.get("vote_average") or 0)),
    )
    out: list[str] = []
    main = document.get("backdrop_path" if key == "backdrops" else "poster_path")
    for image in ranked:
        ref = image_ref(image.get("file_path"))
        if ref and ref != main and ref not in out:
            out.append(ref)
        if len(out) >= limit:
            break
    return out


class TmdbConnector(HttpConnector):
    key = "tmdb"
    name = "TMDB (The Movie Database)"
    description = "Rich film and series details: backdrop, cast, saga, budget, box office, genres…"
    icon = "sparkles"
    category = "metadata"
    config_schema: type[BaseModel] = TmdbConfig
    secret_fields: frozenset[str] = frozenset({"api_key"})
    provides: Sequence[CapabilityBinding] = (binding(METADATA), binding(HEALTH_PROBE))
    status_path = "/3/configuration"
    public_path = None

    def _v4(self, service: ServiceHandle) -> bool:
        return service.secrets.get("api_key", "").startswith("eyJ")  # a read access token is a JWT

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        if self._v4(service):
            return {"Authorization": f"Bearer {service.secrets.get('api_key', '')}"}
        return {}

    async def get_json(self, service: ServiceHandle, path: str, **params: Any) -> Any:
        if not self._v4(service):
            params["api_key"] = service.secrets.get("api_key", "")
        return await super().get_json(service, path, **params)

    def describe(self, status: Any) -> str:
        if not isinstance(status, Mapping) or "images" not in status:
            raise InvalidPayload("not the TMDB configuration")
        return "TMDB"

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == METADATA:
            return _Metadata(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None


class _Metadata:
    def __init__(self, connector: TmdbConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service
        self.images = ConnectorHttpClient(
            IMAGE_HOST, timeout_seconds=15, max_response_bytes=8 * 1024 * 1024, retries=1
        )

    def _language(self, language: str) -> str:
        configured = str(self.service.config.get("language") or "")
        if configured:
            return configured
        if re.fullmatch(r"[a-z]{2}", language):
            return f"{language}-{language.upper()}" if language != "en" else "en-US"
        return language if re.fullmatch(r"[a-z]{2}-[A-Z]{2}", language) else "en-US"

    async def _document(self, kind: str, tmdb_id: str, language: str) -> Mapping[str, Any] | None:
        movie = kind == "movie"
        appended = (
            "credits,keywords,external_ids,release_dates,images"
            if movie
            else "aggregate_credits,keywords,external_ids,content_ratings,images"
        )
        document = await self.connector.get_json(
            self.service,
            f"/3/{'movie' if movie else 'tv'}/{int(tmdb_id)}",
            language=language,
            append_to_response=appended,
            include_image_language=f"{language.split('-')[0]},en,null" if language else "en,null",
        )
        return document if isinstance(document, Mapping) and document.get("id") else None

    async def _find(
        self, kind: str, ids: Mapping[str, str], title: str, year: int | None, language: str
    ) -> str | None:
        movie = kind == "movie"
        for scheme, source in (("imdb", "imdb_id"), ("tvdb", "tvdb_id")):
            value = ids.get(scheme)
            if value and re.fullmatch(r"[A-Za-z0-9]{1,20}", value):
                found = await self.connector.get_json(
                    self.service, f"/3/find/{value}", external_source=source, language=language
                )
                results = (found or {}).get("movie_results" if movie else "tv_results") or []
                if results:
                    return str(results[0]["id"])
        params: dict[str, Any] = {"query": title[:200], "language": language, "include_adult": "false"}
        if year:
            params["year" if movie else "first_air_date_year"] = year
        found = await self.connector.get_json(
            self.service, f"/3/search/{'movie' if movie else 'tv'}", **params
        )
        results = (found or {}).get("results") or []
        if not results and year:  # the year differs between sources sometimes: try without it
            params.pop("year", None)
            params.pop("first_air_date_year", None)
            found = await self.connector.get_json(
                self.service, f"/3/search/{'movie' if movie else 'tv'}", **params
            )
            results = (found or {}).get("results") or []
        return str(results[0]["id"]) if results else None

    async def lookup(
        self, kind: str, ids: Mapping[str, str], title: str, year: int | None, language: str
    ) -> MetadataRecord | None:
        if kind not in ("movie", "series"):
            return None
        lang = self._language(language)
        tmdb_id = ids.get("tmdb") if str(ids.get("tmdb") or "").isdigit() else None
        if tmdb_id is None:
            tmdb_id = await self._find(kind, ids, title, year, lang)
        if tmdb_id is None:
            return None
        document = await self._document(kind, tmdb_id, lang)
        if document is None:
            return None
        return map_document(document, kind, country=lang.split("-")[-1])

    async def fetch_image(self, ref: str, size: str) -> bytes:
        if not IMAGE_PATH.fullmatch(ref) or size not in SIZES:
            raise InvalidPayload("unexpected image reference")
        try:
            response = await self.images.get(f"/t/p/{size}{ref}")
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code >= 400:
            raise ConnectionError(f"TMDB images answered HTTP {response.status_code}")
        return response.content
