"""Shared plumbing of the HTTP connectors (Jellyfin, Plex, Radarr, Sonarr, Seerr, RomM).

Each concrete connector declares how it authenticates (:meth:`HttpConnector.auth_headers`), which
authenticated endpoint proves the credentials (``status_path``) and how to name the server from it; this
module turns HTTP outcomes into the SDK's typed results: 401/403 → :class:`ProviderAuthError`, transport
errors and 5xx → ``ConnectionError``, unparsable bodies → :class:`InvalidPayload`. Every call goes through
the service's :class:`ConnectorHttpClient` (timeouts, size cap, same-host redirects, secret redaction).

Image references stored in the catalog are *opaque ids* validated here before a path is built from them,
so a value read from the source can never point the client at another host.
"""

import re
import time
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.connector_http import ConnectorHttpClient, ConnectorHttpError
from portalab.capabilities.connector_sdk import (
    Candidate,
    CapabilityBinding,
    Manifest,
    ServiceHandle,
    SourceRecord,
    SyncContext,
    SyncProgress,
    TestResult,
)
from portalab.capabilities.health import HEALTH_PROBE, ProbeResult
from portalab.capabilities.health import SPECS as HEALTH_SPECS
from portalab.capabilities.identity_provider import SPECS as IDENTITY_SPECS
from portalab.capabilities.media import SPECS as MEDIA_SPECS
from portalab.capabilities.results import InvalidPayload, ProviderAuthError, ProviderNotFound

EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
LIBRARY_LISTING_BYTES = 100 * 1024 * 1024  # 027: whole-library answers (Radarr /movie) of large libraries
SPECS = {spec.name: spec for spec in (*HEALTH_SPECS, *MEDIA_SPECS, *IDENTITY_SPECS)}
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class BaseConfig(BaseModel):
    """What every HTTP connector needs: where the service is, and whether to check its certificate."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(
        min_length=8,
        max_length=512,
        pattern=r"^https?://[^\s/$.?#].[^\s]*$",
        title="Address",
        description="The address you open in your browser, e.g. http://192.168.1.10:8096",
    )
    verify_tls: bool = Field(default=True, title="Check the HTTPS certificate")


def binding(name: str, *, syncable: bool = False, driven: bool = False) -> CapabilityBinding:
    return CapabilityBinding(SPECS[name], syncable=syncable, driven=driven)


def safe_id(value: Any) -> str:
    text = str(value)
    if not SAFE_ID.fullmatch(text):
        raise InvalidPayload("unexpected identifier")
    return text


def image_key(ref: str) -> str:
    """#272: an image reference is ``<item>`` or ``<item>:<version>`` — both safe identifiers; the item is
    what is fetched, the version only tells a changed image apart."""
    key, _, version = str(ref).partition(":")
    if version:
        safe_id(version)
    return safe_id(key)


def parse_time(value: Any) -> datetime | None:
    """ISO 8601 strings (with or without zone) and epoch seconds/milliseconds."""
    if value is None or value == "":
        return None
    if isinstance(value, int | float):
        seconds = value / 1000 if abs(value) > 10**11 else value
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None  # 027: a nonsense timestamp from a source is no date, never a failed sync
    try:
        text = str(value).replace("Z", "+00:00")
        if "." in text:  # .NET writes 7 fractional digits; Python accepts at most 6
            head, _, tail = text.partition(".")
            digits = re.match(r"\d+", tail)
            rest = tail[digits.end() :] if digits else tail
            text = f"{head}.{(digits.group() if digits else '0')[:6]}{rest}"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def clean(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Drop empty values so unchanged items hash the same between runs."""
    return {k: v for k, v in payload.items() if v not in (None, "", [], {})}


