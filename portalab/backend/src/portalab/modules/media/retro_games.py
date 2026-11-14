"""``media.game_source`` (issue 419): which library holds a catalog game, for the retro module that plays it
in the portal — once the viewer may open it: a household profile's kept-out titles, kinds and ratings hold,
and so does its screen time of the day (the same gate as the portal's player and reader)."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.retro import GameSource
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.modules.media.models import MediaObject, SourceItem
from portalab.modules.media.restrictions import TitleGate

GAME = "game"


class LibraryGames:
    def __init__(self, database: Database, gate: TitleGate) -> None:
        self.database = database
        self.gate = gate

    async def sources(
        self, object_id: UUID, viewer: Principal, services: Sequence[str]
    ) -> Sequence[GameSource]:
        await self.gate.check(viewer, object_id)  # 032: a profile's kept-out titles, kinds and ratings
        await self.gate.check_screen(viewer)  # 032: and its screen time of the day
        wanted = {s for s in services if s}
        if not wanted:
            return []
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(SourceItem.service_id, SourceItem.external_id, MediaObject.title)
                    .join(MediaObject, MediaObject.id == SourceItem.object_id)
                    .where(
                        SourceItem.object_id == object_id,
                        SourceItem.active.is_(True),
                        SourceItem.kind == GAME,
                    )
                    .order_by(SourceItem.last_seen_at.desc())
                )
            ).all()
        return [
            GameSource(
                object_id=object_id,
                title=row.title or "",
                service_id=row.service_id,
                external_id=row.external_id,
            )
            for row in rows
            if str(row.service_id) in wanted and row.external_id
        ]

    async def screen(self, viewer: Principal) -> tuple[int, int] | None:
        return await self.gate.screen_today(viewer)
