"""Retro play (issue 419): a member — or a household profile — plays a library's game in the portal's page.

* which game: media says which library holds the catalog title and whether the viewer may open it (a
  profile's restrictions and screen time hold, ``media.game_source``); the library says its platform and its
  file, and the platform its emulator core (RomM's own table, :mod:`.cores`);
* a sitting: started when the page opens the game, kept alive by the page while the game runs (each beat
  counts the time since the last one, at most :data:`GAP_S`), ended when the page leaves — or by the sweep
  once nothing was heard of it for :data:`IDLE`. Its minutes go to the portal as a portal sitting of a game
  (``media.playback_abandoned`` with the time played: the statistics, the XP, the streak, a profile's screen
  time) and to the library (its play time), told once, retried by the sweep;
* the files: the game, its platform's firmware and the emulator are relayed from the library as it sends them
  (a range for a range), never exposing it — the game and the firmware only to the sitting's player, while
  it is open.
"""

import asyncio
from collections.abc import Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.media import StreamBody
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.results import (
    AuthenticationFailed,
    CapabilityResult,
    InvalidPayload,
    ProviderAuthError,
    ProviderNotFound,
)
from portalab.capabilities.results import NotFound as ResultNotFound
from portalab.capabilities.retro import (
    GAME_SOURCE,
    RETRO_SOURCE,
    FileKind,
    GameSource,
    GameSourceLocator,
    RetroFirmware,
    RetroGame,
    RetroSource,
)
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Forbidden, NotFound, PortalError, Unavailable
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.retro.cores import RUFFLE, THREADED, control_scheme, core_for
from portalab.modules.retro.models import Sitting

TIMEOUT_S = 20.0
STREAM_TIMEOUT_S = 90.0
HEARTBEAT_S = 30  # how often the page tells the game still runs
GAP_S = 90.0  # the most one beat counts (a tab asleep, a laptop closed: not played)
IDLE = timedelta(minutes=5)  # nothing heard for this long (a background tab still beats): the sitting is over
RETELL = timedelta(days=2)  # a library told nothing for this long after a sitting is no longer retried
SOURCE = "retro"
log = get_logger("portalab.retro")


class NotPlayable(NotFound):
    default_code = "retro.not_playable"
    default_title = "This game cannot be played in the portal"


class LibraryDenied(Forbidden):
    default_code = "retro.library_denied"
    default_title = "The library refused"


class LibraryFailed(Unavailable):
    default_code = "retro.library_failed"
    default_title = "The library did not answer"


class SittingNotFound(NotFound):
    default_code = "retro.sitting_not_found"
    default_title = "No such game in progress"


def _value(found: Any) -> Any:
    """A connector's answer through the connectors' guard (a result: the value, or why there is none)."""
    if not isinstance(found, CapabilityResult):
        return found  # a provider of the portal itself (the catalog), or a stream's context
    if found.has_data:
        return found.value  # type: ignore[attr-defined]
    if isinstance(found, AuthenticationFailed):
        raise LibraryDenied("The library refused this game.")
    if isinstance(found, ResultNotFound):
        raise NotPlayable("The library has nothing here.")
    raise LibraryFailed("The library did not answer.")


async def _call[T](operation: Any, limit: float = TIMEOUT_S) -> T:
    try:
        result: T = _value(await asyncio.wait_for(operation, timeout=limit))
    except PortalError:
        raise
    except ProviderAuthError as exc:
        raise LibraryDenied("The library refused this game.") from exc
    except ProviderNotFound as exc:
        raise NotPlayable("The library has nothing here.") from exc
    except (TimeoutError, ConnectionError, InvalidPayload) as exc:
        raise LibraryFailed("The library did not answer.") from exc
    return result


@dataclass(frozen=True, slots=True)
class Playable:
    source: GameSource
    game: RetroGame
    core: str
    service_name: str | None

    @property
    def threads(self) -> bool:
        return self.core in THREADED

    @property
    def engine(self) -> str:
        """421: the engine the page starts — EmulatorJS, or Ruffle for Flash."""
        return "ruffle" if self.core == RUFFLE else "emulatorjs"

    @property
    def control_scheme(self) -> str | None:
        return control_scheme(self.game.platform)


