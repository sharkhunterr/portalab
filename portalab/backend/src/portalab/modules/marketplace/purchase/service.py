"""Acquisition (T024; R9, FR-006/010/011/013, CD-006): **one unit of work** — eligibility (strict AND,
named), ownership check (a permanent product once; ``repeatable`` opt-in), scarcity (027: copies left
and purchases per period, under the product row lock), the Coins spend through the 013
ledger in the same transaction, the ownership row with its snapshot (version, price paid, conditions) and
``marketplace.purchase``. A replayed ``Idempotency-Key`` returns the same ownership. Activation runs after
the commit and never undoes it."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from portalab.capabilities.economy import InsufficientCoins
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.activation.service import LIVE, Activation
from portalab.modules.marketplace.availability.service import Availability
from portalab.modules.marketplace.eligibility.service import Eligibility
from portalab.modules.marketplace.models import Category, Ownership, Product, ProductVersion
from portalab.modules.marketplace.notify import notify_owner
from portalab.modules.marketplace.observability import metrics
from portalab.modules.marketplace.pricing import active_discounts, price_now
from portalab.modules.marketplace.resolution.service import Resolution
from portalab.modules.marketplace.types.registry import offered


class ConditionsUnmet(Conflict):
    default_code = "marketplace.conditions_unmet"
    default_title = "Conditions not met"


class AlreadyOwned(Conflict):
    default_code = "marketplace.already_owned"
    default_title = "Already owned"


class NotAvailable(Conflict):
    default_code = "marketplace.not_available"
    default_title = "Not available"


class NotEnoughCoins(Conflict):
    default_code = "marketplace.insufficient_coins"
    default_title = "Not enough Coins"


class Purchases:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        eligibility: Eligibility,
        activation: Activation,
        resolution: Resolution,
        *,
        availability: Availability | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.eligibility = eligibility
        self.activation = activation
        self.resolution = resolution
        self.availability = availability
        self.clock = clock
        self.after_spend: Any = None  # test hook (fault injection between the spend and the ownership)

    async def _active(self, user: UUID) -> bool:
        providers = self.capabilities.system_providers(DIRECTORY)
        return bool(providers) and bool(await providers[0].provider.is_active_account(user))

    async def acquire(self, actor: Principal, key: str, request_key: str) -> Ownership:
        user = actor.acting_for or actor.user_id
        if user is None or not await self._active(user):
            raise Forbidden(
                "Only active accounts can acquire products.", code="marketplace.not_active_account"
            )
        idempotency = f"acquire:{user}:{key}:{request_key}"[:200]
        async with self.database.session() as session:
            existing = await session.scalar(select(Ownership).where(Ownership.idempotency_key == idempotency))
            product = await session.scalar(select(Product).where(Product.key == key))
            version = (
                await session.get(ProductVersion, (product.id, product.current_version)) if product else None
            )
            category = (
                await session.get(Category, product.category_id) if product and product.category_id else None
            )
        if existing is not None:
            return existing
        if product is None or version is None or product.state != "available":
            raise NotAvailable("This product cannot be acquired now.")
        if not offered(self.activation.types, product.type, version.payload or {}):
            raise NotAvailable("This product cannot be acquired now.")  # issue 173: not offered now
        # 027: the price now — less the best reduction of an active campaign
        discounts = await active_discounts(self.capabilities, utc_now(self.clock))
        reduced, _ = price_now(
            discounts, product.key, category.key if category else None, version.price_coins, product.season
        )
        checks = await self.eligibility.checks(user, list(version.conditions), None)
        unmet = [c for c in checks if not c.met]
        if unmet:
            raise ConditionsUnmet(
                "Some conditions are not met.",
                extensions={
                    "unmet": [c.label() for c in unmet],
                    "reasons": {c.label(): c.reason for c in unmet},
                },
            )
        price = int(reduced or 0)
        try:
            async with self.database.unit_of_work() as uow:
                session = uow.session
                if not product.repeatable:
                    owned = await session.scalar(
                        select(Ownership.id).where(
                            Ownership.user_id == user,
                            Ownership.product_id == product.id,
                            Ownership.state.in_(LIVE),
                        )
                    )
                    if owned is not None:
                        raise AlreadyOwned("You already own this product.")
                if self.availability is not None:  # 027: copies left, purchases left in the period
                    await self.availability.guard(session, user, product, version)
                transaction = None
                if price:
                    try:
                        transaction = await self.resolution.economy().spend(
                            user,
                            price,
                            reason=f"product {product.key}",
                            source_kind="marketplace",
                            source_ref=f"product:{product.key}",
                            idempotency_key=idempotency,
                            session=session,
                        )
                    except InsufficientCoins as error:
                        raise NotEnoughCoins("You do not have enough Coins.") from error
                if self.after_spend is not None:
                    await self.after_spend()
                ownership = Ownership(
                    user_id=user,
                    product_id=product.id,
                    origin="purchase",
                    repeatable=product.repeatable,
                    product_version=version.version,
                    price_paid=price,
                    conditions_snapshot=list(version.conditions),
                    purchase_tx_ref=transaction.id if transaction is not None else None,
                    idempotency_key=idempotency,
                    state="needs_configuration" if version.config_required else "activation_failed",
                    configuration={},
                    acquired_at=utc_now(self.clock),
                )
                session.add(ownership)
                await session.flush()
                await self.events.publish(
                    session,
                    "marketplace.purchase",
                    {"product": product.key, "ownership": str(ownership.id), "price": price},
                    occurred_at=utc_now(self.clock),
                    actor=actor,
                    subject=SubjectRef("user", str(user)),
                    dedup_key=f"marketplace.purchase:{ownership.id}",
                )
        except IntegrityError as error:  # a concurrent acquisition won the race
            async with self.database.session() as session:
                winner: Ownership | None = await session.scalar(
                    select(Ownership).where(Ownership.idempotency_key == idempotency)
                )
            if winner is not None:
                return winner
            raise AlreadyOwned("You already own this product.") from error
        metrics.increment("marketplace.purchases")
        await notify_owner(
            self.capabilities, user, "purchase", product.key, f"purchase:{ownership.id}", version.names
        )
        if not version.config_required:
            return await self.activation.activate(ownership.id)
        return ownership
