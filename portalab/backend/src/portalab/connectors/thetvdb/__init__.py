"""``thetvdb`` connector (issue 231): TheTVDB, the community database of series and films — here, the image
of each role: the character itself (in costume, drawn, made up), cut for a portrait.

* ``media.characters``: a film's or a series' roles with an image of their own, found by its TMDB (else IMDb)
  id; a role showing only its actor's portrait is left out. Their bytes from TheTVDB's image host.
* ``service.health_probe``: a sign-in and a film every key may read.

A project API key (thetvdb.com → dashboard → API keys) is all it needs; its token (a month long) is asked
for once and kept in memory. TheTVDB asks for attribution wherever its data is shown.
"""

import re
import time
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field

from portalab.capabilities.connector_http import ConnectorHttpClient, ConnectorHttpError
from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import CHARACTERS, CharacterImage
from portalab.capabilities.results import InvalidPayload, ProviderAuthError
from portalab.connectors.http_base import BaseConfig, HttpConnector, _Probe, binding

ARTWORKS = "https://artworks.thetvdb.com"
IMAGE_PATH = re.compile(r"^/banners/[A-Za-z0-9/_.-]{1,200}\.(jpg|jpeg|png|webp)$")
TOKEN_SECONDS = 25 * 24 * 3600  # a token lasts a month: asked again a little before
REMOTE = re.compile(r"^(tt)?[0-9]{1,12}$")
_TOKENS: dict[Any, tuple[str, float]] = {}


class TvdbConfig(BaseConfig):
    base_url: str = Field(
        default="https://api4.thetvdb.com/v4",
        min_length=8,
        max_length=512,
        pattern=r"^https?://[^\s/$.?#].[^\s]*$",
        title="Address",
        description="Leave https://api4.thetvdb.com/v4 unless you use a proxy.",
    )


def image_ref(url: Any) -> str | None:
    """The path of an image on TheTVDB's image host (the only host its images are fetched from)."""
    if not isinstance(url, str) or not url.startswith(ARTWORKS):
        return None
    path = url[len(ARTWORKS) :]
    return path if IMAGE_PATH.fullmatch(path) else None


def map_characters(record: Any) -> list[CharacterImage]:
    """The actors' roles with an image of their own (not their portrait), in the credits' order."""
    out: list[CharacterImage] = []
    for item in (record or {}).get("characters") or [] if isinstance(record, Mapping) else []:
        if not isinstance(item, Mapping) or item.get("peopleType") != "Actor":
            continue
        image, portrait = item.get("image"), item.get("personImgURL")
        ref = image_ref(image)
        if ref is None or image == portrait or not item.get("personName"):
            continue
        character = str(item.get("name") or "").strip() or None
        sort = item.get("sort")
        out.append(
            CharacterImage(
                person=str(item["personName"])[:160],
                character=character[:200] if character else None,
                image=ref,
                sort=int(sort) if isinstance(sort, int) else 999,
            )
        )
    return sorted(out, key=lambda c: c.sort)


def pick(found: Any, kind: str) -> str | None:
    """TheTVDB's id of the work a remote id names — a film's or a series' (one number may be both)."""
    field = "movie" if kind == "movie" else "series"
    for hit in found if isinstance(found, list) else []:
        record = hit.get(field) if isinstance(hit, Mapping) else None
        if isinstance(record, Mapping) and str(record.get("id") or "").isdigit():
            return str(record["id"])
    return None


class TvdbConnector(HttpConnector):
    key = "thetvdb"
    name = "TheTVDB"
    description = "The community database of series and films: each role's own image, for the cards."
    icon = "image"
    category = "metadata"
    config_schema: type[BaseModel] = TvdbConfig
    secret_fields: frozenset[str] = frozenset({"api_key"})
    provides: Sequence[CapabilityBinding] = (binding(CHARACTERS), binding(HEALTH_PROBE))
    status_path = "/movies/131079"
    public_path = None

    async def _token(self, service: ServiceHandle, *, fresh: bool = False) -> str:
        kept = _TOKENS.get(service.service_id)
        if kept and not fresh and kept[1] > time.monotonic():
            return kept[0]
        answer = await super().request(
            service, "POST", "/login", json_body={"apikey": service.secrets.get("api_key", "")}
        )
        token = (answer or {}).get("data", {}).get("token") if isinstance(answer, Mapping) else None
        if not isinstance(token, str) or not token:
            raise InvalidPayload("TheTVDB gave no token")
        _TOKENS[service.service_id] = (token, time.monotonic() + TOKEN_SECONDS)
        return token

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        return {}

    async def get_json(self, service: ServiceHandle, path: str, **params: Any) -> Any:
        for fresh in (False, True):
            token = await self._token(service, fresh=fresh)
            try:
                return await self.request(
                    service, "GET", path, params=params, headers={"Authorization": f"Bearer {token}"}
                )
            except ProviderAuthError:
                if fresh:
                    raise
        return None  # pragma: no cover — the loop returns or raises

    def describe(self, status: Any) -> str:
        if not isinstance(status, Mapping) or not isinstance(status.get("data"), Mapping):
            raise InvalidPayload("not TheTVDB")
        return "TheTVDB"

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == CHARACTERS:
            return _Characters(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None


class _Characters:
    def __init__(self, connector: TvdbConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service
        self.images = ConnectorHttpClient(
            ARTWORKS, timeout_seconds=20, max_response_bytes=8 * 1024 * 1024, retries=1
        )

    async def characters(self, kind: str, ids: Mapping[str, str]) -> list[CharacterImage]:
        if kind not in ("movie", "series"):
            return []
        work = str(ids["tvdb"]) if kind == "series" and str(ids.get("tvdb") or "").isdigit() else None
        for remote in (ids.get("tmdb"), ids.get("imdb")):
            if work or not remote or not REMOTE.fullmatch(str(remote)):
                continue
            try:
                found = await self.connector.get_json(self.service, f"/search/remoteid/{remote}")
            except ConnectionError:
                continue  # TheTVDB does not know this id (it answers 404)
            work = pick((found or {}).get("data") if isinstance(found, Mapping) else None, kind)
        if work is None:
            return []
        path = f"/movies/{work}/extended" if kind == "movie" else f"/series/{work}/extended"
        try:
            record = await self.connector.get_json(self.service, path, short="false")
        except ConnectionError:
            return []
        return map_characters((record or {}).get("data") if isinstance(record, Mapping) else None)

    async def fetch_character(self, ref: str) -> bytes:
        if not IMAGE_PATH.fullmatch(ref):
            raise InvalidPayload("unexpected image reference")
        try:
            response = await self.images.get(ref)
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code >= 400:
            raise ConnectionError(f"TheTVDB images answered HTTP {response.status_code}")
        return response.content
