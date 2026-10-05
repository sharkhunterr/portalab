"""``tautulli`` connector: Tautulli, the Plex monitoring companion (API v2).

* ``media.activity_history``: every play Tautulli recorded — films, episodes, live TV and music — with
  the time actually watched, the progress reached, the player and the platform; paged oldest first for
  the backfill, then followed from the last play. Tautulli reports the same plays as Plex, so its rows
  share the ``plex`` family and win over Plex's own history (richer: duration, progress, device).
* ``service.accounts``: the Plex users Tautulli knows (ids are Plex account ids).
* ``service.health_probe``: an authenticated ``get_tautulli_info`` round trip.

Authentication uses the API key of *Settings → Web Interface → API*. Tautulli only accepts it as the
``apikey`` query parameter; the HTTP client redacts it from every error and log.
"""

import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle, TestResult
from portalab.capabilities.health import HEALTH_PROBE, ProbeResult
from portalab.capabilities.media import (
    ACCOUNTS,
    ACTIVITY_HISTORY,
    ActivityPage,
    ServiceAccount,
    SourceActivity,
)
from portalab.capabilities.results import InvalidPayload, ProviderAuthError
from portalab.connectors.http_base import HttpConnector, binding, parse_time

PAGE = 500
KINDS = {"movie": "movie", "episode": "episode", "track": "track", "clip": "other"}
GUID_SCHEMES = ("tmdb", "imdb", "tvdb")


def _float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _ids(row: Mapping[str, Any]) -> dict[str, str]:
    ids: dict[str, str] = {}
    for guid in [row.get("guid"), *(row.get("guids") or [])]:
        if isinstance(guid, str):
            scheme, _, value = guid.partition("://")
            if scheme in GUID_SCHEMES and value and scheme not in ids:
                ids[scheme] = value.split("?")[0][:200]
    return ids


def map_history_row(row: Mapping[str, Any]) -> SourceActivity | None:
    """One ``get_history`` row as a play; ``None`` for rows without a user, a time or a known type."""
    started = parse_time(row.get("started") or row.get("date"))
    ref = row.get("id") or row.get("row_id") or row.get("reference_id")
    user = row.get("user_id")
    media_type = str(row.get("media_type") or "").lower()
    if started is None or ref is None or user in (None, ""):
        return None
    kind = "live" if str(row.get("live") or "0") in ("1", "true", "True") else KINDS.get(media_type)
    if kind is None:
        return None
    stopped = parse_time(row.get("stopped"))
    watched = _float(row.get("play_duration")) or _float(row.get("duration")) or 0.0
    percent = _float(row.get("percent_complete"))
    grandparent = row.get("grandparent_title") or None
    title = row.get("title") or row.get("full_title") or "?"
    return SourceActivity(
        ref=str(ref),
        external_user_id=str(user),
        kind=kind,
        title=str(title)[:500],
        started_at=started,
        stopped_at=stopped,
        watched_s=max(0.0, watched),
        duration_s=_float(row.get("media_duration")),  # rarely given: the play length is ``duration``
        progress=min(1.0, percent / 100) if percent is not None else None,
        item_external_id=str(row["rating_key"]) if row.get("rating_key") else None,
        # live TV (027): the programme's show, when the guide names one, groups its episodes
        parent_title=str(grandparent)[:500] if grandparent and kind in ("episode", "track", "live") else None,
        ids=_ids(row),
        year=int(row["year"]) if str(row.get("year") or "").isdigit() else None,
        device=(row.get("player") or row.get("product") or None),
        platform=row.get("platform") or None,
        family="plex",
        priority=20,
    )


