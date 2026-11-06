"""``igdb`` connector (#368): IGDB, the game database RomM matches the library's games with — a franchise's
games (those the library lacks too) and a game's sheet, with its cover, screenshots and artworks.

* ``media.game_database``: a franchise (or a series) found by its name — among its namesakes, the one
  holding the library's own games (their IGDB ids, which RomM keeps), else the one named exactly so with the
  most games —, its games the oldest first (a game's versions, DLC and bundles left out); a game's sheet:
  summary, storyline, release, platforms, genres, themes, modes, studios and publishers, franchises, its
  titles in other languages, rating, trailer, screenshots and artworks.
* ``service.health_probe``: a one-row read of the platforms.

IGDB's API wants a Twitch application (dev.twitch.tv/console): its Client ID (configuration) and Client
Secret (secret) are exchanged for an app access token (``client_credentials``), kept until it nearly
expires and renewed when refused. Calls are made by the portal only; images are fetched from IGDB's image
host through the portal. IGDB's figures (ratings) are told as IGDB's.
"""

import asyncio
import re
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from portalab.capabilities.connector_http import ConnectorHttpClient, ConnectorHttpError
from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import GAME_DATABASE, GameDetails, GameFranchise, PersonCredit
from portalab.capabilities.results import InvalidPayload, ProviderAuthError, ProviderNotFound
from portalab.connectors.http_base import BaseConfig, HttpConnector, _Probe, binding

API = "/v4/"
AUTH_HOST = "https://id.twitch.tv"
AUTH_PATH = "/oauth2/token"
IMAGE_HOST = "https://images.igdb.com"
IMAGE_ID = re.compile(r"^[a-z0-9]{1,40}$")
# a reference's size → IGDB's own (a cover's, a screenshot's, an artwork's)
SIZES = {"cover": "t_cover_big", "screenshot": "t_screenshot_big", "artwork": "t_1080p"}
CANDIDATES = 5  # the franchises (and series) of a name looked at
GAMES = 500  # a franchise's games asked at once (the API's cap)
IMAGES = 12  # a game's screenshots and artworks told
# the kinds of game told in a franchise (IGDB's game types): a main game, a standalone expansion, a
# remake, a remaster, an expanded game, a port — not a DLC, a bundle, a mod, an episode or an update
GAME_TYPES = frozenset({0, 4, 8, 9, 10, 11})
KEPT_SECONDS = 6 * 3600
USER_AGENT = "Portalab (self-hosted media portal; issue 368)"
STATUS = "fields id; limit 1;"
_FRANCHISE = "fields id, name, games; where name ~ {name}; limit {limit};"
_GAMES = (
    "fields id, name, first_release_date, cover.image_id, total_rating, total_rating_count, version_parent,"
    " parent_game, game_type; where id = ({ids}); limit {limit};"
)
_GAME = (
    "fields name, summary, storyline, first_release_date, cover.image_id, screenshots.image_id,"
    " artworks.image_id, genres.name, themes.name, game_modes.name, platforms.name,"
    " involved_companies.developer, involved_companies.publisher, involved_companies.company.name,"
    " franchises.name, collections.name, total_rating, total_rating_count, videos.video_id,"
    " alternative_names.name, alternative_names.comment, game_localizations.name,"
    " game_localizations.region.identifier; where id = {id};"
)

_TOKENS: dict[tuple[str, str], tuple[float, str]] = {}  # (address, client id) → (expires, token)
_KEPT: dict[tuple[Any, str], tuple[float, Any]] = {}


class IgdbConfig(BaseConfig):
    base_url: str = Field(
        default="https://api.igdb.com",
        min_length=8,
        max_length=512,
        pattern=r"^https?://[^\s/$.?#].[^\s]*$",
        title="Address",
        description="Leave https://api.igdb.com unless you use a proxy.",
    )
    client_id: str = Field(
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9]+$",
        title="Client ID",
        description="Your Twitch application's Client ID (dev.twitch.tv/console → Applications).",
    )


