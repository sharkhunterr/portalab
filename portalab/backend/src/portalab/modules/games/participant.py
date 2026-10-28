"""Privacy participant (issue 265): the games a member played (their scores), the parties they played in and
the challenges they completed are exported with their data and erased with them."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.games.models import ChallengeDone, GameSession, Party, PartyPlayer


class GamesParticipant:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            played = await session.execute(
                select(GameSession.game, GameSession.mode, GameSession.score, GameSession.finished_at).where(
                    GameSession.user_id == user_id, GameSession.status == "done"
                )
            )
            parties = await session.execute(
                select(Party.game, PartyPlayer.score, PartyPlayer.rank, Party.updated_at)
                .join(Party, Party.id == PartyPlayer.party_id)
                .where(PartyPlayer.user_id == user_id, Party.status == "done")
            )
            challenges = await session.execute(
                select(ChallengeDone.week, ChallengeDone.kind, ChallengeDone.at).where(
                    ChallengeDone.user_id == user_id
                )
            )
            return [
                *(
                    ExportRecord(
                        "games.played",
                        {"game": g, "mode": m, "score": s, "at": at.isoformat() if at else None},
                    )
                    for g, m, s, at in played
                ),
                *(
                    ExportRecord("games.party", {"game": g, "score": s, "rank": r, "at": at.isoformat()})
                    for g, s, r, at in parties
                ),
                *(
                    ExportRecord("games.challenge", {"week": w.isoformat(), "kind": k, "at": at.isoformat()})
                    for w, k, at in challenges
                ),
            ]

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(delete(GameSession).where(GameSession.user_id == user_id))
            await uow.session.execute(delete(PartyPlayer).where(PartyPlayer.user_id == user_id))
            await uow.session.execute(delete(Party).where(Party.host_id == user_id))
            await uow.session.execute(delete(ChallengeDone).where(ChallengeDone.user_id == user_id))
