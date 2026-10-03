"""Hello — the code part of the sample plugin. It imports only ``portalab.sdk`` and the standard library
(checked by the install-time scanner) and contributes through ``ctx`` so the portal can remove everything
when the plugin is disabled."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from portalab.sdk import (
    AITool,
    ActionDef,
    ActionType,
    ActivationResult,
    BaseModel,
    CalendarItem,
    CalendarSourceResult,
    Candidate,
    ConnectorManifest,
    DiscoveryShelf,
    MediaType,
    PluginContext,
    ProductType,
    ProfileSection,
    ProviderResult,
    SearchItem,
    SectionResult,
    SourceRef,
    TestResult,
    ToolResult,
    WidgetDefinition,
    WidgetPayload,
)

KEY = "hello"


class Counter:
    def __init__(self, ctx: PluginContext) -> None:
        self.ctx = ctx

    async def count(self) -> int:
        rows = await self.ctx.db.execute("SELECT count(*) AS n FROM greetings")
        return int(rows[0]["n"]) if rows else 0


class CounterWidget:
    def __init__(self, counter: Counter) -> None:
        self.counter = counter

    async def load(self, principal: Any, config: Mapping[str, Any], ctx: Any) -> WidgetPayload:
        return WidgetPayload("available", as_of=datetime.now(UTC), data={"value": await self.counter.count()})


class GreetingSearch:
    kind = "plugin:hello.greetings"
    label_key = "plugin.hello:nav.home"
    required_permission = "plugin:hello.view"

    def facets(self) -> list[Any]:
        return []

    async def search(self, query: Any, principal: Any, ctx: Any, *, limit: int, cursor: str | None) -> ProviderResult:
        if "hello" not in query.normalized:
            return ProviderResult()
        return ProviderResult(items=[SearchItem(kind=self.kind, id="hello", title="Hello", url_ref="/plugins/hello/main")])

    async def hydrate(self, ids: Any, principal: Any) -> list[SearchItem]:
        return [SearchItem(kind=self.kind, id="hello", title="Hello", url_ref="/plugins/hello/main")] if "hello" in ids else []


class HelloCalendar:
    kind = "plugin_hello"
    label_key = "plugin.hello:nav.home"

    async def items(self, start: datetime, end: datetime, viewer: Any, ctx: Any) -> CalendarSourceResult:
        at = start + timedelta(hours=1)
        return CalendarSourceResult(
            [CalendarItem(source_kind=self.kind, source_id="day", type="event", title="Hello day", starts_at=at)]
        )

    async def item(self, source_id: str, viewer: Any) -> CalendarItem | None:
        return None


class Sticker:
    async def activate(self, ownership: Any) -> ActivationResult:
        return ActivationResult("active")

    async def deactivate(self, ownership: Any) -> None:
        return None


class HelloConfig(BaseModel):
    greeting: str = "Hello"


class HelloConnector:
    key = "hello_conn"
    name = "Hello"
    manifest = ConnectorManifest(version="1.0.0")
    config_schema = HelloConfig
    secret_fields = frozenset()
    provides: tuple[Any, ...] = ()

    async def test_connection(self, service: Any) -> TestResult:
        return TestResult(ok=True, reachable=True, authenticated=True)

    async def discover(self, targets: Any) -> list[Candidate]:
        return []

    async def sync(self, ctx: Any, cursor: Any) -> Any:
        if False:  # pragma: no cover — nothing to synchronize
            yield None

    def provider(self, capability: str, service: Any) -> Any:
        return None

    def actions(self) -> dict[str, Any]:
        return {}


def register(ctx: PluginContext) -> None:
    counter = Counter(ctx)

    async def count(principal: Any, query: Mapping[str, Any], body: Any) -> dict[str, Any]:
        return {"state": "available", "value": await counter.count(), "label": "greetings"}

    async def greet(principal: Any, query: Mapping[str, Any], body: Any) -> dict[str, Any]:
        name = str((body or {}).get("name", ""))[:40] or "friend"
        await ctx.db.execute("INSERT INTO greetings (name) VALUES (:name)", {"name": name})
        return {"state": "available", "message": f"Hello, {name}!"}

    async def boom(principal: Any, query: Mapping[str, Any], body: Any) -> dict[str, Any]:
        raise RuntimeError("the sample plugin fails on purpose")

    ctx.route("GET", "greetings/count", count, permission="plugin:hello.view")
    ctx.route("POST", "greet", greet, permission="plugin:hello.view")
    ctx.route("GET", "boom", boom, permission="plugin:hello.view")
    ctx.widget(
        WidgetDefinition(
            key="plugin:hello.counter",
            owner="plugin:hello",
            title_key="plugin.hello:page.count",
            required_permission="plugin:hello.view",
            template="stat",
        ),
        CounterWidget(counter),
    )
    ctx.search_provider(GreetingSearch())
    ctx.action(ActionDef("plugin:hello.open", "plugin.hello:nav.home", "plugin:hello.view", route="/plugins/hello/main"))
    ctx.event_type("waved", automatable=True)
    ctx.calendar_source(HelloCalendar())

    async def run(params: Mapping[str, Any], principal: Any) -> Mapping[str, Any]:
        return {"greeted": params.get("name", "friend")}

    ctx.automation_action(
        ActionType("plugin:hello.greet", "Greet someone", "plugin:hello.view", "name", run, params_schema={"name": "string?"})
    )

    async def tool(principal: Any, params: Mapping[str, Any]) -> ToolResult:
        return ToolResult("ok", {"greeting": "Hello"}, (SourceRef("plugin", "plugin:hello", "Hello", "real", datetime.now(UTC), "/plugins/hello/main"),))

    ctx.ai_tool(
        AITool(
            name="hello.greet",
            description="Say hello.",
            params_schema={"type": "object", "properties": {}, "additionalProperties": False},
            required_permission="plugin:hello.view",
            sensitivity="read",
            handler=tool,
        )
    )

    async def on_verified(envelope: Any, context: Any) -> None:
        return None

    ctx.consume("welcome", ["user.verified"], on_verified)
    ctx.provide("plugin.hello.greeter", counter)
    ctx.product_type(ProductType("plugin:hello.sticker", "plugin:hello", Sticker(), payload_fields=("shape",)))
    ctx.media_type(MediaType("hello.song", "plugin.hello:nav.home", "plugin:hello"))

    async def badge(owner: Any, viewer: Any) -> SectionResult:
        return SectionResult("available", {"text": "Says hello"})

    async def picks(viewer: Any, limit: int) -> list[dict[str, Any]]:
        return [{"id": "hello", "title": "Hello", "url": "/plugins/hello/main"}]

    ctx.profile_section(ProfileSection("plugin:hello.badge", "plugin:hello", "progression", badge, 90))
    ctx.discovery_shelf(DiscoveryShelf("plugin:hello.picks", "plugin:hello", picks, 90))
    ctx.connector(HelloConnector())
