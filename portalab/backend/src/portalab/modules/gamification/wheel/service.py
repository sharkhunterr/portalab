"""The daily wheel (issue 225): once a day — a day of the economy's time zone — a member spins it and wins
what its segment says: Coins, XP, a shop product offered (a discovery booster, into their reserve) or
nothing — never a loss (the owner's rule: the wheel only gives; a segment taking Coins is left out).

The draw is the server's (weighted by the segments' ``weight``), recorded with what it gave before the
member's page animates anything: the page only turns the wheel to the segment it is told. A product is
offered through ``marketplace.gifts`` once the spin is recorded; when the shop cannot offer it (unknown,
switched off) the segment's ``fallback`` Coins are given instead, so a spin never gives nothing by mistake.
"""

import random
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from portalab.capabilities.marketplace import GIFTS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.errors import Conflict, Unavailable
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.ledger.writer import Entry, LedgerWriter, lock_user
from portalab.modules.gamification.models import Balance, WheelSpin
from portalab.modules.gamification.observability import log
from portalab.modules.gamification.settings import DEFAULT_SEGMENTS

SPIN_MS = 5200  # how long the page turns the wheel before Portalab says what it gave
MAX_SEGMENTS = 16
SOURCE = "wheel"  # its own source in the histories (issue 225)


class AlreadySpun(Conflict):
    default_code = "gamification.wheel_already_spun"
    default_title = "The wheel was already spun today"


class Segment(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,47}$")
    kind: Literal["coins", "xp", "product", "nothing"]
    amount: int = Field(default=0, ge=0, le=10_000)  # the wheel never takes anything
    product: str | None = Field(default=None, max_length=96)
    labels: dict[str, str] = Field(default_factory=dict)
    weight: int = Field(default=1, ge=1, le=1000)
    fallback: int = Field(default=50, ge=0, le=10_000)  # Coins when the product cannot be offered

    @model_validator(mode="after")
    def _coherent(self) -> "Segment":
        if self.kind == "coins" and self.amount <= 0:
            raise ValueError("a Coins segment wins some")
        if self.kind == "xp" and self.amount <= 0:
            raise ValueError("an XP segment wins some")
        if self.kind == "product" and not self.product:
            raise ValueError("a product segment names its product")
        return self

    def label(self, language: str) -> str | None:
        return self.labels.get(language.split("-")[0]) or self.labels.get("en") or None


def parse_segments(raw: Any) -> list[Segment]:
    """The administrator's segments (those that do not make sense are left out); the default wheel when
    fewer than two remain."""
    out: list[Segment] = []
    seen: set[str] = set()
    for item in (raw if isinstance(raw, list) else [])[:MAX_SEGMENTS]:
        try:
            segment = Segment.model_validate(item)
        except ValidationError:
            continue
        if segment.key not in seen:
            seen.add(segment.key)
            out.append(segment)
    if len(out) < 2:
        return [Segment.model_validate(item) for item in DEFAULT_SEGMENTS]
    return out


@dataclass(frozen=True, slots=True)
class Spun:
    segment: str
    index: int | None
    kind: str
    amount: int
    delta: int
    product: str | None
    given: bool
    spun_at: datetime


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError):
        return ZoneInfo("UTC")


