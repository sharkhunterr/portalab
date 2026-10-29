"""The homelab's radio (issue 168): what a ``media.radio`` station plays, its live stream and covers
relayed by the portal, and asking its DJ for a song in the member's name (their display name on air).

A member asks at most once every ``ASK_EVERY`` seconds here (the station also limits its listeners), and
(issue 184) a few times a day for free — beyond, each request spends a credit bought in the shop."""

import time
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timedelta
from datetime import time as clock_time
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.dashboard import Refresh, Size, SizeLimits, WidgetDefinition, WidgetPayload
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.media import (
    RADIO,
    RadioRequest,
    RadioState,
    RadioStation,
    RadioTrack,
    StreamBody,
    unwrap,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import NotFound, PortalError, Unavailable
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.ids import new_id
from portalab.core.time import Clock, utc_now
from portalab.modules.media.models import RadioCreditLedger, RadioSitting
from portalab.modules.media.observability import log
from portalab.modules.media.permissions import MEDIA_PLAY
from portalab.modules.media.settings import MediaConfig

ASK_EVERY = 20
# issue 227: the radio's listening counted by the server — what the stream relayed to a member is added to
# their sitting every ``HEARD_EVERY`` seconds; issue 259: a sitting nothing was heard of for ``IDLE`` is over,
# and its minutes count then (like a film's)
HEARD_EVERY = 60
IDLE = timedelta(minutes=10)


MAX_FOLLOWED = 5000  # the requests whose owner is kept, the oldest forgotten first


class RadioUnavailable(Unavailable):
    default_code = "media.radio_unavailable"
    default_title = "The radio is not available"


class RadioNoCredits(PortalError):
    status = 429
    default_code = "media.radio_no_credits"
    default_title = "No request left today"


class RadioAskedTooSoon(PortalError):
    status = 429
    default_code = "media.radio_too_soon"
    default_title = "One request at a time"


def track_out(track: RadioTrack | None) -> dict[str, Any] | None:
    if track is None:
        return None
    out = asdict(track)
    out["started_at"] = track.started_at.isoformat() if track.started_at else None
    return out


def request_out(request: RadioRequest) -> dict[str, Any]:
    return {
        "id": request.id,
        "status": request.status,
        "detail": request.detail,
        "track": track_out(request.track),
    }


class RadioService:
    def __init__(
        self,
        capabilities: CapabilityRegistry,
        database: Database | None = None,
        config: Callable[[], MediaConfig] = MediaConfig,
        *,
        clock: Clock | None = None,
        events: EventPublisher | None = None,
    ) -> None:
        self.capabilities = capabilities
        self.database = database
        self.config = config
        self.clock = clock
        self.events = events
        self._asked: dict[UUID, float] = {}
        self._requests: dict[str, UUID] = {}  # #280: whose request each one is (the last ones asked)

    # --- issue 184: free requests each day, then credits -----------------------------------------------
    def _today(self) -> datetime:
        now = utc_now(self.clock)
        return datetime.combine(now.date(), clock_time(0), tzinfo=now.tzinfo)

    async def _counts(self, session: AsyncSession, user: UUID) -> tuple[int, int]:
        """(free requests used today, credits held)."""
        used = await session.scalar(
            select(func.count())
            .select_from(RadioCreditLedger)
            .where(
                RadioCreditLedger.user_id == user,
                RadioCreditLedger.reason == "ask",
                RadioCreditLedger.delta == 0,
                RadioCreditLedger.created_at >= self._today(),
            )
        )
        balance = await session.scalar(
            select(func.coalesce(func.sum(RadioCreditLedger.delta), 0)).where(
                RadioCreditLedger.user_id == user
            )
        )
        return int(used or 0), int(balance or 0)

    async def allowance(self, user: UUID) -> dict[str, int]:
        free = max(0, self.config().radio_free_requests_per_day)
        if self.database is None:
            return {"free_per_day": free, "free_left": free, "credits": 0}
        async with self.database.session() as session:
            used, balance = await self._counts(session, user)
        return {"free_per_day": free, "free_left": max(0, free - used), "credits": max(0, balance)}

    async def grant(self, user: UUID, count: int, source_ref: str) -> int:
        """The shop credits requests (``RadioCredits``) — once per purchase."""
        assert self.database is not None
        async with self.database.unit_of_work() as uow:
            session = uow.session
            exists = await session.scalar(
                select(RadioCreditLedger.id).where(RadioCreditLedger.source_ref == source_ref[:200])
            )
            if exists is None and count > 0:
                session.add(
                    RadioCreditLedger(
                        user_id=user,
                        delta=min(int(count), 500),
                        reason="purchase",
                        source_ref=source_ref[:200],
                        created_at=utc_now(self.clock),
                    )
                )
                await session.flush()
            _, balance = await self._counts(session, user)
            return balance

    async def _charge(self, user: UUID) -> None:
        """Count one request: a free one of the day, else a credit; none left: refused."""
        if self.database is None:
            return
        free = max(0, self.config().radio_free_requests_per_day)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            # one member's requests are counted one at a time (two clicks never spend one credit twice)
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"media.radio:{user}"}
            )
            used, balance = await self._counts(session, user)
            if used >= free and balance <= 0:
                raise RadioNoCredits("No request left today: buy credits in the shop, or come back tomorrow.")
            session.add(
                RadioCreditLedger(
                    user_id=user,
                    delta=0 if used < free else -1,
                    reason="ask",
                    source_ref=f"ask:{new_id()}",
                    created_at=utc_now(self.clock),
                )
            )

    async def _refund(self, user: UUID) -> None:
        """The station refused the request: the member's last request of today is given back."""
        if self.database is None:
            return
        async with self.database.unit_of_work() as uow:
            last = (
                await uow.session.execute(
                    select(RadioCreditLedger)
                    .where(
                        RadioCreditLedger.user_id == user,
                        RadioCreditLedger.reason == "ask",
                        RadioCreditLedger.created_at >= self._today(),
                    )
                    .order_by(RadioCreditLedger.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if last is not None:
                await uow.session.delete(last)

    def station(self) -> RadioStation | None:
        try:
            providers = self.capabilities.system_providers(RADIO)
        except Exception:
            return None
        return providers[0].provider if providers else None

    def _station(self) -> RadioStation:
        station = self.station()
        if station is None:
            raise RadioUnavailable("No radio is connected.")
        return station

    async def state(self) -> dict[str, Any]:
        station = self.station()
        if station is None:
            return {"available": False}
        try:
            state: RadioState = unwrap(await station.state())  # wrapped by the capability layer
        except Exception as exc:
            raise RadioUnavailable("The radio does not answer right now.") from exc
        return {
            "available": True,
            "station": state.station,
            "on_air": state.on_air,
            "host": state.host,
            "tagline": state.tagline,
            "listeners": state.listeners,
            "mood": state.mood,
            "current": track_out(state.current),
            "upcoming": [track_out(t) for t in state.upcoming],
            "recent": [track_out(t) for t in state.recent],
        }

    async def _name(self, user: UUID) -> str:
        try:
            providers = self.capabilities.system_providers(DIRECTORY)
            summary = await providers[0].provider.get_user_summary(user) if providers else None
        except Exception:
            summary = None
        return (summary.display_name if summary is not None and summary.display_name else "anon")[:40]

    async def ask(self, user: UUID, text: str) -> dict[str, Any]:
        station = self._station()
        now = time.monotonic()
        last = self._asked.get(user)
        if last is not None and now - last < ASK_EVERY:
            raise RadioAskedTooSoon(
                "Wait a moment before asking again.",
                extensions={"retry_after": int(ASK_EVERY - (now - last)) + 1},
            )
        await self._charge(user)
        self._asked[user] = now
        try:
            answer = unwrap(await station.ask(text.strip()[:280], await self._name(user)))
        except Exception as exc:
            await self._refund(user)
            raise RadioUnavailable("The radio does not answer right now.") from exc
        if answer.status == "failed":
            await self._refund(user)  # refused by the station: it does not count
        else:
            await self._publish(user, "media.radio_requested", {"request": str(answer.id)}, str(answer.id))
            self._requests[str(answer.id)] = user
            while len(self._requests) > MAX_FOLLOWED:
                del self._requests[next(iter(self._requests))]
        return {**request_out(answer), "allowance": await self.allowance(user)}

    # --- issue 227: listening, counted by the server -------------------------------------------------------
    async def heard(self, user: UUID, seconds: float) -> None:
        """The stream was relayed to this member ``seconds`` more. Issue 259: added to their sitting — the one
        heard of less than ``IDLE`` ago (a pause opens a new stream to play on), or a new one."""
        if self.database is None or seconds <= 0:
            return
        now = utc_now(self.clock)
        try:
            async with self.database.unit_of_work() as uow:
                session = uow.session
                sitting = await session.scalar(
                    select(RadioSitting)
                    .where(
                        RadioSitting.user_id == user,
                        RadioSitting.ended_at.is_(None),
                        RadioSitting.updated_at >= now - IDLE,
                    )
                    .order_by(RadioSitting.updated_at.desc())
                    .limit(1)
                    .with_for_update()
                )
                if sitting is None:
                    sitting = RadioSitting(
                        user_id=user, seconds=0.0, started_at=now - timedelta(seconds=seconds), updated_at=now
                    )
                    session.add(sitting)
                sitting.seconds += seconds
                sitting.updated_at = now
        except Exception:  # the radio plays on whatever happens to its rewards
            log.warning("radio listening not counted", exc_info=True)

    async def sweep(self, limit: int = 200) -> int:
        """Issue 259: the sittings nothing was heard of for ``IDLE`` end — each one's minutes make one
        ``media.radio_listened`` (the rules say what it earns, as a film's minutes). How many ended."""
        if self.database is None:
            return 0
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            over = (
                await session.scalars(
                    select(RadioSitting)
                    .where(RadioSitting.ended_at.is_(None), RadioSitting.updated_at < now - IDLE)
                    .order_by(RadioSitting.updated_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for sitting in over:
                sitting.ended_at = sitting.updated_at
                minutes = int(sitting.seconds // 60)
                if self.events is None or minutes < 1:
                    continue
                await self.events.publish(
                    session,
                    "media.radio_listened",
                    {"minutes": minutes, "session": str(sitting.id)},
                    occurred_at=sitting.updated_at,
                    subject=SubjectRef("user", str(sitting.user_id)),
                    source="media",
                    dedup_key=f"media.radio_listened:{sitting.user_id}:{sitting.id}",
                )
        return len(over)

    async def _publish(self, user: UUID, name: str, payload: dict[str, Any], key: str) -> None:
        if self.events is None or self.database is None:
            return
        try:
            async with self.database.unit_of_work() as uow:
                await self.events.publish(
                    uow.session,
                    name,
                    payload,
                    occurred_at=utc_now(self.clock),
                    subject=SubjectRef("user", str(user)),
                    source="media",
                    dedup_key=f"{name}:{user}:{key}",
                )
        except Exception:  # the radio plays on whatever happens to its rewards
            log.warning("radio event not published", exc_info=True)

    async def request_status(self, request_id: str, user: UUID | None = None) -> dict[str, Any]:
        """Where a request stands — #280: a member follows only their own."""
        if user is not None and self._requests.get(request_id) != user:
            raise NotFound("No such request.")
        try:
            return request_out(unwrap(await self._station().request_status(request_id)))
        except RadioUnavailable:
            raise
        except Exception as exc:
            raise RadioUnavailable("The radio does not answer right now.") from exc

    @asynccontextmanager
    async def listen(self) -> AsyncIterator[StreamBody]:
        try:
            opened = self._station().listen()
            body = await opened.__aenter__()
        except RadioUnavailable:
            raise
        except Exception as exc:
            raise RadioUnavailable("The radio stream cannot be reached.") from exc
        try:
            yield body
        finally:
            await opened.__aexit__(None, None, None)

    async def cover(self, cover_ref: str) -> bytes:
        try:
            data: bytes = unwrap(await self._station().cover(cover_ref))
            return data
        except RadioUnavailable:
            raise
        except Exception as exc:
            raise RadioUnavailable("No cover for this track.") from exc


# --- the dashboard's widget --------------------------------------------------------------------------------
RADIO_WIDGET = WidgetDefinition(
    key="media.radio",
    owner="module:media",
    title_key="media:widget.radio.title",
    description_key="media:widget.radio.description",
    icon="radio",
    required_permission=MEDIA_PLAY,
    size=SizeLimits(default=Size(6, 2), min=Size(3, 1), max=Size(12, 4)),
    refresh=Refresh(mode="interval", interval_s=30),
    stale_after_s=120,
    component_id="media.radio",
)


class RadioWidget:
    """Issue 168: the radio on the dashboard — what plays, listen, ask for a song."""

    def __init__(self, radio: RadioService, clock: Clock | None = None) -> None:
        self.radio, self.clock = radio, clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        if self.radio.station() is None:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        try:
            state = await self.radio.state()
        except RadioUnavailable:
            return WidgetPayload("unavailable", as_of=utc_now(self.clock))
        return WidgetPayload("available", as_of=utc_now(self.clock), data=state)
