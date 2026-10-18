"""The context a confined plugin's ``register(ctx)`` receives (spec 030, R1).

It has spec 023's surface (``portalab.sdk.PluginContext``): every registration is *recorded* and sent to
Portalab, which replays it on its own context with proxies in place of the plugin's callables. What a plugin
reaches at run time — its storage, portal data, the network, live channels, notifications, events, jobs —
goes through :class:`Wire` to Portalab, which checks every request against what the Admin granted.
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Protocol


class Wire(Protocol):
    async def ask(self, cap: str, args: dict[str, Any]) -> Any: ...


class Denied(PermissionError):
    """Portalab refused the request (not granted, outside the grant, over a limit)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _Part:
    def __init__(self, wire: Wire) -> None:
        self._wire = wire


class ConfinedDb(_Part):
    """``ctx.db``: one statement at a time, run by Portalab as this plugin's own database role."""

    async def execute(self, sql: str, params: Mapping[str, Any] | None = None) -> Sequence[Mapping[str, Any]]:
        answer = await self._wire.ask("db.execute", {"sql": sql, "params": dict(params or {})})
        return list(answer.get("rows", []))


class ConfinedPortal(_Part):
    """``ctx.portal``: an operation of Portalab's exposure catalog, accepted at review."""

    async def call(
        self, operation: str, params: Mapping[str, Any] | None = None, *, member: Any = None
    ) -> Any:
        args: dict[str, Any] = {"operation": operation, "params": dict(params or {})}
        if member is not None:
            args["member_id"] = str(getattr(member, "user_id", member))
        answer = await self._wire.ask("portal.call", args)
        return answer


class HttpResponse:
    def __init__(self, raw: Mapping[str, Any]) -> None:
        self.status_code = int(raw.get("status", 0))
        self.headers = dict(raw.get("headers") or {})
        self.content: bytes = raw.get("body") or b""

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        import json

        return json.loads(self.content or b"null")


class ConfinedHttp(_Part):
    """``ctx.http``: outgoing calls through Portalab, to the hosts the Admin accepted only."""

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        content: bytes | None = None,
        timeout: float = 10.0,  # noqa: ASYNC109 — Portalab's deadline, sent with the request
    ) -> HttpResponse:
        answer = await self._wire.ask(
            "http.request",
            {
                "method": method.upper(),
                "url": url,
                "headers": dict(headers or {}),
                "params": dict(params or {}),
                "json": json,
                "body": content,
                "timeout_s": float(timeout),
            },
        )
        return HttpResponse(answer)

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> HttpResponse:
        return await self.request("POST", url, **kwargs)


class ConfinedLive(_Part):
    """``ctx.live``: Portalab's live channels (no connection of the plugin's own)."""

    def __init__(self, wire: Wire, record: Callable[[str, tuple[Any, ...], dict[str, Any]], None]) -> None:
        super().__init__(wire)
        self._record = record

    async def publish(
        self,
        topic: str,
        payload: Mapping[str, Any],
        *,
        users: Sequence[Any] | None = None,
        permission: str | None = None,
        author: Any = None,
    ) -> None:
        await self._wire.ask(
            "live.publish",
            {
                "topic": topic,
                "payload": dict(payload),
                "users": [str(u) for u in users] if users is not None else None,
                "permission": permission,
                "author": str(author) if author is not None else None,
            },
        )

    def on_presence(self, topic: str, handler: Callable[..., Awaitable[None]]) -> None:
        self._record("live_presence", (topic, handler), {})


