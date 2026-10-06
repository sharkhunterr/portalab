"""Torrent clients (027): ``qbittorrent`` and ``deluge``.

* ``media.download_clients``: the transfers behind the download managers' queues, by info hash — state
  (downloading, stalled, waiting for metadata, queued, paused, checking, seeding, error), progress, speeds,
  time left, seeds and peers — so a title's request journey says *why* a download does not move.
* ``service.health_probe``: an authenticated round trip.

Authentication: qBittorrent's Web UI user (configuration) and password (secret) exchanged for the ``SID``
cookie (``POST /api/v2/auth/login``); Deluge's Web UI password (secret) for the ``_session_id`` cookie
(JSON-RPC ``auth.login``), then the Web UI is connected to its daemon if it is not yet. Sessions are
renewed when refused.
"""

import time
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from portalab.capabilities.connector_http import ConnectorHttpError
from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle, TestResult
from portalab.capabilities.health import HEALTH_PROBE, ProbeResult
from portalab.capabilities.media import DOWNLOAD_CLIENTS, TorrentState
from portalab.capabilities.results import InvalidPayload, ProviderAuthError
from portalab.connectors.http_base import BaseConfig, HttpConnector, binding

HASH_CHARS = frozenset("0123456789abcdef")
INFINITE_ETA = 8_640_000


def clean_hashes(hashes: Sequence[str]) -> list[str]:
    out = []
    for value in hashes:
        text = str(value).strip().lower()
        if 32 <= len(text) <= 64 and set(text) <= HASH_CHARS:
            out.append(text)
    return sorted(set(out))[:200]


def _cookie(headers: Mapping[str, str], name: str) -> str | None:
    raw = headers.get("set-cookie") or headers.get("Set-Cookie") or ""
    for part in raw.split(";"):
        key, _, value = part.strip().partition("=")
        if key.endswith(name) and value:
            return value
    return None