class TautulliConnector(HttpConnector):
    key = "tautulli"
    name = "Tautulli"
    description = "Plex watch statistics: every film, episode, live TV channel and song played, by whom."
    icon = "chart"
    category = "media"
    secret_fields: frozenset[str] = frozenset({"api_key"})
    provides: Sequence[CapabilityBinding] = (
        binding(ACTIVITY_HISTORY),
        binding(ACCOUNTS),
        binding(HEALTH_PROBE),
    )
    status_path = "/api/v2"
    public_path = None

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        return {}

    async def command(self, service: ServiceHandle, cmd: str, **params: Any) -> Any:
        body = await self.get_json(
            service, "/api/v2", apikey=service.secrets.get("api_key", ""), cmd=cmd, **params
        )
        response = body.get("response") if isinstance(body, Mapping) else None
        if not isinstance(response, Mapping):
            raise InvalidPayload("not a Tautulli answer")
        if response.get("result") != "success":
            message = str(response.get("message") or "")
            if "api" in message.lower() and "key" in message.lower():
                raise ProviderAuthError("Tautulli refused the API key")
            raise InvalidPayload("Tautulli refused the command")
        return response.get("data")

    async def test_connection(self, service: ServiceHandle) -> TestResult:
        try:
            info = await self.command(service, "get_tautulli_info")
        except ProviderAuthError:
            return TestResult(
                ok=False,
                reachable=True,
                authenticated=False,
                detail="Tautulli answered but refused the API key: copy it from Settings → Web Interface.",
            )
        except InvalidPayload:
            return TestResult(
                ok=False,
                reachable=True,
                authenticated=False,
                compatible=False,
                detail="Something answered at this address, but it is not Tautulli.",
            )
        except (ConnectionError, OSError):
            return TestResult(
                ok=False,
                reachable=False,
                authenticated=False,
                detail="Cannot reach the service: check the address, the port and that it is running.",
            )
        version = info.get("tautulli_version") if isinstance(info, Mapping) else None
        return TestResult(
            ok=True,
            reachable=True,
            authenticated=True,
            detail=f"Connected to Tautulli {version or ''}".strip(),
        )

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == ACTIVITY_HISTORY:
            return _History(self, service)
        if capability == ACCOUNTS:
            return _Accounts(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None


class _History:
    def __init__(self, connector: TautulliConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def history(self, *, since: datetime | None, cursor: str | None) -> ActivityPage:
        start = int(cursor) if cursor and cursor.isdigit() else 0
        params: dict[str, Any] = {
            "length": PAGE,
            "start": start,
            "order_column": "date",
            "order_dir": "asc",
            "grouping": 0,
        }
        if since is not None:
            # ``after`` takes a day; the exact bound is applied below
            params["after"] = (since.astimezone(UTC) - timedelta(days=1)).date().isoformat()
        data = await self.connector.command(self.service, "get_history", **params)
        rows = data.get("data") if isinstance(data, Mapping) else data
        if not isinstance(rows, list):
            raise InvalidPayload("unexpected get_history payload")
        items = [a for a in (map_history_row(r) for r in rows if isinstance(r, Mapping)) if a is not None]
        if since is not None:
            items = [a for a in items if a.started_at >= since]
        total = data.get("recordsFiltered") if isinstance(data, Mapping) else None
        return ActivityPage(
            items=items,
            cursor=str(start + len(rows)) if len(rows) >= PAGE else None,
            total=int(total) if isinstance(total, int | str) and str(total).isdigit() else None,
            position=start + len(rows),
        )


class _Accounts:
    def __init__(self, connector: TautulliConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def list_accounts(self) -> Sequence[ServiceAccount]:
        users = await self.connector.command(self.service, "get_users")
        rows = users if isinstance(users, list) else (users or {}).get("data", [])
        return [
            ServiceAccount(
                external_id=str(u["user_id"]),
                username=u.get("username") or None,
                display_name=u.get("friendly_name") or u.get("username") or None,
                email=u.get("email") or None,
            )
            for u in rows
            if isinstance(u, Mapping) and u.get("user_id") not in (None, 0, "0") and u.get("is_active", 1)
        ]


class _Probe:
    def __init__(self, connector: TautulliConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def probe(self) -> ProbeResult:
        started = time.monotonic()
        try:
            await self.connector.command(self.service, "get_tautulli_info")
        except ProviderAuthError:
            return ProbeResult(reachable=True, error_code="auth", detail="Tautulli rejected the API key.")
        except InvalidPayload:
            return ProbeResult(reachable=True, error_code="invalid_response", detail="Unexpected answer.")
        except (ConnectionError, OSError):
            return ProbeResult(
                reachable=False, error_code="unreachable", detail="Tautulli cannot be reached."
            )
        return ProbeResult(reachable=True, latency_ms=round((time.monotonic() - started) * 1000, 1))
