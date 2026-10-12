"""Activation (T026; R10, FR-012/013): after an acquisition or grant commits, the product type's handler
activates the ownership — ``active``, ``needs_configuration`` until the owner configures it, or
``activation_failed`` (incompatible or failing). A failure never undoes the ownership and never affects
other products; failed activations are retried by a job every ``marketplace.activationRetryMinutes``."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.marketplace import OwnershipView, ProductTypeRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.models import Ownership, Product, ProductVersion
from portalab.modules.marketplace.observability import log, metrics

# what a member holds — ``locked`` (#81): won in a booster before they meet its level or Contribution
LIVE = ("active", "needs_configuration", "activation_failed", "locked")
# what a member may use (wear, see in their entitlements)
USABLE = ("active", "needs_configuration", "activation_failed")
MAX_ATTEMPTS = 10


class Activation:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        types: ProductTypeRegistry,
        config: Callable[[], Any],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.types = types
        self.config = config
        self.clock = clock

    async def view(self, ownership: Ownership) -> OwnershipView:
        async with self.database.session() as session:
            product = await session.get(Product, ownership.product_id)
            version = await session.get(ProductVersion, (ownership.product_id, ownership.product_version))
        assert product is not None and version is not None
        return OwnershipView(
            ownership.id,
            ownership.user_id,
            product.key,
            product.type,
            dict(version.payload),
            dict(ownership.configuration),
        )

    async def activate(self, ownership_id: UUID) -> Ownership:
        async with self.database.session() as session:
            ownership = await session.get(Ownership, ownership_id)
        if ownership is None:
            raise NotFound("This product is not owned.", code="marketplace.not_owned")
        if ownership.state not in USABLE:  # a locked one waits for its conditions (#81)
            return ownership
        view = await self.view(ownership)
        product_type = self.types.get(view.product_type)
        try:
            if product_type is None:
                raise RuntimeError("unknown product type")
            result = await product_type.handler.activate(view)
            state = {"active": "active", "needs_configuration": "needs_configuration"}.get(
                result.state, "activation_failed"
            )
            detail = result.detail or None
        except Exception as error:
            state, detail = "activation_failed", type(error).__name__
            log.warning("product activation failed", extra={"fields": {"type": view.product_type}})
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Ownership, ownership_id, with_for_update=True)
            assert row is not None
            if row.state not in USABLE:
                return row
            became_active = state == "active" and row.state != "active"
            row.state, row.activation_detail = state, (detail or None)
            row.activation_attempts += 1
            if became_active:
                await self.events.publish(
                    uow.session,
                    "marketplace.unlock",
                    {"product": view.product_key, "ownership": str(row.id), "price": row.price_paid},
                    occurred_at=utc_now(self.clock),
                    actor=Principal(user_id=row.user_id, channel="system"),
                    subject=SubjectRef("user", str(row.user_id)),
                    dedup_key=f"marketplace.unlock:{row.id}",
                )
        metrics.increment(f"marketplace.activation.{state}")
        return row

    async def deactivate(self, ownership: Ownership) -> None:
        view = await self.view(ownership)
        product_type = self.types.get(view.product_type)
        if product_type is None:
            return
        try:
            await product_type.handler.deactivate(view)
        except Exception:
            log.warning("product deactivation failed", extra={"fields": {"type": view.product_type}})

    async def configure(
        self, actor: Principal, ownership_id: UUID, configuration: dict[str, Any]
    ) -> Ownership:
        user = actor.acting_for or actor.user_id
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Ownership, ownership_id, with_for_update=True)
            if row is None or row.user_id != user:
                raise NotFound("This product is not owned.", code="marketplace.not_owned")
            if row.state not in ("needs_configuration", "activation_failed", "active"):
                raise Conflict("This product cannot be configured now.", code="marketplace.not_configurable")
            row.configuration = configuration
            if row.state == "needs_configuration":
                row.state = "activation_failed"  # re-run activation with the configuration
        return await self.activate(ownership_id)

    async def retry(self) -> int:
        """Retry failed activations (job); bounded attempts."""
        cutoff = utc_now(self.clock) - timedelta(minutes=max(1, self.config().activation_retry_minutes))
        async with self.database.session() as session:
            ids = list(
                (
                    await session.execute(
                        select(Ownership.id).where(
                            Ownership.state == "activation_failed",
                            Ownership.activation_attempts < MAX_ATTEMPTS,
                            Ownership.acquired_at <= cutoff,
                        )
                    )
                ).scalars()
            )
        for ownership_id in ids:
            await self.activate(ownership_id)
        return len(ids)
