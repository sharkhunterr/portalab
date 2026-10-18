"""A confined plugin's outgoing calls (spec 030, R8-R9): through Portalab, to the hosts the Admin accepted.

The plugin's process has no socket; this is its only way out. A call must name a listed host, port and
scheme; the name is resolved here and a private, loopback, link-local or reserved address is refused unless
the host was listed as private; Portalab then connects to **that** address (no second resolution, so a name
cannot change its answer in between), never follows a redirect, bounds time and size, and adds the plugin's
secret settings where its manifest says — the plugin never reads them. Each call is counted per hour.
"""

import asyncio
import ipaddress
import socket
import time
from collections import defaultdict, deque
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

import httpx
from sqlalchemy.dialects.postgresql import insert

from portalab.core import egress
from portalab.core.db import Database
from portalab.core.secrets import SecretBox
from portalab.core.time import Clock, utc_now
from portalab.modules.plugins.confined.host import Denied
from portalab.modules.plugins.manifest.schema import Manifest
from portalab.modules.plugins.models import NetworkCall, SecretSetting

MAX_BODY = 5 * 1024 * 1024
MAX_TIMEOUT = 10.0
PER_MINUTE = 60
DROPPED_HEADERS = {
    "host",
    "connection",
    "content-length",
    "transfer-encoding",
    "upgrade",
    "proxy-authorization",
}
KEPT_ANSWER_HEADERS = {
    "content-type",
    "content-language",
    "etag",
    "last-modified",
    "cache-control",
    "retry-after",
}


def is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(ip.is_global) and not (ip.is_multicast or ip.is_reserved)


