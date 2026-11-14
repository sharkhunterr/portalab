"""``romm`` connector: RomM, the retro games library manager.

* ``media.library`` (sync): every game (ROM) with its platform as a genre, IGDB id and cover — paged
  through ``/api/roms`` (both the list answer of RomM 3 and the ``{items, total}`` page of RomM 4); #351:
  how long it takes to play by style (HowLongToBeat, when RomM knows it), its main story as its length.
* ``service.health_probe``: an authenticated ``/api/users/me`` round trip.
* ``media.activity_history`` (#190): what the configured account played — each play session with its length
  (``/api/play-sessions``) and each game it played, dated by its last play and finished or not
  (``rom_user``: ``/api/roms?last_played``). RomM tells these to the account itself only: the member linked to
  that account gets them.

Authentication uses a RomM account (an administrator or a dedicated read-only user): HTTP Basic with its
username (configuration) and password (secret).
"""

import base64
import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, Field

from portalab.capabilities.connector_http import ConnectorHttpError
from portalab.capabilities.connector_sdk import (
    CapabilityBinding,
    ServiceHandle,
    SourceRecord,
    SyncContext,
    SyncProgress,
)
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.household import RATING_WORDS, age_of
from portalab.capabilities.media import (
    ACCOUNTS,
    ACTIVITY_HISTORY,
    ITEM_LINKS,
    LIBRARY,
    PLAY_STYLES,
    ActivityPage,
    ServiceAccount,
    SourceActivity,
    StreamBody,
)
from portalab.capabilities.results import InvalidPayload, ProviderAuthError, ProviderNotFound
from portalab.capabilities.retro import (
    RETRO_SOURCE,
    FileKind,
    LinkStart,
    LinkToken,
    MemberAccount,
    RetroFirmware,
    RetroGame,
    SaveKind,
)
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
# 419: the emulator's files under RomM's EmulatorJS data folder (loader, cores, localisation…)
EMULATOR_FILE = re.compile(r"^(?!.*\.\.)[A-Za-z0-9_./-]{1,200}$")
FILE_NAME = re.compile(r"^[^/\\\x00]{1,400}$")
PORTAL_CLIENT = "portalab"
# 426: what a member's own token may do — who they are, their play sessions, saves and states, the device
MEMBER_SCOPES = ("me.read", "roms.user.write", "assets.read", "assets.write", "devices.read", "devices.write")
PENDING = ("pending", "slow_down", "slow down")
PORTAL_DEVICE = {
    "name": "Portalab",
    "client": PORTAL_CLIENT,
    "platform": "web",
}  # 419: the sessions played here


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


def play_times(game: Mapping[str, Any]) -> dict[str, dict[str, float | int | None]]:
    """#351: how long the game takes by play style, in seconds, with how many players told it (RomM's
    HowLongToBeat block — none for many games)."""
    raw = game.get("hltb_metadata")
    block: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    out: dict[str, dict[str, float | int | None]] = {}
    for style in PLAY_STYLES:
        seconds, players = block.get(style), block.get(f"{style}_count")
        if isinstance(seconds, int | float) and not isinstance(seconds, bool) and 0 < seconds <= 36_000_000:
            count = (
                players
                if isinstance(players, int) and not isinstance(players, bool) and players >= 0
                else None
            )
            out[style] = {"seconds": float(seconds), "players": count}
    return out


