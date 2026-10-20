"""Issue 176 — a member rates an answer (as expected or not, and why), takes it back, and only their own;
the administrators' dashboard counts the questions, answers, errors, tools, response times and verdicts,
and shows the answers rated « not as expected » with their question; members cannot reach it."""

import json
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from portalab.capabilities.ai.testkit import call
from tests.integration.ai.conftest import AiHarness, make_tool, parse_sse, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_verdicts_and_the_dashboard(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    ai.tools.register(make_tool("docs.search", "ai.use"))
    await login(client, "ursula")
    conversation = await start(client)
    ai.provider.turns = [[call("docs.search", q="avatar")], ["Open your account and pick an image."]]
    sent = await client.post(
        f"/api/v1/ai/conversations/{conversation}/messages", json={"content": "How do I change my avatar?"}
    )
    [done] = [data for name, data in parse_sse(sent.text) if name == "done"]
    answer = done["message_id"]  # the answer is kept before the end is told: it can be rated at once

    rated = await client.put(
        f"/api/v1/ai/messages/{answer}/feedback", json={"rating": "down", "comment": "  The menu moved.  "}
    )
    assert rated.status_code == 200 and rated.json() == {"rating": -1, "comment": "The menu moved."}
    detail = (await client.get(f"/api/v1/ai/conversations/{conversation}")).json()
    assert [m["rating"] for m in detail["messages"] if m["role"] == "assistant"] == [-1]

    # issue 181: what the achievements count — the answer once, its first verdict, its first comment
    assert (
        await client.put(f"/api/v1/ai/messages/{answer}/feedback", json={"rating": "up"})
    ).status_code == 200
    async with ai.full.database.session() as session:
        told = (
            await session.execute(
                text(
                    "SELECT type, metadata::text FROM core.event_outbox "
                    "WHERE type IN ('ai.answered', 'ai.answer_rated')"
                )
            )
        ).all()
    assert sorted((kind, json.dumps(json.loads(data), sort_keys=True)) for kind, data in told) == sorted(
        (kind, json.dumps(data, sort_keys=True))
        for kind, data in (
            ("ai.answered", {"conversation": conversation, "sourced": False, "tools": 1}),
            ("ai.answer_rated", {"rating": "down", "commented": False}),
            ("ai.answer_rated", {"rating": "down", "commented": True}),
        )
    )
    await client.put(
        f"/api/v1/ai/messages/{answer}/feedback", json={"rating": "down", "comment": "The menu moved."}
    )

    await login(client, "ulrich")  # another member cannot rate it, nor reach the dashboard
    assert (
        await client.put(f"/api/v1/ai/messages/{answer}/feedback", json={"rating": "up"})
    ).status_code == 404
    assert (await client.get("/api/v1/admin/ai/dashboard")).status_code == 403

    await login(client, "boss")
    board = (await client.get("/api/v1/admin/ai/dashboard?days=7")).json()
    totals = board["totals"]
    assert (totals["questions"], totals["members"], totals["answered"], totals["errors"]) == (1, 1, 1, 0)
    assert totals["rated_down"] == 1 and totals["rated_up"] == 0 and totals["latency_median_ms"] is not None
    assert board["tools"] == [{"name": "docs.search", "calls": 1, "failed": 0}]
    [down] = board["rated_down"]
    assert down["question"] == "How do I change my avatar?" and down["comment"] == "The menu moved."
    assert down["answer"] == "Open your account and pick an image." and down["tools"] == ["docs.search"]
    assert sum(board["hours_utc"]) == 1 and board["members"][0]["questions"] == 1

    await login(client, "ursula")
    taken_back = await client.put(f"/api/v1/ai/messages/{answer}/feedback", json={"rating": None})
    assert taken_back.json() == {"rating": None, "comment": ""}
    await login(client, "boss")
    assert (await client.get("/api/v1/admin/ai/dashboard")).json()["totals"]["rated_down"] == 0