def quoted(text: str) -> str:
    """A text inside an Apicalypse query: between quotes, nothing in it read as syntax."""
    return '"' + " ".join(re.sub(r'["\\;]', " ", text).split())[:200] + '"'


def image_ref(value: Any) -> str | None:
    """An image's id on IGDB's image host (the only host its images are fetched from)."""
    ref = value.get("image_id") if isinstance(value, Mapping) else value
    return ref if isinstance(ref, str) and IMAGE_ID.fullmatch(ref) else None


def _names(values: Any, key: str = "name") -> list[str]:
    return list(
        dict.fromkeys(str(v[key])[:120] for v in values or [] if isinstance(v, Mapping) and v.get(key))
    )


def _date(seconds: Any) -> datetime | None:
    if not isinstance(seconds, int | float) or isinstance(seconds, bool):
        return None
    try:
        return datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _rating(value: Any) -> float | None:
    return round(float(value) / 10, 1) if isinstance(value, int | float) and value else None


def map_game(game: Any) -> PersonCredit | None:
    """A game of a franchise, as a title of a person's or a series' (its id, cover, rating out of 10)."""
    if not isinstance(game, Mapping) or not game.get("id") or not game.get("name"):
        return None
    released = _date(game.get("first_release_date"))
    return PersonCredit(
        tmdb_id=str(game["id"]),
        kind="game",
        title=str(game["name"])[:300],
        year=released.year if released else None,
        department="game",
        poster=image_ref(game.get("cover")),
        popularity=float(game.get("total_rating_count") or 0),
        vote_average=_rating(game.get("total_rating")),
        vote_count=int(game.get("total_rating_count") or 0),
    )


def told(game: Mapping[str, Any]) -> bool:
    """A game told in its franchise: not a version of another, nor a DLC, a bundle, an update…"""
    kind = game.get("game_type")
    kind = kind.get("id") if isinstance(kind, Mapping) else kind
    return not game.get("version_parent") and (kind is None or kind in GAME_TYPES)


def map_details(game: Any) -> GameDetails | None:
    if not isinstance(game, Mapping) or not game.get("id") or not game.get("name"):
        return None
    released = _date(game.get("first_release_date"))
    companies = [c for c in game.get("involved_companies") or [] if isinstance(c, Mapping)]
    names: dict[str, str] = {}
    for local in game.get("game_localizations") or []:
        region = ((local or {}).get("region") or {}).get("identifier")
        if region and local.get("name"):
            names.setdefault(str(region)[:20], str(local["name"])[:300])
    for alternative in game.get("alternative_names") or []:
        comment = str((alternative or {}).get("comment") or "").strip()
        if comment and alternative.get("name"):
            names.setdefault(comment[:60], str(alternative["name"])[:300])
    trailer = next(
        (
            str(v["video_id"])[:20]
            for v in game.get("videos") or []
            if isinstance(v, Mapping) and v.get("video_id")
        ),
        None,
    )
    images = [
        ref
        for ref in (image_ref(i) for key in ("artworks", "screenshots") for i in game.get(key) or [])
        if ref
    ]
    return GameDetails(
        ref=str(game["id"]),
        title=str(game["name"])[:300],
        summary=str(game.get("summary") or "").strip()[:6000] or None,
        storyline=str(game.get("storyline") or "").strip()[:6000] or None,
        year=released.year if released else None,
        release_date=released.date().isoformat() if released else None,
        cover=image_ref(game.get("cover")),
        images=list(dict.fromkeys(images))[:IMAGES],
        genres=_names(game.get("genres")),
        themes=_names(game.get("themes")),
        modes=_names(game.get("game_modes")),
        platforms=_names(game.get("platforms")),
        developers=_names([c.get("company") for c in companies if c.get("developer")]),
        publishers=_names([c.get("company") for c in companies if c.get("publisher")]),
        franchises=_names([*(game.get("franchises") or []), *(game.get("collections") or [])]),
        names=names,
        rating=_rating(game.get("total_rating")),
        votes=int(game.get("total_rating_count") or 0),
        trailer=trailer if trailer and re.fullmatch(r"[A-Za-z0-9_-]{6,20}", trailer) else None,
    )


