"""``plex`` connector: Plex Media Server.

* ``media.library`` (sync): every movie, show, season, episode, album and track of the server's
  libraries (``/library/sections/<id>/all?type=…`` paged with ``X-Plex-Container-*``), with external ids
  from ``Guid`` (``tmdb://``, ``imdb://``, ``tvdb://``).
* ``media.playback``: live sessions (``/status/sessions``) and the watch history
  (``/status/sessions/history/all``).
* ``media.activity_history`` (027): the whole watch history, paged oldest first, for the statistics. When
  Tautulli watches the same server its richer rows win (same ``plex`` family, higher priority).
* ``service.health_probe``: an authenticated ``/`` round trip.

Authentication uses the server's ``X-Plex-Token`` (Plex Web → any item → *Get Info* → *View XML*: the
``X-Plex-Token`` parameter of the address, or ``Preferences.xml`` → ``PlexOnlineToken``).
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from typing import Any

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
    LIBRARY,
    PLAYBACK,
    ActivityPage,
    ServiceAccount,
    SourceActivity,
    SourceHistoryItem,
    SourcePlayback,
)
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import HttpConnector, _Probe, binding, parse_time, safe_id

PAGE = 200
# Plex metadata type numbers per section type, and the Media kind each becomes.
SECTION_TYPES: dict[str, tuple[tuple[int, str], ...]] = {
    "movie": ((1, "movie"),),
    "show": ((2, "series"), (3, "season"), (4, "episode")),
    "artist": ((9, "album"), (10, "track")),
}
KINDS = {
    "movie": "movie",
    "show": "series",
    "season": "season",
    "episode": "episode",
    "album": "album",
    "track": "track",
}


def _container(document: Any) -> Mapping[str, Any]:
    if not isinstance(document, Mapping) or not isinstance(document.get("MediaContainer"), Mapping):
        raise InvalidPayload("not a Plex MediaContainer")
    container: Mapping[str, Any] = document["MediaContainer"]
    return container


def _ids(item: Mapping[str, Any]) -> dict[str, str]:
    ids: dict[str, str] = {}
    for guid in item.get("Guid") or []:
        scheme, _, value = str(guid.get("id", "")).partition("://")
        if scheme in ("tmdb", "imdb", "tvdb") and value:
            ids[scheme] = value
    return ids


def _parent(item: Mapping[str, Any], kind: str) -> str | None:
    if kind in ("season", "episode", "track") and item.get("parentRatingKey"):
        return str(item["parentRatingKey"])
    return None


def _seconds(ms: Any) -> float | None:
    return round(ms / 1000, 1) if isinstance(ms, int | float) and ms > 0 else None


class PlexConnector(HttpConnector):
    key = "plex"
    name = "Plex"
    description = "Your Plex Media Server: films, series, music and what is playing."
    icon = "film"
    category = "media"
    secret_fields: frozenset[str] = frozenset({"token"})
    provides: Sequence[CapabilityBinding] = (
        binding(LIBRARY, syncable=True),
        binding(PLAYBACK),
        binding(HEALTH_PROBE),
        binding(ACCOUNTS),
        binding(ACTIVITY_HISTORY),
    )
    status_path = "/"
    public_path = "/identity"

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        return {
            "X-Plex-Token": service.secrets.get("token", ""),
            "X-Plex-Client-Identifier": "portalab",
            "X-Plex-Product": "Portalab",
        }

    def describe(self, status: Any) -> str:
        container = _container(status)
        if "version" not in container:
            raise InvalidPayload("not a Plex server root")
        return f"{container.get('friendlyName') or self.name} (Plex {container['version']})"

    def looks_like_us(self, public: Any) -> bool:
        try:
            return "machineIdentifier" in _container(public)
        except InvalidPayload:
            return False

    async def sync(
        self, ctx: SyncContext, cursor: Mapping[str, Any] | None
    ) -> AsyncIterator[SourceRecord | SyncProgress]:
        service = ctx.service
        sections = _container(await self.get_json(service, "/library/sections")).get("Directory") or []
        count = 0
        total = 0
        for section in sections:  # sizes first, for the progress bar (one tiny request per type)
            section_id = safe_id(section.get("key"))
            for type_number, _kind in SECTION_TYPES.get(str(section.get("type")), ()):
                head = _container(
                    await self.request(
                        service,
                        "GET",
                        f"/library/sections/{section_id}/all",
                        params={"type": type_number},
                        headers={"X-Plex-Container-Start": "0", "X-Plex-Container-Size": "0"},
                    )
                )
                total += int(head.get("totalSize") or head.get("size") or 0)
        yield SyncProgress(cursor={}, total=total)
        for section in sections:
            section_id = safe_id(section.get("key"))
            for type_number, kind in SECTION_TYPES.get(str(section.get("type")), ()):
                start = 0
                while True:
                    page = _container(
                        await self.request(
                            service,
                            "GET",
                            f"/library/sections/{section_id}/all",
                            params={"type": type_number, "includeGuids": 1},
                            headers={
                                "X-Plex-Container-Start": str(start),
                                "X-Plex-Container-Size": str(PAGE),
                            },
                        )
                    )
                    items = page.get("Metadata") or []
                    for item in items:
                        if not item.get("title"):
                            continue
                        key = safe_id(item.get("ratingKey"))
                        payload = {
                            "title": str(item["title"])[:500],
                            "original_title": item.get("originalTitle"),
                            "ids": _ids(item),
                            "parent": _parent(item, kind),
                            "position": item.get("index"),
                            "year": item.get("year"),
                            "overview": (item.get("summary") or "")[:5000] or None,
                            "genres": [g.get("tag") for g in item.get("Genre") or [] if g.get("tag")][:30],
                            "people": [r.get("tag") for r in item.get("Role") or [] if r.get("tag")][:50],
                            "duration_s": _seconds(item.get("duration")),
                            "image": key if item.get("thumb") else None,
                        }
                        yield self.record(service, key, kind, payload, parse_time(item.get("addedAt")))
                        count += 1
                    start += len(items)
                    total = int(page.get("totalSize") or page.get("size") or 0)
                    if not items or start >= total:
                        break
        yield SyncProgress(cursor={"items": count})

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == LIBRARY:
            return _Library(self, service)
        if capability == PLAYBACK:
            return _Playback(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        if capability == ACCOUNTS:
            return _Accounts(self, service)
        if capability == ACTIVITY_HISTORY:
            return _History(self, service)
        return None


class _Library:
    def __init__(self, connector: PlexConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def fetch_image(self, ref: str) -> bytes:
        return await self.connector.get_bytes(self.service, f"/library/metadata/{safe_id(ref)}/thumb")


class _Playback:
    def __init__(self, connector: PlexConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def now_playing(self) -> Sequence[SourcePlayback]:
        container = _container(await self.connector.get_json(self.service, "/status/sessions"))
        sessions = []
        for item in container.get("Metadata") or []:
            player = item.get("Player") or {}
            user = item.get("User") or {}
            state = player.get("state")
            sessions.append(
                SourcePlayback(
                    session_key=str(item.get("sessionKey")),
                    state=state if state in ("playing", "paused", "buffering") else "playing",
                    kind=KINDS.get(str(item.get("type")), "movie"),
                    title=str(item.get("grandparentTitle") or item.get("title") or "?"),
                    external_user_id=str(user["id"]) if user.get("id") else None,
                    item_external_id=item.get("ratingKey"),
                    ids=_ids(item),
                    position_s=_seconds(item.get("viewOffset")) or 0.0,
                    duration_s=_seconds(item.get("duration")),
                    device=player.get("title") or player.get("device"),
                )
            )
        return sessions

    async def recent_history(self, since: datetime) -> Sequence[SourceHistoryItem]:
        container = _container(
            await self.connector.get_json(
                self.service,
                "/status/sessions/history/all",
                sort="viewedAt:desc",
                **{"viewedAt>": int(since.timestamp())},
            )
        )
        history = []
        for item in container.get("Metadata") or []:
            viewed = parse_time(item.get("viewedAt"))
            if viewed is None or viewed < since:
                continue
            duration = _seconds(item.get("duration"))
            history.append(
                SourceHistoryItem(
                    external_user_id=str(item.get("accountID")),
                    kind=KINDS.get(str(item.get("type")), "movie"),
                    title=str(item.get("grandparentTitle") or item.get("title") or "?"),
                    occurred_at=viewed,
                    position_s=duration or 0.0,
                    duration_s=duration,
                    item_external_id=item.get("ratingKey"),
                )
            )
        return sorted(history, key=lambda h: h.occurred_at)


def map_history(item: Mapping[str, Any]) -> SourceActivity | None:
    viewed = parse_time(item.get("viewedAt"))
    account = item.get("accountID")
    kind = "live" if item.get("live") in (1, "1", True) else KINDS.get(str(item.get("type")))
    if viewed is None or account in (None, "") or kind not in ("movie", "episode", "track", "live"):
        return None
    key = str(item.get("historyKey") or "").rstrip("/").rsplit("/", 1)[-1]
    ref = key or f"{item.get('ratingKey')}-{int(viewed.timestamp())}-{account}"
    duration = _seconds(item.get("duration"))
    parent = item.get("grandparentTitle") if kind in ("episode", "track") else None
    return SourceActivity(
        ref=ref[:200],
        external_user_id=str(account),
        kind=kind,
        title=str(item.get("title") or "?")[:500],
        started_at=viewed,
        stopped_at=viewed,
        watched_s=duration or 0.0,
        duration_s=duration,
        progress=1.0,
        item_external_id=str(item["ratingKey"]) if item.get("ratingKey") else None,
        parent_title=str(parent)[:500] if parent else None,
        ids=_ids(item),
        year=item.get("year") if isinstance(item.get("year"), int) else None,
        family="plex",
        priority=10,
    )


class _History:
    def __init__(self, connector: PlexConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def history(self, *, since: datetime | None, cursor: str | None) -> ActivityPage:
        start = int(cursor) if cursor and cursor.isdigit() else 0
        params: dict[str, Any] = {"sort": "viewedAt:asc"}
        if since is not None:
            params["viewedAt>"] = int(since.timestamp()) - 1
        container = _container(
            await self.connector.request(
                self.service,
                "GET",
                "/status/sessions/history/all",
                params=params,
                headers={"X-Plex-Container-Start": str(start), "X-Plex-Container-Size": str(PAGE)},
            )
        )
        rows = container.get("Metadata") or []
        items = [a for a in (map_history(r) for r in rows) if a is not None]
        total = int(container.get("totalSize") or 0)
        done = len(rows) < PAGE or (total and start + len(rows) >= total)
        return ActivityPage(
            items=items,
            cursor=None if done else str(start + len(rows)),
            total=total or None,
            position=start + len(rows),
        )


class _Accounts:
    """The accounts known to the server (owner, home and shared users): ids match sessions and history."""

    def __init__(self, connector: PlexConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def list_accounts(self) -> Sequence[ServiceAccount]:
        container = _container(await self.connector.get_json(self.service, "/accounts"))
        return [
            ServiceAccount(external_id=str(a["id"]), username=a.get("name"), display_name=a.get("name"))
            for a in container.get("Account") or []
            if a.get("id") and a.get("name")  # id 0 is the anonymous system account
        ]
