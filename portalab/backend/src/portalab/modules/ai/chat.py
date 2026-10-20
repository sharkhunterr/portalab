"""Chat turns (T011): ``prepare`` checks ownership and the governor **before** streaming (so refusals are
plain HTTP problems), stores the user message; ``events`` streams the turn and stores the assistant answer
(content, cited sources, caveats, tool-call summaries, pending action ids, usage) even when the turn fails
or the client goes away."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from portalab.core.authz_port import Principal
from portalab.modules.ai.conversations import Conversations
from portalab.modules.ai.errors import AiUnavailable
from portalab.modules.ai.governor import Governor
from portalab.modules.ai.models import Message
from portalab.modules.ai.observability import log
from portalab.modules.ai.orchestrator import Event, Orchestrator, TurnOutcome, event
from portalab.modules.ai.principal import subject_of
from portalab.modules.ai.tools.catalog import CHAT


@dataclass
class Turn:
    principal: Principal
    user: UUID
    conversation_id: UUID
    page: dict[str, Any]


class ChatService:
    def __init__(self, conversations: Conversations, governor: Governor, orchestrator: Orchestrator) -> None:
        self.conversations = conversations
        self.governor = governor
        self.orchestrator = orchestrator

    async def prepare(
        self, principal: Principal, conversation_id: UUID, text: str, *, page: dict[str, Any] | None = None
    ) -> Turn:
        conversation = await self.conversations.owned(principal, conversation_id)
        user = subject_of(principal)
        await self.governor.admit(user)
        if self.orchestrator.provider() is None:
            raise AiUnavailable("The assistant is not configured.")
        await self.conversations.append(conversation_id, "user", text)
        # issue 171: the page this message is asked from, else the one the conversation started on
        return Turn(principal, user, conversation_id, dict(page or conversation.context or {}))

    async def events(self, turn: Turn) -> AsyncIterator[Event]:
        outcome = TurnOutcome()
        stored = False
        try:
            async with self.governor.slot(turn.user):
                history = await self.conversations.history(turn.conversation_id)
                messages = await self.orchestrator.messages_for(turn.user, history, turn.page)
                async for item in self.orchestrator.run(
                    turn.principal,
                    messages,
                    policy=CHAT,
                    conversation_id=turn.conversation_id,
                    outcome=outcome,
                ):
                    if item["event"] == "done" and not stored:
                        # issue 176: kept before the end is told, so the answer can be rated by its id
                        stored = True
                        message = await self._store(turn, outcome)
                        if message is not None:
                            item = {**item, "data": {**item["data"], "message_id": str(message.id)}}
                    yield item
        except asyncio.CancelledError:
            outcome.error = outcome.error or "cancelled"
            raise
        except Exception as exc:
            outcome.error = outcome.error or getattr(exc, "code", "failed")
            yield event("error", code=str(getattr(exc, "code", "ai.unavailable")))
        finally:
            if not stored:
                await asyncio.shield(self._store(turn, outcome))

    async def _store(self, turn: Turn, outcome: TurnOutcome) -> Message | None:
        try:
            await self.governor.record(
                turn.user, outcome.tokens_in, outcome.tokens_out, len(outcome.tool_calls)
            )
            if outcome.content or outcome.error or outcome.pending:
                return await self.conversations.append(
                    turn.conversation_id,
                    "assistant",
                    outcome.content,
                    {
                        "sources": outcome.sources,
                        "caveats": outcome.caveats,
                        "interpretation": outcome.interpretation,
                        "tool_calls": outcome.tool_calls,
                        "pending_actions": outcome.pending,
                        "error": outcome.error,
                    },
                    {
                        "tokens_in": outcome.tokens_in,
                        "tokens_out": outcome.tokens_out,
                        "latency_ms": outcome.latency_ms,
                        "model": outcome.model,
                        "nudged": outcome.nudged,
                    },
                )
        except Exception:
            log.warning("ai turn not stored")
        return None
