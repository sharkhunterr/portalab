"""Issue 450 — privacy participant: a member's household row (a profile's restrictions and PIN, a master's
economy) and the access requests it made or answered are exported with its data and erased with it; a
deleted profile leaves no trace in its household (its requests no longer wait, unnamed, for its master)."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, or_, select

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.household.models import AccessRequest, HouseholdMember


class HouseholdParticipant:
    def __init__(self, database: Database, forget: object = None) -> None:
        self.database = database
        self.forget = forget  # the household service's caches, emptied for the member

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            member = await session.get(HouseholdMember, user_id)
            asked = (
                await session.scalars(select(AccessRequest).where(AccessRequest.profile_id == user_id))
            ).all()
        out: list[ExportRecord] = []
        if member is not None:
            out.append(
                ExportRecord(
                    "household.member",
                    {"kind": member.kind, "economy": member.economy, "restrictions": member.restrictions},
                )
            )
        out += [
            ExportRecord(
                "household.request",
                {"title": r.title, "status": r.status, "created_at": r.created_at.isoformat()},
            )
            for r in asked
        ]
        return out

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                delete(AccessRequest).where(
                    or_(AccessRequest.profile_id == user_id, AccessRequest.owner_id == user_id)
                )
            )
            await uow.session.execute(delete(HouseholdMember).where(HouseholdMember.user_id == user_id))
        if callable(self.forget):
            self.forget(user_id)
