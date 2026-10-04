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

PAGE = 250
COVER = re.compile(r"^(?!.*\.\.)[A-Za-z0-9_./ -]{1,300}$")


class RommConfig(BaseConfig):
    username: str = Field(min_length=1, max_length=128, title="Username")


def cover_path(ref: str) -> str:
    """The RomM path of a cover; refuses anything that is not a plain relative resource path."""
    path = ref.lstrip("/")
    if not COVER.fullmatch(path):
        raise InvalidPayload("unexpected cover path")
    return f"/{path}" if path.startswith("assets/") else f"/assets/romm/resources/{path}"


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
        while True:
            page = await self.get_json(ctx.service, "/api/roms", limit=PAGE, offset=offset, order_by="name")
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
                cover = game.get("path_cover_large") or game.get("path_cover_l")
                released = parse_time(game.get("first_release_date"))
                payload = {
                    "title": str(title)[:500],
                    "ids": {"igdb": str(game["igdb_id"])} if game.get("igdb_id") else {},
                    "year": released.year if released else None,
                    "overview": (game.get("summary") or "")[:5000] or None,
                    "genres": [
                        g
                        for g in [
                            game.get("platform_name") or game.get("platform_display_name"),
                            *(game.get("genres") or []),
                        ]
                        if isinstance(g, str) and g
                    ][:30],
                    "image": str(cover).split("?")[0] if cover else None,
                }
                yield self.record(
                    ctx.service,
                    safe_id(game.get("id")),
                    "game",
                    payload,
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