@dataclass(frozen=True, slots=True)
class Started:
    sitting: UUID
    playable: Playable
    firmware: Sequence[RetroFirmware]


@dataclass(frozen=True, slots=True)
class Beat:
    minutes_left: int | None  # a profile's screen time left today (``None``: no screen time)
    stop: bool  # it is spent: the page ends the game


def player_of(viewer: Principal) -> UUID:
    """Who plays: the member — or the household profile their session acts as (its own sittings)."""
    user = viewer.acting_for or viewer.user_id
    if user is None:
        raise SittingNotFound("No member.")
    return user


class RetroService:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
        events: EventPublisher | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self.events = events
        self.accounts: Any = None  # 426: the members' own accounts (set by the module)

    # --- the libraries and the catalog ----------------------------------------------------------------------
    def _libraries(self) -> dict[str, tuple[RetroSource, str | None]]:
        try:
            registrations = self.capabilities.system_providers(RETRO_SOURCE)
        except Exception:
            return {}
        return {r.instance_ref: (r.provider, r.metadata.get("name")) for r in registrations}

    def _library(self, service: UUID | str) -> RetroSource:
        found = self._libraries().get(str(service))
        if found is None:
            raise NotPlayable("This library is no longer connected.")
        return found[0]

    def _locator(self) -> GameSourceLocator:
        providers = self.capabilities.system_providers(GAME_SOURCE)
        if not providers:
            raise NotPlayable("The catalog is not available.")
        locator: GameSourceLocator = providers[0].provider
        return locator

    async def games(self, viewer: Principal, object_id: UUID) -> list[Playable]:
        """Every copy of the title the portal plays (its core, its file in the library) — several ROMs of one
        game (regions, revisions, platforms) for the member to choose from; the most recently seen first."""
        libraries = self._libraries()
        if not libraries:
            raise NotPlayable("No library plays its games in the portal.")
        sources: Sequence[GameSource] = await _call(
            self._locator().sources(object_id, viewer, list(libraries))
        )
        found: list[Playable] = []
        for source in sources:
            library, name = libraries[str(source.service_id)]
            game: RetroGame | None = await _call(library.game(source.external_id))
            if game is None or not game.present:
                continue
            core = core_for(game.platform)
            if core is not None:
                found.append(Playable(source=source, game=game, core=core, service_name=name))
        if not found:
            raise NotPlayable("No emulator here plays this game.")
        return found

    async def game(self, viewer: Principal, object_id: UUID, rom: str | None = None) -> Playable:
        """One copy of the title: the one asked (``rom``: its id in the library), else the first."""
        found = await self.games(viewer, object_id)
        if rom is None:
            return found[0]
        chosen = next((p for p in found if p.game.external_id == rom), None)
        if chosen is None:
            raise NotPlayable("This copy of the game is not played here.")
        return chosen

    # --- a sitting ------------------------------------------------------------------------------------------
    async def start(self, viewer: Principal, object_id: UUID, rom: str | None = None) -> Started:
        playable = await self.game(viewer, object_id, rom)
        library = self._library(playable.source.service_id)
        try:
            firmware: Sequence[RetroFirmware] = await _call(library.firmware(playable.game.platform_id))
        except PortalError:
            firmware = []  # the game may run without it
        now = utc_now(self.clock)
        player = player_of(viewer)
        async with self.database.unit_of_work() as uow:
            row = Sitting(
                user_id=player,
                object_id=object_id,
                service_id=playable.source.service_id,
                external_id=playable.game.external_id,
                platform_id=playable.game.platform_id[:64],
                title=(playable.game.title or playable.source.title)[:500],
                platform=playable.game.platform[:64],
                core=playable.core,
                started_at=now,
                last_seen_at=now,
                played_s=0.0,
            )
            uow.session.add(row)
            await uow.session.flush()
            await self._publish(uow.session, "media.playback_started", row, now)
            sitting = row.id
        return Started(sitting=sitting, playable=playable, firmware=firmware)

    async def _sitting(self, viewer: Principal, sitting: UUID, *, open_only: bool = True) -> Sitting:
        async with self.database.session() as session:
            row = await session.get(Sitting, sitting)
        if row is None or row.user_id != player_of(viewer) or (open_only and row.ended_at is not None):
            raise SittingNotFound("No such game in progress.")
        return row

    async def beat(self, viewer: Principal, sitting: UUID, *, active: bool = True) -> Beat:
        """The page is still there: its time counts while the game is in front (``active``); a page in the
        background (a phone locked, another app) keeps its sitting open without counting."""
        now = utc_now(self.clock)
        player = player_of(viewer)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Sitting, sitting, with_for_update=True)
            if row is None or row.user_id != player or row.ended_at is not None:
                raise SittingNotFound("No such game in progress.")
            self._count(row, now, active=active)
            played = row.played_s
        today: tuple[int, int] | None = await _call(self._locator().screen(viewer))
        if today is None:
            return Beat(minutes_left=None, stop=False)
        used, allowed = today
        left = allowed - used - int(played // 60)
        return Beat(minutes_left=max(0, left), stop=left <= 0)

    async def end(self, viewer: Principal, sitting: UUID) -> None:
        now = utc_now(self.clock)
        player = player_of(viewer)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Sitting, sitting, with_for_update=True)
            if row is None or row.user_id != player:
                raise SittingNotFound("No such game in progress.")
            if row.ended_at is not None:
                return  # ended already (the page left twice, or the sweep was first)
            self._count(row, now)
            await self._close(uow.session, row, now)
        await self._tell(sitting)

    def _count(self, row: Sitting, now: datetime, *, active: bool = True) -> None:
        if active:
            row.played_s += max(0.0, min((now - row.last_seen_at).total_seconds(), GAP_S))
        row.last_seen_at = now

    async def _close(self, session: Any, row: Sitting, now: datetime) -> None:
        row.ended_at = now
        await self._publish(session, "media.playback_abandoned", row, now)

    async def _publish(self, session: Any, name: str, row: Sitting, at: datetime) -> None:
        """The sitting as the portal's player tells its plays (a game is never « finished » by playing it)."""
        if self.events is None:
            return
        ended = name == "media.playback_abandoned"
        payload: dict[str, Any] = {
            "object": str(row.object_id),
            "kind": "game",
            "service": str(row.service_id),
            "session": f"retro:{row.id}",
            "state_seq": 1 if ended else 0,
            "position_s": round(row.played_s, 1),
            "duration_s": None,
            "percent": None,
            "occurred_at": at.isoformat(),
            "via": "portal",
            **({"watched_s": round(row.played_s, 1)} if ended else {}),
        }
        await self.events.publish(
            session,
            name,
            payload,
            occurred_at=at,
            subject=SubjectRef("user", str(row.user_id)),
            source=SOURCE,
            dedup_key=f"{name}:retro:{row.id}",
        )

    async def _tell(self, sitting: UUID) -> bool:
        """The library told of an ended sitting (its play time) — once; the sweep retries a failure."""
        async with self.database.session() as session:
            row = await session.get(Sitting, sitting)
        if row is None or row.ended_at is None or row.told_at is not None:
            return False
        library = self._libraries().get(str(row.service_id))
        if library is not None and row.played_s >= 1:
            # 426: to the member's own account when they authorised the portal there, else the service's
            holder = await self.accounts.account_for(row.user_id, row.service_id) if self.accounts else None
            for account in ([holder.account] if holder is not None else []) + [None]:
                try:
                    _value(
                        await asyncio.wait_for(
                            library[0].record_session(
                                row.external_id,
                                row.started_at,
                                row.ended_at,
                                int(row.played_s * 1000),
                                account=account,
                            ),
                            timeout=TIMEOUT_S,
                        )
                    )
                    break
                except LibraryDenied:
                    if account is None:
                        log.warning("retro sitting refused by the library", extra={"sitting": str(sitting)})
                        return False
                    await self.accounts.refused(row.user_id, row.service_id)  # revoked there: the service's
                except Exception:
                    log.warning("retro sitting not told to the library", extra={"sitting": str(sitting)})
                    return False
        async with self.database.unit_of_work() as uow:
            told = await uow.session.get(Sitting, sitting, with_for_update=True)
            if told is not None:
                told.told_at = utc_now(self.clock)
        return True

    async def sweep(self, limit: int = 100) -> int:
        """The sittings nothing was heard of for a while end (a tab closed without a word); the ended ones
        the library was not told of are told again."""
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            rows = list(
                (
                    await uow.session.execute(
                        select(Sitting)
                        .where(Sitting.ended_at.is_(None), Sitting.last_seen_at < now - IDLE)
                        .order_by(Sitting.last_seen_at)
                        .limit(limit)
                        .with_for_update(skip_locked=True)
                    )
                ).scalars()
            )
            for row in rows:
                await self._close(uow.session, row, row.last_seen_at)
            closed = [row.id for row in rows]
        async with self.database.session() as session:
            untold = list(
                await session.scalars(
                    select(Sitting.id)
                    .where(
                        Sitting.ended_at.is_not(None),
                        Sitting.told_at.is_(None),
                        Sitting.ended_at > now - RETELL,
                    )
                    .order_by(Sitting.ended_at)
                    .limit(limit)
                )
            )
        for sitting in untold:
            await self._tell(sitting)
        return len(closed)

    # --- the files ------------------------------------------------------------------------------------------
    async def sitting_game(self, viewer: Principal, sitting: UUID) -> tuple[RetroSource, RetroGame]:
        """The game of an open sitting of the viewer's, as the library has it now."""
        row = await self._sitting(viewer, sitting)
        library = self._library(row.service_id)
        game: RetroGame | None = await _call(library.game(row.external_id))
        if game is None or not game.present:
            raise NotPlayable("The library no longer has this game.")
        return library, game

    async def open_game(
        self, viewer: Principal, sitting: UUID, range_header: str | None, stack: AsyncExitStack
    ) -> tuple[StreamBody, RetroGame]:
        library, game = await self.sitting_game(viewer, sitting)
        return await self._open(library, "rom", game.external_id, game.file_name, range_header, stack), game

    async def sitting_firmware(
        self, viewer: Principal, sitting: UUID, firmware: str
    ) -> tuple[RetroSource, RetroFirmware]:
        """A firmware of an open sitting's platform (only the game's platform's)."""
        row = await self._sitting(viewer, sitting)
        library = self._library(row.service_id)
        known: Sequence[RetroFirmware] = await _call(library.firmware(row.platform_id))
        found = next((f for f in known if f.id == firmware), None)
        if found is None:
            raise NotPlayable("No such firmware for this game.")
        return library, found

    async def open_firmware(
        self, viewer: Principal, sitting: UUID, firmware: str, stack: AsyncExitStack
    ) -> tuple[StreamBody, RetroFirmware]:
        library, found = await self.sitting_firmware(viewer, sitting, firmware)
        return await self._open(library, "firmware", found.id, found.file_name, None, stack), found

    async def open_emulator(self, service: UUID, path: str, stack: AsyncExitStack) -> StreamBody:
        return await self._open(self._library(service), "emulator", "", path, None, stack)

    async def _open(
        self,
        library: RetroSource,
        kind: FileKind,
        ref: str,
        name: str,
        range_header: str | None,
        stack: AsyncExitStack,
    ) -> StreamBody:
        try:
            body: StreamBody = await _call(
                stack.enter_async_context(library.open(kind, ref, name, range_header)), STREAM_TIMEOUT_S
            )
        except BaseException:
            await stack.aclose()
            raise
        return body
