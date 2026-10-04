"""Media API (contracts/media-contracts.md): catalog, detail sections, images, discovery, my playback,
history, continue, requests and account links; administration of identity (match candidates, merge, split,
overrides) and unlinked activity. Personal data is the caller's own; admin views carry metadata only."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.core.audit_port import AuditRecord
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, Forbidden, Unavailable, ValidationFailed
from portalab.core.time import utc_now
from portalab.modules.media.catalog import ObjectView
from portalab.modules.media.discovery.shelves import SHELVES
from portalab.modules.media.fields.resolver import ADMIN, FIELDS
from portalab.modules.media.identity.resolver import MediaNotFound
from portalab.modules.media.images.service import CONTENT_TYPE
from portalab.modules.media.models import (
    Activity,
    ActivityCursor,
    FieldCandidate,
    MatchCandidate,
    MediaObject,
    MediaRequest,
    ObjectMetadata,
    PlaybackSession,
)
from portalab.modules.media.module import MediaModule
from portalab.modules.media.permissions import MEDIA_MANAGE, MEDIA_READ, MEDIA_REQUEST, SELF
from portalab.modules.media.providers.insight_widgets import posters
from portalab.modules.media.sections.service import SECTIONS

router = APIRouter(prefix="/api/v1", tags=["media"])


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


def media_module(request: Request) -> MediaModule:
    module = getattr(request.app.state, "media_module", None)
    if not isinstance(module, MediaModule):
        raise Unavailable("Media is not available.", code="media.unavailable")
    return module


Module = Annotated[MediaModule, Depends(media_module)]
Reader = Annotated[Principal, require(MEDIA_READ)]
Requester = Annotated[Principal, require(MEDIA_REQUEST)]
User = Annotated[Principal, require(SELF)]
Manager = Annotated[Principal, require(MEDIA_MANAGE)]


def _me(principal: Principal) -> UUID:
    user = principal.acting_for or principal.user_id
    assert user is not None
    return user


# --- DTOs -------------------------------------------------------------------------------------------------
class MediaCard(BaseModel):
    id: UUID
    kind: str
    title: str
    year: int | None
    available: bool
    image_id: UUID | None = None


class MediaPage(BaseModel):
    items: list[MediaCard]
    next_cursor: str | None


class MediaDetail(MediaCard):
    status: str
    parent_id: UUID | None
    position: int | None
    overview: str | None
    genres: list[str]
    ids: dict[str, str]
    sections: list[str]


class MediaSectionOut(BaseModel):
    name: str
    state: str
    as_of: datetime
    data: dict[str, Any]


class MediaShelf(BaseModel):
    shelf: str
    items: list[MediaCard]
    next_action: str | None


class MediaNowPlayingOut(BaseModel):
    session: str
    object_id: UUID | None
    kind: str
    state: str
    position_s: float
    duration_s: float | None
    updated_at: datetime


class MediaHistoryOut(BaseModel):
    object_id: UUID
    kind: str
    title: str
    occurred_at: datetime
    completed: bool


class MediaContinueOut(BaseModel):
    object_id: UUID
    kind: str
    title: str
    percent: float
    resume_position_s: float
    last_occurred_at: datetime


class MediaRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object_id: UUID | None = None
    ids: dict[str, str] = Field(default_factory=dict)
    kind: str | None = Field(default=None, max_length=40)
    title: str | None = Field(default=None, max_length=500)
    service_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=120)


class MediaRequestOut(BaseModel):
    id: UUID
    object_id: UUID | None
    title: str
    kind: str
    state: str
    service_id: UUID
    requested_at: datetime
    updated_at: datetime


class MyMediaRequests(BaseModel):
    items: list[MediaRequestOut]
    quota: dict[str, Any]


class MediaLinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_id: UUID
    external_user_id: str = Field(min_length=1, max_length=200)


class MediaLinkVerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proof: str = Field(min_length=1, max_length=200)


class MediaLinkOut(BaseModel):
    id: UUID
    service_id: UUID
    external_user_id: str
    verified: bool
    created_at: datetime


class MediaMatchCandidateOut(BaseModel):
    id: UUID
    object_a: MediaCard
    object_b: MediaCard
    score: float
    evidence: dict[str, Any]
    state: str


class MediaMergeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    survivor: UUID
    other: UUID
    confirmation: str | None = None


class MediaSplitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    merge: UUID
    confirmation: str | None = None


class MediaOverridesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: dict[str, Any] = Field(default_factory=dict)  # value None removes the override


def _card(row: MediaObject, image: UUID | None = None) -> MediaCard:
    return MediaCard(
        id=row.id, kind=row.kind, title=row.title, year=row.year, available=row.available, image_id=image
    )


def _detail(view: ObjectView) -> MediaDetail:
    return MediaDetail(
        id=view.id,
        kind=view.kind,
        title=view.title,
        year=view.year,
        available=view.available,
        image_id=view.image_id,
        status=view.status,
        parent_id=view.parent_id,
        position=view.position,
        overview=view.effective.get("overview"),
        genres=[str(g) for g in view.effective.get("genres") or []],
        ids=view.ids,
        sections=list(SECTIONS),
    )


def _request(row: MediaRequest) -> MediaRequestOut:
    return MediaRequestOut(
        id=row.id,
        object_id=row.object_id,
        title=str(row.external_ref.get("title", "")),
        kind=str(row.external_ref.get("kind", "")),
        state=row.state,
        service_id=row.service_id,
        requested_at=row.requested_at,
        updated_at=row.updated_at,
    )


# --- catalog ---------------------------------------------------------------------------------------------
@router.get("/media", response_model=MediaPage)
async def browse(
    principal: Reader,
    module: Module,
    kind: Annotated[str | None, Query(max_length=40)] = None,
    genre: Annotated[str | None, Query(max_length=120)] = None,
    year: Annotated[int | None, Query(ge=1800, le=2200)] = None,
    availability: Literal["available", "unavailable"] | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
) -> MediaPage:
    rows, next_cursor = await module.catalog.browse(
        principal, kind=kind, genre=genre, year=year, availability=availability, q=q, cursor=cursor
    )
    return MediaPage(items=[_card(row, image) for row, image in rows], next_cursor=next_cursor)


@router.get("/media/discovery/{shelf}", response_model=MediaShelf)
async def discovery(principal: Reader, shelf: str, module: Module) -> MediaShelf:
    if shelf not in SHELVES:
        raise MediaNotFound("This shelf does not exist.")
    rows, next_action = await module.discovery.shelf(shelf, principal)
    async with module.database.session() as session:
        images = await module.catalog._images(session, [r.id for r in rows])
    return MediaShelf(shelf=shelf, items=[_card(r, images.get(r.id)) for r in rows], next_action=next_action)


@router.get("/media/images/{image_id}")
async def image(_: Reader, image_id: UUID, module: Module) -> Response:
    data = await module.images.content(image_id)
    return Response(
        content=data,
        media_type=CONTENT_TYPE,
        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/media/requests", response_model=MediaRequestOut, status_code=status.HTTP_201_CREATED)
async def create_request(principal: Requester, body: MediaRequestIn, module: Module) -> MediaRequestOut:
    ref = None if body.object_id else {"ids": body.ids, "kind": body.kind, "title": body.title}
    row = await module.requests.submit(
        _me(principal),
        object_id=body.object_id,
        ref=ref,
        service_id=body.service_id,
        idempotency_key=body.idempotency_key,
    )
    return _request(row)


@router.post("/media/requests/{request_id}/cancel", response_model=MediaRequestOut)
async def cancel_request(principal: Requester, request_id: UUID, module: Module) -> MediaRequestOut:
    return _request(await module.requests.cancel(_me(principal), request_id))


# --- 027: statistics, upcoming releases, enriched details -------------------------------------------------
INSIGHT_PERIOD = r"^(7d|30d|90d|365d|all|\d{4})$"
INSIGHT_CATEGORY = r"^(all|movies|series|live|music|books|audiobooks)$"
IMAGE_SIZE = r"^(w92|w154|w185|w300|w342|w500|w780|w1280|h632|original)$"


def _zone(tz: str) -> str:
    try:
        return ZoneInfo(tz).key
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationFailed("Unknown time zone.", code="media.invalid_time_zone") from exc


@router.get("/media/insights")
async def insights(
    principal: Reader,
    module: Module,
    period: Annotated[str, Query(pattern=INSIGHT_PERIOD)] = "30d",
    category: Annotated[str, Query(pattern=INSIGHT_CATEGORY)] = "all",
    scope: Literal["me", "all"] = "me",
    tz: Annotated[str, Query(max_length=64)] = "UTC",
) -> dict[str, Any]:
    """What was watched, listened to and read — mine, or the server's (anonymous unless media manager)."""
    manager = await module.authorizer.is_allowed(principal, MEDIA_MANAGE)
    data = await module.insights.overview(
        period=period,
        category=category,
        user=_me(principal) if scope == "me" else None,
        manager=manager,
        tz=_zone(tz),
    )
    if scope == "all" and manager and (data.get("members") or data.get("recent")):
        names = {str(m.id): m.display_name or m.login for m in await module.accounts.members()}
        for row in data.get("members") or []:
            row["name"] = names.get(row["user_id"]) if row["user_id"] else None
        for row in data.get("recent") or []:
            row["member"] = names.get(row["user_id"]) if row.get("user_id") else None
    works = [UUID(w["id"]) for w in data["top_works"] if w.get("id")]
    if data.get("box_office"):
        works += [UUID(f["id"]) for f in data["box_office"]["top"]]
    images = await posters(module.database, works)
    for work in [*data["top_works"], *((data.get("box_office") or {}).get("top") or [])]:
        work["image_id"] = images.get(UUID(work["id"])) if work.get("id") else None
    data["manager"] = manager
    return data


