"""Issue 225 — the daily wheel: one spin a day (economy time zone), the server's draw given before anything
turns; Coins won or lost (never below zero), XP, a product offered (or Coins when it cannot be)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.marketplace import GIFTS
from portalab.modules.gamification.integrations import WheelWidget
from portalab.modules.gamification.wheel.service import AlreadySpun, parse_segments
from tests.integration.gamification.conftest import GamHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


class Pick:
    """A draw that always lands on ``key`` (and remembers the weights it was given)."""

    def __init__(self, key: str) -> None:
        self.key = key
        self.weights: list[int] = []

    def choices(self, population: list[Any], weights: list[int], k: int = 1) -> list[Any]:
        self.weights = list(weights)
        return [next(s for s in population if s.key == self.key)]


class Gifts:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.given: list[tuple[UUID, str]] = []

    async def gift(self, user: UUID, product_key: str, reason: str) -> bool:
        self.given.append((user, product_key))
        return self.ok


def test_segments_default_when_invalid() -> None:
    default = parse_segments(None)
    assert [s.key for s in default][:2] == ["coins_20", "lose_10"]
    assert any(s.kind == "product" and s.product == "booster_discovery" for s in default)
    # nonsense left out; fewer than two left: the default wheel
    assert parse_segments([{"key": "a", "kind": "coins", "amount": 0}, {"key": "b", "kind": "xp"}]) == default
    kept = parse_segments(
        [
            {"key": "a", "kind": "coins", "amount": 5},
            {"key": "a", "kind": "coins", "amount": 9},  # the same key twice: the first
            {"key": "gift", "kind": "product"},  # no product named
            {"key": "b", "kind": "nothing", "weight": 3},
        ]
    )
    assert [(s.key, s.amount) for s in kept] == [("a", 5), ("b", 0)]


async def test_coins_won_once_a_day(gm: GamHarness) -> None:
    user = gm.people["ursula"]
    gm.module.wheel.rng = Pick("coins_50")  # type: ignore[assignment]
    state = await gm.module.wheel.spin(user)
    assert state["today"]["segment"] == "coins_50" and state["today"]["delta"] == 50
    assert state["today"]["index"] == 2 and state["coins"] == 50
    assert await gm.balance(user, "coins") == 50
    with pytest.raises(AlreadySpun):
        await gm.module.wheel.spin(user)
    assert await gm.balance(user, "coins") == 50
    gm.clock.advance(timedelta(days=1))  # a new day: a new spin
    assert (await gm.module.wheel.state(user))["today"] is None
    await gm.module.wheel.spin(user)
    assert await gm.balance(user, "coins") == 100


async def test_a_loss_never_below_zero(gm: GamHarness) -> None:
    user = gm.people["ursula"]
    gm.module.wheel.rng = Pick("lose_25")  # type: ignore[assignment]
    await gm.module.rewards.grant_manual(gm.p("boss"), user, "coins", 10, reason="seed", idempotency_key="w1")
    state = await gm.module.wheel.spin(user)
    assert state["today"]["amount"] == -25 and state["today"]["delta"] == -10
    assert await gm.balance(user, "coins") == 0
    gm.clock.advance(timedelta(days=1))
    state = await gm.module.wheel.spin(user)  # nothing left to lose
    assert state["today"]["delta"] == 0 and await gm.balance(user, "coins") == 0


async def test_the_day_is_the_economys(gm: GamHarness) -> None:
    user = gm.people["ursula"]
    gm.module.config = replace(gm.module.config, timezone="Europe/Paris")
    gm.module.wheel.rng = Pick("coins_10")  # type: ignore[assignment]
    gm.clock.set(datetime(2026, 10, 22, 21, 30, tzinfo=UTC))  # 23:30 in Paris
    state = await gm.module.wheel.spin(user)
    assert state["day"] == "2026-10-22"
    assert state["next_at"] == "2026-10-22T22:00:00+00:00"  # midnight in Paris
    gm.clock.set(datetime(2026, 10, 22, 22, 30, tzinfo=UTC))  # 00:30 in Paris: the next day
    assert (await gm.module.wheel.spin(user))["day"] == "2026-10-23"


async def test_xp_and_nothing(gm: GamHarness) -> None:
    user = gm.people["ursula"]
    gm.module.wheel.rng = Pick("xp_100")  # type: ignore[assignment]
    await gm.module.wheel.spin(user)
    assert await gm.balance(user) == 100
    gm.clock.advance(timedelta(days=1))
    gm.module.wheel.rng = Pick("nothing")  # type: ignore[assignment]
    state = await gm.module.wheel.spin(user)
    assert state["today"]["kind"] == "nothing" and state["today"]["delta"] == 0
    assert await gm.balance(user) == 100 and await gm.balance(user, "coins") == 0


async def test_a_booster_offered_or_coins_instead(gm: GamHarness) -> None:
    user = gm.people["ursula"]
    gm.module.wheel.rng = Pick("booster")  # type: ignore[assignment]
    gifts = Gifts()
    gm.ev.full.identity.capabilities.provide(GIFTS, gifts, instance_ref="t", owner="test")
    state = await gm.module.wheel.spin(user)
    assert gifts.given == [(user, "booster_discovery")]
    assert state["today"]["given"] is True and state["today"]["delta"] == 0
    assert await gm.balance(user, "coins") == 0
    gm.clock.advance(timedelta(days=1))
    gifts.ok = False  # the shop cannot offer it: Coins instead
    state = await gm.module.wheel.spin(user)
    assert state["today"]["given"] is False and state["today"]["delta"] == 50
    assert await gm.balance(user, "coins") == 50


async def test_switched_off(gm: GamHarness) -> None:
    gm.module.config = replace(gm.module.config, wheel={"enabled": False, "segments": []})
    with pytest.raises(Exception, match="switched off"):
        await gm.module.wheel.spin(gm.people["ursula"])


async def test_api(gm: GamHarness, client: AsyncClient) -> None:
    gm.module.wheel.rng = Pick("jackpot")  # type: ignore[assignment]
    await login(client, "ursula")
    shown = (await client.get("/api/v1/me/wheel")).json()
    assert shown["today"] is None and shown["enabled"] is True and shown["spin_ms"] > 0
    booster = next(s for s in shown["segments"] if s["kind"] == "product")
    assert booster["label"] == "Discovery booster"
    spun = await client.post("/api/v1/me/wheel/spin")
    assert spun.status_code == 200, spun.text
    assert spun.json()["today"]["delta"] == 150 and spun.json()["coins"] == 150
    # its own source in my history, nothing raw shown
    ops = (await client.get("/api/v1/me/progression/operations")).json()["items"]
    assert [(o["source"], o["delta"], o["reason"]) for o in ops] == [("wheel", 150, None)]
    again = await client.post("/api/v1/me/wheel/spin")
    assert again.status_code == 409 and again.json()["code"] == "gamification.wheel_already_spun"
    payload = await WheelWidget(gm.module.wheel).load(gm.p("ursula"), {}, LocaleContext(language="fr"))
    assert payload.state == "available" and payload.data["today"]["segment"] == "jackpot"
    labels = {s["key"]: s["label"] for s in payload.data["segments"]}
    assert labels["booster"] == "Booster Découverte"
