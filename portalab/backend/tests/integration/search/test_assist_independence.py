"""008 T018 — the AI and classic search fail independently: no assistant ⇒ the assist stream says
unavailable and ``/search`` is unaffected; a failing classic source still lets the assistant answer from
the permitted references; ``source_ref`` vs ``synthesis`` are distinct; references the principal may not
see never reach the assistant; an assistant crash ends the stream with an error event."""

import json
from collections.abc import AsyncIterator, Sequence

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.search import ASSISTANT, AssistEvent, IntentSuggestion
from portalab.core.authz_port import Principal
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.search.conftest import SearchHarness
from tests.unit.search.fakes import FakeProvider

pytestmark = pytest.mark.integration


class Assistant:
    def __init__(self, crash: bool = False) -> None:
        self.crash = crash
        self.received: list[tuple[str, str]] = []

    async def stream(
        self, query: str, principal: Principal, refs: Sequence[tuple[str, str]]
    ) -> AsyncIterator[AssistEvent]:
        self.received = list(refs)
        for kind, item_id in refs:
            yield AssistEvent("source_ref", {"kind": kind, "id": item_id})
        yield AssistEvent("source_ref", {"kind": "tickets", "id": "made-up"})  # not a real permitted result
        if self.crash:
            raise RuntimeError("model crashed")
        yield AssistEvent("synthesis", {"text": f"{len(refs)} relevant results"})

    async def interpret(
        self, text: str, principal: Principal, page: str | None
    ) -> Sequence[IntentSuggestion]:
        return []


def events(body: str) -> list[tuple[str, dict[str, object]]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


async def test_independence(app: FastAPI, client: httpx.AsyncClient, search: SearchHarness) -> None:
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    search.registry.register(FakeProvider("tickets", permission="audit.read"), owner="module:support")
    no_ai = await client.post("/api/v1/search/assist", json={"q": "media"})
    assert no_ai.headers["content-type"].startswith("text/event-stream")
    assert events(no_ai.text) == [("status", {"state": "unavailable"})]
    assert (await client.post("/api/v1/search", json={"q": "media"})).status_code == 200

    assistant = Assistant()
    search.full.identity.capabilities.provide(ASSISTANT, assistant, instance_ref="ai", owner="module:ai")

    async def down() -> list[object]:
        raise RuntimeError("directory down")

    search.directory.services = down  # type: ignore[method-assign]
    classic = (await client.post("/api/v1/search", json={"q": "media"})).json()
    assert {g["kind"]: g["state"] for g in classic["groups"]}["services"] == "unavailable"
    refs = [{"kind": "navigation", "id": "health.services"}, {"kind": "tickets", "id": "0"}]
    answer = events((await client.post("/api/v1/search/assist", json={"q": "media", "refs": refs})).text)
    assert assistant.received == [("navigation", "health.services")]  # forbidden ticket never sent
    assert [e for e, _ in answer] == ["status", "source_ref", "synthesis", "status"]
    assert answer[1][1] == {"kind": "navigation", "id": "health.services"}

    assistant.crash = True
    crashed = events((await client.post("/api/v1/search/assist", json={"q": "media"})).text)
    assert crashed[-1] == ("error", {"code": "search.assist_failed"})
    assert (await client.post("/api/v1/search", json={"q": "media"})).status_code == 200
