"""AI integration fixtures: the AI module on the full platform with isolated registries, a scripted
provider, and helpers to run a turn through the SSE API."""

import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.ai import AITool, AIToolRegistry, SourceRef, ToolResult
from portalab.capabilities.ai.testkit import ScriptedProvider
from portalab.capabilities.events import EventTypeRegistry
from portalab.capabilities.navigation import NavigationRegistry
from portalab.capabilities.search import SearchRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.ai.module import AiModule
from tests.integration.privacy.conftest import NOW
from tests.privacy_fixtures import FullPlatform, make_full_platform


@dataclass
class Recorder:
    """A tool handler that records each call and answers with a fixed result."""

    result: ToolResult = field(default_factory=lambda: ToolResult("ok", {"answer": 42}))
    calls: list[tuple[Principal, dict[str, Any]]] = field(default_factory=list)

    async def __call__(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        self.calls.append((principal, dict(params)))
        return self.result


def make_tool(
    name: str,
    permission: str,
    sensitivity: Any = "read",
    handler: Any = None,
    *,
    schema: Mapping[str, Any] | None = None,
    owner: str = "module:test",
) -> AITool:
    return AITool(
        name,
        f"test tool {name}",
        schema or {"type": "object", "properties": {"q": {"type": "string"}}, "additionalProperties": False},
        permission,
        sensitivity,
        handler or Recorder(),
        summarize=lambda params: f"Run {name} with {sorted(params.items())}",
        owner=owner,
    )


@dataclass
class AiHarness:
    full: FullPlatform
    module: AiModule
    tools: AIToolRegistry
    provider: ScriptedProvider
    clock: FixedClock
    search: SearchRegistry
    navigation: NavigationRegistry
    people: dict[str, UUID] = field(default_factory=dict)

    def p(self, name: str) -> Principal:
        return Principal(user_id=self.people[name])


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def ai(database: Database, tmp_path: Path, clock: FixedClock) -> AiHarness:
    full = make_full_platform(database, tmp_path / "blobs", clock)
    await full.authz.catalog.sync()
    tools, search, navigation = AIToolRegistry(), SearchRegistry(), NavigationRegistry()
    module = AiModule(
        database,
        full.authz.engine.events,
        full.authz.audit,
        full.identity.capabilities,
        full.authz.engine,
        clock=clock,
        tools=tools,
        event_types=EventTypeRegistry(),
        search=search,
        navigation=navigation,
    )
    provider = ScriptedProvider()
    module.provider_override = provider
    module.config = type(module.config)(enabled=True, rate_limit_per_minute=100)
    module.register()
    return AiHarness(full, module, tools, provider, clock, search, navigation)


@pytest.fixture
def app(ai: AiHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = ai.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        ai=ai.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http


@pytest.fixture
async def people(app: FastAPI, ai: AiHarness) -> dict[str, UUID]:
    """``boss`` (admin), ``ursula`` and ``ulrich`` (users)."""
    from tests.authz_fixtures import make_admin
    from tests.integration.identity.helpers import create_user, module_of

    out = {name: await create_user(module_of(app), name) for name in ("boss", "ursula", "ulrich")}
    await make_admin(ai.full, out["boss"])
    ai.people = out
    return out


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.strip().split("\n\n"):
        name, data = "", ""
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = line[6:]
        if name:
            events.append((name, json.loads(data or "{}")))
    return events


async def start(client: httpx.AsyncClient, context: dict[str, str] | None = None) -> str:
    response = await client.post("/api/v1/ai/conversations", json={"context": context} if context else {})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def say(client: httpx.AsyncClient, conversation: str, text: str) -> list[tuple[str, dict[str, Any]]]:
    response = await client.post(f"/api/v1/ai/conversations/{conversation}/messages", json={"content": text})
    assert response.status_code == 200, response.text
    return parse_sse(response.text)


def done(events: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    found = [data for name, data in events if name == "done"]
    assert found, f"no done event in {events}"
    return found[0]


def names(events: list[tuple[str, dict[str, Any]]]) -> list[str]:
    return [name for name, _ in events]


def source(kind: str, ref: str, title: str) -> SourceRef:
    return SourceRef(kind, ref, title, "real", NOW)