@router.get("/media/upcoming")
async def upcoming(
    _: Reader, module: Module, days: Annotated[int, Query(ge=1, le=120)] = 30
) -> dict[str, Any]:
    return {"items": await module.upcoming.list(days)}


@router.get("/media/metadata-images")
async def metadata_image(
    _: Reader,
    module: Module,
    ref: Annotated[str, Query(pattern=r"^/[A-Za-z0-9_-]{1,64}\.(jpg|jpeg|png|svg)$")],
    size: Annotated[str, Query(pattern=IMAGE_SIZE)] = "w500",
) -> Response:
    """A metadata provider image (backdrop, portrait…), served by the portal: browsers never call TMDB."""
    try:
        data = await module.enricher.image(ref, size)
    except LookupError as exc:
        raise MediaNotFound("No metadata provider is connected.") from exc
    except Exception as exc:
        raise Unavailable("The image cannot be fetched right now.", code="media.image_unavailable") from exc
    media_type = (
        "image/png" if ref.endswith(".png") else "image/svg+xml" if ref.endswith(".svg") else "image/jpeg"
    )
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=2592000, immutable",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
    )


@router.get("/media/{object_id}/metadata")
async def object_metadata(_: Reader, object_id: UUID, module: Module) -> dict[str, Any]:
    """Enriched details of a film or a series (backdrop, cast, saga, budget, revenue…), when known."""
    row = await module.enricher.details(object_id)
    if row is None:
        raise MediaNotFound("No enriched details for this title yet.")
    return {"provider": row.provider, "language": row.language, "fetched_at": row.fetched_at, **row.data}


