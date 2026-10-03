"""Scripted provider and the ``LLMProvider`` conformance kit (spec 018 T004).

``ScriptedProvider(turns)`` answers each ``chat`` call with the next scripted turn: a list of text chunks
and/or ``ToolCall``s — deterministic tool-calling conversations for tests. Adapters prove themselves with::

    class TestMyProvider(LLMProviderContractKit):
        def make_provider(self) -> LLMProvider: ...      # pointed at a fake server answering the kit's script
"""

import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from portalab.capabilities.ai import (
    ChatMessage,
    LLMEvent,
    ProviderCapabilities,
    ProviderError,
    ToolCall,
    ToolSpec,
)

Turn = Sequence[str | ToolCall]


@dataclass
class ScriptedProvider:
    turns: list[Turn] = field(default_factory=list)
    calls: list[tuple[list[ChatMessage], list[ToolSpec]]] = field(default_factory=list)
    fail: str | None = None  # ProviderError code to raise
    delay: float = 0.0

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec] = (),
        *,
        max_tokens: int = 1024,
        timeout: float = 60,  # noqa: ASYNC109 — part of the provider protocol
    ) -> AsyncIterator[LLMEvent]:
        self.calls.append((list(messages), list(tools)))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise ProviderError(self.fail)
        turn = self.turns.pop(0) if self.turns else ["…"]
        for item in turn:
            if isinstance(item, ToolCall):
                yield LLMEvent("tool_call", tool_call=item)
            else:
                yield LLMEvent("delta", text=item)
        yield LLMEvent("usage", tokens_in=sum(len(m.content) for m in messages) // 4, tokens_out=10)
        yield LLMEvent("done")


def call(name: str, call_id: str = "c1", **arguments: Any) -> ToolCall:
    return ToolCall(call_id, name, arguments)


class LLMProviderContractKit:
    """Subclass and implement ``make_provider``; the provider must answer the kit's scripted exchanges."""

    def make_provider(self) -> Any:
        raise NotImplementedError

    async def collect(
        self, provider: Any, messages: list[ChatMessage], tools: list[ToolSpec] | None = None
    ) -> list[LLMEvent]:
        return [event async for event in provider.chat(messages, tools or [], max_tokens=64, timeout=5)]

    async def test_streams_text_then_done(self) -> None:
        events = await self.collect(self.make_provider(), [ChatMessage("user", "say hello")])
        assert any(e.kind == "delta" and e.text for e in events)
        assert events[-1].kind == "done"

    async def test_tool_call_round_trip(self) -> None:
        tool = ToolSpec(
            "health.service_state",
            "state of a service",
            {"type": "object", "properties": {"service": {"type": "string"}}},
        )
        events = await self.collect(self.make_provider(), [ChatMessage("user", "is media up?")], [tool])
        calls = [e.tool_call for e in events if e.kind == "tool_call"]
        assert calls and calls[0] is not None and calls[0].name == "health.service_state"
        assert isinstance(calls[0].arguments, dict)

    async def test_errors_are_mapped(self) -> None:
        provider = self.make_provider()
        try:
            await self.collect(provider, [ChatMessage("user", "__fail__")])
        except ProviderError as error:
            assert error.code and "key" not in error.code.lower()
        else:  # pragma: no cover - providers must fail on the kit's failure trigger
            raise AssertionError("the provider did not report the failure")
