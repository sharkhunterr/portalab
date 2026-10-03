"""013 T033 (F4) — automation actions ``award.xp|coins|contribution`` and ``reward.unlock``: author-bounded
(the author needs ``rewards.grant``), idempotent, ``source_kind=automation``, subject to the anomaly guard;
016's ``grant_contribution`` grants Contribution once per source."""

from dataclasses import replace

import pytest
from sqlalchemy import text

from portalab.capabilities.support import CONTRIBUTIONS
from portalab.core.authz_port import Principal
from portalab.core.errors import Forbidden
from tests.integration.gamification.conftest import SYSTEM, GamHarness

pytestmark = pytest.mark.integration


async def test_actions(gm: GamHarness) -> None:
    keys = {a.key for a in gm.actions.all()}
    assert {"award.xp", "award.coins", "award.contribution", "reward.unlock"} <= keys
    user = gm.people["ursula"]
    author = Principal(channel="automation", acting_for=gm.people["boss"])
    award = gm.actions.get("award.coins")
    assert award is not None
    params = {"user": str(user), "amount": 7, "idempotency": "run-1", "automation": "automation:welcome"}
    first = await award.run(params, author)
    second = await award.run(params, author)
    assert first["transaction"] == second["transaction"] and await gm.balance(user, "coins") == 7
    with pytest.raises(Forbidden):
        await award.run(
            {**params, "idempotency": "run-2"},
            Principal(channel="automation", acting_for=gm.people["ulrich"]),
        )
    gm.module.config = replace(gm.module.config, anomaly_max_grants_per_hour=1)
    flagged = await award.run({**params, "idempotency": "run-3"}, author)
    assert flagged["withheld"] is True and await gm.balance(user, "coins") == 7
    await gm.module.achievements.save(
        SYSTEM, "welcome", {"label": "Welcome", "criteria": [{"kind": "level_at_least", "level": 99}]}
    )
    unlock = gm.actions.get("reward.unlock")
    assert unlock is not None
    assert (await unlock.run({"user": str(user), "achievement": "welcome"}, author)) == {"unlocked": True}
    assert (await unlock.run({"user": str(user), "achievement": "welcome"}, author)) == {"unlocked": False}
    async with gm.database.session() as session:
        sources = (
            (await session.execute(text("SELECT DISTINCT source_kind FROM gamification.transactions")))
            .scalars()
            .all()
        )
    assert sources == ["automation"]


async def test_contribution_grants(gm: GamHarness) -> None:
    port = gm.ev.full.identity.capabilities.system_providers(CONTRIBUTIONS)[0].provider
    user = gm.people["ursula"]
    staff = Principal(user_id=gm.people["boss"])
    first = await port.grant_contribution(user, "bug_report", "feedback:42", staff)
    again = await port.grant_contribution(user, "bug_report", "feedback:42", staff)
    assert first == again and await gm.balance(user, "contribution") == 10