@router.get("/media/{object_id}", response_model=MediaDetail)
async def detail(principal: Reader, object_id: UUID, module: Module) -> MediaDetail:
    return _detail(await module.catalog.get(principal, object_id))


@router.get("/media/{object_id}/sections/{name}", response_model=MediaSectionOut)
async def section(principal: Reader, object_id: UUID, name: str, module: Module) -> MediaSectionOut:
    if name not in SECTIONS:
        raise MediaNotFound("This section does not exist.")
    loaded = await module.sections.load(name, object_id, principal)
    return MediaSectionOut(name=name, state=loaded.state, as_of=loaded.as_of, data=loaded.data)


# --- me ----------------------------------------------------------------------------------------------------
@router.get("/me/media/now-playing", response_model=list[MediaNowPlayingOut])
async def now_playing(principal: User, module: Module) -> list[MediaNowPlayingOut]:
    rows = await module.poller.now_playing(_me(principal))
    return [
        MediaNowPlayingOut(
            session=r.session_key.split(":", 1)[-1][:64],
            object_id=r.object_id,
            kind=r.kind,
            state=r.state,
            position_s=r.position_s,
            duration_s=r.duration_s,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.get("/me/media/history", response_model=list[MediaHistoryOut])
async def my_history(
    principal: User,
    module: Module,
    before: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MediaHistoryOut]:
    rows = await module.history.history(_me(principal), limit=limit, before=before)
    return [
        MediaHistoryOut(
            object_id=o.id, kind=o.kind, title=o.title, occurred_at=h.occurred_at, completed=h.completed
        )
        for h, o in rows
    ]


@router.get("/me/media/continue", response_model=list[MediaContinueOut])
async def my_continue(principal: User, module: Module) -> list[MediaContinueOut]:
    rows = await module.history.continue_items(_me(principal))
    return [
        MediaContinueOut(
            object_id=o.id,
            kind=o.kind,
            title=o.title,
            percent=p.percent,
            resume_position_s=p.resume_position_s,
            last_occurred_at=p.last_occurred_at,
        )
        for p, o in rows
    ]


@router.get("/me/media/requests", response_model=MyMediaRequests)
async def my_requests(principal: Requester, module: Module) -> MyMediaRequests:
    user = _me(principal)
    rows = await module.requests.mine(user)
    return MyMediaRequests(items=[_request(r) for r in rows], quota=await module.quota.summary(user))


@router.get("/me/media/links", response_model=list[MediaLinkOut])
async def my_links(principal: User, module: Module) -> list[MediaLinkOut]:
    return [MediaLinkOut(**vars_of(v)) for v in await module.links.mine(_me(principal))]


@router.post("/me/media/links", response_model=MediaLinkOut, status_code=status.HTTP_201_CREATED)
async def add_link(principal: User, body: MediaLinkIn, module: Module) -> MediaLinkOut:
    view = await module.links.claim(_me(principal), body.service_id, body.external_user_id)
    return MediaLinkOut(**vars_of(view))


@router.post("/me/media/links/{link_id}/verify", response_model=MediaLinkOut)
async def verify_link(
    principal: User, link_id: UUID, body: MediaLinkVerifyIn, module: Module
) -> MediaLinkOut:
    return MediaLinkOut(**vars_of(await module.links.verify(_me(principal), link_id, body.proof)))


@router.delete("/me/media/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(principal: User, link_id: UUID, module: Module) -> Response:
    await module.links.remove(_me(principal), link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def vars_of(view: Any) -> dict[str, Any]:
    return {
        name: getattr(view, name)
        for name in ("id", "service_id", "external_user_id", "verified", "created_at")
    }


# --- administration --------------------------------------------------------------------------------------
async def _audit(
    module: MediaModule, principal: Principal, action: str, resource: str, context: dict[str, Any]
) -> None:
    async with module.database.unit_of_work() as uow:
        await module.audit.record(
            uow.session,
            AuditRecord(
                action=action,
                actor=principal,
                resource=ResourceRef("media", resource),
                decision="allow",
                result="success",
                context=context,
                sensitive=True,
            ),
        )


async def _confirm(
    module: MediaModule, principal: Principal, resource: str, payload: dict[str, Any], token: str | None
) -> None:
    providers = module.capabilities.system_providers(CONFIRMATIONS)
    if not providers:
        raise Unavailable("Confirmations are not available.", code="authz.unavailable")
    confirmations = providers[0].provider
    ref = ResourceRef("media", resource)
    if token is None:
        issued = await confirmations.issue(principal, MEDIA_MANAGE, ref, payload)
        raise ConfirmationRequired(
            "Merging or splitting changes the identity of catalog objects. Confirm to continue.",
            extensions={"confirmation": issued},
        )
    if not await confirmations.consume(token, principal, MEDIA_MANAGE, ref, payload):
        raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")


@router.get("/admin/media/match-candidates", response_model=list[MediaMatchCandidateOut])
async def match_candidates(_: Manager, module: Module) -> list[MediaMatchCandidateOut]:
    async with module.database.session() as session:
        rows = (
            (
                await session.execute(
                    select(MatchCandidate)
                    .where(MatchCandidate.state == "proposed")
                    .order_by(MatchCandidate.score.desc())
                    .limit(200)
                )
            )
            .scalars()
            .all()
        )
        objects = {
            o.id: o
            for o in (
                await session.execute(
                    select(MediaObject).where(
                        MediaObject.id.in_([r.object_a for r in rows] + [r.object_b for r in rows])
                    )
                )
            ).scalars()
        }
    return [
        MediaMatchCandidateOut(
            id=r.id,
            object_a=_card(objects[r.object_a]),
            object_b=_card(objects[r.object_b]),
            score=r.score,
            evidence=r.evidence,
            state=r.state,
        )
        for r in rows
        if r.object_a in objects and r.object_b in objects
    ]


@router.post("/admin/media/match-candidates/{candidate_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_candidate(principal: Manager, candidate_id: UUID, module: Module) -> Response:
    async with module.database.unit_of_work() as uow:
        row = await uow.session.get(MatchCandidate, candidate_id, with_for_update=True)
        if row is None or row.state != "proposed":
            raise MediaNotFound("This candidate does not exist.")
        row.state, row.decided_at = "rejected", utc_now(module.clock)
    await _audit(module, principal, "media.match_rejected", str(candidate_id), {})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/admin/media/merge")
async def merge(principal: Manager, body: MediaMergeIn, module: Module) -> dict[str, Any]:
    payload = {"survivor": str(body.survivor), "other": str(body.other)}
    await _confirm(module, principal, str(body.survivor), payload, body.confirmation)
    now = utc_now(module.clock)
    async with module.database.unit_of_work() as uow:
        entry = await module.identity.merge(uow.session, body.survivor, body.other, now)
        users = {
            r[0]
            for r in await uow.session.execute(
                select(PlaybackSession.user_id).where(PlaybackSession.object_id == body.survivor)
            )
            if r[0] is not None
        }
        await module.history.recompute(uow.session, users | await _history_users(uow.session, body.survivor))
        await module.writer.refresh(uow.session, body.survivor)
        await module.writer.publish(
            uow.session,
            "media.merged",
            {"object": str(body.survivor), "other": str(body.other)},
            f"media.merged:{entry.id}",
        )
        merge_id = entry.id
    await _audit(
        module,
        principal,
        "media.merged",
        str(body.survivor),
        {"other": str(body.other), "merge": str(merge_id)},
    )
    return {"merge": str(merge_id), "object": str(body.survivor)}


async def _history_users(session: Any, object_id: UUID) -> set[UUID]:
    from portalab.modules.media.models import HistoryEntry

    return {
        r[0]
        for r in await session.execute(
            select(HistoryEntry.user_id).where(HistoryEntry.object_id == object_id).distinct()
        )
    }


@router.post("/admin/media/split")
async def split(principal: Manager, body: MediaSplitIn, module: Module) -> dict[str, Any]:
    payload = {"merge": str(body.merge)}
    await _confirm(module, principal, str(body.merge), payload, body.confirmation)
    now = utc_now(module.clock)
    async with module.database.unit_of_work() as uow:
        entry = await module.identity.split(uow.session, body.merge, now)
        users = await _history_users(uow.session, entry.object_id) | await _history_users(
            uow.session, entry.other_id
        )
        await module.history.recompute(uow.session, users)
        for object_id in (entry.object_id, entry.other_id):
            await module.writer.refresh(uow.session, object_id)
        await module.writer.publish(
            uow.session,
            "media.split",
            {"object": str(entry.object_id), "other": str(entry.other_id)},
            f"media.split:{entry.id}",
        )
        restored = entry.other_id
    await _audit(module, principal, "media.split", str(body.merge), {"restored": str(restored)})
    return {"object": str(restored)}


@router.put("/admin/media/objects/{object_id}/overrides", response_model=MediaDetail)
async def overrides(
    principal: Manager, object_id: UUID, body: MediaOverridesIn, module: Module
) -> MediaDetail:
    unknown = set(body.fields) - set(FIELDS)
    if unknown:
        raise ValidationFailed("Unknown field.", code="media.invalid", extensions={"fields": sorted(unknown)})
    now = utc_now(module.clock)
    async with module.database.unit_of_work() as uow:
        if await uow.session.get(MediaObject, object_id) is None:
            raise MediaNotFound("This object does not exist.")
        for name, value in body.fields.items():
            if value is None:
                await uow.session.execute(
                    delete(FieldCandidate).where(
                        FieldCandidate.object_id == object_id,
                        FieldCandidate.field == name,
                        FieldCandidate.source_system == ADMIN,
                    )
                )
                continue
            values = {"value": value, "observed_at": now, "source_item_id": None}
            await uow.session.execute(
                insert(FieldCandidate)
                .values(object_id=object_id, field=name, source_system=ADMIN, **values)
                .on_conflict_do_update(index_elements=["object_id", "field", "source_system"], set_=values)
            )
        await module.writer.refresh(uow.session, object_id)
    await _audit(module, principal, "media.override_changed", str(object_id), {"fields": sorted(body.fields)})
    return _detail(await module.catalog.get(principal, object_id))


@router.get("/admin/media/unlinked-activity")
async def unlinked(_: Manager, module: Module) -> list[dict[str, Any]]:
    async with module.database.session() as session:
        rows = await session.execute(
            select(PlaybackSession.service_id, func.count(), func.max(PlaybackSession.updated_at))
            .where(PlaybackSession.user_id.is_(None))
            .group_by(PlaybackSession.service_id)
        )
        return [  # counts per service only: no account names, titles or devices
            {
                "service_id": str(service),
                "sessions": int(count),
                "last_at": last.isoformat() if last else None,
            }
            for service, count, last in rows
        ]


class AccountLinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_user_id: str = Field(min_length=1, max_length=200)
    user_id: UUID | None = None


class ApplySuggestionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_id: UUID | None = None


def _suggestion(value: tuple[UUID, str] | None) -> dict[str, str] | None:
    return {"user_id": str(value[0]), "reason": value[1]} if value else None


@router.get("/admin/media/accounts")
async def service_accounts(_: Manager, module: Module) -> dict[str, Any]:
    """027: every account of the connected services, its member (or a suggestion) — for the mapping screen."""
    blocks, members = await module.accounts.overview()
    return {
        "services": [
            {
                "service_id": b.service_id,
                "name": b.name,
                "connector": b.connector,
                "available": b.available,
                "accounts": [
                    {
                        "external_id": a.external_id,
                        "username": a.username,
                        "display_name": a.display_name,
                        "email": a.email,
                        "linked_user_id": str(a.linked_user_id) if a.linked_user_id else None,
                        "verified": a.verified,
                        "suggestion": (
                            {"user_id": str(a.suggestion[0]), "reason": a.suggestion[1]}
                            if a.suggestion
                            else None
                        ),
                        "unlinked_sessions": a.unlinked_sessions,
                    }
                    for a in b.accounts
                ],
            }
            for b in blocks
        ],
        "members": [
            {"id": str(m.id), "login": m.login, "display_name": m.display_name, "email": m.email}
            for m in members
        ],
    }


@router.put("/admin/media/accounts/{service_id}")
async def link_service_account(
    principal: Manager, service_id: UUID, body: AccountLinkIn, module: Module
) -> dict[str, Any]:
    attributed = await module.accounts.link(service_id, body.external_user_id, body.user_id)
    await _audit(
        module,
        principal,
        "media.account_linked" if body.user_id else "media.account_unlinked",
        str(service_id),
        {"attributed_sessions": attributed},
    )
    return {"linked": body.user_id is not None, "attributed_sessions": attributed}


@router.post("/admin/media/accounts/apply-suggestions")
async def apply_account_suggestions(
    principal: Manager, body: ApplySuggestionsIn, module: Module
) -> dict[str, int]:
    made = await module.accounts.apply_suggestions(body.service_id)
    await _audit(module, principal, "media.account_suggestions_applied", "accounts", {"linked": made})
    return {"linked": made}


@router.post("/admin/media/links/{link_id}/verify", response_model=MediaLinkOut)
async def admin_verify_link(principal: Manager, link_id: UUID, module: Module) -> MediaLinkOut:
    view = await module.links.verify(None, link_id, None)
    await _audit(module, principal, "media.link_verified", str(link_id), {})
    return MediaLinkOut(**vars_of(view))


@router.get("/admin/media/status")
async def admin_status(_: Manager, module: Module) -> dict[str, Any]:
    return await module.status()


@router.get("/admin/media/insights/sources")
async def insight_sources(_: Manager, module: Module) -> dict[str, Any]:
    """Where the history ingestion of each service stands (backfill, incremental, last error), and the
    metadata enrichment progress."""
    names = await module.accounts.service_names()
    async with module.database.session() as session:
        cursors = list((await session.execute(select(ActivityCursor))).scalars())
        per_service = await session.execute(
            select(Activity.service_id, func.count()).group_by(Activity.service_id)
        )
        counts: dict[UUID, int] = {service: int(n) for service, n in per_service.all()}
        per_status = await session.execute(
            select(ObjectMetadata.status, func.count()).group_by(ObjectMetadata.status)
        )
        metadata: dict[str, int] = {state: int(n) for state, n in per_status.all()}
        unattributed = await session.scalar(select(func.count()).where(Activity.user_id.is_(None)))
    return {
        "sources": [
            {
                "service_id": str(c.service_id),
                "name": names.get(str(c.service_id), str(c.service_id)),
                "source": c.source,
                "mode": c.mode,
                "items": int(counts.get(c.service_id, 0)),
                "watermark": c.watermark,
                "backfilled_at": c.backfilled_at,
                "last_run_at": c.last_run_at,
                "last_error": c.last_error,
            }
            for c in sorted(cursors, key=lambda c: names.get(str(c.service_id), ""))
        ],
        "metadata": {
            "provider": module.enricher.provider() is not None,
            "found": int(metadata.get("found", 0)),
            "missing": int(metadata.get("missing", 0)),
            "error": int(metadata.get("error", 0)),
        },
        "unattributed": int(unattributed or 0),
    }


@router.post("/admin/media/insights/sources/{service_id}/resync", status_code=status.HTTP_202_ACCEPTED)
async def resync_source(principal: Manager, service_id: UUID, module: Module) -> dict[str, str]:
    await module.ingestor.reset(service_id)
    await _audit(module, principal, "media.activity_resync", str(service_id), {})
    return {"state": "scheduled"}


@router.post("/admin/media/objects/{object_id}/metadata/refresh")
async def refresh_metadata(principal: Manager, object_id: UUID, module: Module) -> dict[str, Any]:
    result = await module.enricher.refresh(object_id)
    if result is None:
        raise MediaNotFound("No metadata provider, or this title cannot be enriched.")
    await _audit(module, principal, "media.metadata_refreshed", str(object_id), {"status": result})
    return {"status": result}
