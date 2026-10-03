"""Refunds (T028; R12, FR-015, CD-005): within the product version's policy (refundable, window, percent),
a refund is a **new ledger transaction** reversing the purchase (never an edit), recorded append-only;
the ownership becomes ``refunded`` and is deactivated. Non-refundable products — plugins, access, and
quota units already used — are refused with ``marketplace.not_refundable``. An administrator with
``marketplace.refund`` may refund outside the window (audited, confirmed by the API)."""

from datetime import timedelta
from uuid import UUID

from portalab.capabilities.marketplace import ProductTypeRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.activation.service import LIVE, Activation
from portalab.modules.marketplace.models import Ownership, Product, ProductVersion, Refund
from portalab.modules.marketplace.notify import notify_owner
from portalab.modules.marketplace.observability import metrics
from portalab.modules.marketplace.resolution.service import Resolution
from portalab.modules.marketplace.types.registry import QuotaHandler


class NotRefundable(Conflict):
    default_code = "marketplace.not_refundable"
    default_title = "Not refundable"


class Refunds:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        types: ProductTypeRegistry,
        activation: Activation,
        resolution: Resolution,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.capabilities = resolution.capabilities
        self.database = database
        self.events = events
        self.audit = audit
        self.types = types
        self.activation = activation
        self.resolution = resolution
        self.clock = clock

    async def refund(
        self,
        actor: Principal,
        ownership_id: UUID,
        reason: str,
        *,
        by_admin: bool = False,
        percent: int | None = None,
        ground: str | None = None,
    ) -> Ownership:
        user = actor.acting_for or actor.user_id
        now = utc_now(self.clock)
        async with self.database.session() as session:
            ownership = await session.get(Ownership, ownership_id)
            product = await session.get(Product, ownership.product_id) if ownership else None
            version = (
                await session.get(ProductVersion, (ownership.product_id, ownership.product_version))
                if ownership
                else None
            )
        if (
            ownership is None
            or product is None
            or version is None
            or (not by_admin and ownership.user_id != user)
        ):
            raise NotFound("This product is not owned.", code="marketplace.not_owned")
        if ownership.state not in LIVE:
            raise Conflict("This product was already settled.", code="marketplace.already_settled")
        policy = dict(version.refund_policy)
        if ownership.origin != "purchase" or ownership.price_paid <= 0 or ownership.purchase_tx_ref is None:
            raise NotRefundable("Only Coins purchases can be refunded.")
        if not by_admin:
            if not policy.get("refundable"):
                raise NotRefundable("This product is not refundable.")
            if now > ownership.acquired_at + timedelta(days=int(policy.get("window_days", 0))):
                raise NotRefundable("The refund window is over.")
        share = int(percent if percent is not None else policy.get("percent", 100 if by_admin else 0))
        if product.type == "quota":
            handler = self.types.get("quota")
            view = await self.activation.view(ownership)
            if (
                handler is None
                or not isinstance(handler.handler, QuotaHandler)
                or not await handler.handler.give_back(view)
            ):
                raise NotRefundable("Some of these units were already used.")
        amount = ownership.price_paid * max(0, min(share, 100)) // 100
        async with self.database.unit_of_work() as uow:
            session = uow.session
            row = await session.get(Ownership, ownership_id, with_for_update=True)
            assert row is not None
            if row.state not in LIVE:
                raise Conflict("This product was already settled.", code="marketplace.already_settled")
            transaction = None
            if amount > 0:
                transaction = await self.resolution.economy().refund(
                    row.purchase_tx_ref,
                    reason=reason[:200],
                    idempotency_key=f"marketplace-refund:{row.id}",
                    session=session,
                    amount=amount,
                )
            row.state = "revoked" if ground else "refunded"
            if ground:
                row.revoked_at, row.revoke_ground, row.revoke_reason = now, ground, reason[:500]
            session.add(
                Refund(
                    ownership_id=row.id,
                    refund_tx_ref=transaction.id if transaction is not None else None,
                    amount=amount,
                    percent=share,
                    reason=reason[:500],
                    actor_user_id=user,
                    created_at=now,
                )
            )
            await self.events.publish(
                session,
                "marketplace.refund",
                {"product": product.key, "ownership": str(row.id), "price": amount},
                occurred_at=now,
                actor=actor,
                subject=SubjectRef("user", str(row.user_id)),
                dedup_key=f"marketplace.refund:{row.id}",
            )
            await self.audit.record(
                session,
                AuditRecord(
                    action="marketplace.refunded",
                    actor=actor,
                    resource=ResourceRef("ownership", str(row.id), owner_id=row.user_id),
                    decision="allow",
                    context={
                        "product": product.key,
                        "amount": amount,
                        "percent": share,
                        "by_admin": by_admin,
                    },
                    sensitive=True,
                ),
            )
        if product.type != "quota":
            await self.activation.deactivate(row)
        metrics.increment("marketplace.refunds")
        if not ground:  # a revocation sends its own notice
            await notify_owner(self.capabilities, row.user_id, "refund", product.key, f"refund:{row.id}")
        return row