class HttpConnector:
    """Base of the HTTP connectors: subclasses set the class attributes and the mapping methods."""

    key: str
    name: str
    description: ClassVar[str] = ""
    icon: ClassVar[str] = "server"
    category: ClassVar[str] = "media"
    manifest = Manifest(version="1.0.0", requires_portal=">=0.1,<2")
    config_schema: type[BaseModel] = BaseConfig
    secret_fields: frozenset[str] = frozenset({"api_key"})
    provides: Sequence[CapabilityBinding] = ()
    status_path: ClassVar[str] = "/"
    public_path: ClassVar[str | None] = None

    # --- to override ----------------------------------------------------------------------------------
    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        return {"X-Api-Key": service.secrets.get("api_key", "")}

    def describe(self, status: Any) -> str:
        """A short "Name version" read from the status document; raise InvalidPayload if it is not ours."""
        return self.name

    def looks_like_us(self, public: Any) -> bool:
        return True

    async def sync(
        self, ctx: SyncContext, cursor: Mapping[str, Any] | None
    ) -> AsyncIterator[SourceRecord | SyncProgress]:
        yield SyncProgress(cursor={})

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None

    def actions(self) -> Mapping[str, Callable[[ServiceHandle, Mapping[str, Any]], Any]]:
        return {}

    # --- HTTP helpers ---------------------------------------------------------------------------------
    def _http(self, service: ServiceHandle) -> ConnectorHttpClient:
        if service.http is None:
            raise ConnectionError("the service address is not configured")
        http: ConnectorHttpClient = service.http
        return http

    async def request(
        self,
        service: ServiceHandle,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        headers: Mapping[str, str] | None = None,
        max_bytes: int | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {"headers": {"Accept": "application/json", **self.auth_headers(service)}}
        if max_bytes:
            kwargs["max_response_bytes"] = max_bytes
        if headers:
            kwargs["headers"].update(headers)
        if params:
            kwargs["params"] = {k: v for k, v in params.items() if v is not None}
        if json_body is not None:
            kwargs["json"] = json_body
        try:
            response = await self._http(service).request(method, path, **kwargs)
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code in (401, 403):
            raise ProviderAuthError("the service rejected the credentials")
        if response.status_code in (404, 410):
            raise ProviderNotFound(f"the service has no such item (HTTP {response.status_code})")
        if response.status_code >= 400:
            raise ConnectionError(f"the service answered HTTP {response.status_code}")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise InvalidPayload("the service did not answer with JSON") from exc

    async def get_json(self, service: ServiceHandle, path: str, **params: Any) -> Any:
        return await self.request(service, "GET", path, params=params)

    async def get_bytes(self, service: ServiceHandle, path: str, **params: Any) -> bytes:
        try:
            response = await self._http(service).get(
                path, headers=self.auth_headers(service), params={k: v for k, v in params.items() if v}
            )
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code in (401, 403):
            raise ProviderAuthError("the service rejected the credentials")
        if response.status_code in (404, 410):
            raise ProviderNotFound(f"the service has no such item (HTTP {response.status_code})")
        if response.status_code >= 400:
            raise ConnectionError(f"the service answered HTTP {response.status_code}")
        return response.content

    def record(
        self,
        service: ServiceHandle,
        external_id: str,
        kind: str,
        payload: Mapping[str, Any],
        observed: datetime | None,
    ) -> SourceRecord:
        return SourceRecord(
            source_system=f"{self.key}:{service.service_id}",
            external_id=external_id,
            kind=kind,
            payload=clean(payload),
            observed_at=observed or EPOCH,
        )

    # --- SDK ------------------------------------------------------------------------------------------
    async def test_connection(self, service: ServiceHandle) -> TestResult:
        try:
            status = await self.get_json(service, self.status_path)
            label = self.describe(status)
        except ProviderAuthError:
            return TestResult(
                ok=False,
                reachable=True,
                authenticated=False,
                detail=f"{self.name} answered but refused the credentials: check the key.",
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

    async def discover(self, targets: Sequence[str]) -> list[Candidate]:
        if self.public_path is None:
            return []
        found = []
        for target in targets:
            try:
                client = ConnectorHttpClient(target, timeout_seconds=3, retries=0)
                response = await client.get(self.public_path, headers={"Accept": "application/json"})
                if response.status_code < 400 and self.looks_like_us(response.json()):
                    found.append(Candidate(target=target, details={"config": {"base_url": target}}))
            except Exception:  # noqa: S112 — best effort: a failing target is skipped
                continue
        return found


class _Probe:
    def __init__(self, connector: HttpConnector, service: ServiceHandle) -> None:
        self.connector = connector
        self.service = service

    async def probe(self) -> ProbeResult:
        started = time.monotonic()
        try:
            await self.connector.get_json(self.service, self.connector.status_path)
        except ProviderAuthError:
            return ProbeResult(
                reachable=True,
                latency_ms=(time.monotonic() - started) * 1000,
                error_code="auth",
                detail="The service rejected the credentials.",
            )
        except InvalidPayload:
            return ProbeResult(reachable=True, error_code="invalid_response", detail="Unexpected answer.")
        except (ConnectionError, OSError):
            return ProbeResult(
                reachable=False, error_code="unreachable", detail="The service cannot be reached."
            )
        return ProbeResult(reachable=True, latency_ms=round((time.monotonic() - started) * 1000, 1))
