"""MCP servers as an optional access/action layer (T030; US7), e.g. MCParr.

Minimal MCP client over the *Streamable HTTP* transport (JSON-RPC 2.0 ``initialize`` → ``tools/list`` /
``tools/call``; JSON or SSE answers) built on ``httpx`` — no SDK dependency (deviation from the plan,
recorded in docs/ai.md). Exposure is decided **only** by the Admin allow-list: each entry maps a server tool
to a portal permission and a sensitivity; anything else is invisible. The portal authorizes the AI
principal before every call (executor), sensitive tools go through confirmation, credentials come from the
secret setting ``ai.mcp.tokens`` and never reach the model. A server that is down simply contributes no
tools."""

import json
import re
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

import httpx

from portalab.capabilities.ai import AITool, ExternalToolDef, ResultState, Sensitivity, SourceRef, ToolResult
from portalab.core import egress
from portalab.core.authz_port import Principal
from portalab.core.permissions import PermissionRegistry, default_permissions
from portalab.core.time import Clock, utc_now
from portalab.modules.ai.observability import log, metrics

PROTOCOL_VERSION = "2025-06-18"
MAX_TEXT = 6000
CACHE_SECONDS = 60.0
_SLUG = re.compile(r"[^a-z0-9_]+")


class McpError(Exception):
    pass


def slug(value: str) -> str:
    cleaned = _SLUG.sub("_", value.lower()).strip("_")
    return cleaned if cleaned[:1].isalpha() else f"t_{cleaned}"


class McpHttpSource:
    """One MCP server (``ExternalToolSource``)."""

    def __init__(
        self,
        name: str,
        url: str,
        token: Callable[[], str | None],
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.name = name
        self.url = url
        egress.EGRESS.allow(urlsplit(url).hostname, "ai tools")  # 030: a configured tool server
        self.token = token
        self.transport = transport
        self.timeout = timeout
        self._next = 0

    def _headers(self, session: str | None) -> dict[str, str]:
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        token = self.token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if session:
            headers["Mcp-Session-Id"] = session
        return headers

    async def _post(
        self,
        client: httpx.AsyncClient,
        method: str,
        params: Mapping[str, Any],
        session: str | None,
        *,
        notify: bool = False,
    ) -> tuple[Any, str | None]:
        self._next += 1
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": dict(params)}
        if not notify:
            message["id"] = self._next
        response = await client.post(self.url, json=message, headers=self._headers(session))
        session = response.headers.get("mcp-session-id", session)
        if notify:
            return None, session
        if response.status_code >= 400:
            raise McpError(f"http_{response.status_code}")
        if response.headers.get("content-type", "").startswith("text/event-stream"):
            payload = None
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    candidate = json.loads(line[5:].strip() or "null")
                    if isinstance(candidate, dict) and candidate.get("id") == message["id"]:
                        payload = candidate
                        break
        else:
            payload = response.json()
        if not isinstance(payload, dict):
            raise McpError("invalid_response")
        if "error" in payload:
            raise McpError("rpc_error")
        return payload.get("result"), session

    async def _session(self, method: str, params: Mapping[str, Any]) -> Any:
        async with httpx.AsyncClient(
            transport=self.transport, timeout=self.timeout, follow_redirects=False, event_hooks=egress.hooks()
        ) as client:
            _, session = await self._post(
                client,
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "portalab", "version": "1"},
                },
                None,
            )
            await self._post(client, "notifications/initialized", {}, session, notify=True)
            result, _ = await self._post(client, method, params, session)
            return result

    async def list_tools(self) -> Sequence[ExternalToolDef]:
        result = await self._session("tools/list", {})
        tools = (result or {}).get("tools") or []
        return [
            ExternalToolDef(
                str(t.get("name")), str(t.get("description") or "")[:300], t.get("inputSchema") or {}
            )
            for t in tools
            if isinstance(t, dict) and t.get("name")
        ]

    async def call(self, tool: str, arguments: Mapping[str, Any]) -> Any:
        return await self._session("tools/call", {"name": tool, "arguments": dict(arguments)})


