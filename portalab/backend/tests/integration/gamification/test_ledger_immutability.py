"""013 T004 — the ledger is append-only (UPDATE/DELETE/TRUNCATE rejected by triggers), idempotency keys are
unique, reversals reference existing transactions, balances never go negative and only the three values
exist (no conversion kind)."""

import pytest
from sqlalchemy import text

from tests.integration.gamification.conftest import RULE, GamHarness

pytestmark = pytest.mark.integration


async def test_immutability_and_constraints(gm: GamHarness) -> None:
    await gm.rule("listen", RULE)
    user = gm.people["ursula"]
    await gm.emit(user)
    for statement in (
        "UPDATE gamification.transactions SET delta = 1000",
        "DELETE FROM gamification.transactions",
        "TRUNCATE gamification.transactions",
    ):
        async with gm.database.session() as session:
            with pytest.raises(Exception, match=r"append-only|cannot truncate"):
                await session.execute(text(statement))
    async with gm.database.session() as session:
        row = (
            (await session.execute(text("SELECT * FROM gamification.transactions LIMIT 1"))).mappings().one()
        )
    insert = (
        "INSERT INTO gamification.transactions (id, user_id, value, delta, kind, source_kind, "
        "idempotency_key, "
        "base_amount, multiplier, modifiers, guards, occurred_at, recorded_at, "
        "reverses_transaction_id) VALUES "
        "(gen_random_uuid(), :u, :value, 1, :kind, 'system', :key, 0, 1, '{}', '{}', now(), now(), :rev)"
    )
    cases = [
        ({"value": "xp", "kind": "grant", "key": row["idempotency_key"], "rev": None}, "idempotency_key"),
        ({"value": "gold", "kind": "grant", "key": "k1", "rev": None}, "ck_transactions_value"),
        ({"value": "xp", "kind": "conversion", "key": "k2", "rev": None}, "ck_transactions_kind"),
        (
            {"value": "xp", "kind": "grant", "key": "k3", "rev": "00000000-0000-7000-8000-000000000000"},
            "reverses",
        ),
    ]
    for params, match in cases:
        async with gm.database.session() as session:
            with pytest.raises(Exception, match=match):
                await session.execute(text(insert), {"u": user, **params})
    async with gm.database.session() as session:
        with pytest.raises(Exception, match="amount_non_negative"):
            await session.execute(
                text("UPDATE gamification.balances SET amount = -1 WHERE user_id = :u"), {"u": user}
            )
