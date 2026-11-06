"""Issue 363: the requests — a member asks for a title the library lacks (refused when the library has it,
turned into a « me too » when another member asked for it already), the others say « me too » or take it
back, the administrators accept, refuse or close them; the library's new titles close those they answer,
each member who wanted one told."""

import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.economy import ECONOMY
from portalab.capabilities.i18n import normalize_for_search
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.media_core import LIBRARY_MATCH, LibraryTitle, WantedTitle
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, Unavailable, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.requests.events import CREATED, FULFILLED, SUPPORTED
from portalab.modules.requests.models import OPEN, Supporter, TitleRequest
from portalab.modules.requests.notify import RequestsNotifier
from portalab.modules.requests.settings import RequestsConfig

log = get_logger("portalab.requests")
_SEPARATORS = re.compile(r"[\W_]+")
LIMIT = 200
SWEEP = 500
# where a request may go from where it stands (« available » also by the library's own titles)
MOVES: Mapping[str, tuple[str, ...]] = {
    "new": ("accepted", "in_progress", "available", "refused"),
    "accepted": ("in_progress", "available", "refused"),
    "in_progress": ("available", "refused", "accepted"),
    "refused": ("new",),
    "available": (),
    "cancelled": (),
}


class RequestNotFound(NotFound):
    default_code = "requests.not_found"
    default_title = "No such request"


class KindClosed(ValidationFailed):
    default_code = "requests.kind_closed"
    default_title = "This kind of title cannot be asked for"


class InLibrary(Conflict):
    default_code = "requests.in_library"
    default_title = "The library has this title"


class AlreadyAsked(Conflict):
    default_code = "requests.already_asked"
    default_title = "Another member asked for this title"


class QuotaReached(Conflict):
    default_code = "requests.quota_reached"
    default_title = "No request of this kind left for now"


class NotNow(Conflict):
    default_code = "requests.not_now"
    default_title = "This request cannot change so"


def fold(text: str) -> str:
    """Lower case, no accents, every separator a single space: how two requests compare their titles."""
    return " ".join(_SEPARATORS.sub(" ", normalize_for_search(text or "")).split())[:300]


def _clean(values: Iterable[Any], *, size: int, count: int) -> list[str]:
    return list(dict.fromkeys(str(v).strip()[:size] for v in values if str(v or "").strip()))[:count]