class Wheel:
    def __init__(
        self,
        database: Database,
        writer: LedgerWriter,
        capabilities: CapabilityRegistry,
        config: Callable[[], Any],
        *,
        clock: Clock | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.database = database
        self.writer = writer
        self.capabilities = capabilities
        self.config = config
        self.clock = clock
        self.rng = rng or secrets.SystemRandom()

    # --- what it is today -------------------------------------------------------------------------------
    def settings(self) -> Mapping[str, Any]:
        raw = getattr(self.config(), "wheel", None)
        return raw if isinstance(raw, Mapping) else {}

    def enabled(self) -> bool:
        return bool(self.settings().get("enabled", True))

    def segments(self) -> list[Segment]:
        return parse_segments(self.settings().get("segments"))

    def _today(self, at: datetime) -> tuple[date, datetime]:
        """Today in the economy's time zone, and when tomorrow starts (UTC)."""
        zone = _zone(str(getattr(self.config(), "timezone", "UTC") or "UTC"))
        local = at.astimezone(zone).date()
        tomorrow = datetime.combine(local + timedelta(days=1), time.min, tzinfo=zone)
        return local, tomorrow.astimezone(at.tzinfo or ZoneInfo("UTC"))

    async def state(self, user: UUID, language: str = "en") -> dict[str, Any]:
        now = utc_now(self.clock)
        day, next_at = self._today(now)
        segments = self.segments()
        async with self.database.session() as session:
            row = await session.scalar(
                select(WheelSpin).where(WheelSpin.user_id == user, WheelSpin.day == day)
            )
            balance = await session.get(Balance, (user, "coins"))
        return {
            "enabled": self.enabled(),
            "day": day.isoformat(),
            "next_at": next_at.isoformat(),
            "spin_ms": SPIN_MS,
            "coins": int(balance.amount) if balance else 0,
            "segments": [self._shown(s, language) for s in segments],
            "today": self._spun(self._of(row, segments)) if row else None,
        }

    @staticmethod
    def _shown(segment: Segment, language: str) -> dict[str, Any]:
        return {
            "key": segment.key,
            "kind": segment.kind,
            "amount": segment.amount,
            "product": segment.product,
            "label": segment.label(language),
        }

    @staticmethod
    def _of(row: WheelSpin, segments: list[Segment]) -> Spun:
        keys = [s.key for s in segments]
        return Spun(
            segment=row.segment,
            index=keys.index(row.segment) if row.segment in keys else None,
            kind=row.kind,
            amount=row.amount,
            delta=row.delta,
            product=row.product,
            given=row.given,
            spun_at=row.spun_at,
        )

    @staticmethod
    def _spun(spun: Spun) -> dict[str, Any]:
        return {
            "segment": spun.segment,
            "index": spun.index,
            "kind": spun.kind,
            "amount": spun.amount,
            "delta": spun.delta,
            "product": spun.product,
            "given": spun.given,
            "spun_at": spun.spun_at.isoformat(),
        }

    # --- the spin ---------------------------------------------------------------------------------------
    async def spin(self, user: UUID, language: str = "en") -> dict[str, Any]:
        if not self.enabled():
            raise Unavailable("The daily wheel is switched off.", code="gamification.wheel_off")
        now = utc_now(self.clock)
        day, _ = self._today(now)
        segments = self.segments()
        drawn = self.rng.choices(segments, weights=[s.weight for s in segments], k=1)[0]
        try:
            async with self.database.unit_of_work() as uow:
                session = uow.session
                await lock_user(session, user)
                if await session.scalar(
                    select(WheelSpin.id).where(WheelSpin.user_id == user, WheelSpin.day == day)
                ):
                    raise AlreadySpun("Come back tomorrow for another spin.")
                delta = await self._record(session, user, drawn, day, now)
                session.add(
                    WheelSpin(
                        user_id=user,
                        day=day,
                        segment=drawn.key,
                        kind=drawn.kind,
                        amount=drawn.amount,
                        delta=delta,
                        product=drawn.product,
                        given=False,
                        spun_at=now,
                    )
                )
                await session.flush()
        except IntegrityError as exc:  # a second spin at the same moment
            raise AlreadySpun("Come back tomorrow for another spin.") from exc
        if drawn.kind == "product":
            await self._offer(user, drawn, day, now)
        return await self.state(user, language)

    async def _record(self, session: Any, user: UUID, drawn: Segment, day: date, now: datetime) -> int:
        if drawn.kind not in ("coins", "xp"):
            return 0
        amount = drawn.amount
        await self.writer.record(
            session,
            Entry(
                user_id=user,
                value=drawn.kind,
                delta=amount,
                kind="grant",
                source_kind=SOURCE,
                source_ref=f"wheel:{day.isoformat()}",
                idempotency_key=f"wheel:{user}:{day.isoformat()}",
                occurred_at=now,
                base_amount=amount,
                reason=f"wheel {drawn.key}",
            ),
        )
        return amount

    async def _offer(self, user: UUID, drawn: Segment, day: date, now: datetime) -> None:
        given = False
        gifts = self.capabilities.system_providers(GIFTS)
        if gifts and drawn.product:
            try:
                given = bool(await gifts[0].provider.gift(user, drawn.product, f"wheel {day.isoformat()}"))
            except Exception:
                given = False
        async with self.database.unit_of_work() as uow:
            row = await uow.session.scalar(
                select(WheelSpin).where(WheelSpin.user_id == user, WheelSpin.day == day).with_for_update()
            )
            if row is None:
                return
            row.given = given
            if not given and drawn.fallback > 0:
                log.warning("wheel product not offered, Coins instead")
                await lock_user(uow.session, user)
                await self.writer.record(
                    uow.session,
                    Entry(
                        user_id=user,
                        value="coins",
                        delta=drawn.fallback,
                        kind="grant",
                        source_kind=SOURCE,
                        source_ref=f"wheel:{day.isoformat()}",
                        idempotency_key=f"wheel:{user}:{day.isoformat()}:fallback",
                        occurred_at=now,
                        base_amount=drawn.fallback,
                        reason=f"wheel {drawn.key} (fallback)",
                    ),
                )
                row.delta = drawn.fallback
