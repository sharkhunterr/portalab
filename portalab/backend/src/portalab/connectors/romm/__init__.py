"""``romm`` connector: RomM, the retro games library manager.

* ``media.library`` (sync): every game (ROM) with its platform as a genre, IGDB id and cover — paged
  through ``/api/roms`` (both the list answer of RomM 3 and the ``{items, total}`` page of RomM 4).
* ``service.health_probe``: an authenticated ``/api/users/me`` round trip.

Authentication uses a RomM account (an administrator or a dedicated read-only user): HTTP Basic with its
username (configuration) and password (secret).
"""

import base64
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field

from portalab.capabilities.connector_sdk import (
    CapabilityBinding,
    ServiceHandle,
    SourceRecord,
    SyncContext,
    SyncProgress,
)
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import ACCOUNTS, LIBRARY, ServiceAccount
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import BaseConfig, HttpConnector, _Probe, binding, parse_time, safe_id

PAGE = 100
# 027: a RomM 4 page carries each game's full metadata — a large library's pages can weigh tens of MB; a
# page may take up to this much, and one still too big is asked again in smaller pieces
PAGE_MAX_BYTES = 32 * 1024 * 1024
SMALLEST_PAGE = 10
COVER = re.compile(r"^(?!.*\.\.)[A-Za-z0-9_./ -]{1,300}$")


class RommConfig(BaseConfig):
    username: str = Field(min_length=1, max_length=128, title="Username")


def cover_path(ref: str) -> str:
    """The RomM path of a cover; refuses anything that is not a plain relative resource path."""
    path = ref.lstrip("/")
    if not COVER.fullmatch(path):
        raise InvalidPayload("unexpected cover path")
    return f"/{path}" if path.startswith("assets/") else f"/assets/romm/resources/{path}"


def _names(values: Any) -> list[str]:
    """Names out of a RomM list — plain strings (RomM 3) or ``{name: …}`` objects (RomM 4 metadata)."""
    out: list[str] = []
    for value in values if isinstance(values, list) else []:
        name = value.get("name") if isinstance(value, Mapping) else value
        if isinstance(name, str) and name.strip() and name not in out:
            out.append(name.strip())
    return out


def game_payload(game: Mapping[str, Any], title: str) -> dict[str, Any]:
    """027: a game's metadata from RomM 3 (on the game itself) or RomM 4 (``metadatum`` — the merged
    metadata — and the IGDB block): year, genres (the platform first), franchises and game modes as tags,
    the publisher; and which copy this is (platform, regions, revision) when RomM holds several."""
    sources: list[Mapping[str, Any]] = [game]
    for block in ("metadatum", "igdb_metadata"):
        if isinstance(game.get(block), Mapping):
            sources.append(game[block])

    def pick(key: str) -> Any:
        for source in sources:
            value = source.get(key)
            if value not in (None, "", [], {}):
                return value
        return None

    platform = (
        game.get("platform_display_name") or game.get("platform_name") or game.get("platform_custom_name")
    )
    released = parse_time(pick("first_release_date"))
    cover = game.get("path_cover_large") or game.get("path_cover_l")
    companies = _names(pick("companies"))
    variant = [
        str(platform) if platform else "",
        ", ".join(_names(game.get("regions"))),
        str(game.get("revision") or ""),
    ]
    return {
        "title": title[:500],
        "ids": {"igdb": str(game["igdb_id"])} if game.get("igdb_id") else {},
        "year": released.year if released and 1950 <= released.year <= 2200 else None,
        "released": released.date().isoformat() if released and released.year >= 1950 else None,
        "overview": (game.get("summary") or "")[:5000] or None,
        "genres": [g for g in [str(platform) if platform else "", *_names(pick("genres"))] if g][:30],
        "tags": [*_names(pick("franchises")), *_names(pick("game_modes"))][:40],
        "publisher": companies[0][:200] if companies else None,
        "image": str(cover).split("?")[0] if cover else None,
        "variant": " · ".join(v for v in variant if v)[:200] or str(game.get("fs_name") or "")[:200] or None,
    }


class RommConnector(HttpConnector):
    key = "romm"
    name = "RomM"
    description = "Your retro games library: every game, its platform and its cover."
    icon = "game"
    category = "games"
    config_schema: type[BaseModel] = RommConfig
    secret_fields: frozenset[str] = frozenset({"password"})
    provides: Sequence[CapabilityBinding] = (
        binding(LIBRARY, syncable=True),
        binding(HEALTH_PROBE),
        binding(ACCOUNTS),
    )
    status_path = "/api/users/me"
    public_path = "/api/heartbeat"

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        raw = f"{service.config.get('username', '')}:{service.secrets.get('password', '')}"
        return {"Authorization": "Basic " + base64.b64encode(raw.encode()).decode()}

    def describe(self, status: Any) -> str:
        if not isinstance(status, Mapping) or "username" not in status:
            raise InvalidPayload("not a RomM user")
        return f"RomM (as {status['username']})"

    def looks_like_us(self, public: Any) -> bool:
        return isinstance(public, Mapping) and "SYSTEM" in public

    async def sync(
        self, ctx: SyncContext, cursor: Mapping[str, Any] | None
    ) -> AsyncIterator[SourceRecord | SyncProgress]:
        offset = 0
        size = PAGE
        while True:
            try:
                page = await self.request(
                    ctx.service,
                    "GET",
                    "/api/roms",
                    params={"limit": size, "offset": offset, "order_by": "name"},
                    max_bytes=PAGE_MAX_BYTES,
                )
            except ConnectionError as exc:
                if "larger than" not in str(exc) or size <= SMALLEST_PAGE:
                    raise
                size = max(SMALLEST_PAGE, size // 2)  # too heavy: the same games in smaller pages
                continue
            if isinstance(page, list):  # RomM 3: the whole list
                games, total = page, len(page)
            elif isinstance(page, Mapping) and isinstance(page.get("items"), list):
                games, total = page["items"], int(page.get("total") or 0)
            else:
                raise InvalidPayload("unexpected /roms payload")
            if offset == 0:
                yield SyncProgress(cursor={}, total=total)
            for game in games:
                title = game.get("name") or game.get("fs_name_no_ext")
                if not title:
                    continue
                yield self.record(
                    ctx.service,
                    safe_id(game.get("id")),
                    "game",
                    game_payload(game, str(title)),
                    parse_time(game.get("updated_at") or game.get("created_at")),
                )
            offset += len(games)
            if isinstance(page, list) or not games or offset >= total:
                break
        yield SyncProgress(cursor={"items": offset})

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == LIBRARY:
            return _Covers(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        if capability == ACCOUNTS:
            return _Accounts(self, service)
        return None


class _Covers:
    def __init__(self, connector: RommConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def fetch_image(self, ref: str) -> bytes:
        return await self.connector.get_bytes(self.service, cover_path(ref))


class _Accounts:
    def __init__(self, connector: RommConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def list_accounts(self) -> Sequence[ServiceAccount]:
        users = await self.connector.get_json(self.service, "/api/users")
        if not isinstance(users, list):
            raise InvalidPayload("unexpected /users payload")
        return [
            ServiceAccount(external_id=str(u["id"]), username=u.get("username"), email=u.get("email"))
            for u in users
            if u.get("id") is not None
        ]
