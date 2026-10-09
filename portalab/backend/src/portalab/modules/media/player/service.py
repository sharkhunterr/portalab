"""``PlayerService`` (027, #2): watch a film or an episode in the portal, transcoded by its media server.

* **Which copy.** A catalog object plays from an active source item on a service that offers
  ``media.streaming`` (Plex) — a series or a season from its next episode for the member.
* **As whom.** The member's verified account on that service (``media.user_links``): their rights, resume
  points and history stay theirs. Without one, the player says so — unless the administrator lets such
  members play through the service's own account (``media.player.ownerFallback``).
* **Relayed.** Playlists, segments and subtitles go through the portal under a signed ticket
  (:mod:`.tickets`): no address or token of the service reaches the browser.
* **Quality.** Members pick among Plex's qualities, up to ``media.player.maxQuality``.
"""

import asyncio
import uuid
from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.media import (
    QUALITIES,
    STREAMING,
    PlayableItem,
    ResumePoint,
    StreamBody,
    StreamOptions,
    StreamStart,
    SubtitleCue,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.results import InvalidPayload, ProviderAuthError, ProviderNotFound
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, NotFound, PortalError, Unavailable
from portalab.core.time import Clock, utc_now
from portalab.modules.media.models import SourceItem, UserLink
from portalab.modules.media.player.subtitles import SubtitleFeeds
from portalab.modules.media.player.tickets import (
    LIFETIME_S,
    REMOTE_LIFETIME_S,
    Ticket,
    read,
    remote_key,
    sign,
)
from portalab.modules.media.settings import MediaConfig

PLAYABLE = ("movie", "episode", "series", "season")
STATES = ("playing", "paused", "buffering", "stopped")
TIMEOUT_S = 30.0
SEGMENT_TIMEOUT_S = 90.0


class PlayerOff(Forbidden):
    default_code = "media.player_disabled"
    default_title = "The player is turned off"


class PlayerUnlinked(Conflict):
    default_code = "media.player_unlinked"
    default_title = "Link your account on the media server first"


class PlayerDenied(Forbidden):
    default_code = "media.player_denied"
    default_title = "Your account on the media server cannot play this"


class NothingToPlay(NotFound):
    default_code = "media.player_nothing"
    default_title = "Nothing to play here"


class PlayerFailed(Unavailable):
    default_code = "media.player_unavailable"
    default_title = "The media server did not answer"


@dataclass(frozen=True, slots=True)
class Continuing:
    """027 (#23): the services' own « Continue watching » for a member — with the catalog object of each
    title — and which services and history families it speaks for (their history no longer decides)."""

    points: list[tuple[ResumePoint, UUID | None]]
    services: set[UUID]
    families: set[str]


@dataclass(frozen=True, slots=True)
class PlayerInfo:
    service_id: UUID
    service_name: str | None
    linked: bool  # played as the member's own account on the service
    item: PlayableItem
    qualities: list[str]
    cast_base_url: str | None = None  # 027 (#11): where casting devices reach the portal, when not its own


async def _call[T](operation: Any, limit: float = TIMEOUT_S) -> T:
    """A provider call, its failures as the player's problems."""
    try:
        result: T = await asyncio.wait_for(operation, timeout=limit)
    except PortalError:
        raise
    except ProviderAuthError as exc:
        raise PlayerDenied("Your account on the media server cannot play this.") from exc
    except ProviderNotFound as exc:
        raise NothingToPlay("The media server has nothing to play here.") from exc
    except (TimeoutError, ConnectionError, InvalidPayload) as exc:
        raise PlayerFailed("The media server did not answer.") from exc
    return result


class PlayerService:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        config: Callable[[], MediaConfig],
        key: bytes,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.config = config
        self.key = key
        self.clock = clock
        self.feeds = SubtitleFeeds()

    # --- where and as whom --------------------------------------------------------------------------------
    def _providers(self) -> dict[str, tuple[Any, str | None]]:
        try:
            registrations = self.capabilities.system_providers(STREAMING)
        except Exception:
            return {}
        return {r.instance_ref: (r.provider, r.metadata.get("name")) for r in registrations}

    def _enabled(self) -> None:
        if not self.config().player_enabled:
            raise PlayerOff("The administrator turned the player off.")

    async def _source(self, object_id: UUID) -> SourceItem:
        providers = self._providers()
        if not providers:
            raise NothingToPlay("No media server can play in the portal.")
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(SourceItem)
                        .where(
                            SourceItem.object_id == object_id,
                            SourceItem.active.is_(True),
                            SourceItem.kind.in_(PLAYABLE),
                        )
                        .order_by(SourceItem.last_seen_at.desc())
                    )
                )
                .scalars()
                .all()
            )
        row = next((r for r in rows if str(r.service_id) in providers), None)
        if row is None:
            raise NothingToPlay("This title cannot be played in the portal.")
        return row

    async def _account(self, user: UUID, service_id: UUID) -> str | None:
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
        if account:
            return str(account)
        if self.config().player_owner_fallback:
            return None
        raise PlayerUnlinked("Link your account on the media server to watch here.")

    def _registrations(self) -> dict[str, tuple[Any, str]]:
        """Streaming providers by service, with their connector (the history family they speak for)."""
        try:
            registrations = self.capabilities.system_providers(STREAMING)
        except Exception:
            return {}
        return {r.instance_ref: (r.provider, str(r.metadata.get("connector") or "")) for r in registrations}

    def _channel(self, service_id: UUID | str, account: str | None) -> Any:
        provider = self._providers().get(str(service_id))
        if provider is None:
            raise PlayerFailed("This media server is not available.")
        return provider[0].channel(account)

    def qualities(self) -> list[str]:
        keys = list(QUALITIES)
        cap = self.config().player_max_quality
        return keys[keys.index(cap) :] if cap in keys else keys

    # --- before playing -----------------------------------------------------------------------------------
    async def info(self, user: UUID, object_id: UUID, item: str | None = None) -> PlayerInfo:
        self._enabled()
        source = await self._source(object_id)
        account = await self._account(user, source.service_id)
        playable: PlayableItem = await _call(
            self._channel(source.service_id, account).playable(item or source.external_id)
        )
        return PlayerInfo(
            service_id=source.service_id,
            service_name=self._providers()[str(source.service_id)][1],
            linked=account is not None,
            item=playable,
            qualities=self.qualities(),
            cast_base_url=self.config().player_cast_base_url.strip().rstrip("/") or None,
        )

    async def start(
        self,
        user: UUID,
        object_id: UUID,
        item: str,
        options: StreamOptions,
        duration_s: float | None,
        *,
        remote: bool = False,
    ) -> tuple[str, str | None, StreamStart]:
        """The stream's ticket — and, for a ``remote`` device (Chromecast, AirPlay), a remote ticket its
        playlist and segments are fetched with, without a session."""
        self._enabled()
        source = await self._source(object_id)
        account = await self._account(user, source.service_id)
        allowed = self.qualities()
        if options.quality not in allowed:
            options = replace(options, quality=allowed[0])
        session = uuid.uuid4().hex[:24]
        started: StreamStart = await _call(
            self._channel(source.service_id, account).start(item, options, session)
        )
        ticket = Ticket(
            user=user,
            service=source.service_id,
            account=account,
            item=item,
            session=started.session,
            # the subtitle feed only serves subtitles drawn by the player
            options=options if started.subtitles == "text" else replace(options, subtitle=None),
            duration_s=duration_s,
            expires=int(utc_now(self.clock).timestamp()) + LIFETIME_S,
        )
        remote_ticket = None
        if remote:
            expires = int(utc_now(self.clock).timestamp()) + REMOTE_LIFETIME_S
            remote_ticket = sign(remote_key(self.key), replace(ticket, expires=expires))
        return sign(self.key, ticket), remote_ticket, started

    async def continuing(self, user: UUID, limit: int = 12) -> Continuing:
        """What the member is in the middle of, as each media server they are linked to keeps it (Plex's
        « Continue watching »): exact, at once, and empty again after « Back to zero ». A server that does
        not answer leaves the decision to the imported history."""
        providers = self._registrations()
        if not providers:
            return Continuing([], set(), set())
        async with self.database.session() as session:
            links = (
                await session.execute(
                    select(UserLink.service_id, UserLink.external_user_id).where(
                        UserLink.user_id == user, UserLink.verified.is_(True)
                    )
                )
            ).all()
        points: list[tuple[ResumePoint, UUID]] = []
        services: set[UUID] = set()
        families: set[str] = set()
        for service_id, account in links:
            registration = providers.get(str(service_id))
            if registration is None:
                continue
            try:
                found = await asyncio.wait_for(registration[0].channel(account).continuing(limit), timeout=8)
            except Exception:  # noqa: S112 — this server's say is skipped: the history still speaks
                continue
            services.add(service_id)
            families.add(registration[1])
            points.extend((point, service_id) for point in found)
        async with self.database.session() as session:
            objects = {
                (row.service_id, row.external_id): row.object_id
                for row in (
                    await session.execute(
                        select(SourceItem).where(
                            SourceItem.service_id.in_(services or {UUID(int=0)}),
                            SourceItem.external_id.in_([p.external_id for p, _ in points] or [""]),
                        )
                    )
                ).scalars()
            }
        points.sort(key=lambda p: p[0].at.timestamp() if p[0].at else 0.0, reverse=True)
        return Continuing(
            [(point, objects.get((service, point.external_id))) for point, service in points][:limit],
            services,
            families,
        )

    async def objects_on(self, services: set[UUID], object_ids: list[UUID]) -> set[UUID]:
        """The objects among ``object_ids`` that the given services hold."""
        if not services or not object_ids:
            return set()
        async with self.database.session() as session:
            rows = await session.execute(
                select(SourceItem.object_id).where(
                    SourceItem.service_id.in_(services), SourceItem.object_id.in_(object_ids)
                )
            )
            return {r[0] for r in rows if r[0] is not None}

    async def reset(self, user: UUID, object_id: UUID, item: str | None = None) -> None:
        """« Back to zero » without playing: the member's resume point on the service is forgotten."""
        self._enabled()
        source = await self._source(object_id)
        account = await self._account(user, source.service_id)
        await _call(self._channel(source.service_id, account).reset(item or source.external_id))

    # --- while playing ------------------------------------------------------------------------------------
    def ticket(self, user: UUID, token: str) -> Ticket:
        return read(self.key, token, user=user, now=utc_now(self.clock))

    async def open(self, user: UUID, token: str, path: str, stack: AsyncExitStack) -> StreamBody:
        """A playlist or segment, entered on ``stack`` (closed by the caller once relayed)."""
        ticket = self.ticket(user, token)
        channel = self._channel(ticket.service, ticket.account)
        try:
            body: StreamBody = await _call(
                stack.enter_async_context(channel.open(ticket.session, path)), SEGMENT_TIMEOUT_S
            )
        except BaseException:
            await stack.aclose()
            raise
        return body

    async def open_remote(self, token: str, path: str, stack: AsyncExitStack) -> StreamBody:
        """027 (#11): the same stream for a casting device, addressed by the remote ticket alone."""
        ticket = read(remote_key(self.key), token, user=None, now=utc_now(self.clock))
        channel = self._channel(ticket.service, ticket.account)
        try:
            body: StreamBody = await _call(
                stack.enter_async_context(channel.open(ticket.session, path)), SEGMENT_TIMEOUT_S
            )
        except BaseException:
            await stack.aclose()
            raise
        return body

    async def subtitles(self, user: UUID, token: str, at: float, *, seek: bool) -> list[SubtitleCue]:
        ticket = self.ticket(user, token)
        if ticket.options.subtitle is None:
            return []
        channel = self._channel(ticket.service, ticket.account)
        feed = self.feeds.get(
            ticket.session, lambda: channel.subtitles(ticket.item, ticket.options, ticket.session)
        )
        feed.ensure(at, seek=seek)
        return feed.window(at)

    async def report(
        self, user: UUID, token: str, state: str, position_s: float, duration_s: float | None
    ) -> None:
        ticket = self.ticket(user, token)
        channel = self._channel(ticket.service, ticket.account)
        await _call(
            channel.report(
                ticket.item,
                ticket.session,
                state if state in STATES else "playing",
                position_s,
                duration_s or ticket.duration_s,
            )
        )

    async def image(self, user: UUID, token: str, ref: str, at_s: float | None) -> bytes:
        """A chapter's picture or a seek-bar preview of the stream's title, as the member's account."""
        ticket = self.ticket(user, token)
        channel = self._channel(ticket.service, ticket.account)
        data: bytes = await _call(channel.image(ref, at_s), 15.0)
        return data

    async def stop(self, user: UUID, token: str) -> None:
        ticket = self.ticket(user, token)
        self.feeds.close(ticket.session)
        channel = self._channel(ticket.service, ticket.account)
        await _call(channel.stop(ticket.session))
