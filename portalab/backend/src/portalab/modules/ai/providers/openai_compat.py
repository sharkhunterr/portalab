"""OpenAI-compatible Chat Completions adapter (T007; R6): hosted APIs and local servers (Ollama, vLLM,
LM Studio…). Streams Server-Sent Events, assembles streamed tool calls, maps every failure to a stable
``ProviderError`` code — the API key is sent as a bearer header only, never logged or echoed."""

import json
from collections.abc import AsyncIterator, Callable, Sequence
from typing import Any

import httpx

from portalab.capabilities.ai import (
    ChatMessage,
    LLMEvent,
    ProviderCapabilities,
    ProviderError,
    ToolCall,
    ToolSpec,
)

MAX_LINE = 1_000_000


def _message(message: ChatMessage) -> dict[str, Any]:
    out: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        out["tool_calls"] = [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.name, "arguments": json.dumps(dict(c.arguments))},
            }
            for c in message.tool_calls
        ]
    if message.tool_call_id:
        out["tool_call_id"] = message.tool_call_id
    return out


class OpenAICompatibleProvider:
    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: Callable[[], str | None],
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        max_context: int = 8192,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.transport = transport
        self.max_context = max_context

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(tools=True, streaming=True, max_context=self.max_context)

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec] = (),
        *,
        max_tokens: int = 1024,
        timeout: float = 60,  # noqa: ASYNC109 — part of the provider protocol
    ) -> AsyncIterator[LLMEvent]:
        if not self.endpoint or not self.model:
            raise ProviderError("not_configured")
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [_message(m) for m in messages],
            "stream": True,
            "max_tokens": max_tokens,
            "stream_options": {"include_usage": True},
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": dict(t.parameters),
                    },
                }
                for t in tools
            ]
        headers = {"Accept": "text/event-stream"}
        key = self.api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        partial: dict[int, dict[str, Any]] = {}
        try:
            async with (
                httpx.AsyncClient(
                    transport=self.transport, timeout=timeout, follow_redirects=False
                ) as client,
                client.stream(
                    "POST", f"{self.endpoint}/chat/completions", json=body, headers=headers
                ) as response,
            ):
                if response.status_code in (401, 403):
                    raise ProviderError("auth")
                if response.status_code == 429:
                    raise ProviderError("rate_limited")
                if response.status_code >= 400:
                    raise ProviderError(f"http_{response.status_code}")
                async for line in response.aiter_lines():
                    if len(line) > MAX_LINE:
                        raise ProviderError("oversized")
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise ProviderError("invalid_response") from exc
                    usage = chunk.get("usage")
                    if usage:
                        yield LLMEvent(
                            "usage",
                            tokens_in=int(usage.get("prompt_tokens", 0)),
                            tokens_out=int(usage.get("completion_tokens", 0)),
                        )
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            yield LLMEvent("delta", text=str(delta["content"]))
                        for call in delta.get("tool_calls") or []:
                            slot = partial.setdefault(
                                int(call.get("index", 0)), {"id": "", "name": "", "arguments": ""}
                            )
                            slot["id"] = call.get("id") or slot["id"]
                            function = call.get("function") or {}
                            slot["name"] = function.get("name") or slot["name"]
                            slot["arguments"] += function.get("arguments") or ""
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("unreachable") from exc
        for index in sorted(partial):
            slot = partial[index]
            try:
                arguments = json.loads(slot["arguments"] or "{}")
            except json.JSONDecodeError:
                arguments = {"__invalid__": True}
            yield LLMEvent(
                "tool_call",
                tool_call=ToolCall(
                    slot["id"] or f"call_{index}",
                    slot["name"],
                    arguments if isinstance(arguments, dict) else {},
                ),
            )
        yield LLMEvent("done")
