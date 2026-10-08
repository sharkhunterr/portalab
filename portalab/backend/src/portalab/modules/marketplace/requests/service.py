"""Requests to handle (027): some purchases are not delivered by the portal on its own — a special request
(a film in 4K, with the member's wishes: Dolby Atmos, languages…) or access to a service. Buying one opens
a request the administrators handle by a deadline set on the product (``deadline_days``): they start it,
mark it done — for a service, after approving the account (Portalab offers to create it in the identity
provider) — or decline it, which gives the Coins back. The member follows it on « My purchases » and is
notified at each step."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.marketplace import OwnershipView
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.models import MarketRequest, Product, ProductVersion
from portalab.modules.marketplace.notify import product_name
from portalab.modules.marketplace.observability import log

Kind = Literal["special", "service"]
Action = Literal["start", "done", "decline"]
OPEN = ("pending", "in_progress")
DEFAULT_DEADLINE_DAYS = 7
FIELD_TYPES = ("text", "textarea", "choice", "multi", "boolean")

# what a service approval does, once the administrator agrees: (user, details, create account) → outcome
Provision = Callable[[UUID, Mapping[str, Any], bool], Awaitable[str]]
Unprovision = Callable[[UUID, Mapping[str, Any]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class RequestView:
    id: UUID
    kind: str
    state: str
    product_key: str
    product_name: str
    user_id: UUID
    user_name: str | None
    details: dict[str, Any]
    form: list[dict[str, Any]]
    due_at: datetime
    overdue: bool
    note: str | None
    decided_at: datetime | None
    created_at: datetime


def form_of(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The fields a special request asks for (``payload.form``), each ``{key, type, labels, options,
    required}`` — anything malformed is left out."""
    out: list[dict[str, Any]] = []
    for raw in payload.get("form") or []:
        if not isinstance(raw, Mapping):
            continue
        key, kind = str(raw.get("key") or ""), str(raw.get("type") or "text")
        if not key.isidentifier() or kind not in FIELD_TYPES:
            continue
        out.append(
            {
                "key": key,
                "type": kind,
                "labels": {str(k): str(v) for k, v in dict(raw.get("labels") or {}).items()},
                "options": [str(o) for o in raw.get("options") or []][:30],
                "required": bool(raw.get("required")),
            }
        )
    return out[:20]


def answers(form: Sequence[Mapping[str, Any]], configuration: Mapping[str, Any]) -> dict[str, Any]:
    """The member's answers kept to the form's fields; a required one left empty is refused."""
    kept: dict[str, Any] = {}
    for field in form:
        value = configuration.get(field["key"])
        if field["type"] == "boolean":
            value = bool(value)
        elif field["type"] == "multi":
            value = [str(v)[:200] for v in value or [] if str(v) in field["options"] or not field["options"]]
        elif field["type"] == "choice":
            value = str(value or "")[:200]
            if field["options"] and value and value not in field["options"]:
                value = ""
        else:
            value = str(value or "").strip()[: 2000 if field["type"] == "textarea" else 300]
        if field["required"] and value in ("", [], None):
            raise ValidationFailed(
                f"« {field['key']} » is required.", code="marketplace.request_field_required"
            )
        kept[field["key"]] = value
    return kept


