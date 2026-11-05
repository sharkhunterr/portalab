"""``BookService`` (#20, #21): listen to an audiobook and read a book in the portal.

* **Which copy.** A catalog object is listened to from an active ``audiobook`` source item, or read from an
  active ``book`` one, on a service that offers ``media.audio`` or ``media.reading`` (Grimmory).
* **Relayed.** The audio (with byte ranges, so the member can seek), the EPUB or PDF file and a comic's
  pages go through the portal under a signed ticket (:mod:`.tickets`): no address or token of the service
  reaches the browser.
* **Where the member stopped.** Kept in the portal for every member (``media.book_positions``, per
  format), and written back to the service when it keeps this member's progress (Grimmory: the member is
  linked to the account configured on the service). Opening again resumes from the latest of the two.
* **Activity.** Listening and reading publish the same ``media.playback_*`` events as a film watched on
  Plex: the history, « Continue », the statistics and the rewards follow without anything new.
"""

import asyncio
import uuid
from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.media import (
    AUDIO,
    READING,
    READING_FORMATS,
    AudioItem,
    AudioPosition,
    ReadableBook,
    ReadingPosition,
    StreamBody,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.results import InvalidPayload, ProviderAuthError, ProviderNotFound
from portalab.core.db import Database
from portalab.core.errors import Forbidden, NotFound, PortalError, Unavailable
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.media.books.tickets import LIFETIME_S, BookTicket, books_key, read, sign
from portalab.modules.media.models import BookPosition, SourceItem, UserLink
from portalab.modules.media.settings import MediaConfig

TIMEOUT_S = 30.0
STREAM_TIMEOUT_S = 90.0
STATES = ("playing", "paused", "stopped", "finished")
FINISHED = 0.995  # a book read to here is finished
# #256: a sitting nothing has been heard of for this long is over (its page went away without a word)
IDLE = timedelta(minutes=30)
HEARD_SLACK_S = 5.0  # #353: a report's own lateness, on top of 3x the time between two reports
ENDINGS = ("media.playback_finished", "media.playback_abandoned")
AUDIO_FORMAT = "audio"


class BooksOff(Forbidden):
    default_code = "media.books_disabled"
    default_title = "Listening and reading in the portal are turned off"


class NothingToOpen(NotFound):
    default_code = "media.books_nothing"
    default_title = "Nothing to listen to or read here"


class BooksDenied(Forbidden):
    default_code = "media.books_denied"
    default_title = "The library refused this book"


class BooksFailed(Unavailable):
    default_code = "media.books_unavailable"
    default_title = "The library did not answer"


@dataclass(frozen=True, slots=True)
class Listening:
    ticket: str
    service_name: str | None
    synced: bool  # the member's position is also kept by the service
    item: AudioItem
    resume: AudioPosition | None


@dataclass(frozen=True, slots=True)
class Reading:
    ticket: str
    service_name: str | None
    synced: bool
    book: ReadableBook
    resume: dict[str, ReadingPosition]  # by format


async def _call[T](operation: Any, limit: float = TIMEOUT_S) -> T:
    try:
        result: T = await asyncio.wait_for(operation, timeout=limit)
    except PortalError:
        raise
    except ProviderAuthError as exc:
        raise BooksDenied("The library refused this book.") from exc
    except ProviderNotFound as exc:
        raise NothingToOpen("The library has nothing here.") from exc
    except (TimeoutError, ConnectionError, InvalidPayload) as exc:
        raise BooksFailed("The library did not answer.") from exc
    return result


def _latest[P: (AudioPosition, ReadingPosition)](mine: P | None, theirs: P | None) -> P | None:
    """The more recent of the portal's and the service's positions (the service's when it gives no date
    and the portal has none)."""
    if mine is None or theirs is None:
        return mine or theirs
    if theirs.at is not None and mine.at is not None and theirs.at > mine.at:
        return theirs
    return mine


class BookService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        config: Callable[[], MediaConfig],
        key: bytes,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.config = config
        self.key = books_key(key)
        self.clock = clock

    # --- where and as whom --------------------------------------------------------------------------------
    def _providers(self, capability: str) -> dict[str, tuple[Any, str | None]]:
        try:
            registrations = self.capabilities.system_providers(capability)
        except Exception:
            return {}
        return {r.instance_ref: (r.provider, r.metadata.get("name")) for r in registrations}

    def _enabled(self, mode: str) -> None:
        config = self.config()
        if not (config.listening_enabled if mode == "listen" else config.reading_enabled):
            raise BooksOff("The administrator turned this off.")

    async def _source(self, object_id: UUID, kind: str, capability: str) -> SourceItem:
        providers = self._providers(capability)
        if not providers:
            raise NothingToOpen("No library can open books in the portal.")
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(SourceItem)
                        .where(
                            SourceItem.object_id == object_id,
                            SourceItem.active.is_(True),
                            SourceItem.kind == kind,
                        )
                        .order_by(SourceItem.last_seen_at.desc())
                    )
                )
                .scalars()
                .all()
            )
        row = next((r for r in rows if str(r.service_id) in providers), None)
        if row is None:
            raise NothingToOpen("This title cannot be opened in the portal.")
        return row

    async def _account(self, user: UUID, service_id: UUID) -> str | None:
        """The member's verified account on the service — or none: the book still opens, through the
        service's own account, and the member's position stays in the portal."""
        async with self.database.session() as session:
            account = (
                await session.execute(
                    select(UserLink.external_user_id).where(
                        UserLink.user_id == user,
                        UserLink.service_id == service_id,
                        UserLink.verified.is_(True),
                    )
                )
            ).scalar_one_or_none()
        return str(account) if account else None

    def _channel(self, capability: str, service_id: UUID | str, account: str | None) -> Any:
        provider = self._providers(capability).get(str(service_id))
        if provider is None:
            raise BooksFailed("This library is not available.")
        return provider[0].channel(account)

    def _ticket(
        self, user: UUID, source: SourceItem, account: str | None, mode: str, file: str | None = None
    ) -> str:
        return sign(
            self.key,
            BookTicket(
                user=user,
                service=source.service_id,
                account=account,
                object_id=source.object_id or UUID(int=0),
                item=source.external_id,
                mode=mode,
                session=uuid.uuid4().hex[:24],
                expires=int(utc_now(self.clock).timestamp()) + LIFETIME_S,
                file=file,
            ),
        )

    def ticket(self, user: UUID, token: str, mode: str) -> BookTicket:
        return read(self.key, token, user=user, mode=mode, now=utc_now(self.clock))

    async def _positions(self, user: UUID, object_id: UUID) -> dict[str, BookPosition]:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(BookPosition).where(
                        BookPosition.user_id == user, BookPosition.object_id == object_id
                    )
                )
            ).scalars()
            return {row.format: row for row in rows}

    # --- listening (#20) ----------------------------------------------------------------------------------
    async def listen(self, user: UUID, object_id: UUID) -> Listening:
        self._enabled("listen")
        source = await self._source(object_id, "audiobook", AUDIO)
        account = await self._account(user, source.service_id)
        channel = self._channel(AUDIO, source.service_id, account)
        item: AudioItem = await _call(channel.item(source.external_id))
        mine = (await self._positions(user, object_id)).get(AUDIO_FORMAT)
        kept = (
            AudioPosition(
                position_s=float(mine.position),
                track=mine.track,
                percent=mine.percent,
                at=mine.updated_at,
            )
            if mine is not None and _number(mine.position)
            else None
        )
        return Listening(
            ticket=self._ticket(user, source, account, "listen", item.file_ref),
            service_name=self._providers(AUDIO)[str(source.service_id)][1],
            synced=item.position is not None or await _call(_synced(channel)),
            item=item,
            resume=_latest(kept, item.position),
        )

    async def audio(
        self, user: UUID, token: str, track: int | None, byte_range: str | None, stack: AsyncExitStack
    ) -> StreamBody:
        """The audio (or one of its files), entered on ``stack`` (closed by the caller once relayed)."""
        ticket = self.ticket(user, token, "listen")
        channel = self._channel(AUDIO, ticket.service, ticket.account)
        try:
            body: StreamBody = await _call(
                stack.enter_async_context(channel.open(ticket.item, track, byte_range)), STREAM_TIMEOUT_S
            )
        except BaseException:
            await stack.aclose()
            raise
        return body

    async def listened(
        self,
        user: UUID,
        token: str,
        *,
        state: str,
        position_s: float,
        duration_s: float | None,
        track: int | None,
        seq: int,
    ) -> None:
        """Where the member is: kept, written back to the service, and published as activity."""
        ticket = self.ticket(user, token, "listen")
        share = min(1.0, position_s / duration_s) if duration_s else None
        finished = state == "finished" or (share is not None and share >= FINISHED)
        await self._record(
            ticket,
            AUDIO_FORMAT,
            file_ref=None,
            position=str(round(position_s, 1)),
            track=track,
            percent=1.0 if finished else (share or 0.0),
            state="finished" if finished else state,
            seq=seq,
            kind="audiobook",
            position_s=position_s,
            duration_s=duration_s,
        )
        channel = self._channel(AUDIO, ticket.service, ticket.account)
        item = AudioItem(
            external_id=ticket.item, kind="audiobook", title="", duration_s=duration_s, file_ref=ticket.file
        )
        await _call(
            channel.report(
                item,
                AudioPosition(position_s=position_s, track=track, percent=1.0 if finished else share),
            )
        )

    # --- reading (#21) ------------------------------------------------------------------------------------
    async def read(self, user: UUID, object_id: UUID) -> Reading:
        self._enabled("read")
        source = await self._source(object_id, "book", READING)
        account = await self._account(user, source.service_id)
        channel = self._channel(READING, source.service_id, account)
        book: ReadableBook = await _call(channel.book(source.external_id))
        theirs = {p.format: p for p in book.positions}
        resume: dict[str, ReadingPosition] = {}
        for name, row in (await self._positions(user, object_id)).items():
            if name in READING_FORMATS:
                resume[name] = ReadingPosition(
                    format=name,
                    position=row.position,
                    percent=row.percent,
                    file_ref=row.file_ref,
                    at=row.updated_at,
                )
        for name, position in theirs.items():
            chosen = _latest(resume.get(name), position)
            if chosen is not None:
                resume[name] = chosen
        return Reading(
            ticket=self._ticket(user, source, account, "read"),
            service_name=self._providers(READING)[str(source.service_id)][1],
            synced=bool(book.positions) or await _call(_synced(channel)),
            book=book,
            resume=resume,
        )

    async def file(self, user: UUID, token: str, file_ref: str, stack: AsyncExitStack) -> StreamBody:
        ticket = self.ticket(user, token, "read")
        channel = self._channel(READING, ticket.service, ticket.account)
        try:
            body: StreamBody = await _call(
                stack.enter_async_context(channel.open(ticket.item, file_ref)), STREAM_TIMEOUT_S
            )
        except BaseException:
            await stack.aclose()
            raise
        return body

    async def pages(self, user: UUID, token: str, file_ref: str) -> list[int]:
        ticket = self.ticket(user, token, "read")
        channel = self._channel(READING, ticket.service, ticket.account)
        found: list[int] = await _call(channel.pages(ticket.item, file_ref))
        return found

    async def page(
        self, user: UUID, token: str, file_ref: str, number: int, stack: AsyncExitStack
    ) -> StreamBody:
        ticket = self.ticket(user, token, "read")
        channel = self._channel(READING, ticket.service, ticket.account)
        try:
            body: StreamBody = await _call(
                stack.enter_async_context(channel.page(ticket.item, file_ref, number)), STREAM_TIMEOUT_S
            )
        except BaseException:
            await stack.aclose()
            raise
        return body

    async def progressed(
        self,
        user: UUID,
        token: str,
        *,
        state: str,
        format: str,
        file_ref: str | None,
        position: str,
        percent: float,
        seconds: float,
        seq: int,
    ) -> None:
        """Where the member is in the book (a CFI or a page) and for how long they have been reading."""
        ticket = self.ticket(user, token, "read")
        if format not in READING_FORMATS:
            raise NothingToOpen("The portal does not read this format.")
        share = min(1.0, max(0.0, percent))
        finished = state == "finished" or share >= FINISHED
        await self._record(
            ticket,
            format,
            file_ref=file_ref,
            position=position,
            track=None,
            percent=share,
            state="finished" if finished else state,
            seq=seq,
            kind="book",
            position_s=seconds,  # a book's « position » in the activity: the time spent reading it
            duration_s=None,
        )
        channel = self._channel(READING, ticket.service, ticket.account)
        book = ReadableBook(external_id=ticket.item, title="")
        await _call(
            channel.report(
                book,
                ReadingPosition(format=format, position=position, percent=share, file_ref=file_ref),
            )
        )

    # --- keeping and publishing ---------------------------------------------------------------------------
    async def _record(
        self,
        ticket: BookTicket,
        format: str,
        *,
        file_ref: str | None,
        position: str,
        track: int | None,
        percent: float,
        state: str,
        seq: int,
        kind: str,
        position_s: float,
        duration_s: float | None,
    ) -> None:
        now = utc_now(self.clock)
        state = state if state in STATES else "playing"
        async with self.database.unit_of_work() as uow:
            session = uow.session
            row = await session.get(
                BookPosition, (ticket.user, ticket.object_id, format), with_for_update=True
            )
            last: tuple[float, datetime] | None = None
            if row is None:
                await session.execute(
                    insert(BookPosition)
                    .values(
                        user_id=ticket.user,
                        object_id=ticket.object_id,
                        format=format,
                        service_id=ticket.service,
                        external_id=ticket.item,
                        file_ref=file_ref,
                        position=position[:2000],
                        track=track,
                        percent=percent,
                        updated_at=now,
                        event_at=None,
                    )
                    .on_conflict_do_nothing()
                )
                row = await session.get(BookPosition, (ticket.user, ticket.object_id, format))
            else:
                # #353: where the last report left the player, and when — what an audiobook heard since
                last = (float(row.position), row.updated_at) if _number(row.position) else None
                row.service_id, row.external_id = ticket.service, ticket.item
                row.file_ref, row.position, row.track = file_ref, position[:2000], track
                row.percent, row.updated_at = percent, now
            watched = None
            if row is not None:  # #94: the minutes of this sitting — what the progression counts
                ended = row.session_ref == ticket.session[:64] and row.session_ended_at is not None
                if ended and state in ("paused", "stopped"):
                    return  # #256: its end was counted already — the page left, then the player closed
                if ended or row.session_ref != ticket.session[:64] or row.session_started_at is None:
                    # a new sitting (or the same page back from the browser's cache once its sitting ended)
                    row.session_ref, row.session_start_s = ticket.session[:64], position_s
                    row.session_started_at, row.session_ended_at = now, None
                    row.session_watched_s, last = None, None
                if kind == "book":
                    watched = _watched(kind, position_s, row.session_start_s, now - row.session_started_at)
                else:  # #353: what was heard report after report — a jump (a chapter skipped) is not heard
                    watched = (row.session_watched_s or 0.0) + (
                        _heard(position_s, *last, now) if last is not None else 0.0
                    )
                row.session_watched_s = watched
            name = self._event(state, seq, row.event_at if row is not None else None, now)
            if name is None:
                return
            if row is not None and name in ("media.playback_progressed", "media.playback_started"):
                row.event_at = now
            if row is not None and name in ENDINGS:
                row.session_ended_at = now
            await self._publish(
                session,
                name,
                user=ticket.user,
                object_id=ticket.object_id,
                service=ticket.service,
                sitting=ticket.session,
                started=row.session_started_at if row is not None else None,
                kind=kind,
                seq=seq,
                position_s=position_s,
                duration_s=duration_s,
                percent=percent,
                watched=watched,
                at=now,
            )

    async def _publish(
        self,
        session: Any,
        name: str,
        *,
        user: UUID,
        object_id: UUID,
        service: UUID,
        sitting: str,
        started: datetime | None,
        kind: str,
        seq: int,
        position_s: float,
        duration_s: float | None,
        percent: float,
        watched: float | None,
        at: datetime,
    ) -> None:
        payload = {
            "object": str(object_id),
            "kind": kind,
            "service": str(service),
            "session": sitting,
            "state_seq": max(0, int(seq)),
            "position_s": round(max(0.0, position_s), 1),
            "duration_s": duration_s,
            "percent": round(percent, 4),
            "occurred_at": at.isoformat(),
            **({"watched_s": round(watched, 1)} if watched is not None else {}),
            "via": "portal",  # #103: read or listened to in the portal
        }
        # a sitting ends once: finished once per session, abandoned once per sitting (#256: the page leaving,
        # then the player closed, or the sweep after either, never count its minutes twice)
        if name == "media.playback_finished":
            dedup = f"media.playback_finished:{sitting}"
        elif name == "media.playback_abandoned":
            begun = int(started.timestamp()) if started is not None else seq
            dedup = f"media.playback_abandoned:{sitting}:{begun}"
        else:
            dedup = f"media.playback:{sitting}:{seq}"
        await self.events.publish(
            session,
            name,
            payload,
            occurred_at=at,
            subject=SubjectRef("user", str(user)),
            source="media",
            dedup_key=dedup,
        )

    async def sweep(self, limit: int = 200) -> int:
        """#256: end the sittings nothing has been heard of for a while — the member's page went away
        without a word (a phone's app closed, a tab dropped): their minutes are counted, as when the member
        closes it."""
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            rows = (
                await session.execute(
                    select(BookPosition)
                    .where(
                        BookPosition.session_ref.is_not(None),
                        BookPosition.session_started_at.is_not(None),
                        BookPosition.session_ended_at.is_(None),
                        BookPosition.updated_at < now - IDLE,
                    )
                    .order_by(BookPosition.updated_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).scalars()
            ended = 0
            for row in rows:
                audio = row.format == AUDIO_FORMAT
                kind = "audiobook" if audio else "book"
                heard = float(row.position) if audio and _number(row.position) else None
                watched = row.session_watched_s
                if watched is None and heard is not None and row.session_started_at is not None:
                    spent = row.updated_at - row.session_started_at
                    watched = _watched(kind, heard, row.session_start_s, spent)
                row.session_ended_at = now
                await self._publish(
                    session,
                    "media.playback_finished" if row.percent >= FINISHED else "media.playback_abandoned",
                    user=row.user_id,
                    object_id=row.object_id,
                    service=row.service_id,
                    sitting=row.session_ref or "",
                    started=row.session_started_at,
                    kind=kind,
                    seq=0,
                    # a book's « position » in the activity: the time spent reading it (as it reports it)
                    position_s=heard if heard is not None else (watched or 0.0),
                    duration_s=None,
                    percent=row.percent,
                    watched=watched,
                    at=row.updated_at,  # when it was last heard of: when it really ended
                )
                ended += 1
            return ended

    def _event(self, state: str, seq: int, last: datetime | None, now: datetime) -> str | None:
        """The activity a report means: started once, progress at most every so often, then paused,
        finished or abandoned (the member closed the book or the player)."""
        if state == "finished":
            return "media.playback_finished"
        if state == "paused":
            return "media.playback_paused"
        if state == "stopped":
            return "media.playback_abandoned"
        if seq <= 1:
            return "media.playback_started"
        every = timedelta(seconds=max(10, self.config().progress_event_seconds))
        if last is None or now - last >= every:
            return "media.playback_progressed"
        return None


def _heard(position_s: float, last_s: float, last_at: datetime, now: datetime) -> float:
    """#353: what an audiobook played between two reports — forward, and no faster than 3x (a fast
    listener); a jump forward or back (a chapter picked, a skip) counts nothing."""
    gone = position_s - last_s
    if gone <= 0 or gone > max(0.0, (now - last_at).total_seconds()) * 3 + HEARD_SLACK_S:
        return 0.0
    return gone


def _watched(kind: str, position_s: float, start_s: float | None, elapsed: timedelta) -> float:
    """#94: the minutes of a sitting — a book reports the time spent reading in it, an audiobook its position:
    what was heard since the sitting began (up to 3x its time, for a fast reader)."""
    seconds = elapsed.total_seconds()
    if kind == "book":
        return min(max(0.0, position_s), seconds + 60)
    heard = position_s - (start_s if start_s is not None else position_s)
    return min(max(0.0, heard), seconds * 3 + 60)


def _number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


async def _synced(channel: Any) -> bool:
    """Whether the service keeps this member's progress (an account of theirs it writes to)."""
    own = getattr(channel, "own", None)
    if own is None:
        return False
    return bool(await own())
