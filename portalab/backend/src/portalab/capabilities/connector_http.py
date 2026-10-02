"""``ConnectorHttpClient`` (spec 005 T008, R6): the only way connectors talk HTTP.

Per-call timeout, maximum response size (streamed, aborted beyond the limit), redirects followed only on the
configured host, bounded retries with backoff for idempotent requests on connection errors and 5xx, optional
TLS verification (homelab targets often use private CAs), correlation id propagation, and errors whose text
never contains credentials. Homelab services live on private addresses, so private ranges are allowed.
"""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from portalab.core.logging import get_correlation_id, redact_text, register_secret_value
from portalab.core.metrics import Timer

IDEMPOTENT = frozenset({"GET", "HEAD", "OPTIONS"})


class ConnectorHttpError(RuntimeError):
    pass


class ResponseTooLarge(ConnectorHttpError):
    pass


class RedirectRefused(ConnectorHttpError):
    pass


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    content: bytes

    def json(self) -> Any:
        import json

        return json.loads(self.content)


class ConnectorHttpClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
        max_response_bytes: int = 5 * 1024 * 1024,
        retries: int = 2,
        backoff_seconds: float = 0.5,
        verify_tls: bool = True,
        secrets: Mapping[str, str] | None = None,
        default_headers: Mapping[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parts = urlsplit(base_url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ConnectorHttpError("base URL must be an absolute http(s) URL")
        self.base_url = base_url.rstrip("/") + "/"
        self.host = parts.netloc
        self.timeout = timeout_seconds
        self.max_bytes = max_response_bytes
        self.retries = retries
        self.backoff = backoff_seconds
        self.verify_tls = verify_tls
        self.default_headers = dict(default_headers or {})
        self.transport = transport
        for value in (secrets or {}).values():
            register_secret_value(value)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout, verify=self.verify_tls, follow_redirects=False, transport=self.transport
        )

    async def request(self, method: str, path: str, **kwargs: Any) -> HttpResponse:
        method = method.upper()
        url = urljoin(self.base_url, path.lstrip("/"))
        headers = {**self.default_headers, **kwargs.pop("headers", {})}
        correlation = get_correlation_id()
        if correlation:
            headers["X-Correlation-Id"] = correlation
        attempts = self.retries + 1 if method in IDEMPOTENT else 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                with Timer("external_wait", "connectors", "http.request", {"method": method}):
                    response = await self._send(method, url, headers, kwargs, redirects=5)
                if response.status_code >= 500 and attempt < attempts - 1:
                    await asyncio.sleep(self.backoff * 2**attempt)
                    continue
                return response
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt < attempts - 1:
                    await asyncio.sleep(self.backoff * 2**attempt)
        raise ConnectorHttpError(redact_text(f"{type(last_error).__name__}: {last_error}"))

    async def _send(
        self, method: str, url: str, headers: dict[str, str], kwargs: dict[str, Any], *, redirects: int
    ) -> HttpResponse:
        async with (
            self._client() as client,
            client.stream(method, url, headers=headers, **kwargs) as response,
        ):
            if response.is_redirect:
                location = response.headers.get("location", "")
                target = urljoin(url, location)
                if urlsplit(target).netloc != self.host:
                    raise RedirectRefused("redirect to another host refused")
                if redirects <= 0:
                    raise RedirectRefused("too many redirects")
                return await self._send(
                    "GET" if response.status_code == 303 else method,
                    target,
                    headers,
                    kwargs,
                    redirects=redirects - 1,
                )
            declared = response.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > self.max_bytes:
                raise ResponseTooLarge(f"response larger than {self.max_bytes} bytes")
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > self.max_bytes:
                    raise ResponseTooLarge(f"response larger than {self.max_bytes} bytes")
                chunks.append(chunk)
            return HttpResponse(response.status_code, dict(response.headers), b"".join(chunks))

    async def get(self, path: str, **kwargs: Any) -> HttpResponse:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> HttpResponse:
        return await self.request("POST", path, **kwargs)
