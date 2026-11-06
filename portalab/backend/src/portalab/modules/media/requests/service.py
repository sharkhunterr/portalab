"""``RequestService`` (T026; R12, FR-021..023): requests go to a ``request.service`` provider after a quota
check, are mirrored with a normalized state machine, and follow the source of truth through sync records
(``RequestSink``). Idempotent per ``idempotency_key``; a failed submission gives the quota back; no paid
priority exists anywhere in the flow."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.media import (
    REQUESTS,
    RequestPayload,
    SourceDuplicate,
    SourceQuotaExceeded,
    SourceRefused,
    SourceUnavailable,
    unwrap,
)
from portalab.capabilities.media_core import WantedTitle
from portalab.capabilities.record_sink import ServiceRef, SinkResult
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, Unavailable, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.media.common import sort_title, strong_ids
from portalab.modules.media.identity.resolver import MediaNotFound, live_object
from portalab.modules.media.library_match import MediaLibraryMatch
from portalab.modules.media.links.service import UserLinkService
from portalab.modules.media.matching import fold
from portalab.modules.media.models import ExternalId, MediaObject, MediaRequest, UserLink
from portalab.modules.media.observability import metrics
from portalab.modules.media.requests.quota import QuotaExceeded, RequestQuota
from portalab.modules.media.requests.service_quota import ServiceQuotas, kind_of

CANCELLABLE = ("pending", "approved")


class RequestServiceUnavailable(Unavailable):
    default_code = "media.service_unavailable"
    default_title = "No request service is available"


class RequestDuplicate(Conflict):
    default_code = "media.request_duplicate"
    default_title = "Already requested"


class RequestRefused(Forbidden):
    default_code = "media.request_refused"
    default_title = "The request service refused this request"


class RequestInLibrary(Conflict):
    default_code = "media.request_in_library"
    default_title = "The library has this title"


# #378: the kinds of titles a request service takes when it does not tell (Seerr: films and series)
SCREEN_KINDS = ("movie", "series", "tv", "season")
CREATORS, DETAILS = 10, 12


OPEN_STATES = ("pending", "approved", "processing")
FACES = 50  # requests given a cover and a sheet per run (#379)
# #379: a book's, a game's cover and sheet, as a database knows it — (kind, title, creators, details)
Faces = Callable[[str, str, Sequence[str], Mapping[str, str]], Awaitable[dict[str, str] | None]]


class Requests:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        quota: RequestQuota,
        links: UserLinkService,
        *,
        clock: Clock | None = None,
        faces: Faces | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.quota = quota
        self.links = links
        self.clock = clock
        self.faces = faces
        self._faced: set[UUID] = set()  # looked for already (found or not) in this round
        # #3: the request service's own quotas (Seerr) — the truth for members whose account is linked
        self.service_quotas = ServiceQuotas(database, capabilities, clock=clock)

    @staticmethod
    def takes(provider: Any, kind: str) -> bool:
        """#378: whether a request service takes this kind of title — what it tells (``kinds()``), else a
        film or a series."""
        kinds = getattr(provider, "kinds", None)
        if callable(kinds):
            try:
                return kind in kinds()
            except Exception:
                return False
        return kind in SCREEN_KINDS

    def kinds(self) -> list[str]:
        """#378: every kind of title a request service takes."""
        out: list[str] = []
        for _, provider in self._providers():
            kinds = getattr(provider, "kinds", None)
            told = list(kinds()) if callable(kinds) else ["movie", "series"]
            out.extend(k for k in told if k not in out)
        return out

    def _providers(self) -> list[tuple[UUID, Any]]:
        try:
            registrations = self.capabilities.system_providers(REQUESTS)
        except Exception:
            return []
        out = []
        for registration in registrations:
            try:
                out.append((UUID(registration.instance_ref), registration.provider))
            except ValueError:
                continue
        return out

    async def publish(self, session: AsyncSession, row: MediaRequest, name: str) -> None:
        if row.requester_user_id is None:
            return
        await self.events.publish(
            session,
            name,
            {
                "request": str(row.id),
                "object": str(row.object_id) if row.object_id else None,
                "kind": str(row.external_ref.get("kind", "")),
                "state": row.state,
            },
            occurred_at=utc_now(self.clock),
            subject=SubjectRef("user", str(row.requester_user_id)),
            source="media",
            dedup_key=f"media.request:{row.id}:{row.state}:{name}",
        )

    async def _target(
        self, session: AsyncSession, object_id: UUID | None, ref: Mapping[str, Any] | None
    ) -> tuple[UUID | None, dict[str, Any]]:
        if object_id is not None:
            row = await live_object(session, object_id)
            if row is None or row.status != "active":
                raise MediaNotFound("This object does not exist.")
            ids = {
                scheme: value
                for scheme, value in await session.execute(
                    select(ExternalId.scheme, ExternalId.value).where(ExternalId.object_id == row.id)
                )
            }
            return row.id, {"ids": ids, "kind": row.kind, "title": row.title}
        ids = strong_ids((ref or {}).get("ids") or {})
        title = str((ref or {}).get("title") or "").strip()[:500]
        kind = str((ref or {}).get("kind") or "").strip()[:40]
        screen = kind in SCREEN_KINDS
        if (screen and not ids) or not title or not kind:
            raise ValidationFailed("Give the media's ids, kind and title.", code="media.invalid")
        found = await self.resolve(session, ids, kind, title) if screen else None
        return found, {"ids": ids, "kind": kind, "title": title}

    async def resolve(
        self, session: AsyncSession, ids: Mapping[str, str], kind: str, title: str | None = None
    ) -> UUID | None:
        return await catalog_title(session, ids, kind, title, utc_now(self.clock))

    async def submit(
        self,
        user: UUID,
        *,
        object_id: UUID | None,
        ref: Mapping[str, Any] | None,
        service_id: UUID | None,
        idempotency_key: str | None,
        seasons: Sequence[int] | None = None,
        is4k: bool = False,
        told: Mapping[str, Any] | None = None,
    ) -> MediaRequest:
        """``told`` (#378): what a member says of a book, a game… no catalog finds it by — ``creators``,
        ``year``, ``details`` (edition, language…), ``note``, and the ``cover`` and ``sheet`` of the
        database that knows it."""
        kind = await self._kind_of(object_id, ref)
        chosen = next(
            (
                (s, p)
                for s, p in self._providers()
                if (service_id is None or s == service_id) and self.takes(p, kind)
            ),
            None,
        )
        if chosen is None:
            raise RequestServiceUnavailable("No request service takes this kind of title.")
        extra = _told(told or {})
        if kind not in SCREEN_KINDS:  # #378: a book, a game… the library has: nothing to ask for
            await self._not_in_library(kind, ref or {}, extra)
            if not (extra.get("cover") and extra.get("sheet")):  # #379: asked without its sheet
                extra = {
                    **(await self._face(kind, str((ref or {}).get("title") or ""), extra) or {}),
                    **extra,
                }
        service, provider = chosen
        # #3: the service's own quota for a linked account (read before anything is written)
        service_quota = await self.service_quotas.check(user, service)
        key = f"{user}:{idempotency_key}"[:200] if idempotency_key else None
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            if key is not None:
                existing = (
                    await session.execute(select(MediaRequest).where(MediaRequest.idempotency_key == key))
                ).scalar_one_or_none()
                if existing is not None:
                    return existing
            target, external_ref = await self._target(session, object_id, ref)
            external_ref.update(extra)
            if external_ref["kind"] not in SCREEN_KINDS:
                await self._not_asked_again(session, external_ref)
            elif kind_of(external_ref["kind"]) == "movie":
                await self._not_asked_yet(session, external_ref)
            if seasons:
                external_ref["seasons"] = sorted({int(n) for n in seasons if int(n) > 0})
            if is4k:
                external_ref["is4k"] = True
            row = MediaRequest(
                object_id=target,
                external_ref=external_ref,
                requester_user_id=user,
                service_id=service,
                state="pending",
                source_state="",
                idempotency_key=key,
                counted="none",
                requested_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            window = None
            if service_quota is not None:
                window = getattr(service_quota, kind_of(external_ref["kind"]))
            row.counted = await self.quota.consume(session, user, str(row.id), window)
            request_id, counted = row.id, row.counted
        requester = await self._external_user(user, service)
        options: dict[str, Any] = {}
        if external_ref.get("seasons"):
            options["seasons"] = external_ref["seasons"]
        if is4k:
            options["is4k"] = True
        if counted == "extra" and service_quota is not None:
            options["bypass_quota"] = True  # #3: paid with a bought unit — not counted by the service
        options.update({k: v for k, v in extra.items() if k in ("creators", "year", "details", "note")})
        try:
            answer = unwrap(
                await asyncio.wait_for(
                    provider.submit(
                        external_ref["ids"], external_ref["kind"], external_ref["title"], requester, **options
                    ),
                    timeout=20,
                )
            )
        except (SourceQuotaExceeded, SourceDuplicate, SourceRefused) as exc:
            # refused by the service: the request never was — nothing is used, nothing stays
            async with self.database.unit_of_work() as uow:
                refused = await uow.session.get(MediaRequest, request_id, with_for_update=True)
                if refused is not None:
                    await self.quota.give_back(uow.session, user, str(refused.id), refused.counted)
                    await uow.session.delete(refused)
            self.service_quotas.forget(user)
            if isinstance(exc, SourceDuplicate):
                raise RequestDuplicate("This title is already requested.") from exc
            if isinstance(exc, SourceRefused):
                raise RequestRefused("The request service refused this request (4K, or this kind).") from exc
            raise QuotaExceeded("You have used your requests for this period.") from exc
        except (SourceUnavailable, TimeoutError, ConnectionError, OSError) as exc:
            metrics.increment("media.requests.failed")
            async with self.database.unit_of_work() as uow:
                failed = await uow.session.get(MediaRequest, request_id, with_for_update=True)
                assert failed is not None
                row = failed
                await self.quota.give_back(uow.session, user, str(row.id), row.counted)
                row.state, row.counted, row.source_state, row.updated_at = (
                    "failed",
                    "none",
                    "",
                    utc_now(self.clock),
                )
                await self.publish(uow.session, row, "media.request_created")
            raise RequestServiceUnavailable("The request service did not answer; nothing was used.") from exc
        async with self.database.unit_of_work() as uow:
            done = await uow.session.get(MediaRequest, request_id, with_for_update=True)
            assert done is not None
            row = done
            row.external_request_id = answer.external_request_id[:200]
            row.state, row.source_state = answer.state, answer.source_state[:60]
            row.updated_at = utc_now(self.clock)
            await self.publish(uow.session, row, "media.request_created")
            if row.state == "available":
                await self.publish(uow.session, row, "media.request_available")
        self.service_quotas.forget(user)
        return row

    async def _kind_of(self, object_id: UUID | None, ref: Mapping[str, Any] | None) -> str:
        if object_id is None:
            return str((ref or {}).get("kind") or "").strip()[:40]
        async with self.database.session() as session:
            row = await live_object(session, object_id)
            return row.kind if row is not None else ""

    async def _not_in_library(self, kind: str, ref: Mapping[str, Any], told: Mapping[str, Any]) -> None:
        """#378: a book, a game… the library has — by one of its identifiers, else its title by its
        creators — is not asked for: its page instead."""
        wanted = WantedTitle(
            "asked",
            kind,
            str(ref.get("title") or ""),
            tuple(told.get("creators") or ()),
            {scheme: [value] for scheme, value in strong_ids(ref.get("ids") or {}).items()},
        )
        found = (await MediaLibraryMatch(self.database).find([wanted])).get("asked")
        if found is not None:
            raise RequestInLibrary(
                "The library has it already.",
                extensions={"object_id": str(found.object_id), "route": f"/media/{found.object_id}"},
            )

    async def _face(self, kind: str, title: str, told: Mapping[str, Any]) -> dict[str, str] | None:
        """#379: the cover and sheet a database gives a book, a game… — nothing when none answers."""
        if self.faces is None or not title:
            return None
        try:
            return await self.faces(
                kind, title, list(told.get("creators") or ()), dict(told.get("details") or {})
            )
        except Exception:
            return None

    async def give_faces(self) -> int:
        """#379: the books, games… asked without a cover or a sheet (asked by hand, or before requests kept
        them) given those a database knows — each looked for once in turn, then all again."""
        if self.faces is None:
            return 0
        async with self.database.session() as session:
            rows = [
                (row.id, row.external_ref or {})
                for row in (
                    await session.execute(
                        select(MediaRequest)
                        .where(MediaRequest.external_ref["kind"].astext.not_in(SCREEN_KINDS))
                        .where(
                            or_(
                                ~MediaRequest.external_ref.has_key("cover"),
                                ~MediaRequest.external_ref.has_key("sheet"),
                            )
                        )
                        .order_by(MediaRequest.requested_at.desc())
                        .limit(FACES + len(self._faced))
                    )
                ).scalars()
                if row.id not in self._faced
            ][:FACES]
        if not rows:  # every one looked for: the next run looks again (a database may know them now)
            self._faced.clear()
        given = 0
        for request_id, ref in rows:
            self._faced.add(request_id)
            found = await self._face(str(ref.get("kind") or ""), str(ref.get("title") or ""), ref)
            if not found:
                continue
            async with self.database.unit_of_work() as uow:
                row = await uow.session.get(MediaRequest, request_id, with_for_update=True)
                if row is not None:
                    row.external_ref = {**found, **(row.external_ref or {})}
                    given += 1
        return given

    async def _not_asked_again(self, session: AsyncSession, external_ref: Mapping[str, Any]) -> None:
        """#378: a book, a game… someone asked for (still open) is not asked again — by one of its ids, else
        its title by one of its creators: follow that request."""
        wanted = set(strong_ids(external_ref.get("ids") or {}).items())
        title = fold(str(external_ref.get("title") or ""))
        creators = {fold(c) for c in external_ref.get("creators") or ()} - {""}
        rows = (
            await session.execute(select(MediaRequest).where(MediaRequest.state.in_(OPEN_STATES)).limit(2000))
        ).scalars()
        for row in rows:
            ref = row.external_ref or {}
            if ref.get("kind") != external_ref.get("kind"):
                continue
            theirs = {fold(c) for c in ref.get("creators") or ()} - {""}
            same_title = bool(title) and fold(str(ref.get("title") or "")) == title
            if wanted & set(strong_ids(ref.get("ids") or {}).items()) or (
                same_title and (not creators or not theirs or bool(creators & theirs))
            ):
                raise RequestDuplicate("This title is already requested.")

    async def _not_asked_yet(self, session: AsyncSession, external_ref: Mapping[str, Any]) -> None:
        """#4: a film someone already asked for (still open) is not asked again — follow that request."""
        wanted = set(strong_ids(external_ref.get("ids") or {}).items())
        if not wanted:
            return
        rows = (
            await session.execute(select(MediaRequest).where(MediaRequest.state.in_(OPEN_STATES)).limit(2000))
        ).scalars()
        for row in rows:
            ref = row.external_ref or {}
            if kind_of(str(ref.get("kind") or "")) != "movie":
                continue
            if wanted & set(strong_ids(ref.get("ids") or {}).items()):
                raise RequestDuplicate("This film is already requested.")

    async def _external_user(self, user: UUID, service: UUID) -> str | None:
        async with self.database.session() as session:
            return (
                await session.execute(
                    select(UserLink.external_user_id).where(
                        UserLink.user_id == user, UserLink.service_id == service, UserLink.verified.is_(True)
                    )
                )
            ).scalar_one_or_none()

    async def cancel(self, user: UUID, request_id: UUID) -> MediaRequest:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(MediaRequest, request_id, with_for_update=True)
            if row is None or row.requester_user_id != user:
                raise MediaNotFound("This request does not exist.")
            if row.state not in CANCELLABLE:
                raise ValidationFailed("This request can no longer be cancelled.", code="media.invalid")
            row.state, row.updated_at = "cancelled", utc_now(self.clock)
            await self.publish(uow.session, row, "media.request_updated")
            providers = dict(self._providers())
        cancel = getattr(providers.get(row.service_id), "cancel", None)
        if cancel is not None and row.external_request_id:
            try:
                await asyncio.wait_for(cancel(row.external_request_id), timeout=10)
            except Exception:
                metrics.increment("media.requests.cancel_not_propagated")
        return row

    async def mine(self, user: UUID, *, limit: int = 100) -> list[MediaRequest]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(MediaRequest)
                        .where(MediaRequest.requester_user_id == user)
                        .order_by(MediaRequest.requested_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )


class RequestSink:
    """``RecordSink`` for ``request.service`` sync records: the source is the truth for request state."""

    def __init__(self, requests: Requests) -> None:
        self.requests = requests

    async def upsert(self, records: Sequence[SourceRecord], service: ServiceRef) -> SinkResult:
        added = modified = ignored = errored = 0
        now = utc_now(self.requests.clock)
        async with self.requests.database.unit_of_work() as uow:
            session = uow.session
            for record in records:
                if record.removed:
                    ignored += 1
                    continue
                try:
                    payload = RequestPayload.model_validate(dict(record.payload))
                except ValidationError:
                    errored += 1
                    continue
                row = (
                    await session.execute(
                        select(MediaRequest)
                        .where(
                            MediaRequest.service_id == service.service_id,
                            MediaRequest.external_request_id == record.external_id,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if row is None:
                    requester = await self.requests.links.resolve(service.service_id, payload.requester)
                    target, ref = (
                        await self.requests._target(
                            session, None, {"ids": payload.ids, "kind": payload.kind, "title": payload.title}
                        )
                        if strong_ids(payload.ids)
                        else (None, {"ids": {}, "kind": payload.kind, "title": payload.title})
                    )
                    if payload.requester:  # kept so a later account link attributes the request (027)
                        ref = {**ref, "requester": payload.requester}
                    if payload.available_at:
                        ref = {**ref, "available_at": payload.available_at.isoformat()}
                    row = MediaRequest(
                        object_id=target,
                        external_ref=ref,
                        requester_user_id=requester,
                        service_id=service.service_id,
                        external_request_id=record.external_id[:200],
                        state=payload.state,
                        source_state=payload.source_state,
                        idempotency_key=None,
                        counted="none",
                        requested_at=record.observed_at,
                        updated_at=now,
                    )
                    session.add(row)
                    await session.flush()
                    await self.requests.publish(session, row, "media.request_created")
                    added += 1
                    continue
                if row.object_id is None and payload.object_id is not None:
                    row.object_id = payload.object_id  # #378: the library's book, game… the source found
                elif row.object_id is None and strong_ids(
                    payload.ids
                ):  # 027: the title arrived in the catalog later
                    row.object_id = await self.requests.resolve(
                        session, payload.ids, payload.kind, payload.title
                    )
                attributed = await self._attribution(row, payload.requester, service, payload.available_at)
                if row.state == payload.state and row.source_state == payload.source_state:
                    if attributed:  # who asked changed: no notification, nothing else moved
                        row.updated_at = now
                        modified += 1
                    else:
                        ignored += 1
                    continue
                became_available = payload.state == "available" and row.state != "available"
                if became_available and not (row.external_ref or {}).get("available_at"):
                    row.external_ref = {**(row.external_ref or {}), "available_at": now.isoformat()}
                row.state, row.source_state, row.updated_at = payload.state, payload.source_state, now
                await self.requests.publish(session, row, "media.request_updated")
                if became_available:
                    await self.requests.publish(session, row, "media.request_available")
                modified += 1
        return SinkResult(added=added, modified=modified, ignored=ignored, errored=errored)

    async def _attribution(
        self, row: MediaRequest, requester: str | None, service: ServiceRef, available_at: Any = None
    ) -> bool:
        """027: remember who asked on the service, and attribute the request once the account is linked."""
        changed = False
        if available_at and (row.external_ref or {}).get("available_at") is None:
            row.external_ref = {**(row.external_ref or {}), "available_at": available_at.isoformat()}
            changed = True
        if requester and (row.external_ref or {}).get("requester") != requester:
            row.external_ref = {**(row.external_ref or {}), "requester": requester}
            changed = True
        if requester and row.requester_user_id is None:
            member = await self.requests.links.resolve(service.service_id, requester)
            if member is not None:
                row.requester_user_id = member
                changed = True
        return changed

    async def deactivate(self, external_ids: Sequence[str], service: ServiceRef) -> int:
        return 0  # a request vanishing from the source keeps its last known state

    async def active_ids(self, service: ServiceRef) -> set[str]:
        async with self.requests.database.session() as session:
            rows = await session.execute(
                select(MediaRequest.external_request_id).where(
                    MediaRequest.service_id == service.service_id,
                    MediaRequest.external_request_id.is_not(None),
                )
            )
            return {str(r[0]) for r in rows}

    async def purge(self, service: ServiceRef) -> int:
        async with self.requests.database.unit_of_work() as uow:
            result = await uow.session.execute(
                delete(MediaRequest).where(MediaRequest.service_id == service.service_id)
            )
            return int(getattr(result, "rowcount", 0) or 0)


def _told(told: Mapping[str, Any]) -> dict[str, Any]:
    """#378: what a member said of a book, a game… — kept short; a cover and a sheet only as the portal's
    own addresses."""
    out: dict[str, Any] = {}
    creators = [str(c).strip()[:120] for c in told.get("creators") or () if str(c or "").strip()]
    if creators:
        out["creators"] = list(dict.fromkeys(creators))[:CREATORS]
    year = told.get("year")
    if isinstance(year, int) and 0 < year < 3000:
        out["year"] = year
    details = {
        str(k)[:32]: str(v).strip()[:120]
        for k, v in dict(told.get("details") or {}).items()
        if str(v or "").strip()
    }
    if details:
        out["details"] = dict(list(details.items())[:DETAILS])
    note = str(told.get("note") or "").strip()[:1000]
    if note:
        out["note"] = note
    cover, sheet = str(told.get("cover") or ""), str(told.get("sheet") or "")
    if cover.startswith("/api/v1/media/") and len(cover) <= 400:
        out["cover"] = cover
    if sheet.startswith("/media/") and len(sheet) <= 400:
        out["sheet"] = sheet
    return out


SERIES_KINDS = ("tv", "series", "season", "episode")


async def known_title(session: AsyncSession, ids: Mapping[str, str], kind: str) -> UUID | None:
    """The catalog title with one of these strong ids and the same kind (a film and a series may share a
    TMDB number) — ``None`` when the catalog has none; nothing is created."""
    wanted = ("series", "season") if kind in SERIES_KINDS else ("movie",)
    for scheme, value in strong_ids(ids).items():
        found = await session.scalar(
            select(ExternalId.object_id)
            .join(MediaObject, MediaObject.id == ExternalId.object_id)
            .where(
                ExternalId.scheme == scheme,
                ExternalId.value == value,
                MediaObject.kind.in_(wanted),
                MediaObject.status == "active",
            )
            .limit(1)
        )
        if found is not None:
            return found
    return None


async def catalog_title(
    session: AsyncSession, ids: Mapping[str, str], kind: str, title: str | None, now: datetime
) -> UUID | None:
    """The catalog title a request is about (027): same strong id **and** same kind of title — a film
    and a series may share a TMDB number. A film or series no library holds yet gets its own title, not
    available, so every request opens a page (the enriched details and the journey live there); the
    library's copy joins it later through the same id."""
    strong = strong_ids(ids)
    found = await known_title(session, strong, kind)
    if found is not None:
        return found
    name = (title or "").strip()[:500]
    if not strong or not name or kind not in ("movie", *SERIES_KINDS[:2]):
        return None
    owned = await session.scalar(
        select(ExternalId.object_id).where(
            or_(*(and_(ExternalId.scheme == s, ExternalId.value == v) for s, v in strong.items()))
        )
    )
    if owned is not None:  # the id belongs to another kind of title: never steal it
        return None
    row = MediaObject(
        kind="movie" if kind == "movie" else "series",
        title=name,
        sort_title=sort_title(name),
        available=False,
        effective={},
        field_provenance={},
        status="active",
        first_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    for scheme, value in strong.items():
        await session.execute(
            insert(ExternalId)
            .values(scheme=scheme, value=value, object_id=row.id)
            .on_conflict_do_nothing(index_elements=["scheme", "value"])
        )
    return row.id
