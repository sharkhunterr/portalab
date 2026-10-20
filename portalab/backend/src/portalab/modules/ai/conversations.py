"""Conversations (T011; FR-021): owner-only — another user (an Admin included) gets ``404``, nothing is
revealed. Messages are numbered per conversation; raw tool results are never stored (only summaries and
source references in ``blocks``). Retention ``ai.retentionDays``; the user may delete at any time."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select

from portalab.capabilities.ai import ChatMessage
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.ai.errors import ConversationNotFound
from portalab.modules.ai.models import Conversation, Message

HISTORY = 40
PAGE = 50


def _owner(principal: Principal) -> UUID:
    if principal.channel != "user" or principal.user_id is None:
        raise ConversationNotFound("This conversation does not exist.")
    return principal.user_id


def _context(context: Mapping[str, Any] | None) -> dict[str, Any]:
    if not context:
        return {}
    return {k: str(context[k])[:200] for k in ("route", "title", "help_key") if context.get(k)}


class Conversations:
    def __init__(self, database: Database, events: EventPublisher, *, clock: Clock | None = None) -> None:
        self.database = database
        self.events = events
        self.clock = clock

    async def create(
        self, principal: Principal, title: str = "", context: Mapping[str, Any] | None = None
    ) -> Conversation:
        user = _owner(principal)
        now = utc_now(self.clock)
        row = Conversation(
            user_id=user, title=title[:200], context=_context(context), created_at=now, updated_at=now
        )
        async with self.database.unit_of_work() as uow:
            uow.session.add(row)
            await uow.session.flush()
            await self.events.publish(
                uow.session,
                "ai.conversation_started",
                {"conversation": str(row.id)},
                occurred_at=now,
                actor=principal,
                subject=SubjectRef("ai_conversation", str(row.id)),
                dedup_key=f"ai.conversation_started:{row.id}",
            )
        return row

    async def owned_list(self, principal: Principal) -> list[Conversation]:
        user = _owner(principal)
        async with self.database.session() as session:
            rows = await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user)
                .order_by(Conversation.updated_at.desc())
                .limit(PAGE)
            )
            return list(rows.scalars().all())

    async def owned(self, principal: Principal, conversation_id: UUID) -> Conversation:
        user = _owner(principal)
        async with self.database.session() as session:
            row = await session.get(Conversation, conversation_id)
        if row is None or row.user_id != user:
            raise ConversationNotFound("This conversation does not exist.")
        return row

    async def messages(self, conversation_id: UUID, limit: int = 200) -> list[Message]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.seq.desc())
                .limit(limit)
            )
            return list(reversed(rows.scalars().all()))

    async def history(self, conversation_id: UUID) -> list[ChatMessage]:
        return [
            ChatMessage("user" if m.role == "user" else "assistant", m.content)
            for m in await self.messages(conversation_id, HISTORY)
            if m.role in ("user", "assistant") and m.content
        ]

    async def announce(self, principal: Principal, message: Message, *, sourced: bool, tools: int) -> None:
        """Issue 181: an answer given, told once (the achievements count them) — never its text."""
        async with self.database.unit_of_work() as uow:
            await self.events.publish(
                uow.session,
                "ai.answered",
                {"conversation": str(message.conversation_id), "sourced": sourced, "tools": tools},
                occurred_at=message.created_at,
                actor=principal,
                subject=SubjectRef("ai_conversation", str(message.conversation_id)),
                dedup_key=f"ai.answered:{message.id}",
            )

    async def append(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        blocks: Mapping[str, Any] | None = None,
        usage: Mapping[str, Any] | None = None,
    ) -> Message:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            conversation = await uow.session.get(Conversation, conversation_id, with_for_update=True)
            if conversation is None:
                raise ConversationNotFound("This conversation does not exist.")
            seq = int(
                await uow.session.scalar(
                    select(func.coalesce(func.max(Message.seq), 0)).where(
                        Message.conversation_id == conversation_id
                    )
                )
                or 0
            )
            row = Message(
                conversation_id=conversation_id,
                seq=seq + 1,
                role=role,
                content=content,
                blocks=dict(blocks or {}),
                usage=dict(usage or {}),
                created_at=now,
            )
            uow.session.add(row)
            if role == "user" and not conversation.title:
                conversation.title = " ".join(content.split())[:80]
            conversation.updated_at = now
        return row

    async def delete(self, principal: Principal, conversation_id: UUID) -> None:
        await self.owned(principal, conversation_id)
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(delete(Conversation).where(Conversation.id == conversation_id))

    async def purge(self, retention_days: int) -> int:
        cutoff = utc_now(self.clock) - timedelta(days=max(1, retention_days))
        async with self.database.unit_of_work() as uow:
            result = await uow.session.execute(delete(Conversation).where(Conversation.updated_at < cutoff))
            return int(getattr(result, "rowcount", 0) or 0)
