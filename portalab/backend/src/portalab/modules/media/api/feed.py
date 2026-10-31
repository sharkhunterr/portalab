"""HTTP API of « Mon fil » (#299): what I follow (people, titles, genres — private, mine alone), what the
library brought me lately because of it, what is coming from the people I follow, and the moment I last
read it (what came since is unread)."""

import asyncio
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from portalab.core.errors import ValidationFailed
from portalab.core.time import utc_now
from portalab.modules.media.api.people import FilmCreditOut, _filmography
from portalab.modules.media.api.router import Module, Reader, _me
from portalab.modules.media.feed import Followed, FollowRefused, Kind
from portalab.modules.media.models import MediaObject
from portalab.modules.media.providers.insight_widgets import posters

router = APIRouter(prefix="/api/v1", tags=["media"])
UPCOMING_PEOPLE = 12  # the people whose coming titles are asked for (the most recently followed)
UPCOMING = 30


class FollowIn(BaseModel):
    kind: Kind
    ref: str = Field(min_length=1, max_length=200)


class FollowOut(BaseModel):
    kind: Kind
    ref: str
    label: str
    since: datetime


class FollowsOut(BaseModel):
    items: list[FollowOut]


class Because(BaseModel):
    kind: Kind
    label: str


class FeedItemOut(BaseModel):
    object_id: UUID
    kind: str
    title: str
    year: int | None = None
    image_id: UUID | None = None
    at: datetime
    unread: bool = False
    because: list[Because]
    units: list[str] = []  # a followed series' new episodes or seasons (« S02E05 »)


class FeedUpcomingOut(FilmCreditOut):
    person: str  # whom I follow it comes with


class FeedOut(BaseModel):
    items: list[FeedItemOut]
    upcoming: list[FeedUpcomingOut]
    seen_at: datetime | None = None  # when I last read it: what came after is unread
    follows: int = 0


def _out(followed: Followed) -> FollowOut:
    return FollowOut(kind=followed.kind, ref=followed.ref, label=followed.label, since=followed.created_at)


@router.get("/me/media/follows", response_model=FollowsOut)
async def my_follows(principal: Reader, module: Module) -> FollowsOut:
    """What I follow — the most recent first."""
    return FollowsOut(items=[_out(f) for f in await module.feed.follows(_me(principal))])


@router.put("/me/media/follows", response_model=FollowOut)
async def follow(principal: Reader, module: Module, body: FollowIn) -> FollowOut:
    """Follow a person (by the name the library credits them under), a title (its id) or a genre."""
    try:
        return _out(await module.feed.follow(_me(principal), body.kind, body.ref))
    except FollowRefused as exc:
        raise ValidationFailed(str(exc), code="media.follow_refused") from exc


@router.delete("/me/media/follows", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow(
    principal: Reader,
    module: Module,
    kind: Annotated[Kind, Query()],
    ref: Annotated[str, Query(min_length=1, max_length=200)],
) -> None:
    await module.feed.unfollow(_me(principal), kind, ref)


async def _upcoming(module: Module, people: list[str], language: str) -> list[FeedUpcomingOut]:
    """What is announced for the people I follow — this year's and later titles the library has not got."""
    this_year = utc_now().year

    async def of(name: str) -> list[FeedUpcomingOut]:
        page = await module.people.page(name)
        if page is None:
            return []
        profile = await module.profiles.profile(
            page.name,
            {"tmdb": page.ref} if page.ref else {},
            language,
            books=set(page.roles) <= {"author", "narrator"},
        )
        if profile is None or profile.record is None:
            return []
        return [
            FeedUpcomingOut(**credit.model_dump(), person=page.name)
            for credit in await _filmography(module, profile.record.credits)
            if credit.year is not None and credit.year >= this_year and credit.status != "available"
        ]

    found = await asyncio.gather(*(of(name) for name in people[:UPCOMING_PEOPLE]))
    seen: set[tuple[str, str]] = set()
    out = []
    for credit in sorted((c for batch in found for c in batch), key=lambda c: (c.year or 0, -c.votes)):
        if (credit.kind, credit.tmdb_id) not in seen:
            seen.add((credit.kind, credit.tmdb_id))
            out.append(credit)
    return out[:UPCOMING]


@router.get("/me/media/feed", response_model=FeedOut)
async def my_feed(principal: Reader, module: Module) -> FeedOut:
    """« Mon fil »: what the library brought lately for what I follow (each with why), what is coming from
    the people I follow, and when I last read it."""
    user = _me(principal)
    follows = await module.feed.follows(user)
    arrivals = await module.feed.arrivals(user, follows)
    seen_at = await module.feed.seen_at(user)
    since = seen_at or (min(f.created_at for f in follows) if follows else None)
    ids = [a.object_id for a in arrivals]
    rows: dict[UUID, MediaObject] = {}
    if ids:
        async with module.database.session() as session:
            found = await session.execute(select(MediaObject).where(MediaObject.id.in_(ids)))
            rows = {row.id: row for row in found.scalars()}
    images = await posters(module.database, ids)
    items = [
        FeedItemOut(
            object_id=a.object_id,
            kind=rows[a.object_id].kind,
            title=rows[a.object_id].title,
            year=rows[a.object_id].year,
            image_id=UUID(images[a.object_id]) if a.object_id in images else None,
            at=a.at,
            unread=since is not None and a.at > since,
            because=[Because(kind=kind, label=label) for kind, label in a.because],
            units=a.units,
        )
        for a in arrivals
        if a.object_id in rows
    ]
    people = [f.ref for f in follows if f.kind == "person"]
    upcoming = await _upcoming(module, people, await module.member_language(principal)) if people else []
    return FeedOut(items=items, upcoming=upcoming, seen_at=seen_at, follows=len(follows))


@router.post("/me/media/feed/seen", status_code=status.HTTP_204_NO_CONTENT)
async def feed_seen(principal: Reader, module: Module) -> None:
    """I read my feed: what came until now is no longer unread."""
    await module.feed.mark_seen(_me(principal))
