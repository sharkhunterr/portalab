"""``seerr`` connector: Overseerr, Jellyseerr and their forks (API v1).

* ``request.service`` (sync + live): every request with its state, synchronised so Media shows members
  where their requests stand; members' new requests are submitted here (``POST /api/v1/request``).
* ``service.health_probe``: an authenticated request listing.

Authentication uses the API key of *Settings → General*, sent as ``X-Api-Key``.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from portalab.capabilities.connector_sdk import (
    CapabilityBinding,
    ServiceHandle,
    SourceRecord,
    SyncContext,
    SyncProgress,
)
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import REQUESTS, RequestState, SourceRequest
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import HttpConnector, _Probe, binding, parse_time, safe_id

PAGE = 100
# request.status: 1 pending, 2 approved, 3 declined (4 failed, 5 completed in recent versions);
# media.status: 1 unknown, 2 pending, 3 processing, 4 partially available, 5 available (6 blacklisted).
REQUEST_STATES: dict[int, RequestState] = {
    1: "pending",
    2: "approved",
    3: "declined",
    4: "failed",
    5: "available",
}
MEDIA_STATES: dict[int, RequestState] = {3: "processing", 4: "available", 5: "available"}
KINDS = {"movie": "movie", "tv": "series"}


def state_of(request: Mapping[str, Any]) -> tuple[RequestState, str]:
    status = int(request.get("status") or 1)
    media_status = int((request.get("media") or {}).get("status") or 1)
    state: RequestState = REQUEST_STATES.get(status, "pending")
    if state == "approved":
        state = MEDIA_STATES.get(media_status, "approved")
    return state, f"request:{status}/media:{media_status}"


class SeerrConnector(HttpConnector):
    key = "seerr"
    name = "Seerr (Overseerr / Jellyseerr)"
    description = "Media requests: members ask for a film or a series, Seerr sends it to Radarr or Sonarr."
    icon = "inbox"
    category = "requests"
    provides: Sequence[CapabilityBinding] = (binding(REQUESTS, syncable=True), binding(HEALTH_PROBE))
    status_path = "/api/v1/settings/main"
    public_path = "/api/v1/status"

    def describe(self, status: Any) -> str:
        if not isinstance(status, Mapping) or "applicationTitle" not in status:
            raise InvalidPayload("not a Seerr settings document")
        return str(status.get("applicationTitle") or self.name)

    def looks_like_us(self, public: Any) -> bool:
        return isinstance(public, Mapping) and "version" in public and "commitTag" in public

    async def _title(self, service: ServiceHandle, kind: str, tmdb: Any, cache: dict[str, str]) -> str:
        key = f"{kind}:{tmdb}"
        if key not in cache:
            try:
                details = await self.get_json(service, f"/api/v1/{kind}/{safe_id(tmdb)}")
                cache[key] = str((details or {}).get("title") or (details or {}).get("name") or key)
            except (ConnectionError, InvalidPayload):
                cache[key] = key
        return cache[key]

    async def sync(
        self, ctx: SyncContext, cursor: Mapping[str, Any] | None
    ) -> AsyncIterator[SourceRecord | SyncProgress]:
        service = ctx.service
        titles: dict[str, str] = {}
        skip = 0
        while True:
            page = await self.get_json(service, "/api/v1/request", take=PAGE, skip=skip, sort="added")
            if not isinstance(page, Mapping) or not isinstance(page.get("results"), list):
                raise InvalidPayload("unexpected /request payload")
            for request in page["results"]:
                media = request.get("media") or {}
                media_type = str(media.get("mediaType") or request.get("type") or "movie")
                tmdb = media.get("tmdbId")
                state, source_state = state_of(request)
                ids = {
                    "tmdb": str(tmdb) if tmdb else None,
                    "tvdb": str(media["tvdbId"]) if media.get("tvdbId") else None,
                }
                requester = (request.get("requestedBy") or {}).get("id")
                payload = {
                    "title": (await self._title(service, media_type, tmdb, titles)) if tmdb else "?",
                    "kind": KINDS.get(media_type, "movie"),
                    "ids": {k: v for k, v in ids.items() if v},
                    "state": state,
                    "source_state": source_state,
                    "requester": str(requester) if requester else None,
                }
                yield self.record(
                    service,
                    safe_id(request.get("id")),
                    "request",
                    payload,
                    parse_time(request.get("updatedAt") or request.get("createdAt")),
                )
            skip += len(page["results"])
            total = int((page.get("pageInfo") or {}).get("results") or 0)
            if not page["results"] or skip >= total:
                break
        yield SyncProgress(cursor={"items": skip})

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == REQUESTS:
            return _Requests(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None


class _Requests:
    def __init__(self, connector: SeerrConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def submit(
        self, ids: Mapping[str, str], kind: str, title: str, requester: str | None
    ) -> SourceRequest:
        tmdb = ids.get("tmdb")
        if not tmdb:
            raise InvalidPayload("Seerr needs a TMDB id to request a title")
        media_type = "tv" if kind in ("series", "season", "episode") else "movie"
        body: dict[str, Any] = {"mediaType": media_type, "mediaId": int(safe_id(tmdb))}
        if media_type == "tv":
            body["seasons"] = "all"
        if requester and requester.isdigit():
            body["userId"] = int(requester)
        created = await self.connector.request(self.service, "POST", "/api/v1/request", json_body=body)
        if not isinstance(created, Mapping) or "id" not in created:
            raise InvalidPayload("unexpected answer to a request")
        state, source_state = state_of(created)
        return SourceRequest(external_request_id=str(created["id"]), state=state, source_state=source_state)

    async def status(self, external_request_id: str) -> SourceRequest:
        request = await self.connector.get_json(
            self.service, f"/api/v1/request/{safe_id(external_request_id)}"
        )
        if not isinstance(request, Mapping):
            raise InvalidPayload("unexpected request payload")
        state, source_state = state_of(request)
        return SourceRequest(external_request_id=external_request_id, state=state, source_state=source_state)
