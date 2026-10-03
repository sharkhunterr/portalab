"""Grants (T030; R13, FR-016): an administrator grants a product without payment — ``origin=grant``,
optional expiry, audited, ``marketplace.grant``; activation as for a purchase. An expiry job ends expired
grants (``expired``, deactivated, ``marketplace.revocation`` with ground ``grant_expired``)."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.activation.service import LIVE, Activation
from portalab.modules.marketplace.models import Ownership, Product
from portalab.modules.marketplace.products.service import ProductNotFound
from portalab.modules.marketplace.purchase.service import AlreadyOwned


class Grants:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        activation: Activation,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.activation = activation
        self.clock = clock

    async def grant(
        self, actor: Principal, user: UUID, product_key: str, reason: str, expires_at: datetime | None = None
    ) -> Ownership:
        now = utc_now(self.clock)
        if expires_at is not None and expires_at <= now:
            raise ValidationFailed("A grant expires in the future.", code="marketplace.invalid_grant")
        async with self.database.unit_of_work() as uow:
            session = uow.session
            product = await session.scalar(select(Product).where(Product.key == product_key))
            if product is None or product.state == "draft":
                raise ProductNotFound("This product does not exist.")
            if not product.repeatable:
                owned = await session.scalar(
                    select(Ownership.id).where(
                        Ownership.user_id == user,
                        Ownership.product_id == product.id,
                        Ownership.state.in_(LIVE),
                    )
                )
                if owned is not None:
                    raise AlreadyOwned("This member already owns the product.")
            ownership = Ownership(
                user_id=user,
                product_id=product.id,
                origin="grant",
                repeatable=product.repeatable,
                product_version=product.current_version,
                price_paid=0,
                conditions_snapshot=[],
                idempotency_key=f"grant:{uuid4()}",
                state="activation_failed",
                configuration={},
                acquired_at=now,
                expires_at=expires_at,
            )
            session.add(ownership)
            await session.flush()
            await self.events.publish(
                session,
                "marketplace.grant",
                {"product": product.key, "ownership": str(ownership.id), "price": 0},
                occurred_at=now,
                actor=actor,
                subject=SubjectRef("user", str(user)),
                dedup_key=f"marketplace.grant:{ownership.id}",
            )
            await self.audit.record(
                session,
                AuditRecord(
                    action="marketplace.granted",
                    actor=actor,
                    resource=ResourceRef("ownership", str(ownership.id), owner_id=user),
                    decision="allow",
                    context={"product": product.key, "reason": reason[:200], "expires": bool(expires_at)},
                    sensitive=True,
                ),
            )
        return await self.activation.activate(ownership.id)
