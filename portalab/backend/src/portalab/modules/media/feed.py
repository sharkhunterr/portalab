"""#299 — « Mon fil »: what a member follows (people, titles, genres — private) and what the library brought
them lately: a work with a person they follow, a new season or new episodes of a title they follow, a title
they follow (a film, a book, a game…) arrived in the library (#499), a work of a genre they follow. Read from
the library itself (when each object was first seen), nothing copied per member; what arrived since they last
opened their feed is unread."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased

from portalab.capabilities.media import GAME_DATABASE, unwrap
from portalab.capabilities.notifications import CommunicationRequest, Notifications, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.models import (
    Credit,
    ExternalId,
    FeedNotified,
    FeedSeen,
    Follow,
    MediaObject,
    ObjectTag,
)
from portalab.modules.media.people import WORK, People, _credited

Kind = Literal["person", "title", "genre"]
KINDS: tuple[Kind, ...] = ("person", "title", "genre")
WORKS = ("movie", "series", "book", "audiobook", "game", "album")
WINDOW = timedelta(days=45)  # how far back the feed reads
LIMIT = 60
GENRE_LIMIT = 30  # a genre brings much: its latest only
MAX_FOLLOWS = 200
CATEGORY = "media.feed"  # the notices of « Mon fil » (each member chooses where they go)


# issue 501: a title the library lacks, followed by its sheet (« /media/game?service=…&ref=… »): the scheme
# of the database that knows it, by which the library's title is found once it arrives
SHEETS = {"/media/game": "igdb"}


def sheet_ref(ref: str) -> tuple[str, str, str] | None:
    """A sheet's database service, the identifier scheme and the title's id there — ``None``: not a sheet."""
    address = urlsplit(ref)
    query = parse_qs(address.query)
    service, value = (query.get("service") or [""])[0], (query.get("ref") or [""])[0]
    scheme = SHEETS.get(address.path)
    if scheme is None or not service or not value.isdigit() or len(ref) > 200:
        return None
    return service, scheme, value


async def game_title(capabilities: CapabilityRegistry, service: str, ref: str) -> str | None:
    """Issue 501: a game's name as the game database (that service) tells it; ``None``: unknown."""
    for registration in capabilities.system_providers(GAME_DATABASE):
        if str(registration.instance_ref) == service:
            try:
                game = unwrap(await asyncio.wait_for(registration.provider.game(ref), timeout=15))
            except Exception:
                return None
            title = getattr(game, "title", None)
            return str(title) if title else None
    return None


def _is_object(ref: str) -> bool:
    try:
        UUID(ref)
    except ValueError:
        return False
    return True


class FollowRefused(ValueError):
    """Nothing in the library by that reference (or too many follows)."""


@dataclass(frozen=True, slots=True)
class Followed:
    kind: Kind
    ref: str
    label: str
    created_at: datetime


@dataclass(slots=True)
class Arrival:
    """A work the library brought, why it is in my feed (what I follow, as ``(kind, label)``), and for a
    series I follow the episodes or seasons that came (« S02E05 »)."""

    object_id: UUID
    at: datetime
    because: list[tuple[str, str]] = field(default_factory=list)
    units: list[str] = field(default_factory=list)


