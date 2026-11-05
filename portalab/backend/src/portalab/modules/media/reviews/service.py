"""Members' reviews (#355): what a member thought of a work they watched, read, listened to or played — a
rating from 1 to 5, a few words if they want. One review per member and work (an episode's goes to its
series); only a member the services saw on it may review it. The others' reviews are signed with their name
when they are known in the community, « Anonymous » otherwise (their progression kept to themselves). The
first review of a work tells the progression (``media.reviewed``), once per member and work."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Forbidden, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.core.visibility_port import OwnerOnlyVisibility, Redacted, VisibilityFilter
from portalab.modules.media.models import Activity, MediaObject, Review

EVENT = "media.reviewed"
REVIEWED = frozenset({"movie", "series", "book", "audiobook", "game"})
PROGRESSION = "progression"  # owned by gamification (013): « public » or « anonymous » in the community
MAX_COMMENT = 2000
PAGE = 50


@dataclass(frozen=True, slots=True)
class ReviewLine:
    author_id: UUID | None  # None: anonymous to the viewer
    author: str | None
    mine: bool
    rating: int
    comment: str | None
    at: datetime


@dataclass(frozen=True, slots=True)
class Reviews:
    object_id: UUID
    reviewable: bool  # a kind of work members review
    can_review: bool  # the viewer was seen on it (watched, read, listened to, played)
    count: int
    average: float | None
    mine: ReviewLine | None
    items: list[ReviewLine]


class ReviewService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        *,
        visibility: VisibilityFilter | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.visibility = visibility or OwnerOnlyVisibility()
        self.clock = clock

    async def _work(self, session: Any, object_id: UUID) -> MediaObject | None:
        """An episode's or a season's review goes to its series; a merged title's to the one it joined."""
        current = await session.get(MediaObject, object_id)
        for _ in range(4):
            if current is None:
                return None
            if current.status == "merged" and current.merged_into is not None:
                current = await session.get(MediaObject, current.merged_into)
            elif current.parent_id is not None:
                current = await session.get(MediaObject, current.parent_id)
            else:
                return current  # type: ignore[no-any-return]
        return current  # type: ignore[no-any-return]

    async def _seen(self, session: Any, user: UUID, work: UUID) -> bool:
        """Whether a service saw the member on this work (a play, a reading, a game session)."""
        found = await session.scalar(
            select(Activity.id)
            .where(Activity.user_id == user, or_(Activity.work_id == work, Activity.object_id == work))
            .limit(1)
        )
        return found is not None

    async def _named(self, viewer: Principal, author: UUID) -> bool:
        if author == (viewer.acting_for or viewer.user_id):
            return True
        result = await self.visibility.filter(viewer, author, PROGRESSION, None, True)
        return not isinstance(result, Redacted)

    async def _names(self, ids: set[UUID]) -> dict[UUID, str]:
        providers = self.capabilities.system_providers(DIRECTORY)
        if not providers:
            return {}
        directory = providers[0].provider
        out: dict[UUID, str] = {}
        for user in ids:
            summary = await directory.get_user_summary(user)
            if summary is not None and summary.display_name and summary.is_active:
                out[user] = summary.display_name
        return out

    async def view(self, viewer: Principal, object_id: UUID) -> Reviews:
        me = viewer.acting_for or viewer.user_id
        async with self.database.session() as session:
            work = await self._work(session, object_id)
            if work is None:
                return Reviews(object_id, False, False, 0, None, None, [])
            count, average = (
                await session.execute(
                    select(func.count(), func.avg(Review.rating)).where(Review.object_id == work.id)
                )
            ).one()
            rows = list(
                (
                    await session.execute(
                        select(Review)
                        .where(Review.object_id == work.id)
                        .order_by(Review.updated_at.desc())
                        .limit(PAGE)
                    )
                ).scalars()
            )
            own = await session.get(Review, (me, work.id)) if me else None
            seen = bool(me) and work.kind in REVIEWED and await self._seen(session, me, work.id)  # type: ignore[arg-type]
        named = {r.user_id for r in rows if await self._named(viewer, r.user_id)}
        names = await self._names(named)

        def line(row: Review) -> ReviewLine:
            known = row.user_id in names
            return ReviewLine(
                author_id=row.user_id if known else None,
                author=names.get(row.user_id),
                mine=row.user_id == me,
                rating=row.rating,
                comment=row.comment,
                at=row.updated_at,
            )

        return Reviews(
            object_id=work.id,
            reviewable=work.kind in REVIEWED,
            can_review=seen or own is not None,
            count=int(count),
            average=round(float(average), 2) if average is not None else None,
            mine=line(own) if own is not None else None,
            items=[line(r) for r in rows if r.user_id != me],
        )

    async def save(self, viewer: Principal, object_id: UUID, rating: int, comment: str | None) -> UUID:
        me = viewer.acting_for or viewer.user_id
        if me is None:
            raise Forbidden("Only a member reviews a title.")
        if not 1 <= rating <= 5:
            raise ValidationFailed("A rating goes from 1 to 5.", code="media.review_rating")
        text = (comment or "").strip()[:MAX_COMMENT] or None
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            work = await self._work(session, object_id)
            if work is None or work.kind not in REVIEWED:
                raise ValidationFailed("This title takes no review.", code="media.review_unavailable")
            first = await session.get(Review, (me, work.id)) is None
            if first and not await self._seen(session, me, work.id):
                raise Forbidden(
                    "Review what you watched, read, listened to or played.", code="media.review_unseen"
                )
            await session.execute(
                insert(Review)
                .values(
                    user_id=me, object_id=work.id, rating=rating, comment=text, created_at=now, updated_at=now
                )
                .on_conflict_do_update(
                    index_elements=["user_id", "object_id"],
                    set_={"rating": rating, "comment": text, "updated_at": now},
                )
            )
            if first:  # #355: the progression is told once per member and work
                await self.events.publish(
                    session,
                    EVENT,
                    {
                        "object": str(work.id),
                        "kind": work.kind,
                        "rating": rating,
                        "commented": text is not None,
                    },
                    occurred_at=now,
                    subject=SubjectRef("user", str(me)),
                    source="media",
                    dedup_key=f"{EVENT}:{work.id}:{me}",
                )
            return work.id

    async def remove(self, viewer: Principal, object_id: UUID) -> None:
        me = viewer.acting_for or viewer.user_id
        async with self.database.unit_of_work() as uow:
            work = await self._work(uow.session, object_id)
            if work is not None and me is not None:
                await uow.session.execute(
                    delete(Review).where(Review.user_id == me, Review.object_id == work.id)
                )