def _ids(ids: Mapping[str, Sequence[Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for scheme, values in list(ids.items())[:20]:
        key = str(scheme).strip().lower()[:32]
        if key and (kept := _clean(values, size=200, count=10)):
            out[key] = kept
    return out


def _details(details: Mapping[str, Any]) -> dict[str, str]:
    return {str(k)[:32]: str(v).strip()[:120] for k, v in list(details.items())[:12] if str(v or "").strip()}


def _same_people(one: Sequence[str], other: Sequence[str]) -> bool:
    """No creator told on one side, or one in common."""
    mine, theirs = {fold(c) for c in one} - {""}, {fold(c) for c in other} - {""}
    return not mine or not theirs or bool(mine & theirs)


class Requests:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        config: Any,
        *,
        events: EventPublisher | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.config = config  # () -> RequestsConfig
        self.events = events
        self.clock = clock
        self.notify = RequestsNotifier(capabilities)

    def _now(self) -> datetime:
        return self.clock.now() if self.clock else utc_now()

    def _settings(self) -> RequestsConfig:
        config: RequestsConfig = self.config()
        return config

    def _library(self) -> Any:
        providers = self.capabilities.system_providers(LIBRARY_MATCH)
        return providers[0].provider if providers else None

    async def _in_library(self, wanted: Sequence[WantedTitle]) -> Mapping[str, LibraryTitle]:
        library = self._library()
        if library is None or not wanted:
            return {}
        try:
            found: Mapping[str, LibraryTitle] = await library.find(wanted)
            return found
        except Exception as exc:
            log.warning("library lookup failed", extra={"fields": {"error": type(exc).__name__}})
            return {}

    # --- a member ---------------------------------------------------------------------------------------
    async def options(self, user: UUID) -> dict[str, Any]:
        """The kinds open to requests, what a request costs, and how many a member has left of each."""
        config = self._settings()
        left: dict[str, int | None] = {}
        async with self.database.session() as session:
            for kind in config.kinds:
                quota = config.quota(kind)
                if not quota.limit:
                    left[kind] = None
                    continue
                used = await self._used(session, user, kind, quota.days)
                left[kind] = max(0, quota.limit - used)
        return {
            "kinds": list(config.kinds),
            "price": config.price,
            "left": left,
            "quotas": {k: config.quota(k).model_dump() for k in config.kinds},
        }

    async def _used(self, session: AsyncSession, user: UUID, kind: str, days: int) -> int:
        since = self._now() - timedelta(days=days)
        return int(
            await session.scalar(
                select(func.count())
                .select_from(Supporter)
                .join(TitleRequest, TitleRequest.id == Supporter.request_id)
                .where(
                    Supporter.user_id == user,
                    Supporter.asked.is_(True),
                    TitleRequest.kind == kind,
                    TitleRequest.created_at >= since,
                    TitleRequest.status != "cancelled",
                )
            )
            or 0
        )

    async def create(
        self,
        user: UUID,
        *,
        kind: str,
        title: str,
        creators: Sequence[str] = (),
        year: int | None = None,
        details: Mapping[str, Any] | None = None,
        ids: Mapping[str, Sequence[Any]] | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        config = self._settings()
        if kind not in config.kinds:
            raise KindClosed("Titles of this kind are not asked for here.")
        title = title.strip()[:300]
        folded = fold(title)
        if not folded:
            raise ValidationFailed("Tell the title.", code="requests.no_title")
        creators = _clean(creators, size=120, count=10)
        wanted_ids = _ids(ids or {})
        found = await self._in_library([WantedTitle("new", kind, title, creators, wanted_ids)])
        if "new" in found:
            there = found["new"]
            raise InLibrary(
                "The library has it already.",
                extensions={"object_id": str(there.object_id), "route": f"/media/{there.object_id}"},
            )
        now = self._now()
        async with self.database.unit_of_work() as uow:
            session = uow.session
            twin = await self._twin(session, kind, folded, creators)
            if twin is not None:
                raise AlreadyAsked(
                    "Another member asked for it: say « me too ».", extensions={"request_id": str(twin.id)}
                )
            quota = config.quota(kind)
            if quota.limit and await self._used(session, user, kind, quota.days) >= quota.limit:
                raise QuotaReached(
                    "You made all the requests of this kind you may for now.",
                    extensions={"limit": quota.limit, "days": quota.days},
                )
            row = TitleRequest(
                kind=kind,
                title=title,
                folded=folded,
                creators=creators,
                year=year,
                details=_details(details or {}),
                ids=wanted_ids,
                note=(note or "").strip()[:1000] or None,
                status="new",
                requester_id=user,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            if config.price:
                economy = self._economy()
                spent = await economy.spend(
                    user,
                    config.price,
                    reason="A request to the administrators",
                    source_kind="requests",
                    source_ref=f"request:{row.id}",
                    idempotency_key=f"request:{row.id}",
                    session=session,
                )
                row.spend_id = spent.id
            session.add(Supporter(request_id=row.id, user_id=user, asked=True, since=now))
            await self._publish(session, CREATED, user, row, {"request": str(row.id), "kind": kind})
        await self.notify.queue(row.id, kind, title)
        return await self.one(user, row.id)

    def _economy(self) -> Any:
        providers = self.capabilities.system_providers(ECONOMY)
        if not providers:
            raise Unavailable("Coins are not available.", code="requests.no_economy")
        return providers[0].provider

    async def _twin(
        self, session: AsyncSession, kind: str, folded: str, creators: Sequence[str]
    ) -> TitleRequest | None:
        rows = (
            await session.execute(
                select(TitleRequest).where(
                    TitleRequest.kind == kind, TitleRequest.folded == folded, TitleRequest.status.in_(OPEN)
                )
            )
        ).scalars()
        return next((row for row in rows if _same_people(row.creators, creators)), None)

    async def support(self, user: UUID, request_id: UUID) -> dict[str, Any]:
        """« Me too »: the member wants it as well (once)."""
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(TitleRequest, request_id, with_for_update=True)
            if row is None:
                raise RequestNotFound("No such request.")
            if row.status not in OPEN:
                raise NotNow("This request is closed.")
            if await uow.session.get(Supporter, (request_id, user)) is None:
                uow.session.add(
                    Supporter(request_id=request_id, user_id=user, asked=False, since=self._now())
                )
                row.updated_at = self._now()
                await self._publish(
                    uow.session, SUPPORTED, user, row, {"request": str(row.id), "kind": row.kind}
                )
        return await self.one(user, request_id)

    async def withdraw(self, user: UUID, request_id: UUID) -> dict[str, Any] | None:
        """The member no longer wants it. Who asked first hands it to the member who said « me too » first;
        the last one cancels it (its Coins given back while nobody took it in hand)."""
        refund: UUID | None = None
        async with self.database.unit_of_work() as uow:
            session = uow.session
            row = await session.get(TitleRequest, request_id, with_for_update=True)
            mine = await session.get(Supporter, (request_id, user))
            if row is None or mine is None:
                raise RequestNotFound("No such request.")
            if row.status not in OPEN:
                raise NotNow("This request is closed.")
            await session.delete(mine)
            await session.flush()
            row.updated_at = self._now()
            if row.requester_id == user:
                await self._hand_over(session, row)
                if row.status == "cancelled" and row.spend_id is not None:
                    refund, row.spend_id = row.spend_id, None
        if refund is not None:
            await self._refund(refund, "The request was cancelled")
        async with self.database.session() as session:
            return await self._view(session, user, request_id)

    async def _hand_over(self, session: AsyncSession, row: TitleRequest) -> None:
        heir = (
            await session.execute(
                select(Supporter)
                .where(Supporter.request_id == row.id)
                .order_by(Supporter.since, Supporter.user_id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if heir is None:
            row.status, row.requester_id = "cancelled", None
        else:
            row.requester_id = heir.user_id

    async def _refund(self, spend_id: UUID, reason: str) -> None:
        try:
            await self._economy().refund(spend_id, reason=reason, idempotency_key=f"refund:{spend_id}")
        except Exception as exc:
            log.warning("request refund failed", extra={"fields": {"error": type(exc).__name__}})

    async def one(self, user: UUID, request_id: UUID) -> dict[str, Any]:
        async with self.database.session() as session:
            view = await self._view(session, user, request_id)
        if view is None:
            raise RequestNotFound("No such request.")
        return view

    async def mine(self, user: UUID) -> list[dict[str, Any]]:
        """The requests I want — asked for or « me too » —, the open ones first, the latest first."""
        query = (
            select(TitleRequest)
            .join(Supporter, Supporter.request_id == TitleRequest.id)
            .where(Supporter.user_id == user)
            .order_by(TitleRequest.status.in_(OPEN).desc(), TitleRequest.updated_at.desc())
            .limit(LIMIT)
        )
        return await self._views(query, user)

    async def wanted(self, user: UUID, kind: str | None = None) -> list[dict[str, Any]]:
        """Every open request, the most wanted first: what I may say « me too » to."""
        query = select(TitleRequest).where(TitleRequest.status.in_(OPEN))
        if kind:
            query = query.where(TitleRequest.kind == kind)
        counted = (
            select(func.count())
            .select_from(Supporter)
            .where(Supporter.request_id == TitleRequest.id)
            .scalar_subquery()
        )
        return await self._views(query.order_by(counted.desc(), TitleRequest.created_at).limit(LIMIT), user)

    async def _views(
        self, query: Select[Any], user: UUID | None, *, names: bool = False
    ) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            rows = list((await session.execute(query)).scalars())
            supporters = await self._supporters(session, [row.id for row in rows])
        who = await self._names({s.user_id for group in supporters.values() for s in group}) if names else {}
        return [self._shape(row, supporters.get(row.id, []), user, who if names else None) for row in rows]

    async def _view(
        self, session: AsyncSession, user: UUID | None, request_id: UUID
    ) -> dict[str, Any] | None:
        row = await session.get(TitleRequest, request_id)
        if row is None:
            return None
        supporters = await self._supporters(session, [row.id])
        return self._shape(row, supporters.get(row.id, []), user, None)

    async def _supporters(self, session: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, list[Supporter]]:
        out: dict[UUID, list[Supporter]] = {}
        if not ids:
            return out
        for supporter in (
            await session.execute(
                select(Supporter).where(Supporter.request_id.in_(ids)).order_by(Supporter.since)
            )
        ).scalars():
            out.setdefault(supporter.request_id, []).append(supporter)
        return out

    async def _names(self, users: Iterable[UUID]) -> dict[UUID, str]:
        providers = self.capabilities.system_providers(DIRECTORY)
        out: dict[UUID, str] = {}
        for user in set(users):
            summary = await providers[0].provider.get_user_summary(user) if providers else None
            out[user] = (summary.display_name if summary else None) or "?"
        return out

    def _shape(
        self,
        row: TitleRequest,
        supporters: Sequence[Supporter],
        user: UUID | None,
        names: Mapping[UUID, str] | None,
    ) -> dict[str, Any]:
        mine = next((s for s in supporters if s.user_id == user), None)
        view: dict[str, Any] = {
            "id": str(row.id),
            "kind": row.kind,
            "title": row.title,
            "creators": list(row.creators),
            "year": row.year,
            "details": dict(row.details),
            "ids": {k: list(v) for k, v in row.ids.items()},
            "note": row.note,
            "status": row.status,
            "reason": row.reason,
            "supporters": len(supporters),
            "mine": mine is not None,
            "asked": row.requester_id is not None and row.requester_id == user,
            "route": f"/media/{row.object_id}" if row.object_id and row.status == "available" else None,
            "object_id": str(row.object_id) if row.object_id else None,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }
        if names is not None:  # the administrators: who wants it
            view["requester"] = names.get(row.requester_id) if row.requester_id else None
            view["wanted_by"] = [
                {"name": names.get(s.user_id, "?"), "asked": s.asked, "since": s.since.isoformat()}
                for s in supporters
            ]
        return view

    # --- the administrators -----------------------------------------------------------------------------
    async def queue(self, status: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
        """Every request (or those of a status, a kind), the open and most wanted first, with who wants it."""
        query = select(TitleRequest)
        if status:
            query = query.where(TitleRequest.status == status)
        if kind:
            query = query.where(TitleRequest.kind == kind)
        counted = (
            select(func.count())
            .select_from(Supporter)
            .where(Supporter.request_id == TitleRequest.id)
            .scalar_subquery()
        )
        query = query.order_by(
            TitleRequest.status.in_(OPEN).desc(), counted.desc(), TitleRequest.created_at
        ).limit(LIMIT)
        return await self._views(query, None, names=True)

    async def figures(self) -> dict[str, int]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(TitleRequest.status, func.count()).group_by(TitleRequest.status)
            )
            return {str(status): int(count) for status, count in rows}

    async def decide(
        self,
        actor: UUID,
        request_id: UUID,
        status: str,
        *,
        reason: str | None = None,
        object_id: UUID | None = None,
    ) -> dict[str, Any]:
        """An administrator moves a request on: accepted, in progress, refused (why), there (which title)."""
        there: LibraryTitle | None = None
        if status == "available":
            library = self._library()
            if object_id is None or library is None or (there := await library.get(object_id)) is None:
                raise ValidationFailed("Tell the library's title.", code="requests.no_title_there")
        reason = (reason or "").strip()[:500] or None
        if status == "refused" and not reason:
            raise ValidationFailed("Tell why it is refused.", code="requests.no_reason")
        refund: UUID | None = None
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(TitleRequest, request_id, with_for_update=True)
            if row is None:
                raise RequestNotFound("No such request.")
            if status != row.status and status not in MOVES.get(row.status, ()):
                raise NotNow(f"A request {row.status} cannot become {status}.")
            if status == row.status:
                return await self._admin_view(request_id)
            row.status, row.decided_by, row.updated_at = status, actor, self._now()
            row.reason = reason if status == "refused" else None
            if status == "refused" and row.spend_id is not None:
                refund, row.spend_id = row.spend_id, None
            if there is not None:
                await self._fulfil(uow.session, row, there)
            users = [s.user_id for s in (await self._supporters(uow.session, [row.id])).get(row.id, [])]
        if refund is not None:
            await self._refund(refund, "The request was refused")
        await self.notify.status(users, row, there)
        return await self._admin_view(request_id)

    async def _admin_view(self, request_id: UUID) -> dict[str, Any]:
        views = await self._views(select(TitleRequest).where(TitleRequest.id == request_id), None, names=True)
        if not views:
            raise RequestNotFound("No such request.")
        return views[0]

    async def _fulfil(self, session: AsyncSession, row: TitleRequest, there: LibraryTitle) -> None:
        row.status, row.object_id, row.reason = "available", there.object_id, None
        supporters = (await self._supporters(session, [row.id])).get(row.id, [])
        for supporter in supporters:
            await self._publish(
                session,
                FULFILLED,
                supporter.user_id,
                row,
                {
                    "request": str(row.id),
                    "kind": row.kind,
                    "asked": supporter.asked,
                    "supporters": len(supporters),
                },
            )

    async def sweep(self) -> int:
        """The open requests the library now answers (one of their identifiers, their title by their
        creators): closed, each member who wanted one told."""
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(TitleRequest)
                        .where(TitleRequest.status.in_(OPEN))
                        .order_by(TitleRequest.updated_at)
                        .limit(SWEEP)
                    )
                ).scalars()
            )
        found = await self._in_library(
            [WantedTitle(str(r.id), r.kind, r.title, tuple(r.creators), r.ids) for r in rows]
        )
        closed = 0
        for request_id, there in found.items():
            async with self.database.unit_of_work() as uow:
                row = await uow.session.get(TitleRequest, UUID(request_id), with_for_update=True)
                if row is None or row.status not in OPEN:
                    continue
                row.updated_at = self._now()
                await self._fulfil(uow.session, row, there)
                users = [s.user_id for s in (await self._supporters(uow.session, [row.id])).get(row.id, [])]
            await self.notify.status(users, row, there)
            closed += 1
        return closed

    async def _publish(
        self, session: AsyncSession, event: str, user: UUID, row: TitleRequest, payload: dict[str, Any]
    ) -> None:
        if self.events is None:
            return
        await self.events.publish(
            session,
            event,
            payload,
            occurred_at=self._now(),
            subject=SubjectRef("user", str(user)),
            source="requests",
            dedup_key=f"{event}:{row.id}:{user}",
        )

    # --- a member's data --------------------------------------------------------------------------------
    async def export(self, user: UUID) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(TitleRequest, Supporter.asked, Supporter.since)
                .join(Supporter, Supporter.request_id == TitleRequest.id)
                .where(Supporter.user_id == user)
                .order_by(Supporter.since)
            )
            return [
                {
                    "kind": row.kind,
                    "title": row.title,
                    "creators": list(row.creators),
                    "note": row.note if asked else None,
                    "asked": asked,
                    "status": row.status,
                    "since": since.isoformat(),
                }
                for row, asked, since in rows
            ]

    async def erase(self, user: UUID) -> None:
        """A member's « me too » gone; the requests they stood for handed over (or cancelled: no one left)."""
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await session.execute(delete(Supporter).where(Supporter.user_id == user))
            await session.flush()
            for row in (
                await session.execute(select(TitleRequest).where(TitleRequest.requester_id == user))
            ).scalars():
                row.note = None  # their own words go with them
                if row.status in OPEN:
                    await self._hand_over(session, row)
                    if row.status == "cancelled":
                        await session.delete(row)
                else:
                    row.requester_id = None
            for row in (
                await session.execute(select(TitleRequest).where(TitleRequest.decided_by == user))
            ).scalars():
                row.decided_by = None
