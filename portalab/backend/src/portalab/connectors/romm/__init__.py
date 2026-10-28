"""``romm`` connector: RomM, the retro games library manager.

* ``media.library`` (sync): every game (ROM) with its platform as a genre, IGDB id and cover — paged
  through ``/api/roms`` (both the list answer of RomM 3 and the ``{items, total}`` page of RomM 4).
* ``service.health_probe``: an authenticated ``/api/users/me`` round trip.
* ``media.activity_history`` (#190): what the configured account played — each play session with its length
  (``/api/play-sessions``) and each game it played, dated by its last play and finished or not
  (``rom_user``: ``/api/roms?last_played``). RomM tells these to the account itself only: the member linked to
  that account gets them.

Authentication uses a RomM account (an administrator or a dedicated read-only user): HTTP Basic with its
username (configuration) and password (secret).
"""

import base64
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
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
from portalab.capabilities.media import (
    ACCOUNTS,
    ACTIVITY_HISTORY,
    ITEM_LINKS,
    LIBRARY,
    ActivityPage,
    ServiceAccount,
    SourceActivity,
)
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import BaseConfig, HttpConnector, _Probe, binding, parse_time, safe_id

PAGE = 100
# 027: a RomM 4 page carries each game's full metadata — a large library's pages can weigh tens of MB; a
# page may take up to this much, and one still too big is asked again in smaller pieces
PAGE_MAX_BYTES = 32 * 1024 * 1024
SMALLEST_PAGE = 10
COVER = re.compile(r"^(?!.*\.\.)[A-Za-z0-9_./ -]{1,300}$")
SESSIONS_PAGE = 500
PLAYED_PAGE = 100
DONE = ("finished", "completed_100")  # a game the player marked finished (or completed at 100 %)


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
    metadata — and the IGDB block): year, genres (the platform first), franchises and game modes as tags
    (the first franchise as its series too), the publisher; and which copy this is (platform, regions,
    revision) when RomM holds several."""
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
    franchises = _names(pick("franchises"))
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
        "tags": [*franchises, *_names(pick("game_modes"))][:40],
        # #190: its first franchise is its series, as a book's — the games of one saga go together
        "series": franchises[0][:200] if franchises else None,
        "publisher": companies[0][:200] if companies else None,
        "people": [c[:200] for c in companies[:6]],  # the studios and publishers behind it
        "platform": str(platform)[:120] if platform else None,
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
        binding(ITEM_LINKS),  # 027: each game's page in RomM, where it is played
        binding(ACTIVITY_HISTORY, driven=True),  # #190: what the account played
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
                try:
                    payload = game_payload(game, str(title))
                except (TypeError, ValueError, KeyError, AttributeError):
                    continue  # 027: one game with odd metadata never stops the whole library
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
        if capability == ITEM_LINKS:
            return _Links()
        if capability == ACCOUNTS:
            return _Accounts(self, service)
        if capability == ACTIVITY_HISTORY:
            return _Played(self, service)
        return None


class _Covers:
    def __init__(self, connector: RommConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def fetch_image(self, ref: str) -> bytes:
        return await self.connector.get_bytes(self.service, cover_path(ref))


class _Links:
    """027: a game's page in RomM — its details, with RomM's own « Play » (in the browser when the
    platform has an emulator)."""

    async def item_path(self, external_id: str, kind: str) -> str | None:
        return f"/rom/{external_id}" if kind == "game" and external_id.isdigit() else None


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


def _page(answer: Any) -> list[Mapping[str, Any]]:
    items = answer.get("items") if isinstance(answer, Mapping) else answer
    return [i for i in items if isinstance(i, Mapping)] if isinstance(items, list) else []


def map_played(game: Mapping[str, Any], user: str) -> SourceActivity | None:
    """#190: a game the account played — a row per game and day of its last play (a later play makes another
    one); finished when its player said so. Its time comes with the play sessions."""
    raw = game.get("rom_user")
    mine: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    at = parse_time(mine.get("last_played"))
    title = game.get("name") or game.get("fs_name_no_ext")
    if at is None or game.get("id") is None or not title:
        return None
    return SourceActivity(
        ref=f"played:{safe_id(game['id'])}:{at.date().isoformat()}",
        external_user_id=user,
        kind="game",
        title=str(title)[:500],
        started_at=at,
        stopped_at=at,
        progress=1.0 if mine.get("status") in DONE else None,
        item_external_id=safe_id(game["id"]),
        ids={"igdb": str(game["igdb_id"])} if game.get("igdb_id") else {},
        platform=str(game.get("platform_display_name") or "")[:60] or None,
        family="romm",
    )


def map_session(session: Mapping[str, Any], user: str, title: str) -> SourceActivity | None:
    """#190: one play session — when, how long, of which game."""
    start, end = parse_time(session.get("start_time")), parse_time(session.get("end_time"))
    if start is None or session.get("id") is None or session.get("rom_id") is None:
        return None
    return SourceActivity(
        ref=f"session:{safe_id(session['id'])}",
        external_user_id=user,
        kind="game",
        title=title[:500],
        started_at=start,
        stopped_at=end,
        watched_s=max(0.0, float(session.get("duration_ms") or 0) / 1000),
        item_external_id=safe_id(session["rom_id"]),
        family="romm",
    )


class _Played:
    """#190: the account's games — its play sessions and the games it played (one page: a player's own)."""

    def __init__(self, connector: RommConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def history(self, *, since: datetime | None, cursor: str | None) -> ActivityPage:
        me = await self.connector.get_json(self.service, "/api/users/me")
        if not isinstance(me, Mapping) or me.get("id") is None:
            raise InvalidPayload("unexpected /users/me payload")
        user = str(me["id"])
        names: dict[str, str] = {}
        items: list[SourceActivity] = []
        offset = 0
        while True:  # the games played, the most recent first
            games = _page(
                await self.connector.get_json(
                    self.service,
                    "/api/roms",
                    last_played=True,
                    order_by="last_played",
                    order_dir="desc",
                    limit=PLAYED_PAGE,
                    offset=offset,
                )
            )
            for game in games:
                played = map_played(game, user)
                if played is None:
                    continue
                names[played.item_external_id or ""] = played.title
                if since is None or played.started_at >= since:
                    items.append(played)
            offset += len(games)
            if len(games) < PLAYED_PAGE:
                break
        offset = 0
        while True:
            params: dict[str, Any] = {"limit": SESSIONS_PAGE, "offset": offset}
            if since is not None:
                params["start_after"] = since.isoformat()
            sessions = _page(await self.connector.get_json(self.service, "/api/play-sessions", **params))
            for session in sessions:
                rom = str(session.get("rom_id"))
                if rom not in names:
                    game = await self.connector.get_json(self.service, f"/api/roms/{safe_id(rom)}")
                    names[rom] = str((game or {}).get("name") or (game or {}).get("fs_name_no_ext") or rom)
                mapped = map_session(session, user, names[rom])
                if mapped is not None:
                    items.append(mapped)
            offset += len(sessions)
            if len(sessions) < SESSIONS_PAGE:
                break
        return ActivityPage(items=items, cursor=None, total=len(items), position=len(items))