def fold(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


class IgdbConnector(HttpConnector):
    key = "igdb"
    name = "IGDB"
    description = "The game database: a franchise's games and a game's sheet, with their images."
    icon = "gamepad"
    category = "metadata"
    config_schema: type[BaseModel] = IgdbConfig
    secret_fields: frozenset[str] = frozenset({"client_secret"})
    provides: Sequence[CapabilityBinding] = (binding(GAME_DATABASE), binding(HEALTH_PROBE))
    status_path = API + "platforms"
    public_path = None

    def token_client(self, service: ServiceHandle) -> ConnectorHttpClient:
        """Twitch's token endpoint (a host of its own)."""
        return ConnectorHttpClient(AUTH_HOST, timeout_seconds=10, retries=1)

    async def token(self, service: ServiceHandle, *, fresh: bool = False) -> str:
        client_id = str(service.config.get("client_id") or "")
        secret = service.secrets.get("client_secret", "").strip()
        if not client_id or not secret:
            raise ProviderAuthError("IGDB needs a Client ID and a Client Secret")
        key = (str(service.config.get("base_url") or ""), client_id)
        kept = _TOKENS.get(key)
        if kept is not None and not fresh and kept[0] > time.time():
            return kept[1]
        try:
            response = await self.token_client(service).request(
                "POST",
                AUTH_PATH,
                params={"client_id": client_id, "client_secret": secret, "grant_type": "client_credentials"},
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            )
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code in (400, 401, 403):
            raise ProviderAuthError("Twitch refused the Client ID or the Client Secret")
        if response.status_code >= 400:
            raise ConnectionError(f"Twitch answered HTTP {response.status_code}")
        try:
            answer = response.json()
        except ValueError as exc:
            raise InvalidPayload("Twitch did not answer with JSON") from exc
        token = answer.get("access_token") if isinstance(answer, Mapping) else None
        if not isinstance(token, str) or not token:
            raise InvalidPayload("Twitch gave no access token")
        lasts = answer.get("expires_in")
        lasts = int(lasts) if isinstance(lasts, int) and lasts > 0 else 3600
        _TOKENS[key] = (time.time() + max(60, lasts - 300), token)  # renewed before it expires
        return token

    async def query(self, service: ServiceHandle, endpoint: str, body: str, *, again: bool = True) -> Any:
        """An Apicalypse query on one of IGDB's endpoints; a refused token renewed once."""
        token = await self.token(service)
        headers = {
            "Client-ID": str(service.config.get("client_id") or ""),
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "text/plain",
            "User-Agent": USER_AGENT,
        }
        try:
            response = await self._http(service).request(
                "POST", API + endpoint, content=body.encode(), headers=headers
            )
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code in (401, 403):
            if again:
                await self.token(service, fresh=True)
                return await self.query(service, endpoint, body, again=False)
            raise ProviderAuthError("IGDB refused the token")
        if response.status_code == 404:
            raise ProviderNotFound("IGDB has no such endpoint")
        if response.status_code == 429:
            raise ConnectionError("IGDB asks to slow down (4 requests a second)")
        if response.status_code >= 400:
            raise ConnectionError(f"IGDB answered HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise InvalidPayload("IGDB did not answer with JSON") from exc

    async def get_json(self, service: ServiceHandle, path: str, **params: Any) -> Any:
        """The status (the connection test, the health probe): a one-row read of the platforms."""
        return await self.query(service, "platforms", STATUS)

    def describe(self, status: Any) -> str:
        if not isinstance(status, list):
            raise InvalidPayload("not IGDB")
        return "IGDB"

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == GAME_DATABASE:
            return _Games(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None


class _Games:
    def __init__(self, connector: IgdbConnector, service: ServiceHandle) -> None:
        self.connector = connector
        self.service = service
        self.images = ConnectorHttpClient(IMAGE_HOST, timeout_seconds=15, max_response_bytes=8 * 1024 * 1024)

    async def _kept(self, key: str, make: Any) -> Any:
        slot = (self.service.service_id, key)
        kept = _KEPT.get(slot)
        if kept is not None and time.monotonic() - kept[0] < KEPT_SECONDS:
            return kept[1]
        found = await make()
        if len(_KEPT) > 2000:
            _KEPT.clear()
        _KEPT[slot] = (time.monotonic(), found)
        return found

    async def franchise(self, name: str, known: Sequence[str]) -> GameFranchise | None:
        key = f"franchise|{fold(name)}|{','.join(sorted(known))}"
        found: GameFranchise | None = await self._kept(key, lambda: self._franchise(name, known))
        return found

    async def _franchise(self, name: str, known: Sequence[str]) -> GameFranchise | None:
        # a franchise (Zelda) or a series (IGDB's « collections »: The Legend of Zelda), of that name
        body = _FRANCHISE.format(name=quoted(name), limit=CANDIDATES)
        found = await asyncio.gather(
            self.connector.query(self.service, "franchises", body),
            self.connector.query(self.service, "collections", body),
        )
        candidates = [
            (endpoint, c)
            for endpoint, answer in zip(("franchises", "collections"), found, strict=True)
            for c in answer or []
            if isinstance(c, Mapping) and c.get("id") and c.get("name")
        ]
        if not candidates:
            return None
        mine = {int(ref) for ref in known if str(ref).isdigit()}

        def games_of(candidate: Mapping[str, Any]) -> list[int]:
            return [g for g in candidate.get("games") or [] if isinstance(g, int)]

        def shared(item: tuple[str, Mapping[str, Any]]) -> int:
            return len(mine & set(games_of(item[1])))

        best = max(candidates, key=shared)
        if not shared(best):  # else the one of that very name with the most games
            named = [c for c in candidates if fold(str(c[1]["name"])) == fold(name)]
            if not named:
                return None
            best = max(named, key=lambda c: len(games_of(c[1])))
        endpoint, chosen = best
        ids = games_of(chosen)[:GAMES]
        games: list[Any] = []
        if ids:
            games = await self.connector.query(
                self.service, "games", _GAMES.format(ids=",".join(map(str, ids)), limit=GAMES)
            )
        credits = [map_game(g) for g in games or [] if isinstance(g, Mapping) and told(g)]
        kept = sorted(
            (c for c in credits if c is not None), key=lambda c: (c.year is None, c.year or 0, c.title)
        )
        return GameFranchise(
            ids={"igdb": f"{endpoint}:{chosen['id']}"}, name=str(chosen["name"])[:200], games=kept
        )

    async def game(self, ref: str) -> GameDetails | None:
        if not ref.isdigit():
            return None
        found: GameDetails | None = await self._kept(f"game|{ref}", lambda: self._game(ref))
        return found

    async def _game(self, ref: str) -> GameDetails | None:
        answer = await self.connector.query(self.service, "games", _GAME.format(id=int(ref)))
        return map_details(answer[0]) if isinstance(answer, list) and answer else None

    async def image(self, ref: str, size: str) -> bytes:
        if not IMAGE_ID.fullmatch(ref) or size not in SIZES:
            raise InvalidPayload("unexpected image reference")
        try:
            response = await self.images.get(
                f"/igdb/image/upload/{SIZES[size]}/{ref}.jpg", headers={"User-Agent": USER_AGENT}
            )
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code >= 400:
            raise ConnectionError(f"IGDB's images answered HTTP {response.status_code}")
        return response.content
