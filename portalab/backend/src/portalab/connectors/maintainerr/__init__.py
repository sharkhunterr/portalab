"""``maintainerr`` connector (#57): Maintainerr, the rule-based cleanup of a Plex or Jellyfin library.

* ``media.cleanup``: the titles its rules put in a collection to delete — when each one goes (the day it
  entered the collection plus the collection's « delete after » days) — and keeping one: a global
  exclusion (``POST /api/rules/exclusion``), so no rule takes it again.
* ``service.health_probe``: ``GET /api/app/status``.

Maintainerr has no authentication of its own (it sits on the local network, or behind a proxy): the
connector only needs its address. Its ids are the media server's (Plex rating keys, Jellyfin ids) —
``mediaServerId`` since 2.x, ``plexId`` before.
"""

import json
import time
from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any

from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle, TestResult
from portalab.capabilities.health import HEALTH_PROBE, ProbeResult
from portalab.capabilities.media import CLEANUP, LeavingItem
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import HttpConnector, binding, parse_time, safe_id

# Maintainerr 2.x names the kinds; 1.x numbered them
KINDS = {"movie": "movie", "show": "series", "season": "season", "episode": "episode"}
KIND_NUMBERS = {1: "movie", 2: "series", 3: "season", 4: "episode"}
MAX_COLLECTIONS = 100


def _kind(value: Any) -> str | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return KIND_NUMBERS.get(value)
    return KINDS.get(str(value or "").lower())


def _status(document: Any) -> Mapping[str, Any]:
    """``/api/app/status`` answers a JSON document encoded as a string."""
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except ValueError as exc:
            raise InvalidPayload("not a Maintainerr status") from exc
    if not isinstance(document, Mapping) or "version" not in document:
        raise InvalidPayload("not a Maintainerr status")
    return document


def map_media(row: Mapping[str, Any], collection: Mapping[str, Any]) -> LeavingItem | None:
    """One item of a collection; ``None`` without an id, a kind or the day it entered."""
    external = row.get("mediaServerId") or row.get("plexId")
    kind = _kind(collection.get("type"))
    added = parse_time(row.get("addDate"))
    if external in (None, "") or kind is None or added is None:
        return None
    days = collection.get("deleteAfterDays")
    delete_at = (
        added + timedelta(days=int(days))
        if isinstance(days, int) and not isinstance(days, bool) and days > 0
        else None
    )
    ids = {
        scheme: str(row[field])
        for scheme, field in (("tmdb", "tmdbId"), ("tvdb", "tvdbId"))
        if row.get(field) not in (None, "", 0)
    }
    size = row.get("sizeBytes")
    return LeavingItem(
        external_id=safe_id(external),
        kind=kind,
        collection=str(collection.get("title") or "")[:200],
        added_at=added,
        delete_at=delete_at,
        ids=ids,
        size=int(size) if isinstance(size, int | float) and not isinstance(size, bool) and size > 0 else None,
    )


class MaintainerrConnector(HttpConnector):
    key = "maintainerr"
    name = "Maintainerr"
    description = "The library's cleanup: which titles its rules will delete, and when — and saving one."
    icon = "trash"
    category = "media"
    secret_fields: frozenset[str] = frozenset()
    provides: Sequence[CapabilityBinding] = (binding(CLEANUP), binding(HEALTH_PROBE))
    status_path = "/api/app/status"

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        return {}

    async def version(self, service: ServiceHandle) -> str:
        status = _status(await self.get_json(service, self.status_path))
        return f"Maintainerr {status.get('version')}".strip()

    async def test_connection(self, service: ServiceHandle) -> TestResult:
        try:
            label = await self.version(service)
        except InvalidPayload:
            return TestResult(
                ok=False,
                reachable=True,
                authenticated=False,
                compatible=False,
                detail="Something answered at this address, but it is not Maintainerr.",
            )
        except (ConnectionError, OSError):
            return TestResult(
                ok=False,
                reachable=False,
                authenticated=False,
                detail="Cannot reach the service: check the address, the port and that it is running.",
            )
        return TestResult(ok=True, reachable=True, authenticated=True, detail=f"Connected to {label}.")

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == CLEANUP:
            return _Cleanup(self, service)
        if capability == HEALTH_PROBE:
            return _MaintainerrProbe(self, service)
        return None


class _Cleanup:
    def __init__(self, connector: MaintainerrConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def leaving(self) -> Sequence[LeavingItem]:
        collections = await self.connector.get_json(self.service, "/api/collections")
        if not isinstance(collections, list):
            raise InvalidPayload("unexpected /api/collections payload")
        items: list[LeavingItem] = []
        for collection in collections[:MAX_COLLECTIONS]:
            if not isinstance(collection, Mapping) or collection.get("isActive") is False:
                continue
            if collection.get("id") is None:
                continue
            media = await self.connector.get_json(
                self.service, "/api/collections/media/", collectionId=safe_id(collection["id"])
            )
            for row in media if isinstance(media, list) else []:
                if isinstance(row, Mapping) and (item := map_media(row, collection)) is not None:
                    items.append(item)
        return items

    async def keep(self, external_id: str) -> None:
        media = safe_id(external_id)
        body: dict[str, Any] = {"mediaId": media, "action": 0}
        if media.isdigit():
            body["plexId"] = int(media)  # Maintainerr 1.x
        answer = await self.connector.request(self.service, "POST", "/api/rules/exclusion", json_body=body)
        if isinstance(answer, Mapping) and answer.get("code") == 0:
            raise ConnectionError(str(answer.get("message") or "Maintainerr refused the exclusion")[:200])


class _MaintainerrProbe:
    def __init__(self, connector: MaintainerrConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def probe(self) -> ProbeResult:
        started = time.monotonic()
        try:
            await self.connector.version(self.service)
        except InvalidPayload:
            return ProbeResult(reachable=True, error_code="invalid_response", detail="Unexpected answer.")
        except (ConnectionError, OSError):
            return ProbeResult(
                reachable=False, error_code="unreachable", detail="Maintainerr cannot be reached."
            )
        return ProbeResult(reachable=True, latency_ms=round((time.monotonic() - started) * 1000, 1))