class Network:
    def __init__(
        self,
        database: Database,
        box: SecretBox | None,
        *,
        clock: Clock | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Any = None,
    ) -> None:
        self.database = database
        self.box = box
        self.clock = clock
        self.transport = transport  # tests: a fake transport
        self.resolver = resolver  # tests: (host, port) -> [addresses]
        self.allowed_hosts: Any = None  # 030 R14b: the portal-wide outbound allow-list, when switched on
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    async def _resolve(self, host: str, port: int) -> list[str]:
        if self.resolver is not None:
            return list(await self.resolver(host, port))
        try:
            ipaddress.ip_address(host)
            return [host]
        except ValueError:
            pass
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
        return list(dict.fromkeys(str(info[4][0]) for info in infos))

    def _rate(self, key: str) -> None:
        now = time.monotonic()
        calls = self._calls[key]
        while calls and now - calls[0] > 60:
            calls.popleft()
        if len(calls) >= PER_MINUTE:
            raise Denied("rate", "too many outgoing calls")
        calls.append(now)

    async def _secrets(
        self, key: str, manifest: Manifest, host: str
    ) -> tuple[dict[str, str], dict[str, str]]:
        headers: dict[str, str] = {}
        query: dict[str, str] = {}
        wanted = [
            s for s in manifest.secret_settings() if str(s.get("inject", {}).get("host", "")).lower() == host
        ]
        if not wanted or self.box is None:
            return headers, query
        async with self.database.session() as session:
            for setting in wanted:
                row = await session.get(SecretSetting, (key, str(setting["name"])))
                if row is None:
                    continue
                value = self.box.decrypt(row.ciphertext, context=f"plugins.setting:{key}:{setting['name']}")
                inject = setting["inject"]
                if inject.get("header"):
                    headers[str(inject["header"])] = value.reveal()
                elif inject.get("query"):
                    query[str(inject["query"])] = value.reveal()
        return headers, query

    async def _count(self, key: str, host: str, *, refused: bool, sent: int = 0, received: int = 0) -> None:
        now: datetime = utc_now(self.clock)
        hour = now.replace(minute=0, second=0, microsecond=0)
        try:
            async with self.database.unit_of_work() as uow:
                await uow.session.execute(
                    insert(NetworkCall)
                    .values(
                        plugin_key=key,
                        host=host[:253],
                        hour=hour,
                        calls=0 if refused else 1,
                        refused=1 if refused else 0,
                        bytes_in=received,
                        bytes_out=sent,
                    )
                    .on_conflict_do_update(
                        index_elements=[NetworkCall.plugin_key, NetworkCall.host, NetworkCall.hour],
                        set_={
                            "calls": NetworkCall.calls + (0 if refused else 1),
                            "refused": NetworkCall.refused + (1 if refused else 0),
                            "bytes_in": NetworkCall.bytes_in + received,
                            "bytes_out": NetworkCall.bytes_out + sent,
                        },
                    )
                )
        except Exception:  # noqa: S110 — counting never fails a call
            pass

    async def __call__(
        self, key: str, manifest: Manifest, grant: Mapping[str, Any], args: Mapping[str, Any], acting: Any
    ) -> dict[str, Any]:
        method = str(args.get("method", "GET")).upper()
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
            raise Denied("invalid", "an unknown method")
        parts = urlsplit(str(args.get("url", "")))
        scheme, host = parts.scheme.lower(), (parts.hostname or "").lower()
        port = parts.port or (443 if scheme == "https" else 80)
        if parts.username or parts.password or scheme not in ("https", "http") or not host:
            raise Denied("invalid", "an address with a scheme and a host, without credentials")
        listed = next(
            (
                h
                for h in grant.get("hosts") or []
                if h["host"] == host and int(h["port"]) == port and h["scheme"] == scheme
            ),
            None,
        )
        if listed is None:
            await self._count(key, host, refused=True)
            raise Denied("denied_host", f"{host}:{port} is not a host this plugin may reach")
        if self.allowed_hosts is not None and not self.allowed_hosts(host):
            await self._count(key, host, refused=True)
            raise Denied("denied_host", f"{host} is outside the portal's outbound allow-list")
        self._rate(key)
        addresses = await self._resolve(host, port)
        if not addresses:
            raise Denied("unreachable", f"{host} does not resolve")
        if not listed.get("private") and not all(is_public(a) for a in addresses):
            await self._count(key, host, refused=True)
            raise Denied("private_address", f"{host} resolves to a private address")
        address = addresses[0]
        netloc = f"[{address}]:{port}" if ":" in address else f"{address}:{port}"
        secret_headers, secret_query = await self._secrets(key, manifest, host)
        query = parts.query
        params = dict(args.get("params") or {})
        if params or secret_query:
            extra = urlencode({**{k: str(v) for k, v in params.items()}, **secret_query})
            query = f"{query}&{extra}" if query else extra
        url = urlunsplit((scheme, netloc, parts.path or "/", query, ""))
        headers = {
            str(k): str(v)
            for k, v in dict(args.get("headers") or {}).items()
            if str(k).lower() not in DROPPED_HEADERS
        }
        headers.update(secret_headers)
        headers["Host"] = host if port in (80, 443) else f"{host}:{port}"
        body: bytes | None = args.get("body") if isinstance(args.get("body"), (bytes, bytearray)) else None
        payload = args.get("json")
        timeout = min(MAX_TIMEOUT, max(0.5, float(args.get("timeout_s") or MAX_TIMEOUT)))
        extensions = {"sni_hostname": host} if scheme == "https" else {}
        async with httpx.AsyncClient(
            transport=self.transport,
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            event_hooks=egress.hooks(),
        ) as client:
            try:
                request = client.build_request(
                    method,
                    url,
                    headers=headers,
                    content=body,
                    json=payload if body is None else None,
                    extensions=extensions,
                )
                response = await client.send(request, stream=True)
                try:
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_BODY:
                            raise Denied("oversize", "the answer is larger than 5 MiB")
                        chunks.append(chunk)
                finally:
                    await response.aclose()
            except httpx.HTTPError as error:
                raise Denied("unreachable", f"{host}: {type(error).__name__}") from None
        content = b"".join(chunks)
        # a service that echoes what it received must not hand the plugin its secret back
        answer_headers = {k: v for k, v in response.headers.items() if k.lower() in KEPT_ANSWER_HEADERS}
        for value in [*secret_headers.values(), *secret_query.values()]:
            for form in {value, quote(value, safe=""), quote(value)}:
                content = content.replace(form.encode(), b"[secret]")
                answer_headers = {k: v.replace(form, "[secret]") for k, v in answer_headers.items()}
        await self._count(key, host, refused=False, sent=len(request.content or b""), received=len(content))
        return {"status": response.status_code, "headers": answer_headers, "body": content}