class Feed:
    def __init__(
        self,
        database: Database,
        people: People,
        *,
        clock: Clock | None = None,
        sheet_title: Callable[[str, str], Awaitable[str | None]] | None = None,
    ):
        self.database = database
        self.people = people
        self.clock = clock
        # issue 501: a game's name as its database tells it (service, id) — and proof it knows it
        self.sheet_title = sheet_title

    # --- what I follow --------------------------------------------------------------------------------
    async def follows(self, user: UUID) -> list[Followed]:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Follow).where(Follow.user_id == user).order_by(Follow.created_at.desc())
                )
            ).scalars()
            return [Followed(row.kind, row.ref, row.label, row.created_at) for row in rows]  # type: ignore[arg-type]

    async def _label(self, kind: Kind, ref: str) -> str:
        """The subject's name as the library knows it — and proof the library knows it."""
        if kind == "person":
            page = await self.people.page(ref)
            if page is None:
                raise FollowRefused("nobody by that name in the library")
            return page.name
        if kind == "title" and not _is_object(ref):
            found = sheet_ref(ref)
            title = await self.sheet_title(found[0], found[2]) if found and self.sheet_title else None
            if not title:
                raise FollowRefused("not a title the game database knows")
            return title[:200]
        async with self.database.session() as session:
            if kind == "title":
                try:
                    object_id = UUID(ref)
                except ValueError as exc:
                    raise FollowRefused("not a title") from exc
                row = await session.get(MediaObject, object_id)
                if row is None or row.kind not in WORKS or row.status != "active":
                    raise FollowRefused("not a title of the library")
                return row.title
            known = await session.scalar(
                select(ObjectTag.value).where(ObjectTag.tag_kind == "genre", ObjectTag.value == ref).limit(1)
            )
            if known is None:
                raise FollowRefused("no such genre in the library")
            return str(known)

    async def follow(self, user: UUID, kind: Kind, ref: str) -> Followed:
        label = await self._label(kind, ref)
        ref = ref if kind != "person" else label  # a person under the name the library credits them
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            count = await uow.session.scalar(
                select(func.count()).select_from(Follow).where(Follow.user_id == user)
            )
            if int(count or 0) >= MAX_FOLLOWS:
                raise FollowRefused("too many follows")
            await uow.session.execute(
                insert(Follow)
                .values(user_id=user, kind=kind, ref=ref, label=label, created_at=now)
                .on_conflict_do_nothing()
            )
        return Followed(kind, ref, label, now)

    async def unfollow(self, user: UUID, kind: Kind, ref: str) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                delete(Follow).where(Follow.user_id == user, Follow.kind == kind, Follow.ref == ref)
            )

    # --- what the library brought -----------------------------------------------------------------------
    async def arrivals(self, user: UUID, follows: Sequence[Followed] | None = None) -> list[Arrival]:
        follows = await self.follows(user) if follows is None else follows
        if not follows:
            return []
        since = utc_now(self.clock) - WINDOW
        found: dict[UUID, Arrival] = {}

        def add(object_id: UUID, at: datetime, kind: str, label: str, unit: str | None = None) -> None:
            arrival = found.setdefault(object_id, Arrival(object_id, at))
            arrival.at = max(arrival.at, at)
            if (kind, label) not in arrival.because:
                arrival.because.append((kind, label))
            if unit and unit not in arrival.units:
                arrival.units.append(unit)

        people = {f.ref: f.label for f in follows if f.kind == "person"}
        titles = {UUID(f.ref): f.label for f in follows if f.kind == "title" and _is_object(f.ref)}
        sheets = {f.ref: f for f in follows if f.kind == "title" and not _is_object(f.ref)}
        genres = {f.ref: f.label for f in follows if f.kind == "genre"}
        async with self.database.session() as session:
            if people:
                folded = {name: func.media.search_fold(name) for name in people}
                # which followed name each credit is (the same name however it is written)
                name = case(*((Credit.folded == value, key) for key, value in folded.items()), else_=None)
                works = (
                    await session.execute(
                        _credited(select(WORK.label("work"), func.min(name).label("name")))
                        .where(Credit.folded.in_(list(folded.values())))
                        .group_by(WORK)
                    )
                ).all()
                ids = {row.work: row.name for row in works}
                if ids:
                    for row in (
                        await session.execute(
                            select(MediaObject.id, MediaObject.first_seen_at).where(
                                MediaObject.id.in_(ids),
                                MediaObject.kind.in_(WORKS),
                                MediaObject.status == "active",
                                MediaObject.available.is_(True),
                                MediaObject.first_seen_at >= since,
                            )
                        )
                    ).all():
                        add(row.id, row.first_seen_at, "person", people.get(ids[row.id], ids[row.id]))
            # issue 501: a title followed by its sheet — the library's title carrying its id, once there
            waited: dict[UUID, Followed] = {}
            for follow in sheets.values():
                sheet = sheet_ref(follow.ref)
                if sheet is None:
                    continue
                object_id = await session.scalar(
                    select(ExternalId.object_id).where(
                        ExternalId.scheme == sheet[1], ExternalId.value == sheet[2]
                    )
                )
                if object_id is not None:
                    waited[object_id] = follow
            if waited:
                for here in (
                    await session.execute(
                        select(MediaObject.id, MediaObject.available_at).where(
                            MediaObject.id.in_(waited),
                            MediaObject.status == "active",
                            MediaObject.available.is_(True),
                            MediaObject.available_at >= since,
                        )
                    )
                ).all():
                    follow = waited[here.id]
                    if here.available_at > follow.created_at:
                        add(here.id, here.available_at, "title", follow.label)
            if titles:
                season = aliased(MediaObject)
                units = (
                    await session.execute(
                        select(
                            MediaObject.kind,
                            MediaObject.position,
                            MediaObject.first_seen_at,
                            func.coalesce(season.parent_id, MediaObject.parent_id).label("work"),
                            season.position.label("season"),
                        )
                        .outerjoin(
                            season, (season.id == MediaObject.parent_id) & (MediaObject.kind == "episode")
                        )
                        .where(
                            MediaObject.kind.in_(("season", "episode")),
                            MediaObject.status == "active",
                            MediaObject.available.is_(True),
                            MediaObject.first_seen_at >= since,
                            or_(MediaObject.parent_id.in_(titles), season.parent_id.in_(titles)),
                        )
                        .order_by(MediaObject.first_seen_at)
                    )
                ).all()
                for new in units:
                    if new.work not in titles:
                        continue
                    code: str | None = None
                    if new.kind == "episode" and new.season is not None and new.position is not None:
                        code = f"S{new.season:02d}E{new.position:02d}"
                    elif new.kind == "season" and new.position is not None:
                        code = f"S{new.position:02d}"
                    add(new.work, new.first_seen_at, "title", titles[new.work], code)
                # #499: a film, a book, a game… followed before it was here — its arrival in the library,
                # whatever its kind
                followed_at = {
                    UUID(f.ref): f.created_at for f in follows if f.kind == "title" and _is_object(f.ref)
                }
                for here in (
                    await session.execute(
                        select(MediaObject.id, MediaObject.available_at).where(
                            MediaObject.id.in_(titles),
                            MediaObject.status == "active",
                            MediaObject.available.is_(True),
                            MediaObject.available_at >= since,
                        )
                    )
                ).all():
                    if here.available_at > followed_at[here.id]:
                        add(here.id, here.available_at, "title", titles[here.id])
            for genre, label in genres.items():
                latest = (
                    await session.execute(
                        select(MediaObject.id, MediaObject.first_seen_at)
                        .join(ObjectTag, ObjectTag.object_id == MediaObject.id)
                        .where(
                            ObjectTag.tag_kind == "genre",
                            ObjectTag.value == genre,
                            MediaObject.kind.in_(("movie", "series")),
                            MediaObject.status == "active",
                            MediaObject.available.is_(True),
                            MediaObject.first_seen_at >= since,
                        )
                        .order_by(MediaObject.first_seen_at.desc())
                        .limit(GENRE_LIMIT)
                    )
                ).all()
                for hit in latest:
                    add(hit.id, hit.first_seen_at, "genre", label)
        return sorted(found.values(), key=lambda a: a.at, reverse=True)[:LIMIT]

    # --- read, unread -----------------------------------------------------------------------------------
    async def seen_at(self, user: UUID) -> datetime | None:
        async with self.database.session() as session:
            row = await session.get(FeedSeen, user)
            return row.seen_at if row else None

    async def mark_seen(self, user: UUID) -> datetime:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(FeedSeen)
                .values(user_id=user, seen_at=now)
                .on_conflict_do_update(index_elements=[FeedSeen.user_id], set_={"seen_at": now})
            )
        return now

    async def unread(self, user: UUID) -> int:
        """What arrived since I last opened my feed — or, never opened, since I first followed something."""
        follows = await self.follows(user)
        if not follows:
            return 0
        since = await self.seen_at(user) or min(f.created_at for f in follows)
        return sum(1 for arrival in await self.arrivals(user, follows) if arrival.at > since)

    # --- telling members ------------------------------------------------------------------------------
    async def notify_due(self, notifier: Notifications) -> int:
        """Tell each member who follows something what arrived for them since they were last told (and that
        they have not read yet): one notice, grouped. Their preferences decide where it goes (« Mon fil »)."""
        now = utc_now(self.clock)
        async with self.database.session() as session:
            users = list((await session.execute(select(Follow.user_id).distinct())).scalars())
            rows = await session.execute(select(FeedNotified.user_id, FeedNotified.notified_at))
            told: dict[UUID, datetime] = {user_id: at for user_id, at in rows.all()}
        sent = 0
        for user in users:
            follows = await self.follows(user)
            if not follows:
                continue
            seen = await self.seen_at(user)
            since = max(
                d for d in (told.get(user), seen, min(f.created_at for f in follows)) if d is not None
            )
            fresh = [a for a in await self.arrivals(user, follows) if a.at > since]
            if fresh:
                shown = fresh[:8]  # issue 398: the arrivals by name in the e-mail, and why each is there
                async with self.database.session() as session:
                    rows = await session.execute(
                        select(MediaObject.id, MediaObject.title).where(
                            MediaObject.id.in_([a.object_id for a in shown])
                        )
                    )
                    titles: dict[UUID, str] = {row[0]: row[1] for row in rows.all()}
                title = titles.get(fresh[0].object_id)
                lines = "\n".join(
                    f"• {titles.get(a.object_id) or '?'}"
                    + (f" ({', '.join(a.units[:3])})" if a.units else "")
                    + (f" — {a.because[0][1]}" if a.because else "")
                    for a in shown
                )
                await notifier.send(
                    CommunicationRequest(
                        category=CATEGORY,
                        template_key="media:notify.feed",
                        audience=Users((user,)),
                        dedup_key=f"media.feed:{user}:{fresh[0].at.isoformat()}",
                        params={
                            "count": len(fresh),
                            "title": (title or "")[:200],
                            "list": lines[:1500],
                            "more": max(0, len(fresh) - len(shown)),
                        },
                        source="module",
                        subject_ref=f"feed:{user}",
                        required_permission="media.read",
                        action_url="/feed",
                    )
                )
                sent += 1
            async with self.database.unit_of_work() as uow:
                await uow.session.execute(
                    insert(FeedNotified)
                    .values(user_id=user, notified_at=now)
                    .on_conflict_do_update(index_elements=[FeedNotified.user_id], set_={"notified_at": now})
                )
        return sent
