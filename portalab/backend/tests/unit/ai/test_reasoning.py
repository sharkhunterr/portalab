"""Issue 171 — a thinking model (qwen3 on Ollama) reflects before answering, and its thoughts count in the
answer's length: the provider asks for « reasoning_effort » only when the administrators chose one."""

import json

import httpx

from portalab.capabilities.ai import ChatMessage
from portalab.modules.ai.providers.openai_compat import OpenAICompatibleProvider


async def _body(reasoning: str) -> dict[str, object]:
    seen: list[dict[str, object]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            content=b'data: {"choices":[{"delta":{"content":"Paris."}}]}\n\ndata: [DONE]\n\n',
            headers={"content-type": "text/event-stream"},
        )

    provider = OpenAICompatibleProvider(
        "http://ollama.lan:11434/v1",
        "qwen3:8b",
        lambda: None,
        transport=httpx.MockTransport(handle),
        reasoning=reasoning,
    )
    async for _ in provider.chat([ChatMessage("user", "Capital of France?")]):
        pass
    return seen[0]


async def test_reasoning_effort_only_when_chosen() -> None:
    assert (await _body("none"))["reasoning_effort"] == "none"
    assert "reasoning_effort" not in await _body("")
