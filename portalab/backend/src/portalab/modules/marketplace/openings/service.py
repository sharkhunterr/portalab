"""#81: opening a booster, and the reserve it fills.

A booster is a product of type ``booster``. Opening one is **one unit of work**: its price spent through the
013 ledger — or a sealed one taken from the reserve (offered: a level reward, an achievement; or bought
earlier) —, the cards drawn, each look not owned yet granted (an ownership of origin ``booster``; ``locked``
while the member is below its level or Contribution, usable once they reach it), each item to keep added
to the reserve, the duplicates' Coins given back (a partial refund of that spend; credited when the booster
was offered) and the opening recorded with what came out of it. A replayed ``Idempotency-Key`` returns the
same opening. The new looks are activated after the commit, as a purchase.

Using an item of the reserve takes one out and grants the product, which activates as a purchase would
(a ticket — a film in 4K, a community project — then waits for its form, as in « My purchases »)."""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.economy import PERKS, InsufficientCoins
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.activation.service import LIVE, Activation
from portalab.modules.marketplace.availability.service import Availability
from portalab.modules.marketplace.boosters import (
    RARITIES,
    Booster,
    booster_of,
    draw,
    on_sale,
    refund_of,
)
from portalab.modules.marketplace.eligibility.service import Eligibility
from portalab.modules.marketplace.models import (
    BoosterOpening,
    Ownership,
    Product,
    ProductVersion,
    ReserveItem,
)
from portalab.modules.marketplace.observability import log, metrics
from portalab.modules.marketplace.products.service import Catalog, ProductNotFound
from portalab.modules.marketplace.purchase.service import NotAvailable, NotEnoughCoins
from portalab.modules.marketplace.resolution.service import Resolution


class OpeningLimit(Conflict):
    default_code = "marketplace.booster_limit"
    default_title = "No more openings"


class EmptyBooster(Conflict):
    default_code = "marketplace.booster_empty"
    default_title = "Nothing to draw"


class NothingInReserve(Conflict):
    default_code = "marketplace.reserve_empty"
    default_title = "Not in your reserve"


class OpenIt(Conflict):
    default_code = "marketplace.open_booster"
    default_title = "A booster is opened"


@dataclass(frozen=True, slots=True)
class Drawn:
    product: Product
    version: ProductVersion
    outcome: str  # new | duplicate | reserve
    refund: int
    locked: bool = False  # won before its level or Contribution is reached


def pool_keys(rows: list[tuple[Product, ProductVersion]], prefixes: tuple[str, ...]) -> set[str] | None:
    """The products the packs starting with ``prefixes`` hold (``None``: no such limit)."""
    if not prefixes:
        return None
    keys: set[str] = set()
    for product, version in rows:
        if product.type == "bundle" and product.key.startswith(prefixes):
            keys.update(str(k) for k in (version.payload or {}).get("products") or [])
    return keys


def spec(product: Product, version: ProductVersion) -> Booster:
    return booster_of(product.key, version.names, version.price_coins, version.payload or {})