class RecordingContext:
    """What ``register(ctx)`` records, in order: ``(method, args, kwargs)``, values as given."""

    def __init__(self, key: str, wire: Wire, settings: Mapping[str, Any]) -> None:
        self.key = key
        self.owner = f"plugin:{key}"
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self._wire = wire
        self.settings: dict[str, Any] = dict(settings)
        self.db = ConfinedDb(wire)
        self.portal = ConfinedPortal(wire)
        self.http = ConfinedHttp(wire)
        self.live = ConfinedLive(wire, self._rec)

    def _rec(self, method: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.calls.append((method, args, kwargs))

    # --- at run time ---------------------------------------------------------------------------------
    async def notify(
        self, users: Sequence[Any], category: str, title: str, body: str = "", link: str | None = None
    ) -> int:
        answer = await self._wire.ask(
            "notify",
            {
                "users": [str(u) for u in users],
                "category": category,
                "title": title,
                "body": body,
                "link": link,
            },
        )
        return int(answer.get("sent", 0))

    async def emit(self, name: str, payload: Mapping[str, Any], *, subject_id: str | None = None) -> str:
        answer = await self._wire.ask(
            "events.emit", {"type": name, "payload": dict(payload), "subject_id": subject_id}
        )
        return str(answer.get("id", ""))

    async def enqueue(self, job: str, payload: Mapping[str, Any] | None = None) -> str:
        answer = await self._wire.ask("jobs.enqueue", {"job": job, "payload": dict(payload or {})})
        return str(answer.get("id", ""))

    # --- 023's registrations (recorded) ---------------------------------------------------------------
    def nav_entry(self, key: str, label_key: str, route: str, **kwargs: Any) -> None:
        self._rec("nav_entry", (key, label_key, route), kwargs)

    def nav_section(self, key: str, label_key: str, **kwargs: Any) -> None:
        self._rec("nav_section", (key, label_key), kwargs)

    def page(self, page: Any) -> None:
        self._rec("page", (page,), {})

    def widget(self, definition: Any, provider: Any) -> None:
        self._rec("widget", (definition, provider), {})

    def action(self, action: Any) -> None:
        self._rec("action", (action,), {})

    def search_provider(self, provider: Any) -> None:
        self._rec("search_provider", (provider,), {})

    def calendar_source(self, source: Any) -> None:
        self._rec("calendar_source", (source,), {})

    def statistics_pack(self, definitions: Sequence[Mapping[str, Any]]) -> None:
        self._rec("statistics_pack", (list(definitions),), {})

    def automation_action(self, action: Any) -> None:
        self._rec("automation_action", (action,), {})

    def ai_tool(self, tool: Any) -> None:
        self._rec("ai_tool", (tool,), {})

    def notification_category(self, key: str, label_key: str, **kwargs: Any) -> None:
        self._rec("notification_category", (key, label_key), kwargs)

    def theme(self, document: Mapping[str, Any]) -> None:
        self._rec("theme", (dict(document),), {})

    def i18n_catalog(self, bundle: Mapping[str, Mapping[str, Mapping[str, str]]]) -> None:
        self._rec("i18n_catalog", (bundle,), {})

    def permission(self, name: str, description: str, **kwargs: Any) -> str:
        self._rec("permission", (name, description), kwargs)
        return f"plugin:{self.key}.{name}"

    def setting(self, name: str, schema: Any, default: Any, description: str) -> str:
        type_name = getattr(schema, "__name__", str(schema))
        self._rec("setting", (name, type_name, default, description), {})
        return f"plugin.{self.key}.{name}"

    def event_type(self, name: str, **kwargs: Any) -> str:
        self._rec("event_type", (name,), kwargs)
        return f"plugin.{self.key}.{name}"

    def consume(self, name: str, types: Sequence[str], handler: Any) -> None:
        self._rec("consume", (name, list(types), handler), {})

    def provide(self, capability: str, provider: Any) -> None:
        self._rec("provide", (capability, provider), {})

    def product_type(self, product_type: Any) -> None:
        self._rec("product_type", (product_type,), {})

    def media_type(self, media_type: Any) -> None:
        self._rec("media_type", (media_type,), {})

    def profile_section(self, section: Any) -> None:
        self._rec("profile_section", (section,), {})

    def discovery_shelf(self, shelf: Any) -> None:
        self._rec("discovery_shelf", (shelf,), {})

    def connector(self, connector: Any) -> None:
        self._rec("connector", (connector,), {})

    def route(
        self,
        method: str,
        path: str,
        handler: Any,
        *,
        permission: str,
        exposure: str = "action",
        describe: Any = None,
    ) -> None:
        """A route of the plugin; ``exposure`` (``read``, ``action``, ``committing``) says what it does — a
        committing one needs ``describe(principal, query, body) -> {title, lines, amount?}``, what Portalab's
        own dialog shows the member before calling it."""
        kwargs: dict[str, Any] = {"permission": permission, "exposure": exposure}
        if describe is not None:
            kwargs["describe"] = describe
        self._rec("route", (method, path, handler), kwargs)

    def job(self, name: str, handler: Any, *, every_minutes: int | None = None) -> None:
        """A job run by Portalab's worker (queued with ``ctx.enqueue`` or every ``every_minutes``)."""
        self._rec("job", (name, handler), {"every_minutes": every_minutes})

    def privacy(self, *, export: Any, erase: Any) -> None:
        """What the plugin holds about a member: ``export(user_id) -> dict``, ``erase(user_id)`` (021)."""
        self._rec("privacy", (), {"export": export, "erase": erase})

    def slot(self, slot: str, key: str, **kwargs: Any) -> None:
        """A contribution to a slot of Portalab's interface, drawn by Portalab (blocks, data handler)."""
        self._rec("slot", (slot, key), kwargs)
