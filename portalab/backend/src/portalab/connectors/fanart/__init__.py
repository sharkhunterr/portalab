"""``fanart`` connector (issue 229): fanart.tv, the artwork of films and series made by its community — HD
backgrounds, thumbs, clearart (the cast cut out over nothing), logos and, for series, characters.

* ``media.artwork``: a film's by its TMDB (else IMDb) id, a series' by its TVDB id; each image with its
  language (none: no text on it) and its likes; their bytes from fanart.tv's image host.
* ``service.health_probe``: a film every account may read (``/v3/movies/550``).

A personal API key (fanart.tv → profile → API keys) is all it needs.
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field

from portalab.capabilities.connector_http import ConnectorHttpClient, ConnectorHttpError
from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import ARTWORK, Artwork
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import BaseConfig, HttpConnector, _Probe, binding

ASSETS = "https://assets.fanart.tv"
ASSET_PATH = re.compile(r"^/fanart/[A-Za-z0-9/_.-]{1,200}\.(jpg|jpeg|png)$")
# fanart.tv's names for each kind of artwork, a film's then a series'
MOVIE_KINDS = {
    "moviebackground": "background",
    "moviethumb": "thumb",
    "hdmovieclearart": "clearart",
    "movieart": "clearart",
    "hdmovielogo": "logo",
    "movieposter": "poster",
}
TV_KINDS = {
    "showbackground": "background",
    "tvthumb": "thumb",
    "hdclearart": "clearart",
    "clearart": "clearart",
    "characterart": "character",
    "hdtvlogo": "logo",
    "tvposter": "poster",
}


class FanartConfig(BaseConfig):
    base_url: str = Field(
        default="https://webservice.fanart.tv",
        min_length=8,
        max_length=512,
        pattern=r"^https?://[^\s/$.?#].[^\s]*$",
        title="Address",
        description="Leave https://webservice.fanart.tv unless you use a proxy.",
    )


def asset_ref(url: Any) -> str | None:
    """The path of an image on fanart.tv's image host (the only host its images are fetched from)."""
    if not isinstance(url, str) or not url.startswith(ASSETS):
        return None
    path = url[len(ASSETS) :]
    return path if ASSET_PATH.fullmatch(path) else None


def map_artwork(document: Any, kinds: Mapping[str, str]) -> list[Artwork]:
    out: list[Artwork] = []
    if not isinstance(document, Mapping):
        return out
    for field, kind in kinds.items():
        for item in document.get(field) or []:
            ref = asset_ref(item.get("url")) if isinstance(item, Mapping) else None
            if ref is None:
                continue
            lang = str(item.get("lang") or "")
            likes = item.get("likes")
            out.append(
                Artwork(
                    kind=kind,
                    image=ref,
                    lang=None if lang in ("", "00") else lang[:8],
                    likes=int(likes) if str(likes or "").isdigit() else 0,
                )
            )
    return out


class FanartConnector(HttpConnector):
    key = "fanart"
    name = "fanart.tv"
    description = "Artwork of films and series made by its community: HD backgrounds, clearart, characters…"
    icon = "image"
    category = "metadata"
    config_schema: type[BaseModel] = FanartConfig
    secret_fields: frozenset[str] = frozenset({"api_key"})
    provides: Sequence[CapabilityBinding] = (binding(ARTWORK), binding(HEALTH_PROBE))
    status_path = "/v3/movies/550"
    public_path = None

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        return {}

    async def get_json(self, service: ServiceHandle, path: str, **params: Any) -> Any:
        params["api_key"] = service.secrets.get("api_key", "")
        return await super().get_json(service, path, **params)

    def describe(self, status: Any) -> str:
        if not isinstance(status, Mapping) or not status.get("tmdb_id"):
            raise InvalidPayload("not fanart.tv")
        return "fanart.tv"

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == ARTWORK:
            return _Artwork(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None


class _Artwork:
    def __init__(self, connector: FanartConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service
        self.assets = ConnectorHttpClient(
            ASSETS, timeout_seconds=20, max_response_bytes=12 * 1024 * 1024, retries=1
        )

    async def artwork(self, kind: str, ids: Mapping[str, str]) -> list[Artwork]:
        if kind == "movie":
            ref = ids.get("tmdb") or ids.get("imdb")
            path, kinds = f"/v3/movies/{ref}", MOVIE_KINDS
        elif kind == "series":
            ref, path, kinds = ids.get("tvdb"), f"/v3/tv/{ids.get('tvdb')}", TV_KINDS
        else:
            return []
        if not ref or not re.fullmatch(r"[A-Za-z0-9]{1,20}", str(ref)):
            return []
        try:
            document = await self.connector.get_json(self.service, path)
        except ConnectionError:
            return []  # fanart.tv knows nothing of it (it answers 404)
        return map_artwork(document, kinds)

    async def fetch_artwork(self, ref: str, preview: bool = False) -> bytes:
        if not ASSET_PATH.fullmatch(ref):
            raise InvalidPayload("unexpected image reference")
        path = ref.replace("/fanart/", "/preview/", 1) if preview else ref
        try:
            response = await self.assets.get(path)
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code >= 400:
            raise ConnectionError(f"fanart.tv images answered HTTP {response.status_code}")
        return response.content