class Openings:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        catalog: Catalog,
        availability: Availability,
        activation: Activation,
        resolution: Resolution,
        eligibility: Eligibility,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.catalog = catalog
        self.availability = availability
        self.activation = activation
        self.resolution = resolution
        self.eligibility = eligibility
        self.clock = clock

    def today(self) -> date:
        return utc_now(self.clock).date()

    def sold(self, product: Product, version: ProductVersion, today: date | None = None) -> bool:
        """Whether a booster product is on sale now (a season's in its weeks only)."""
        return on_sale(spec(product, version), today or self.today())

    async def boosters(self) -> list[tuple[Product, ProductVersion, Booster]]:
        """The boosters in the shop now."""
        today = self.today()
        rows = await self.catalog.listing(product_type="booster")
        return [(p, v, spec(p, v)) for p, v in rows if on_sale(spec(p, v), today)]

    async def _active(self, user: UUID) -> bool:
        providers = self.capabilities.system_providers(DIRECTORY)
        return bool(providers) and bool(await providers[0].provider.is_active_account(user))

    async def opened(self, user: UUID) -> dict[str, int]:
        """How many times the member bought and opened each booster (the offered ones not counted)."""
        async with self.database.session() as session:
            rows = await session.execute(
                select(BoosterOpening.booster_key, func.count())
                .where(BoosterOpening.user_id == user, BoosterOpening.price > 0)
                .group_by(BoosterOpening.booster_key)
            )
            return {key: int(count) for key, count in rows.all()}

    async def sealed(self, user: UUID) -> dict[str, int]:
        """The sealed boosters the member keeps (offered, or bought), per booster."""
        async with self.database.session() as session:
            rows = await session.execute(
                select(Product.key, ReserveItem.quantity)
                .join(ReserveItem, ReserveItem.product_id == Product.id)
                .where(ReserveItem.user_id == user, ReserveItem.quantity > 0, Product.type == "booster")
            )
            return {key: int(quantity) for key, quantity in rows.all()}

    async def history(self, user: UUID, limit: int = 20) -> list[BoosterOpening]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(BoosterOpening)
                .where(BoosterOpening.user_id == user)
                .order_by(BoosterOpening.opened_at.desc(), BoosterOpening.id.desc())
                .limit(max(1, min(limit, 100)))
            )
            return list(rows.scalars())

    async def _pool(self, booster: Booster, owned: set[UUID]) -> list[tuple[Product, ProductVersion]]:
        """What the booster may hold now: its types, priced, its season's or its packs' if it says so —
        and no limited look with no copy left (one the member owns stays: it comes out as a duplicate)."""
        rows = await self.catalog.listing()
        keys = pool_keys(rows, booster.packs)
        pool = [
            (product, version)
            for product, version in rows
            if product.type in booster.types
            and version.price_coins
            and (keys is None or product.key in keys)
            and (booster.season is None or product.season == booster.season)
        ]
        stock = await self.availability.stock(p for p, _ in pool)
        return [
            (product, version)
            for product, version in pool
            if product.id in owned or stock.get(product.id, (None, None))[1] != 0
        ]

    async def _eligible(self, user: UUID, version: ProductVersion) -> bool:
        if not version.conditions:
            return True
        try:
            checks = await self.eligibility.checks(user, list(version.conditions), None)
        except Exception:
            return False
        return all(check.met for check in checks)

    async def open(
        self, actor: Principal, key: str, request_key: str, *, sealed: bool = False
    ) -> tuple[BoosterOpening, list[Drawn]]:
        user = actor.acting_for or actor.user_id
        if user is None or not await self._active(user):
            raise Forbidden("Only active accounts can open boosters.", code="marketplace.not_active_account")
        idempotency = f"booster:{user}:{key}:{request_key}"[:200]
        replay = await self._replay(idempotency)
        if replay is not None:
            return replay
        async with self.database.session() as session:
            product = await session.scalar(
                select(Product).where(Product.key == key, Product.type == "booster")
            )
            version = (
                await session.get(ProductVersion, (product.id, product.current_version)) if product else None
            )
            owned = set(
                (
                    await session.execute(
                        select(Ownership.product_id).where(
                            Ownership.user_id == user,
                            Ownership.state.in_(LIVE),
                            Ownership.repeatable.is_(False),
                        )
                    )
                ).scalars()
            )
        if product is None or version is None:
            raise ProductNotFound("This booster does not exist.")
        booster = spec(product, version)
        # an offered one opens whenever; a bought one only while it is on sale
        if not sealed and (product.state != "available" or not on_sale(booster, self.today())):
            raise NotAvailable("This booster is not on sale now.")
        pool = await self._pool(booster, owned)
        if not pool:
            raise EmptyBooster("This booster has nothing to draw now.")
        picked = draw(booster, pool, lambda row: row[0].rarity, lambda row: row[0].key)
        drawn: list[Drawn] = []
        for item, item_version in picked:
            if item.repeatable:
                drawn.append(Drawn(item, item_version, "reserve", 0))
            elif item.id in owned:
                drawn.append(Drawn(item, item_version, "duplicate", refund_of(booster, item.rarity)))
            else:
                locked = not await self._eligible(user, item_version)
                drawn.append(Drawn(item, item_version, "new", 0, locked))
        refund = sum(card.refund for card in drawn)
        price = 0 if sealed else booster.price
        now = utc_now(self.clock)
        granted: list[UUID] = []
        try:
            async with self.database.unit_of_work() as uow:
                session = uow.session
                spend = None
                if sealed:
                    kept = await session.get(ReserveItem, (user, product.id), with_for_update=True)
                    if kept is None or kept.quantity <= 0:
                        raise NothingInReserve("You have no such booster to open.")
                    kept.quantity -= 1
                    kept.updated_at = now
                elif price:
                    try:
                        spend = await self.resolution.economy().spend(
                            user,
                            price,
                            reason=f"booster {booster.key}",
                            source_kind="marketplace",
                            source_ref=f"booster:{booster.key}",
                            idempotency_key=idempotency,
                            session=session,
                        )
                    except InsufficientCoins as error:
                        raise NotEnoughCoins("You do not have enough Coins.") from error
                    # the spend locked the member's ledger: openings counted now cannot race
                    if booster.per_member is not None:
                        count = await session.scalar(
                            select(func.count()).where(
                                BoosterOpening.user_id == user,
                                BoosterOpening.booster_key == booster.key,
                                BoosterOpening.price > 0,
                            )
                        )
                        if int(count or 0) >= booster.per_member:
                            raise OpeningLimit(
                                "You opened this booster as many times as one may.",
                                extensions={"limit": booster.per_member},
                            )
                opening = BoosterOpening(
                    user_id=user,
                    booster_key=booster.key,
                    price=price,
                    refund=refund,
                    spend_tx_ref=spend.id if spend is not None else None,
                    drawn=[
                        {
                            "product": card.product.key,
                            "rarity": card.product.rarity,
                            "outcome": card.outcome,
                            "refund": card.refund,
                            "locked": card.locked,
                        }
                        for card in drawn
                    ],
                    idempotency_key=idempotency,
                    opened_at=now,
                )
                session.add(opening)
                await session.flush()
                await self._opened(session, actor, user, booster.key, opening, drawn, now)
                for index, card in enumerate(drawn):
                    if card.outcome == "reserve":
                        await self._stock(session, user, card.product.id, 1)
                    elif card.outcome == "new":
                        ownership = await self._grant(
                            session,
                            actor,
                            user,
                            card.product,
                            card.version,
                            f"booster:{opening.id}:{index}",
                            locked=card.locked,
                        )
                        if not card.locked:
                            granted.append(ownership)
                if refund and spend is not None:
                    # the duplicates' Coins: a partial refund of this very spend
                    back = await self.resolution.economy().refund(
                        spend.id,
                        reason=f"booster {booster.key}: duplicates",
                        idempotency_key=f"booster-refund:{opening.id}",
                        session=session,
                        amount=refund,
                    )
                    opening.refund_tx_ref = back.id
        except IntegrityError:  # the same opening replayed concurrently
            replay = await self._replay(idempotency)
            if replay is None:
                raise
            return replay
        if refund and spend is None:
            await self._credit(user, refund, booster.key, str(opening.id))
        metrics.increment("marketplace.boosters_opened")
        for ownership_id in granted:
            await self.activation.activate(ownership_id)
        return opening, drawn

    async def _opened(
        self,
        session: AsyncSession,
        actor: Principal,
        user: UUID,
        booster: str,
        opening: BoosterOpening,
        drawn: list[Drawn],
        now: datetime,
    ) -> None:
        """#103: a booster opened — what it held (its rarest card, how many new) is the member's event."""
        rarities = [card.product.rarity for card in drawn if card.product.rarity in RARITIES]
        best = max(rarities, key=RARITIES.index, default="common")
        await self.events.publish(
            session,
            "marketplace.booster_opened",
            {
                "booster": booster,
                "opening": str(opening.id),
                "cards": len(drawn),
                "new": sum(1 for card in drawn if card.outcome == "new"),
                "best": best,
                "price": opening.price,
            },
            occurred_at=now,
            actor=actor,
            subject=SubjectRef("user", str(user)),
            dedup_key=f"marketplace.booster_opened:{opening.id}",
        )

    async def _credit(self, user: UUID, amount: int, booster: str, opening: str) -> None:
        """The duplicates' Coins of an offered booster (no spend to refund): credited by the economy."""
        providers = self.capabilities.system_providers(PERKS)
        if not providers:
            return
        try:
            await providers[0].provider.credit_coins(
                user, amount, f"booster:{booster}", f"booster-refund:{opening}"
            )
        except Exception:
            log.warning("booster duplicates not credited")

    async def _replay(self, idempotency: str) -> tuple[BoosterOpening, list[Drawn]] | None:
        async with self.database.session() as session:
            opening = await session.scalar(
                select(BoosterOpening).where(BoosterOpening.idempotency_key == idempotency)
            )
            if opening is None:
                return None
            keys = [str(card["product"]) for card in opening.drawn]
            rows = await session.execute(
                select(Product, ProductVersion)
                .join(
                    ProductVersion,
                    (ProductVersion.product_id == Product.id)
                    & (ProductVersion.version == Product.current_version),
                )
                .where(Product.key.in_(keys))
            )
            found = {product.key: (product, version) for product, version in rows.all()}
        drawn = [
            Drawn(
                *found[str(card["product"])],
                str(card["outcome"]),
                int(card.get("refund") or 0),
                bool(card.get("locked")),
            )
            for card in opening.drawn
            if str(card["product"]) in found
        ]
        return opening, drawn

    async def _stock(self, session: AsyncSession, user: UUID, product: UUID, delta: int) -> None:
        now = utc_now(self.clock)
        statement = insert(ReserveItem).values(
            user_id=user, product_id=product, quantity=delta, updated_at=now
        )
        statement = statement.on_conflict_do_update(
            index_elements=[ReserveItem.user_id, ReserveItem.product_id],
            set_={"quantity": ReserveItem.quantity + delta, "updated_at": now},
        )
        await session.execute(statement)

    async def seal(self, user: UUID, product_key: str, source: str) -> None:
        """A booster owned (bought, or offered by a level reward, an achievement): sealed in the reserve."""
        async with self.database.unit_of_work() as uow:
            product = await uow.session.scalar(select(Product.id).where(Product.key == product_key))
            if product is None:
                raise ProductNotFound("This booster does not exist.")
            await self._stock(uow.session, user, product, 1)
        log.info("booster sealed in the reserve", extra={"fields": {"source": source[:60]}})

    async def _grant(
        self,
        session: AsyncSession,
        actor: Principal,
        user: UUID,
        product: Product,
        version: ProductVersion,
        idempotency: str,
        *,
        locked: bool = False,
    ) -> UUID:
        now = utc_now(self.clock)
        ownership = Ownership(
            user_id=user,
            product_id=product.id,
            origin="booster",
            repeatable=product.repeatable,
            product_version=version.version,
            price_paid=0,
            conditions_snapshot=list(version.conditions),
            idempotency_key=idempotency,
            state="locked"
            if locked
            else "needs_configuration"
            if version.config_required
            else "activation_failed",
            configuration={},
            acquired_at=now,
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
        return ownership.id

    # --- what a booster gave early ---------------------------------------------------------------------
    async def unlock(self, user: UUID) -> int:
        """The member's locked items whose level and Contribution they now reach: usable from now on."""
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Ownership.id, ProductVersion)
                    .join(
                        ProductVersion,
                        (ProductVersion.product_id == Ownership.product_id)
                        & (ProductVersion.version == Ownership.product_version),
                    )
                    .where(Ownership.user_id == user, Ownership.state == "locked")
                )
            ).all()
        unlocked = 0
        for ownership_id, version in rows:
            if not await self._eligible(user, version):
                continue
            async with self.database.unit_of_work() as uow:
                row = await uow.session.get(Ownership, ownership_id, with_for_update=True)
                if row is None or row.state != "locked":
                    continue
                row.state = "needs_configuration" if version.config_required else "activation_failed"
            await self.activation.activate(ownership_id)
            unlocked += 1
        return unlocked

    async def unlock_all(self) -> int:
        async with self.database.session() as session:
            users = list(
                (
                    await session.execute(
                        select(Ownership.user_id).where(Ownership.state == "locked").distinct()
                    )
                ).scalars()
            )
        return sum([await self.unlock(user) for user in users])

    # --- the reserve ----------------------------------------------------------------------------------
    async def reserve(self, user: UUID) -> list[tuple[Product, ProductVersion, int]]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(Product, ProductVersion, ReserveItem.quantity)
                .join(ReserveItem, ReserveItem.product_id == Product.id)
                .join(
                    ProductVersion,
                    (ProductVersion.product_id == Product.id)
                    & (ProductVersion.version == Product.current_version),
                )
                .where(ReserveItem.user_id == user, ReserveItem.quantity > 0)
                .order_by(Product.key)
            )
            return [(product, version, int(quantity)) for product, version, quantity in rows.all()]

    async def use(self, actor: Principal, key: str, request_key: str) -> Ownership:
        """Take one item out of the reserve and grant it — it activates as a purchase would."""
        user = actor.acting_for or actor.user_id
        if user is None or not await self._active(user):
            raise Forbidden(
                "Only active accounts can use their reserve.", code="marketplace.not_active_account"
            )
        idempotency = f"reserve:{user}:{key}:{request_key}"[:200]
        async with self.database.session() as session:
            existing = await session.scalar(select(Ownership).where(Ownership.idempotency_key == idempotency))
        if existing is not None:
            return existing
        try:
            async with self.database.unit_of_work() as uow:
                session = uow.session
                product = await session.scalar(select(Product).where(Product.key == key))
                if product is None:
                    raise ProductNotFound("This product does not exist.")
                if product.type == "booster":
                    raise OpenIt("A booster in the reserve is opened, not used.")
                item = await session.get(ReserveItem, (user, product.id), with_for_update=True)
                if item is None or item.quantity <= 0:
                    raise NothingInReserve("You have none of these in your reserve.")
                version = await session.get(ProductVersion, (product.id, product.current_version))
                assert version is not None
                item.quantity -= 1
                item.updated_at = utc_now(self.clock)
                ownership_id = await self._grant(session, actor, user, product, version, idempotency)
                config_required = version.config_required
        except IntegrityError:
            async with self.database.session() as session:
                winner = await session.scalar(
                    select(Ownership).where(Ownership.idempotency_key == idempotency)
                )
            if winner is None:
                raise
            return winner
        metrics.increment("marketplace.reserve_used")
        if config_required:
            async with self.database.session() as session:
                row = await session.get(Ownership, ownership_id)
                assert row is not None
                return row
        return await self.activation.activate(ownership_id)
