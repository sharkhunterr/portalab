"""Privacy participant (T003): the notification center and deliveries are ``activity`` personal data —
exported (titles, dates, state) and erased with the account (idempotent). Issue 398: a communication meant
for that account alone goes too (its parameters may quote what they wrote)."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select, text

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.notifications.models import Delivery, DigestState, Notification

# a communication no notification nor delivery points at any more (retention, erasure)
UNREFERENCED = (
    "NOT EXISTS (SELECT 1 FROM notify.notifications n WHERE n.communication_id = communications.id)"
    " AND NOT EXISTS (SELECT 1 FROM notify.deliveries d WHERE d.communication_id = communications.id)"
)
# ... and meant for one account alone (constant SQL, the account bound)
ERASE_ALONE = (
    "DELETE FROM notify.communications WHERE audience_spec->>'type' = 'Users'"
    " AND audience_spec->'ids' = jsonb_build_array(CAST(:user AS text))"
    " AND NOT EXISTS (SELECT 1 FROM notify.notifications n WHERE n.communication_id = communications.id)"
    " AND NOT EXISTS (SELECT 1 FROM notify.deliveries d WHERE d.communication_id = communications.id)"
)


class NotificationsParticipant:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(Notification)
                        .where(Notification.user_id == user_id)
                        .order_by(Notification.created_at)
                    )
                )
                .scalars()
                .all()
            )
        return [
            ExportRecord(
                "notifications.item",
                {
                    "category": r.category,
                    "kind": r.kind,
                    "title": r.title,
                    "body": r.body,
                    "created_at": r.created_at.isoformat(),
                    "read": r.read_at is not None,
                },
            )
            for r in rows
        ]

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            for model in (Notification, Delivery, DigestState):
                await uow.session.execute(delete(model).where(model.user_id == user_id))
            await uow.session.execute(text(ERASE_ALONE), {"user": str(user_id)})