class McpToolset:
    """Allow-listed MCP tools as ``AITool``s, cached briefly; refreshed before a turn when stale."""

    def __init__(
        self,
        servers: Callable[[], Sequence[Mapping[str, Any]]],
        tokens: Callable[[], Mapping[str, str]],
        *,
        permissions: PermissionRegistry = default_permissions,
        clock: Clock | None = None,
    ) -> None:
        self.servers = servers
        self.tokens = tokens
        self.permissions = permissions
        self.clock = clock
        self.transport: httpx.AsyncBaseTransport | None = None
        self._tools: list[AITool] = []
        self._states: dict[str, str] = {}
        self._discovered: dict[str, list[str]] = {}
        self._at = 0.0
        self._fingerprint = ""

    def tools(self) -> list[AITool]:
        return list(self._tools)

    def states(self) -> dict[str, str]:
        return dict(self._states)

    def discovered(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in self._discovered.items()}

    def source(self, server: Mapping[str, Any]) -> McpHttpSource:
        name = str(server.get("name"))
        return McpHttpSource(
            name, str(server.get("url")), lambda: self.tokens().get(name), transport=self.transport
        )

    async def refresh(self, *, force: bool = False) -> None:
        servers = list(self.servers() or [])
        fingerprint = json.dumps(servers, sort_keys=True, default=str)
        if not force and fingerprint == self._fingerprint and time.monotonic() - self._at < CACHE_SECONDS:
            return
        tools: list[AITool] = []
        states: dict[str, str] = {}
        discovered: dict[str, list[str]] = {}
        for server in servers:
            name = str(server.get("name") or "")
            if not name or not str(server.get("url") or "").startswith(("http://", "https://")):
                continue
            source = self.source(server)
            try:
                listed = {t.name: t for t in await source.list_tools()}
            except Exception as exc:
                states[name] = "unavailable"
                metrics.increment("ai.mcp.unavailable")
                log.warning(
                    "mcp server unavailable", extra={"fields": {"server": name, "error": type(exc).__name__}}
                )
                continue
            states[name] = "ok"
            discovered[name] = sorted(listed)
            for entry in server.get("allowlist") or []:
                tool = self._tool(source, entry, listed)
                if tool is not None:
                    tools.append(tool)
        self._tools, self._states, self._discovered = tools, states, discovered
        self._at, self._fingerprint = time.monotonic(), fingerprint

    def _tool(
        self, source: McpHttpSource, entry: Mapping[str, Any], listed: Mapping[str, ExternalToolDef]
    ) -> AITool | None:
        remote = str(entry.get("tool") or "")
        permission = str(entry.get("permission") or "")
        declared = entry.get("sensitivity")
        sensitivity: Sensitivity = declared if declared in ("read", "write") else "sensitive"
        definition = listed.get(remote)
        if definition is None or self.permissions.get(permission) is None:
            return None  # unmapped or unknown: invisible
        schema = dict(definition.input_schema) if definition.input_schema.get("type") == "object" else {}
        schema = schema or {"type": "object", "properties": {}}
        server, clock = source.name, self.clock

        async def handler(principal: Principal, params: Mapping[str, Any]) -> ToolResult:
            try:
                result = await source.call(remote, params)
            except Exception:
                return ToolResult("unavailable", detail="mcp server unavailable")
            texts = [
                str(c.get("text", ""))
                for c in (result or {}).get("content") or []
                if isinstance(c, dict) and c.get("type") == "text"
            ]
            source_ref = SourceRef(
                "mcp", f"mcp:{server}/{remote}", f"{server} · {remote}", "real", utc_now(clock)
            )
            state: ResultState = "error" if (result or {}).get("isError") else "ok"
            return ToolResult(state, {"text": "\n".join(texts)[:MAX_TEXT]}, (source_ref,))

        return AITool(
            name=f"mcp.{slug(server)}.{slug(remote)}",
            description=f"[{server}] {definition.description}"[:300],
            params_schema=schema,
            required_permission=permission,
            sensitivity=sensitivity,
            handler=handler,
            owner=f"mcp:{server}",
        )
