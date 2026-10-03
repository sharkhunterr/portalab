"""013 T027 — final deletion records ``destruction`` for the remaining Coins (balance → 0), purges balances,
counters and progress, keeps ledger rows bound to the user id without free text, is idempotent, offers no
refund or transfer, and the export lists the user's own transactions."""

import pytest
from sqlalchemy import text

from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from tests.integration.gamification.conftest import RULE, GamHarness

pytestmark = pytest.mark.integration


async def test_final_deletion(gm: GamHarness) -> None:
    await gm.rule("listen", RULE)
    user, other = gm.people["ursula"], gm.people["ulrich"]
    await gm.emit(user)
    await gm.emit(other)
    capabilities = gm.ev.full.identity.capabilities
    exporter = next(
        p.provider
        for p in capabilities.system_providers(EXPORT_CAPABILITY)
        if p.instance_ref == "gamification"
    )
    exported = await exporter.export(user)
    assert {r.category for r in exported} == {"gamification.transaction"} and len(exported) == 2
    eraser = next(
        p.provider
        for p in capabilities.system_providers(ERASURE_CAPABILITY)
        if p.instance_ref == "gamification"
    )
    await eraser.erase(user, "final")
    await eraser.erase(user, "final")
    async with gm.database.session() as session:
        kinds = (
            await session.execute(
                text(
                    "SELECT kind, value, delta, reason FROM gamification.transactions "
                    "WHERE user_id = :u ORDER BY seq"
                ),
                {"u": user},
            )
        ).all()
        balances = await session.scalar(
            text("SELECT count(*) FROM gamification.balances WHERE user_id = :u"), {"u": user}
        )
        destroyed = await session.scalar(
            text("SELECT count(*) FROM events.events WHERE type = 'economy.coins_destroyed'")
        )
    assert [(k.kind, k.value, k.delta) for k in kinds][-2:] == [
        ("destruction", "coins", -5),
        ("destruction", "xp", -20),
    ]
    assert all(k.reason is None for k in kinds) and balances == 0 and destroyed == 1
    assert await gm.balance(other, "coins") == 5