def game_rating(game: Mapping[str, Any]) -> str | None:
    """Issue 421: a game's strictest age rating among IGDB's (PEGI, ESRB, USK, CERO…, as RomM keeps them:
    ``{"category": "PEGI", "rating": "Twelve"}``), as its label (« PEGI 12 », « ESRB T »); ``None``: unrated
    (most games older than the rating boards)."""
    found: list[tuple[int, str]] = []
    for source in (game.get("igdb_metadata"), game.get("metadatum")):
        if not isinstance(source, Mapping) or not isinstance(source.get("age_ratings"), list):
            continue
        for item in source["age_ratings"]:
            if not isinstance(item, Mapping) or not item.get("category") or not item.get("rating"):
                continue  # a bare rating (« T », « M ») says nothing without its board
            label = f"{str(item['category']).strip()[:20]} {str(item['rating']).strip()[:20]}"
            label = " ".join(RATING_WORDS.get(w.upper(), w) for w in label.split())
            age = age_of(label)
            if age is not None:
                found.append((age, label))
    return max(found)[1] if found else None


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
    times = play_times(game)
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
        # #351: its length is its main story's; every style's for its page
        "duration_s": times["main_story"]["seconds"] if "main_story" in times else None,
        "play_times": times or None,
        "content_rating": game_rating(game),  # issue 421: a household profile's age limit holds to it
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
        binding(RETRO_SOURCE),  # 419: its games played in the portal (RomM's own EmulatorJS)
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
        if capability == RETRO_SOURCE:
            return _Retro(self, service)
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
        portal = await self._portal_devices()
        offset = 0
        while True:
            params: dict[str, Any] = {"limit": SESSIONS_PAGE, "offset": offset}
            if since is not None:
                params["start_after"] = since.isoformat()
            sessions = _page(await self.connector.get_json(self.service, "/api/play-sessions", **params))
            for session in sessions:
                if session.get("device_id") is not None and str(session["device_id"]) in portal:
                    continue  # 419: played in the portal — the portal counted it already
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

    async def _portal_devices(self) -> set[str]:
        try:
            devices = await self.connector.get_json(self.service, "/api/devices")
        except (ConnectionError, InvalidPayload, ProviderNotFound):
            return set()  # a RomM without devices: no session of the portal's either
        return {
            str(d["id"])
            for d in (devices if isinstance(devices, list) else [])
            if isinstance(d, Mapping) and d.get("id") is not None and d.get("client") == PORTAL_CLIENT
        }


