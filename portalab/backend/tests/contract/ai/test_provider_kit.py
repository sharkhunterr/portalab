"""018 T004 — ``LLMProvider`` conformance kit run against the OpenAI-compatible adapter and a fake
Chat Completions server: streamed text, streamed tool calls reassembled, error mapping (auth, rate limit,
HTTP, timeout, oversized, invalid), the API key only in the Authorization header — never in errors/logs."""

import json
import logging

import httpx
import pytest

from portalab.capabilities.ai import ChatMessage, LLMProvider, ProviderError, ToolSpec
from portalab.capabilities.ai.testkit import LLMProviderContractKit, ScriptedProvider
from portalab.modules.ai.providers.openai_compat import OpenAICompatibleProvider

KEY = "sk-test-0123456789abcdef"


def sse(*chunks: dict[str, object]) -> str:
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


def fake_server(request: httpx.Request) -> httpx.Response:
    assert request.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(request.content)
    assert body["stream"] is True
    last = body["messages"][-1]["content"]
    if last == "__fail__":
        return httpx.Response(500, text="boom " + KEY)
    if body.get("tools"):
        name = body["tools"][0]["function"]["name"]
        stream = sse(
            {
                "choices": [
                    {"delta": {"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": name}}]}}
                ]
            },
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '{"serv'}}]}}]},
            {
                "choices": [
                    {"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'ice": "media"}'}}]}}
                ]
            },
            {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 3}},
        )
    else:
        stream = sse(
            {"choices": [{"delta": {"content": "Hel"}}]},
            {"choices": [{"delta": {"content": "lo"}}]},
            {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 2}},
        )
    return httpx.Response(200, text=stream, headers={"content-type": "text/event-stream"})


def adapter(handler: object = fake_server) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        "http://llm.test/v1",
        "test-model",
        lambda: KEY,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


class TestOpenAICompatible(LLMProviderContractKit):
    def make_provider(self) -> LLMProvider:
        return adapter()


class TestScripted(LLMProviderContractKit):
    def make_provider(self) -> LLMProvider:
        from portalab.capabilities.ai.testkit import call

        class Kit(ScriptedProvider):
            async def chat(self, messages, tools=(), *, max_tokens=1024, timeout=60):  # type: ignore[no-untyped-def]  # noqa: ASYNC109
                if messages[-1].content == "__fail__":
                    raise ProviderError("unreachable")
                self.turns = [[call(tools[0].name, service="media")]] if tools else [["hello"]]
                async for event in super().chat(messages, tools, max_tokens=max_tokens, timeout=timeout):
                    yield event

        return Kit()


async def collect(
    provider: OpenAICompatibleProvider, text: str = "hi", tools: list[ToolSpec] | None = None
) -> list:
    return [e async for e in provider.chat([ChatMessage("user", text)], tools or [], max_tokens=8, timeout=5)]


async def test_text_usage_and_tool_arguments() -> None:
    events = await collect(adapter())
    assert "".join(e.text for e in events if e.kind == "delta") == "Hello"
    assert [(e.tokens_in, e.tokens_out) for e in events if e.kind == "usage"] == [(5, 2)]
    tool = ToolSpec("services__status", "state", {"type": "object", "properties": {}})
    calls = [e.tool_call for e in await collect(adapter(), tools=[tool]) if e.kind == "tool_call"]
    assert calls[0] is not None and calls[0].arguments == {"service": "media"} and calls[0].id == "call_1"


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(401), "auth"),
        (httpx.Response(429), "rate_limited"),
        (httpx.Response(503), "http_503"),
        (httpx.Response(200, text="data: {not json\n\n"), "invalid_response"),
        (httpx.Response(200, text="data: " + "x" * 1_000_001 + "\n\n"), "oversized"),
    ],
)
async def test_errors_are_stable_codes(
    response: httpx.Response, code: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ProviderError) as raised:
        await collect(adapter(lambda request: response))
    assert raised.value.code == code
    assert KEY not in str(raised.value) and KEY not in caplog.text


async def test_timeout_and_unreachable() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    for handler, code in ((slow, "timeout"), (down, "unreachable")):
        with pytest.raises(ProviderError) as raised:
            await collect(adapter(handler))
        assert raised.value.code == code


async def test_not_configured() -> None:
    provider = OpenAICompatibleProvider("", "", lambda: None)
    with pytest.raises(ProviderError) as raised:
        await collect(provider)
    assert raised.value.code == "not_configured"
