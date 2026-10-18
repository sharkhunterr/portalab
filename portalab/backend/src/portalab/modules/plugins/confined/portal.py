"""Portal data for a confined plugin (spec 030, R7): an operation of 029's exposure catalog, accepted at
review, called inside Portalab as the member the plugin's current call is for.

Only operations the catalog labels ``read`` or ``action`` and the Admin accepted are called; committing,
forbidden and unlabelled ones are refused. The request goes through Portalab's own application (its
authorization, its rate limits, its intrusion guard), in process, with the member as a ``plugin``-channel
principal acting for them — no session, no cookie, no token is ever made or handed to the plugin.
"""

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlencode

from portalab.capabilities.exposure import Exposure, ExposureRegistry, default_exposure
from portalab.core.authz_port import Principal
from portalab.modules.plugins.confined.host import Denied
from portalab.modules.plugins.manifest.schema import Manifest

MAX_BODY = 1024 * 1024
ALLOWED = (Exposure.READ, Exposure.ACTION)


def fill(template: str, params: dict[str, Any]) -> str:
    """``/api/v1/media/{object_id}`` with its parameters (taken out of ``params``), each one quoted."""
    out = template
    while "{" in out:
        start, end = out.index("{"), out.index("}")
        name = out[start + 1 : end]
        if name not in params:
            raise Denied("invalid", f"the operation needs {name}")
        value = quote(str(params.pop(name)), safe="")
        if not value or value in (".", ".."):
            raise Denied("invalid", f"{name} is empty")
        out = out[:start] + value + out[end + 1 :]
    return out


class PortalCalls:
    def __init__(self, registry: ExposureRegistry = default_exposure) -> None:
        self.registry = registry
        self.app: Any = None  # Portalab's ASGI application, set by the composition root

    async def __call__(
        self, key: str, manifest: Manifest, grant: Mapping[str, Any], args: Mapping[str, Any], acting: Any
    ) -> dict[str, Any]:
        operation = str(args.get("operation", ""))
        method, _, template = operation.partition(" ")
        method = method.upper()
        label = self.registry.resolve(method, template)
        if label.exposure not in ALLOWED or operation not in list(grant.get("operations") or []):
            raise Denied("denied_operation", f"{operation[:80]} is not open to this plugin")
        if not isinstance(acting, Principal) or acting.user_id is None:
            raise Denied("denied", "portal data is read for the member of a call only")
        if self.app is None:
            raise Denied("unavailable", "portal data is not available in this process")
        params = dict(args.get("params") or {})
        path = fill(template, params)
        query = b""
        body = b""
        if method == "GET":
            query = urlencode(
                {k: v for k, v in params.items() if isinstance(v, (str, int, float, bool))}, doseq=False
            ).encode()
        else:
            body = json.dumps(params, default=str).encode()
        principal = Principal(user_id=acting.user_id, channel="plugin", acting_for=acting.user_id)
        status, content_type, content = await self._request(key, method, path, query, body, principal)
        value: Any
        if content_type.startswith("application/json") or content_type.startswith("application/problem+json"):
            value = json.loads(content or b"null")
        else:
            value = content
        return {"status": status, "content_type": content_type, "body": value}

    async def _request(
        self, key: str, method: str, path: str, query: bytes, body: bytes, principal: Principal
    ) -> tuple[int, str, bytes]:
        headers = [(b"host", b"portal.internal"), (b"accept", b"application/json")]
        if body:
            headers += [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query,
            "root_path": "",
            "headers": headers,
            "client": (f"plugin:{key}", 0),  # its own rate limit and intrusion record
            "server": ("portal.internal", 443),
            "state": {"principal": principal},  # resolved already: no session is looked for
        }
        sent = False
        status = 0
        content_type = ""
        chunks: list[bytes] = []
        size = 0

        async def receive() -> dict[str, Any]:
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: Mapping[str, Any]) -> None:
            nonlocal status, content_type, size
            if message["type"] == "http.response.start":
                status = int(message["status"])
                for name, value in message.get("headers", []):
                    if name.lower() == b"content-type":
                        content_type = value.decode("latin-1")
            elif message["type"] == "http.response.body":
                chunk = bytes(message.get("body", b""))
                size += len(chunk)
                if size > MAX_BODY:
                    raise Denied("oversize", "the answer is larger than 1 MiB")
                chunks.append(chunk)

        await self.app(scope, receive, send)
        return status, content_type, b"".join(chunks)
