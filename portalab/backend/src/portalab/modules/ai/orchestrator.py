"""Orchestrator (T010, T014): one assistant turn.

The provider streams text and tool calls; each call goes through the executor (catalog of this turn,
schema, re-authorization, pending action for sensitive tools); results are framed as untrusted data and
numbered for attribution. Budgets: at most ``ai.maxToolCallsPerTurn`` calls, repeated identical calls are
refused, the last round offers no tools so the model must answer. A provider failure or timeout ends the
turn with ``ai.unavailable`` — nothing sensitive is ever executed by a failed turn (pending actions wait
for the user). Events: ``delta``, ``tool_call``, ``tool_result``, ``source``, ``pending_action``,
``error``, ``done``."""

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID

from portalab.capabilities.ai import ChatMessage, LLMProvider, ProviderError, SourceRef, ToolCall, ToolResult
from portalab.capabilities.observability import AiOutcome, report_ai_call
from portalab.core.authz_port import Principal
from portalab.modules.ai.attribution import Attributor
from portalab.modules.ai.context import frame_tool_result, language_of, system_prompt, window
from portalab.modules.ai.errors import AiUnavailable
from portalab.modules.ai.executor import ToolExecutor
from portalab.modules.ai.observability import log, metrics
from portalab.modules.ai.output import sanitize_answer
from portalab.modules.ai.redaction import mask_secrets
from portalab.modules.ai.settings import AiConfig
from portalab.modules.ai.tools.catalog import CHAT, ToolCatalog, ToolPolicy, tool_spec, wire_name

Event = dict[str, Any]
MAX_ANSWER_TOKENS = 1024
REMINDER = (
    "(Answer only from what your tools return now — nothing from your own knowledge; look it up even if the "
    "conversation spoke of it before; never "
    "invent a service, a title, a ticket or a date. Never copy raw field names or timestamps. If this "
    "question names another title or subject than the page, ignore the page. For a « how do I… » question, "
    "search the wiki and suggest the page; if nothing covers it, offer a support ticket.)"
)
THINKING_TOKENS = 3072
NUDGE = (
    "You answered without looking anything up. Use your tools now — the wiki for « how do I… », the portal's "
    "data otherwise — then answer from what they return; if they hold nothing, follow your instruction for "
    "missing information. Same language as my question."
)
SMALL_TALK = re.compile(
    r"^\W*(bonjour|bonsoir|salut|coucou|merci|ok|d'accord|super|parfait|hello|hi|hey|thanks|thank you|bye)\b",
    re.IGNORECASE,
)


def needs_lookup(conversation: Sequence[ChatMessage]) -> bool:
    """A real question (not small talk): an answer to it should come from the portal's data."""
    asked = next((m.content for m in reversed(conversation) if m.role == "user"), "")
    asked = asked.split("\n\n(Answer from", 1)[0].strip()  # without the reminder riding on it
    return len(asked.split()) >= 4 and not SMALL_TALK.match(asked)


def event(name: str, /, **data: Any) -> Event:
    return {"event": name, "data": data}


@dataclass
class TurnOutcome:
    content: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    caveats: list[dict[str, str]] = field(default_factory=list)
    interpretation: bool = True
    tool_calls: list[dict[str, str]] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None
    latency_ms: int = 0


