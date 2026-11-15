"""Issue 443 — a household's items follow its economy: in a common pot, what a profile is given is its
master's too (once, activated as its own; a community project never); dispatched, nothing is copied, and a
switch rebuilds the pot on the master or gives it back (the copies revoked, the reserve's taken back)."""

from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.core.authz_port import Principal
from portalab.modules.marketplace.models import Ownership, Product, ReserveItem
from tests.integration.marketplace.conftest import MkHarness, published

pytestmark = pytest.mark.integration


def households(app: FastAPI) -> Any:
    return app.state.household_module.service


async def _owned(mk: MkHarness, user: UUID) -> dict[str, str]:
    async with mk.ev.full.database.session() as session:
        rows = await session.execute(
            select(Ownership.idempotency_key, Ownership.state).where(Ownership.user_id == user)
        )
        return {key: state for key, state in rows.tuples().all()}


async def _reserve(mk: MkHarness, user: UUID, product: UUID) -> int:
    async with mk.ev.full.database.session() as session:
        row = await session.get(ReserveItem, (user, product))
        return row.quantity if row is not None else 0


async def test_a_common_pots_items_are_its_masters_too(mk: MkHarness, app: FastAPI) -> None:
    owner = mk.people["ursula"]
    master = Principal(user_id=owner)
    created = await households(app).create(master, display_name="Léa", kind="standard", color=None, pin=None)
    lea = UUID(str(created["id"]))
    await published(mk, "night_owl")
    await published(mk, "early_bird")

    await mk.module.grants.grant(mk.p("boss"), lea, "night_owl", "quest")
    lea_items, master_items = await _owned(mk, lea), await _owned(mk, owner)
    assert len(lea_items) == 1 and len(master_items) == 1
    ((copy_key, state),) = master_items.items()
    assert copy_key.startswith(f"household:{lea}:") and state == "active"  # activated as the master's own

    await households(app).set_economy(master, "dispatch")
    assert set((await _owned(mk, owner)).values()) == {"revoked"}  # given back
    await mk.module.grants.grant(mk.p("boss"), lea, "early_bird", "quest")
    assert len(await _owned(mk, lea)) == 2 and len(await _owned(mk, owner)) == 1  # its own only
    async with mk.ev.full.database.unit_of_work() as uow:
        product = await uow.session.scalar(select(Product.id).where(Product.key == "night_owl"))
        assert product is not None
        uow.session.add(ReserveItem(user_id=lea, product_id=product, quantity=2, updated_at=mk.clock.now()))

    await households(app).set_economy(master, "pot")
    owned = await _owned(mk, owner)
    assert sorted(owned.values()) == ["active", "active"]  # both items, the first one back again
    assert await _reserve(mk, owner, product) == 2  # its reserve too

    await households(app).set_economy(master, "dispatch")
    assert set((await _owned(mk, owner)).values()) == {"revoked"}
    assert await _reserve(mk, owner, product) == 0 and await _reserve(mk, lea, product) == 2


async def test_a_levels_product_is_offered_once(mk: MkHarness) -> None:
    """A level's product (a repeatable booster) is offered once, however many later levels are reached —
    every level-up looks at the tiers below it again."""
    from dataclasses import replace

    from tests.integration.marketplace.conftest import product_def

    await mk.module.catalog.create(mk.p("boss"), {**product_def("fox"), "repeatable": True})
    await mk.module.catalog.move(mk.p("boss"), "fox", "available")
    ulrich = mk.people["ulrich"]
    mk.economy.config = replace(mk.economy.config, level_rewards=[{"level": 2, "product": "fox"}])
    for level in (2, 3, 4):
        await mk.economy.level_rewards.give(ulrich, level, mk.clock.now())
    assert len(await _owned(mk, ulrich)) == 1