class Requests:
    def __init__(
        self, database: Database, capabilities: CapabilityRegistry, *, clock: Clock | None = None
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self.refund: Callable[[Principal, UUID, str], Awaitable[Any]] | None = None
        self.provision: Provision | None = None
        self.unprovision: Unprovision | None = None

    def _port(self, name: str) -> Any | None:
        providers = self.capabilities.system_providers(name)
        return providers[0].provider if providers else None

    async def open(self, ownership: OwnershipView, kind: Kind, details: Mapping[str, Any]) -> None:
        """Open the request of a purchase (once: activation may run again)."""
        now = utc_now(self.clock)
        days = int(ownership.payload.get("deadline_days") or DEFAULT_DEADLINE_DAYS)
        async with self.database.unit_of_work() as uow:
            found = await uow.session.scalar(
                select(MarketRequest).where(MarketRequest.ownership_id == ownership.id)
            )
            if found is not None:
                return
            product = await uow.session.scalar(select(Product).where(Product.key == ownership.product_key))
            assert product is not None
            uow.session.add(
                MarketRequest(
                    ownership_id=ownership.id,
                    user_id=ownership.user_id,
                    product_id=product.id,
                    kind=kind,
                    details=dict(details),
                    state="pending",
                    due_at=now + timedelta(days=max(1, min(days, 365))),
                    created_at=now,
                    updated_at=now,
                )
            )

    async def _views(self, rows: Sequence[MarketRequest], viewer: UUID | None) -> list[RequestView]:
        now = utc_now(self.clock)
        directory = self._port(DIRECTORY)
        out: list[RequestView] = []
        async with self.database.session() as session:
            for row in rows:
                product = await session.get(Product, row.product_id)
                version = (
                    await session.get(ProductVersion, (product.id, product.current_version))
                    if product is not None
                    else None
                )
                payload = dict(version.payload) if version is not None else {}
                name = (
                    await product_name(
                        self.capabilities, viewer or row.user_id, product.key, dict(version.names)
                    )
                    if product is not None and version is not None
                    else ""
                )
                user_name = None
                if directory is not None:
                    try:
                        summary = await directory.get_user_summary(row.user_id)
                        user_name = summary.display_name if summary else None
                    except Exception:
                        user_name = None
                out.append(
                    RequestView(
                        id=row.id,
                        kind=row.kind,
                        state=row.state,
                        product_key=product.key if product else "",
                        product_name=name,
                        user_id=row.user_id,
                        user_name=user_name,
                        details=dict(row.details),
                        form=form_of(payload),
                        due_at=row.due_at,
                        overdue=row.state in OPEN and row.due_at < now,
                        note=row.note,
                        decided_at=row.decided_at,
                        created_at=row.created_at,
                    )
                )
        return out

    async def mine(self, user: UUID) -> list[RequestView]:
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(MarketRequest)
                        .where(MarketRequest.user_id == user)
                        .order_by(MarketRequest.created_at.desc())
                        .limit(100)
                    )
                ).scalars()
            )
        return await self._views(rows, user)

    async def queue(self, viewer: UUID | None, *, open_only: bool = True) -> list[RequestView]:
        """For the administrators: the open requests, the most urgent first (or the last ones settled)."""
        async with self.database.session() as session:
            query = select(MarketRequest)
            if open_only:
                query = query.where(MarketRequest.state.in_(OPEN)).order_by(MarketRequest.due_at)
            else:
                query = query.where(MarketRequest.state.not_in(OPEN)).order_by(
                    MarketRequest.decided_at.desc()
                )
            rows = list((await session.execute(query.limit(200))).scalars())
        return await self._views(rows, viewer)

    async def open_count(self) -> tuple[int, int]:
        """(open, overdue) — for the administrators' attention."""
        now = utc_now(self.clock)
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(select(MarketRequest.due_at).where(MarketRequest.state.in_(OPEN)))
                ).scalars()
            )
        return len(rows), sum(1 for due in rows if due < now)

    async def decide(
        self, actor: Principal, request_id: UUID, action: Action, note: str | None, create_account: bool
    ) -> RequestView:
        note = (note or "").strip()[:1000] or None
        async with self.database.session() as session:
            row = await session.get(MarketRequest, request_id)
        if row is None:
            raise NotFound("This request does not exist.", code="marketplace.request_not_found")
        if row.state not in OPEN:
            raise Conflict("This request was already settled.", code="marketplace.request_settled")
        if action == "decline" and not note:
            raise ValidationFailed("Say why it is declined.", code="marketplace.reason_required")
        outcome: str | None = None
        if action == "done" and row.kind == "service" and self.provision is not None:
            # the account first: if it cannot be created, the request stays open with the reason
            outcome = await self.provision(row.user_id, dict(row.details), create_account)
        if action == "decline" and self.refund is not None:
            await self.refund(actor, row.ownership_id, note or "declined")
        now = utc_now(self.clock)
        state = {"start": "in_progress", "done": "done", "decline": "declined"}[action]
        async with self.database.unit_of_work() as uow:
            locked = await uow.session.get(MarketRequest, request_id, with_for_update=True)
            assert locked is not None
            locked.state, locked.updated_at = state, now
            if outcome:
                locked.details = {**dict(locked.details), "outcome": outcome[:300]}
            if note is not None:
                locked.note = note
            if action != "start":
                locked.decided_by, locked.decided_at = actor.user_id, now
        (view,) = await self._views([locked], None)
        await self._notify(view, state)
        return view

    async def _notify(self, view: RequestView, state: str) -> None:
        notify = self._port(NOTIFY)
        if notify is None:
            return
        try:
            await notify.send(
                CommunicationRequest(
                    category="marketplace.request",
                    template_key=f"marketplace:notify.request.{state}",
                    audience=Users((view.user_id,)),
                    dedup_key=f"request:{view.id}:{state}",
                    params={"product": view.product_name[:120], "note": (view.note or "")[:300]},
                    subject_ref=f"request:{view.id}",
                    action_url="/marketplace/owned",
                )
            )
        except Exception:
            log.warning("request notification not sent")

    async def send_account_link(self, user: UUID, link: str) -> None:
        """027: a new account in the identity provider — the member sets their password from this link."""
        notify = self._port(NOTIFY)
        if notify is None:
            return
        try:
            await notify.send(
                CommunicationRequest(
                    category="marketplace.request",
                    template_key="marketplace:notify.request.account",
                    audience=Users((user,)),
                    dedup_key=f"request-account:{user}:{link[-16:]}",
                    params={"link": link[:400]},  # outside: in the text; the button stays in-portal
                    subject_ref=f"user:{user}",
                    action_url="/marketplace/owned",
                )
            )
        except Exception:
            log.warning("account link not sent")

    async def close_for(self, ownership: OwnershipView) -> None:
        """A revoked or refunded purchase: its open request is closed and a granted access withdrawn."""
        async with self.database.unit_of_work() as uow:
            row = await uow.session.scalar(
                select(MarketRequest).where(MarketRequest.ownership_id == ownership.id).with_for_update()
            )
            if row is None:
                return
            was_done = row.state == "done"
            if row.state in OPEN:
                row.state, row.updated_at = "declined", utc_now(self.clock)
            details = dict(row.details)
        if was_done and ownership.product_type == "service_access" and self.unprovision is not None:
            try:
                await self.unprovision(ownership.user_id, details)
            except Exception:
                log.warning("service access not withdrawn")