class Orchestrator:
    def __init__(
        self,
        provider: Callable[[], LLMProvider | None],
        catalog: ToolCatalog,
        executor: ToolExecutor,
        config: Callable[[], AiConfig],
        *,
        language: Callable[[UUID], Awaitable[str]] | None = None,
        secrets: Callable[[], Iterable[str | None]] = tuple,
        who: Callable[[UUID], Awaitable[str | None]] | None = None,
        site: Callable[[str], str | None] | None = None,
    ) -> None:
        self.site = site  # issue 171: the site's name (its identity), for the assistant to say where it is
        self.who = who  # issue 171: the member the assistant speaks with (their display name)
        self.provider = provider
        self.catalog = catalog
        self.executor = executor
        self.config = config
        self.language = language
        self.secrets = secrets

    async def language_for(self, user: UUID) -> str:
        if self.language is None:
            return "en"
        try:
            return await asyncio.wait_for(self.language(user), timeout=2)
        except Exception:
            return "en"

    async def name_of(self, user: UUID) -> str | None:
        if self.who is None:
            return None
        try:
            return await asyncio.wait_for(self.who(user), timeout=2)
        except Exception:
            return None

    async def messages_for(
        self, user: UUID, history: list[ChatMessage], page: dict[str, Any] | None
    ) -> list[ChatMessage]:
        member = {"id": str(user), "name": await self.name_of(user)}
        # issue 171: the language the question is written in, else the member's own — a model answers in the
        # language of the data it read (English) unless the system says otherwise
        asked = next((m.content for m in reversed(history) if m.role == "user"), "")
        language = language_of(asked) or await self.language_for(user)
        config = self.config()
        try:
            site = self.site(language) if self.site is not None else None
        except Exception:
            site = None
        persona = {
            "name": config.assistant_name,
            "role": config.assistant_role,
            "fallback": config.assistant_fallback,
            "site": site,
        }
        system = ChatMessage("system", system_prompt(language, page, member, persona))
        budget = max(500, self.config().max_context_tokens - MAX_ANSWER_TOKENS - len(system.content) // 4)
        kept = window(history, budget)
        # issue 171: a small model forgets the system's rules as a conversation grows — the rule it needs
        # most rides on the question it answers (sent to the model only, never stored)
        if kept and kept[-1].role == "user":
            spoken = language_of(kept[-1].content)
            said = f"Answer in {spoken}." if spoken else "Answer in the language of this question."
            kept[-1] = replace(kept[-1], content=f"{kept[-1].content}\n\n{REMINDER} {said}")
        return [system, *kept]

    async def run(
        self,
        principal: Principal,
        messages: list[ChatMessage],
        *,
        policy: ToolPolicy = CHAT,
        conversation_id: UUID | None = None,
        outcome: TurnOutcome | None = None,
        seed_sources: Sequence[SourceRef] = (),
    ) -> AsyncIterator[Event]:
        outcome = outcome if outcome is not None else TurnOutcome()
        provider = self.provider()
        if provider is None:
            raise AiUnavailable("The assistant is not configured.")
        config = self.config()
        started = time.monotonic()
        offered = await self.catalog.for_principal(principal, policy)
        by_wire = {wire_name(name): tool for name, tool in offered.items()}
        specs = [tool_spec(tool) for tool in offered.values()]
        attributor = Attributor()
        if seed_sources:
            attributor.add("context", ToolResult("ok", sources=tuple(seed_sources)))
        conversation = list(messages)
        secrets = list(self.secrets())
        parts: list[str] = []
        calls_done = 0
        seen: set[str] = set()
        limit = max(0, config.max_tool_calls_per_turn)
        nudged = False
        for round_no in range(limit + 1):
            tools = specs if round_no < limit and calls_done < limit else []
            # issue 171: the first answer waits until we know it looked something up (see NUDGE)
            hold = round_no == 0 and bool(tools)
            text: list[str] = []
            calls: list[ToolCall] = []
            try:
                async with asyncio.timeout(max(1, config.request_timeout_seconds)):
                    async for item in provider.chat(
                        conversation,
                        tools,
                        # issue 171: a thinking model's thoughts count in its length — room for them too
                        max_tokens=MAX_ANSWER_TOKENS
                        + (0 if config.provider_reasoning == "none" else THINKING_TOKENS),
                        timeout=config.request_timeout_seconds,
                    ):
                        if item.kind == "delta" and item.text:
                            text.append(item.text)
                            if not hold:
                                yield event("delta", text=mask_secrets(item.text, secrets))
                        elif item.kind == "tool_call" and item.tool_call is not None:
                            calls.append(item.tool_call)
                        elif item.kind == "usage":
                            outcome.tokens_in += item.tokens_in
                            outcome.tokens_out += item.tokens_out
            except (ProviderError, TimeoutError) as exc:
                code = exc.code if isinstance(exc, ProviderError) else "timeout"
                outcome.error = code
                metrics.increment(f"ai.provider.errors.{code if code.isidentifier() else 'other'}")
                log.warning("ai provider failed", extra={"fields": {"code": code}})
                self._report(config, started, "timeout" if code == "timeout" else "error", outcome)
                yield event("error", code="ai.unavailable", reason=code)
                return
            if hold and not calls:
                if not nudged and needs_lookup(conversation):
                    # a small model answered a real question from thin air: once, it is asked to look first
                    nudged = True
                    metrics.increment("ai.nudged")
                    conversation.append(ChatMessage("user", NUDGE))
                    continue
                if text:
                    yield event("delta", text=mask_secrets("".join(text), secrets))
            parts.extend(text)
            if not calls or not tools:
                break
            conversation.append(ChatMessage("assistant", "".join(text), tool_calls=calls))
            for call in calls:
                tool = by_wire.get(call.name)
                named = ToolCall(call.id, tool.name if tool else call.name.replace("__", "."), call.arguments)
                key = f"{named.name}:{json.dumps(dict(named.arguments), sort_keys=True, default=str)}"
                if calls_done >= limit:
                    result: ToolResult = ToolResult("error", detail="tool_budget_exhausted")
                    attributor.add(named.name, result)
                elif key in seen:
                    result = ToolResult("error", detail="repeated_call")
                else:
                    calls_done += 1
                    seen.add(key)
                    yield event("tool_call", id=call.id, name=named.name)
                    execution = await self.executor.execute(
                        principal, named, offered, conversation_id=conversation_id
                    )
                    result = execution.result
                    added = attributor.add(named.name, result)
                    outcome.tool_calls.append({"name": named.name, "state": result.state})
                    yield event("tool_result", id=call.id, name=named.name, state=result.state)
                    for source in added:
                        yield event("source", **source)
                    if execution.pending is not None:
                        pending = execution.pending
                        outcome.pending.append(str(pending.id))
                        yield event(
                            "pending_action",
                            id=str(pending.id),
                            tool=pending.tool,
                            summary=pending.summary,
                            expires_at=pending.expires_at.isoformat(),
                        )
                conversation.append(
                    ChatMessage(
                        "tool",
                        frame_tool_result(named.name, result, attributor.numbered(result)),
                        tool_call_id=call.id,
                        name=call.name,
                    )
                )
        content, cited, interpretation = attributor.finalize(sanitize_answer("".join(parts), secrets))
        outcome.content, outcome.sources, outcome.interpretation = content.strip(), cited, interpretation
        outcome.caveats = list(attributor.caveats)
        outcome.latency_ms = int((time.monotonic() - started) * 1000)
        metrics.observe("ai.provider.turn_latency_ms", outcome.latency_ms)
        metrics.increment("ai.turns.completed")
        self._report(config, started, "ok", outcome)
        yield event(
            "done",
            content=outcome.content,
            sources=cited,
            caveats=outcome.caveats,
            interpretation=interpretation,
            pending_actions=outcome.pending,
        )

    @staticmethod
    def _report(config: AiConfig, started: float, result: AiOutcome, outcome: TurnOutcome) -> None:
        report_ai_call(
            provider=config.provider_kind,
            model=config.provider_model or "unknown",
            latency_ms=(time.monotonic() - started) * 1000,
            outcome=result,
            tools=[c["name"] for c in outcome.tool_calls],
            actions=len(outcome.pending),
        )

    async def complete(
        self,
        principal: Principal,
        messages: list[ChatMessage],
        *,
        policy: ToolPolicy,
        seed_sources: Sequence[SourceRef] = (),
    ) -> TurnOutcome:
        """Non-streaming turn for facades; raises ``AiUnavailable`` when the provider fails."""
        outcome = TurnOutcome()
        async for _ in self.run(
            principal, messages, policy=policy, outcome=outcome, seed_sources=seed_sources
        ):
            pass
        if outcome.error:
            raise AiUnavailable("The assistant failed to answer.")
        return outcome