class _Retro:
    """419: a game played in the portal — its ROM, its platform's firmware and RomM's EmulatorJS, relayed as
    RomM sends them; the session told back to RomM, which keeps the account's play time."""

    def __init__(self, connector: RommConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def game(self, external_id: str) -> RetroGame | None:
        rom = await self.connector.get_json(self.service, f"/api/roms/{safe_id(external_id)}")
        if not isinstance(rom, Mapping) or rom.get("id") is None or not rom.get("fs_name"):
            return None
        size = rom.get("fs_size_bytes")
        return RetroGame(
            external_id=str(rom["id"]),
            title=str(rom.get("name") or rom.get("fs_name"))[:500],
            platform=str(rom.get("platform_slug") or "").lower(),
            platform_id=str(rom.get("platform_id") or ""),
            file_name=str(rom["fs_name"]),
            size=int(size) if isinstance(size, int) else None,
            multi=bool(rom.get("has_multiple_files")),
            present=not rom.get("missing_from_fs") and rom.get("has_file_on_disk") is not False,
        )

    async def firmware(self, platform_id: str) -> Sequence[RetroFirmware]:
        if not platform_id.isdigit():
            return []
        items = await self.connector.get_json(self.service, "/api/firmware", platform_id=platform_id)
        return [
            RetroFirmware(id=str(f["id"]), file_name=str(f["file_name"]), verified=bool(f.get("is_verified")))
            for f in (items if isinstance(items, list) else [])
            if isinstance(f, Mapping) and f.get("id") is not None and f.get("file_name")
        ]

    def _path(self, kind: FileKind, ref: str, name: str) -> str:
        if kind == "emulator":
            if not EMULATOR_FILE.fullmatch(name):
                raise ProviderNotFound("no such emulator file")
            if name.startswith("ruffle/"):  # 421: Ruffle (Flash), as RomM serves it
                return f"/assets/{name}"
            return f"/assets/emulatorjs/data/{name.removeprefix('emulatorjs/')}"
        if not FILE_NAME.fullmatch(name):
            raise ProviderNotFound("no such file")
        folder = "roms" if kind == "rom" else "firmware"
        return f"/api/{folder}/{safe_id(ref)}/content/{quote(name, safe='')}"

    @asynccontextmanager
    async def open(
        self, kind: FileKind, ref: str, name: str, range_header: str | None = None
    ) -> AsyncIterator[StreamBody]:
        path = self._path(kind, ref, name)
        sent = {"Accept-Encoding": "identity", **({"Range": range_header} if range_header else {})}
        if kind != "emulator":
            sent.update(self.connector.auth_headers(self.service))
        params = {"purpose": "play"} if kind == "rom" else None  # RomM counts a player's load, not a download
        http = self.connector._http(self.service)
        async with http.stream("GET", path, headers=sent, params=params, read_timeout=120) as answer:
            if answer.status_code in (401, 403):
                raise ProviderAuthError("RomM refused this account")
            if answer.status_code in (404, 410):
                raise ProviderNotFound("no such file")
            if answer.status_code == 416:
                raise InvalidPayload("range not satisfiable")
            if answer.status_code >= 400:
                raise ConnectionError(f"RomM answered HTTP {answer.status_code}")
            length = answer.headers.get("content-length")
            encoded = answer.headers.get("content-encoding", "identity") != "identity"
            yield StreamBody(
                status=answer.status_code,
                content_type=answer.headers.get("content-type") or "application/octet-stream",
                length=int(length) if length and length.isdigit() and not encoded else None,
                chunks=answer.chunks,
                content_range=answer.headers.get("content-range"),
            )

    async def record_session(
        self,
        external_id: str,
        started_at: datetime,
        ended_at: datetime,
        duration_ms: int,
        account: MemberAccount | None = None,
    ) -> None:
        if not external_id.isdigit():
            return
        await self.connector.request(
            self.service,
            "POST",
            "/api/play-sessions",
            headers=_as(account),
            json_body={
                "device_id": account.device_id if account is not None else await self._device(),
                "sessions": [
                    {
                        "rom_id": int(external_id),
                        "start_time": started_at.isoformat(),
                        "end_time": ended_at.isoformat(),
                        "duration_ms": max(0, duration_ms),
                    }
                ],
            },
        )

    async def put_file(
        self,
        kind: SaveKind,
        external_id: str,
        core: str,
        file_name: str,
        data: bytes,
        screenshot: bytes | None,
        labels: Sequence[str],
        remote_id: str | None = None,
        account: MemberAccount | None = None,
    ) -> str:
        """420: RomM's ``/api/saves`` or ``/api/states`` — the copy replaced in place when RomM still has it,
        else a new one; labelled (the portal's account in RomM is everyone's)."""
        folder, field = ("saves", "saveFile") if kind == "save" else ("states", "stateFile")
        files: dict[str, tuple[str, bytes, str]] = {field: (file_name, data, "application/octet-stream")}
        if screenshot:
            files["screenshotFile"] = (f"{file_name}.png", screenshot, "image/png")
        made: Any = None
        if remote_id and remote_id.isdigit():
            made = await self._multipart("PUT", f"/api/{folder}/{remote_id}", files, None, account)
        if made is None:
            if not external_id.isdigit():
                raise ProviderNotFound("no such game")
            made = await self._multipart(
                "POST", f"/api/{folder}", files, {"rom_id": external_id, "emulator": core[:64]}, account
            )
        if not isinstance(made, Mapping) or made.get("id") is None:
            raise InvalidPayload(f"unexpected /api/{folder} payload")
        found = str(made["id"])
        await self.connector.request(
            self.service,
            "PUT",
            f"/api/{folder}/{safe_id(found)}/labels",
            headers=_as(account),
            json_body={"labels": [label[:64] for label in labels if label][:8]},
        )
        return found

    async def delete_file(self, kind: SaveKind, remote_id: str, account: MemberAccount | None = None) -> None:
        if not remote_id.isdigit():
            return
        folder = "saves" if kind == "save" else "states"
        try:
            await self.connector.request(
                self.service,
                "POST",
                f"/api/{folder}/delete",
                headers=_as(account),
                json_body={folder: [int(remote_id)]},
            )
        except ProviderNotFound:
            return  # gone already

    async def _multipart(
        self,
        method: str,
        path: str,
        files: Mapping[str, tuple[str, bytes, str]],
        params: Mapping[str, str] | None,
        account: MemberAccount | None = None,
    ) -> Any:
        """A file sent to RomM (``None``: RomM no longer has the item replaced)."""
        try:
            answer = await self.connector._http(self.service).request(
                method,
                path,
                headers={
                    "Accept": "application/json",
                    **self.connector.auth_headers(self.service),
                    **_as(account),
                },
                files=dict(files),
                **({"params": dict(params)} if params else {}),
            )
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if answer.status_code == 404 and method == "PUT":
            return None
        if answer.status_code in (401, 403):
            raise ProviderAuthError("RomM refused this account")
        if answer.status_code >= 400:
            raise ConnectionError(f"RomM answered HTTP {answer.status_code}")
        try:
            return answer.json()
        except ValueError as exc:
            raise InvalidPayload("RomM did not answer with JSON") from exc

    # --- 426: a member's own account ----------------------------------------------------------------------
    async def begin_link(self, device: str, name: str) -> LinkStart:
        """RomM's device authorisation: the member approves the code in RomM, signed in as themselves."""
        answer = await self._open_call(
            "/api/auth/device/init",
            {
                "client_device_identifier": device[:255],
                "name": name[:255] or "Portalab",
                "client": PORTAL_CLIENT,
                "platform": "web",
                "requested_scopes": list(MEMBER_SCOPES),
            },
        )
        body = _json(answer)
        if answer.status_code >= 400 or not isinstance(body, Mapping) or not body.get("device_code"):
            raise ConnectionError(f"RomM answered HTTP {answer.status_code}")
        path = str(body.get("verification_path_complete") or body.get("verification_path") or "/pair/device")
        return LinkStart(
            device_code=str(body["device_code"]),
            user_code=str(body.get("user_code") or ""),
            path=path if path.startswith("/") else f"/{path}",
            expires_in=int(body.get("expires_in") or 600),
            interval=max(2, int(body.get("interval") or 5)),
        )

    async def finish_link(self, device_code: str) -> LinkToken | None:
        answer = await self._open_call("/api/auth/device/token", {"device_code": device_code})
        body = _json(answer)
        if answer.status_code >= 500:
            raise ConnectionError(f"RomM answered HTTP {answer.status_code}")
        if answer.status_code >= 400:
            said = json.dumps(body).lower() if body is not None else ""
            if any(word in said for word in PENDING) or answer.status_code == 428:
                return None  # the member has not approved it yet
            raise ProviderAuthError("RomM refused this authorisation")
        if not isinstance(body, Mapping) or not body.get("access_token"):
            raise InvalidPayload("unexpected device token payload")
        token = str(body["access_token"])
        me = await self.connector.request(
            self.service, "GET", "/api/users/me", headers=_as(MemberAccount(token))
        )
        return LinkToken(
            token=token,
            device_id=str(body["device_id"]) if body.get("device_id") else None,
            scopes=tuple(str(scope) for scope in body.get("scopes") or ()),
            expires_at=parse_time(body.get("expires_at")),
            username=str(me.get("username"))[:128]
            if isinstance(me, Mapping) and me.get("username")
            else None,
        )

    async def end_link(self, account: MemberAccount) -> None:
        if not account.device_id:
            return
        try:  # the device goes, and the token bound to it
            await self.connector.request(
                self.service,
                "DELETE",
                f"/api/devices/{quote(account.device_id, safe='')}",
                headers=_as(account),
            )
        except (ProviderNotFound, ProviderAuthError):
            return  # gone already, or the member revoked it in RomM

    async def _open_call(self, path: str, body: Mapping[str, Any]) -> Any:
        """RomM's open device endpoints, without the service's credentials (the member signs in, not it)."""
        try:
            return await self.connector._http(self.service).request(
                "POST", path, headers={"Accept": "application/json"}, json=dict(body)
            )
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc

    async def _device(self) -> str | None:
        """The portal's device in RomM (created once, found again after): its sessions are the portal's."""
        try:
            made = await self.connector.request(
                self.service,
                "POST",
                "/api/devices",
                json_body={**PORTAL_DEVICE, "allow_existing": True, "allow_duplicate": False},
            )
        except (ConnectionError, InvalidPayload, ProviderNotFound):
            return None  # a RomM without devices: the session goes without one
        found = made.get("device_id") if isinstance(made, Mapping) else None
        return str(found) if found else None


def _as(account: MemberAccount | None) -> dict[str, str]:
    """426: the member's own token in place of the service's credentials."""
    return {"Authorization": f"Bearer {account.token}"} if account is not None else {}


def _json(answer: Any) -> Any:
    try:
        return answer.json() if answer.content else None
    except ValueError:
        return None
