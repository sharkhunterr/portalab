"""Erasure participant (FR-030/031): observability keeps at most a user id on an error; final deletion
clears it (the error itself is technical and stays diagnosable)."""

from uuid import UUID

from sqlalchemy import update

from portalab.capabilities.privacy_participants import ErasureMode
from portalab.core.db import Database
from portalab.modules.observability.models import ErrorRecord


class ObservabilityErasure:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                update(ErrorRecord).where(ErrorRecord.user_ref == user_id).values(user_ref=None)
            )
            await uow.session.execute(
                update(ErrorRecord).where(ErrorRecord.resolved_by == user_id).values(resolved_by=None)
            )
