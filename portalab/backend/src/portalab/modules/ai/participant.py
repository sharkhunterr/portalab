"""Privacy participant (T003): conversations and messages are the owner's ``content`` personal data —
exported only to their owner, erased with the account (pending actions and usage too). Never shown in
admin views."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.ai.models import Conversation, Feedback, Message, PendingAction, Perk, UsageDaily


class AiParticipant:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            conversations = (
                (
                    await session.execute(
                        select(Conversation)
                        .where(Conversation.user_id == user_id)
                        .order_by(Conversation.created_at)
                    )
                )
                .scalars()
                .all()
            )
            # issue 176: the member's verdicts on the answers go with them
            rated = {
                f.message_id: f
                for f in (
                    await session.execute(select(Feedback).where(Feedback.user_id == user_id))
                ).scalars()
            }
            records: list[ExportRecord] = []
            for conversation in conversations:
                messages = (
                    (
                        await session.execute(
                            select(Message)
                            .where(Message.conversation_id == conversation.id)
                            .order_by(Message.seq)
                        )
                    )
                    .scalars()
                    .all()
                )
                records.append(
                    ExportRecord(
                        "ai.conversation",
                        {
                            "title": conversation.title,
                            "created_at": conversation.created_at.isoformat(),
                            "messages": [
                                {
                                    "role": m.role,
                                    "content": m.content,
                                    "created_at": m.created_at.isoformat(),
                                    **(
                                        {"rating": rated[m.id].rating, "comment": rated[m.id].comment}
                                        if m.id in rated
                                        else {}
                                    ),
                                }
                                for m in messages
                            ],
                        },
                    )
                )
            # issue 173: the assistant's capacities bought in the shop
            for perk in (await session.execute(select(Perk).where(Perk.user_id == user_id))).scalars():
                records.append(
                    ExportRecord(
                        "ai.perk",
                        {
                            "perk": perk.perk,
                            "amount": perk.amount,
                            "remaining": perk.remaining,
                            "created_at": perk.created_at.isoformat(),
                            "expires_at": perk.expires_at.isoformat() if perk.expires_at else None,
                        },
                    )
                )
        return records

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            for model in (PendingAction, Feedback, Conversation, UsageDaily, Perk):
                await uow.session.execute(delete(model).where(model.user_id == user_id))
