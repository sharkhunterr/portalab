"""Level service (T008, T024): the curve version in force (``economy.levelCurve.active``, else the latest)
and silent recomputation of cached levels when the curve changes."""

import time
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.levels.curve import DEFAULT_CURVE, Curve, CurveDefinition
from portalab.modules.gamification.models import Balance, LevelCurve

CACHE_SECONDS = 30.0


class LevelService:
    def __init__(self, database: Database, active: Callable[[], int], *, clock: Clock | None = None) -> None:
        self.database = database
        self.active = active
        self.clock = clock
        self._cached: tuple[float, int, Curve] | None = None

    async def ensure_default(self) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(LevelCurve)
                .values(version=1, effective_from=utc_now(self.clock), definition=DEFAULT_CURVE)
                .on_conflict_do_nothing()
            )

    async def curve(self, session: AsyncSession | None = None) -> Curve:
        wanted = self.active()
        if self._cached and self._cached[1] == wanted and time.monotonic() - self._cached[0] < CACHE_SECONDS:
            return self._cached[2]
        if session is None:
            async with self.database.session() as own:
                curve = await self._load(own, wanted)
        else:
            curve = await self._load(session, wanted)
        self._cached = (time.monotonic(), wanted, curve)
        return curve

    async def _load(self, session: AsyncSession, wanted: int) -> Curve:
        statement = select(LevelCurve)
        statement = (
            statement.where(LevelCurve.version == wanted)
            if wanted
            else statement.order_by(LevelCurve.version.desc()).limit(1)
        )
        row = (await session.execute(statement)).scalar_one_or_none()
        return Curve.of(row.version, row.definition) if row else Curve.of(0, DEFAULT_CURVE)

    async def versions(self) -> list[LevelCurve]:
        async with self.database.session() as session:
            return list((await session.execute(select(LevelCurve).order_by(LevelCurve.version))).scalars())

    async def publish(self, definition: Mapping[str, Any]) -> Curve:
        parsed = CurveDefinition.model_validate(dict(definition))
        async with self.database.unit_of_work() as uow:
            current = await uow.session.scalar(select(func.max(LevelCurve.version)))
            version = int(current or 0) + 1
            uow.session.add(
                LevelCurve(
                    version=version, effective_from=utc_now(self.clock), definition=parsed.model_dump()
                )
            )
        self._cached = None
        await self.recompute()
        return Curve.of(version, parsed.model_dump())

    async def recompute(self) -> int:
        """Cached levels follow the curve in force; no level-up is emitted for a curve change."""
        self._cached = None
        curve = await self.curve()
        changed = 0
        async with self.database.unit_of_work() as uow:
            rows = (
                await uow.session.execute(
                    select(Balance.user_id, Balance.amount).where(Balance.value == "xp")
                )
            ).all()
            for user_id, amount in rows:
                await uow.session.execute(
                    update(Balance)
                    .where(Balance.user_id == user_id, Balance.value == "xp")
                    .values(level=curve.level_for(int(amount)), curve_version=curve.version)
                )
                changed += 1
        return changed

    async def level_of(self, user: UUID) -> int:
        async with self.database.session() as session:
            amount = await session.scalar(
                select(Balance.amount).where(Balance.user_id == user, Balance.value == "xp")
            )
        return (await self.curve()).level_for(int(amount or 0))
