"""Revocation (T030; R13, FR-017/018): an enumerated ground (``abuse``, ``grant_expired``, ``refund``,
``withdrawn_for_cause``) and a mandatory reason; access is removed without rewriting history, the member is
notified (``marketplace.revocation``), and a Coins purchase is refunded per its policy **unless** the ground
is ``abuse``. Audited."""

from typing import Literal
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.activation.service import LIVE, Activation
from portalab.modules.marketplace.models import Ownership, Product, ProductVersion
from portalab.modules.marketplace.observability import log
from portalab.modules.marketplace.refunds.service import Refunds

Ground = Literal["abuse", "grant_expired", "refund", "withdrawn_for_cause"]
GROUNDS = ("abuse", "grant_expired", "refund", "withdrawn_for_cause")


class Revocations:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        activation: Activation,
        refunds: Refunds,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.activation = activation
        self.refunds = refunds
        self.clock = clock

    async def revoke(self, actor: Principal, ownership_id: UUID, ground: str, reason: str) -> Ownership:
        if ground not in GROUNDS:
            raise ValidationFailed("Unknown revocation ground.", code="marketplace.invalid_ground")
        if not reason.strip():
            raise ValidationFailed("A revocation needs a reason.", code="marketplace.reason_required")
        async with self.database.session() as session:
            ownership = await session.get(Ownership, ownership_id)
            product = await session.get(Product, ownership.product_id) if ownership else None
            version = (
                await session.get(ProductVersion, (ownership.product_id, ownership.product_version))
                if ownership
                else None
            )
        if ownership is None or product is None or version is None:
            raise NotFound("This ownership does not exist.", code="marketplace.not_owned")
        if ownership.state not in LIVE:
            raise Conflict("This product was already settled.", code="marketplace.already_settled")
        paid = ownership.origin == "purchase" and ownership.price_paid > 0
        if paid and ground != "abuse":
            percent = int(dict(version.refund_policy).get("percent", 100)) if version.refund_policy else 100
            row = await self.refunds.refund(
                actor, ownership_id, reason, by_admin=True, percent=percent, ground=ground
            )
        else:
            row = await self._close(actor, ownership_id, product.key, ground, reason, "revoked")
        await self._notify(row, product.key, ground)
        return row

    async def _close(
        self, actor: Principal, ownership_id: UUID, product_key: str, ground: str, reason: str, state: str
    ) -> Ownership:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Ownership, ownership_id, with_for_update=True)
            assert row is not None
            row.state, row.revoked_at, row.revoke_ground, row.revoke_reason = state, now, ground, reason[:500]
            await self.events.publish(
                uow.session,
                "marketplace.revocation",
                {"product": product_key, "ownership": str(row.id), "price": 0},
                occurred_at=now,
                actor=actor,
                subject=SubjectRef("user", str(row.user_id)),
                dedup_key=f"marketplace.revocation:{row.id}",
            )
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="marketplace.revoked",
                    actor=actor,
                    resource=ResourceRef("ownership", str(row.id), owner_id=row.user_id),
                    decision="allow",
                    context={"product": product_key, "ground": ground},
                    sensitive=True,
                ),
            )
        await self.activation.deactivate(row)
        return row

    async def _notify(self, ownership: Ownership, product_key: str, ground: str) -> None:
        providers = self.capabilities.system_providers(NOTIFY)
        if not providers:
            return
        try:
            await providers[0].provider.send(
                CommunicationRequest(
                    category="marketplace.revocation",
                    template_key=f"marketplace:notify.revocation.{ground}",
                    audience=Users((ownership.user_id,)),
                    dedup_key=f"revocation:{ownership.id}",
                    params={"product": product_key},
                    subject_ref=f"ownership:{ownership.id}",
                    action_url="/marketplace/owned",
                )
            )
        except Exception:
            log.warning("revocation notification not sent")

    async def expire(self) -> int:
        now = utc_now(self.clock)
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(Ownership.id, Product.key)
                        .join(Product, Product.id == Ownership.product_id)
                        .where(
                            Ownership.expires_at.is_not(None),
                            Ownership.expires_at <= now,
                            Ownership.state.in_(LIVE),
                        )
                    )
                ).all()
            )
        system = Principal(channel="system")
        for ownership_id, key in rows:
            row = await self._close(
                system, ownership_id, key, "grant_expired", "The grant expired.", "expired"
            )
            await self._notify(row, key, "grant_expired")
        return len(rows)