def _number(value: Any) -> int | None:
    return int(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


QBIT_STATES = {
    "downloading": "downloading",
    "forceddl": "downloading",
    "stalleddl": "stalled",
    "metadl": "metadata",
    "forcedmetadl": "metadata",
    "queueddl": "queued",
    "queuedup": "seeding",
    "pauseddl": "paused",
    "stoppeddl": "paused",
    "checkingdl": "checking",
    "checkingup": "checking",
    "checkingresumedata": "checking",
    "allocating": "checking",
    "moving": "checking",
    "uploading": "seeding",
    "stalledup": "seeding",
    "forcedup": "seeding",
    "pausedup": "seeding",
    "stoppedup": "seeding",
    "error": "error",
    "missingfiles": "error",
}


def map_qbit(item: Mapping[str, Any], client: str) -> TorrentState | None:
    digest = str(item.get("hash") or "").lower()
    if not digest:
        return None
    eta = _number(item.get("eta"))
    return TorrentState(
        download_id=digest,
        name=str(item.get("name") or "")[:300],
        state=QBIT_STATES.get(str(item.get("state") or "").lower(), "downloading"),
        progress=max(0.0, min(1.0, float(item.get("progress") or 0))),
        download_speed=_number(item.get("dlspeed")) or 0,
        upload_speed=_number(item.get("upspeed")) or 0,
        eta_s=None if eta is None or eta >= INFINITE_ETA else eta,
        seeds=_number(item.get("num_seeds")),
        peers=_number(item.get("num_leechs")),
        client=client,
    )


DELUGE_STATES = {
    "downloading": "downloading",
    "seeding": "seeding",
    "paused": "paused",
    "checking": "checking",
    "queued": "queued",
    "error": "error",
    "moving": "checking",
    "allocating": "checking",
}
DELUGE_FIELDS = [
    "name",
    "state",
    "progress",
    "download_payload_rate",
    "upload_payload_rate",
    "eta",
    "num_seeds",
    "num_peers",
]


def map_deluge(digest: str, item: Mapping[str, Any], client: str) -> TorrentState:
    state = DELUGE_STATES.get(str(item.get("state") or "").lower(), "downloading")
    speed = _number(item.get("download_payload_rate")) or 0
    if state == "downloading" and speed == 0 and float(item.get("progress") or 0) < 100:
        state = "stalled"
    eta = _number(item.get("eta"))
    return TorrentState(
        download_id=digest.lower(),
        name=str(item.get("name") or "")[:300],
        state=state,
        progress=max(0.0, min(1.0, float(item.get("progress") or 0) / 100)),
        download_speed=speed,
        upload_speed=_number(item.get("upload_payload_rate")) or 0,
        eta_s=eta if eta and eta > 0 else None,
        seeds=_number(item.get("num_seeds")),
        peers=_number(item.get("num_peers")),
        client=client,
    )


class _TorrentConnector(HttpConnector):
    category = "downloads"
    icon = "package"
    provides: Sequence[CapabilityBinding] = (binding(DOWNLOAD_CLIENTS), binding(HEALTH_PROBE))
    secret_fields: frozenset[str] = frozenset({"password"})
    cookie_name: ClassVar[str] = ""

    def __init__(self) -> None:
        self._sessions: dict[UUID, tuple[str, float]] = {}

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        session = self._sessions.get(service.service_id)
        return {"Cookie": f"{self.cookie_name}={session[0]}"} if session else {}

    async def login(self, service: ServiceHandle) -> None:
        raise NotImplementedError

    async def version(self, service: ServiceHandle) -> str:
        raise NotImplementedError

    async def fetch(self, service: ServiceHandle, hashes: list[str]) -> list[TorrentState]:
        raise NotImplementedError

    async def ensure(self, service: ServiceHandle) -> None:
        session = self._sessions.get(service.service_id)
        if session is None or time.monotonic() - session[1] > 20 * 60:
            await self.login(service)

    async def torrents(self, service: ServiceHandle, hashes: Sequence[str]) -> list[TorrentState]:
        wanted = clean_hashes(hashes)
        if not wanted:
            return []
        await self.ensure(service)
        try:
            return await self.fetch(service, wanted)
        except ProviderAuthError:
            await self.login(service)  # the session expired: once more with a new one
            return await self.fetch(service, wanted)

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == DOWNLOAD_CLIENTS:
            return _Client(self, service)
        if capability == HEALTH_PROBE:
            return _TorrentProbe(self, service)
        return None

    async def test_connection(self, service: ServiceHandle) -> TestResult:
        try:
            await self.login(service)
            label = await self.version(service)
        except ProviderAuthError:
            return TestResult(
                ok=False,
                reachable=True,
                authenticated=False,
                detail=f"{self.name} answered but refused the credentials: check them.",
            )
        except InvalidPayload:
            return TestResult(
                ok=False,
                reachable=True,
                authenticated=False,
                compatible=False,
                detail=f"Something answered at this address, but it is not {self.name}.",
            )
        except (ConnectionError, OSError):
            return TestResult(
                ok=False,
                reachable=False,
                authenticated=False,
                detail="Cannot reach the service: check the address, the port and that it is running.",
            )
        return TestResult(ok=True, reachable=True, authenticated=True, detail=f"Connected to {label}.")


class _Client:
    def __init__(self, connector: _TorrentConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def torrents(self, hashes: Sequence[str]) -> Sequence[TorrentState]:
        return await self.connector.torrents(self.service, hashes)


class _TorrentProbe:
    def __init__(self, connector: _TorrentConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def probe(self) -> ProbeResult:
        started = time.monotonic()
        try:
            await self.connector.ensure(self.service)
            await self.connector.version(self.service)
        except ProviderAuthError:
            return ProbeResult(
                reachable=True, error_code="auth", detail="The service rejected the credentials."
            )
        except InvalidPayload:
            return ProbeResult(reachable=True, error_code="invalid_response", detail="Unexpected answer.")
        except (ConnectionError, OSError):
            return ProbeResult(
                reachable=False, error_code="unreachable", detail="The service cannot be reached."
            )
        return ProbeResult(reachable=True, latency_ms=round((time.monotonic() - started) * 1000, 1))


class QBittorrentConfig(BaseConfig):
    username: str = Field(default="admin", min_length=1, max_length=128, title="Username")


class QBittorrentConnector(_TorrentConnector):
    key = "qbittorrent"
    name = "qBittorrent"
    description = "The torrents behind your downloads: speed, peers and why one does not move."
    config_schema: type[BaseModel] = QBittorrentConfig
    cookie_name = "SID"

    async def _raw(self, service: ServiceHandle, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._http(service).request(
                method, path, headers={**self.auth_headers(service), "Accept": "*/*"}, **kwargs
            )
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code in (401, 403):
            raise ProviderAuthError("the service rejected the credentials")
        if response.status_code >= 400:
            raise ConnectionError(f"the service answered HTTP {response.status_code}")
        return response

    async def login(self, service: ServiceHandle) -> None:
        self._sessions.pop(service.service_id, None)
        response = await self._raw(
            service,
            "POST",
            "/api/v2/auth/login",
            data={
                "username": str(service.config.get("username") or ""),
                "password": service.secrets.get("password", ""),
            },
        )
        text = response.content.decode("utf-8", "replace").strip()
        sid = _cookie(response.headers, "SID")
        if text.lower().startswith("fails") or (not sid and not text.lower().startswith("ok")):
            raise ProviderAuthError("the service rejected the credentials")
        if sid:
            self._sessions[service.service_id] = (sid, time.monotonic())

    async def version(self, service: ServiceHandle) -> str:
        response = await self._raw(service, "GET", "/api/v2/app/version")
        text = response.content.decode("utf-8", "replace").strip()
        if not text.lower().startswith("v"):
            raise InvalidPayload("not qBittorrent")
        return f"qBittorrent {text}"

    async def fetch(self, service: ServiceHandle, hashes: list[str]) -> list[TorrentState]:
        response = await self._raw(
            service, "GET", "/api/v2/torrents/info", params={"hashes": "|".join(hashes)}
        )
        try:
            body = response.json()
        except ValueError as exc:
            raise InvalidPayload("the service did not answer with JSON") from exc
        if not isinstance(body, list):
            raise InvalidPayload("unexpected /torrents/info payload")
        return [t for item in body if isinstance(item, Mapping) and (t := map_qbit(item, service.name))]


class DelugeConfig(BaseConfig):
    pass


class DelugeConnector(_TorrentConnector):
    key = "deluge"
    name = "Deluge"
    description = "The torrents behind your downloads: speed, peers and why one does not move."
    config_schema: type[BaseModel] = DelugeConfig
    cookie_name = "_session_id"

    def __init__(self) -> None:
        super().__init__()
        self._calls = 0

    async def rpc(self, service: ServiceHandle, method: str, params: list[Any]) -> Any:
        self._calls += 1
        try:
            response = await self._http(service).request(
                "POST",
                "/json",
                headers={**self.auth_headers(service), "Accept": "application/json"},
                json={"method": method, "params": params, "id": self._calls},
            )
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code in (401, 403):
            raise ProviderAuthError("the service rejected the credentials")
        if response.status_code >= 400:
            raise ConnectionError(f"the service answered HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise InvalidPayload("the service did not answer with JSON") from exc
        if not isinstance(body, Mapping) or "result" not in body:
            raise InvalidPayload("not a Deluge JSON-RPC answer")
        error = body.get("error")
        if isinstance(error, Mapping):
            if int(error.get("code") or 0) == 1:  # « Not authenticated »
                raise ProviderAuthError("the session expired")
            raise ConnectionError(str(error.get("message") or "Deluge refused the call")[:200])
        if method == "auth.login":
            return body["result"], response.headers
        return body["result"]

    async def login(self, service: ServiceHandle) -> None:
        self._sessions.pop(service.service_id, None)
        result, headers = await self.rpc(service, "auth.login", [service.secrets.get("password", "")])
        session = _cookie(headers, "_session_id")
        if result is not True or not session:
            raise ProviderAuthError("the service rejected the credentials")
        self._sessions[service.service_id] = (session, time.monotonic())
        if not await self.rpc(service, "web.connected", []):  # the Web UI talks to a daemon: connect it
            hosts = await self.rpc(service, "web.get_hosts", [])
            if isinstance(hosts, list) and hosts and isinstance(hosts[0], list) and hosts[0]:
                await self.rpc(service, "web.connect", [hosts[0][0]])

    async def version(self, service: ServiceHandle) -> str:
        info = await self.rpc(service, "daemon.info", [])
        return f"Deluge {info}" if isinstance(info, str) else "Deluge"

    async def fetch(self, service: ServiceHandle, hashes: list[str]) -> list[TorrentState]:
        body = await self.rpc(service, "core.get_torrents_status", [{"id": hashes}, DELUGE_FIELDS])
        if not isinstance(body, Mapping):
            raise InvalidPayload("unexpected core.get_torrents_status payload")
        return [
            map_deluge(str(h), item, service.name) for h, item in body.items() if isinstance(item, Mapping)
        ]
