"""#81 — boosters are products of the catalog (type ``booster``): in the shop with their odds, refunds and
openings left; opening one charges its price, grants the looks not owned yet, gives the duplicates' Coins
back at once (a fixed amount per rarity) and is replayed by its ``Idempotency-Key``; a look won below its
level or Contribution is held ``locked`` and usable once they are reached; a booster offered (a level
reward, an achievement) waits sealed in the reserve and opens for free; a season's booster draws from its
season's looks and is on sale in its weeks only; the reserve booster fills the reserve (items stack, never
a duplicate), using an item grants it as a purchase would; Discovery opens three times per member."""

from typing import Any

from httpx import AsyncClient

from portalab.capabilities.media_core import QUOTA
from portalab.modules.gamification.ledger.writer import Entry
from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import FakeQuota, MkHarness, product_def, published

CLASSIC = {"pool": "looks", "cards": 5, "odds": {"common": 62, "rare": 26, "epic": 10, "legendary": 2}}


async def look(
    mk: MkHarness, key: str, rarity: str, kind: str = "badge", season: str | None = None, **version: Any
) -> None:
    body = {
        **product_def(key, kind, price_coins=200, **version),
        "presentation": {"rarity": rarity, "season": season},
    }
    await mk.module.catalog.create(mk.p("boss"), body)
    await mk.module.catalog.move(mk.p("boss"), key, "available")


async def booster(mk: MkHarness, key: str, price: int, **payload: Any) -> None:
    body = {
        **product_def(key, "booster", price_coins=price, payload={**CLASSIC, **payload}),
        "repeatable": True,
        "presentation": {"rarity": "rare"},
    }
    await mk.module.catalog.create(mk.p("boss"), body)
    await mk.module.catalog.move(mk.p("boss"), key, "available")


async def test_opening_a_booster(mk: MkHarness, client: AsyncClient) -> None:
    for key, rarity in (
        ("night_owl", "common"),
        ("early_bird", "common"),
        ("comet", "rare"),
        ("nova", "epic"),
    ):
        await look(mk, key, rarity)
    await look(mk, "pulsar", "common", "title", payload={"label": "Pulsar"})
    await published(mk, "some_widget", "widget", price_coins=300)  # not a look: never in a booster
    await booster(mk, "booster_cosmos", 450, guarantee="rare")
    await mk.module.grants.grant(mk.p("boss"), mk.people["ursula"], "night_owl", "gift")
    await mk.coins("ursula", 1000)
    await login(client, "ursula")

    # a product like any other: a tile in the shop, with what it holds
    tile = next(
        p for p in (await client.get("/api/v1/marketplace/products")).json() if p["type"] == "booster"
    )
    assert (
        tile["key"] == "booster_cosmos"
        and tile["booster"]["cards"] == 5
        and tile["booster"]["odds"]["common"] == 62
    )
    assert tile["booster"]["refunds"] == {"common": 10, "rare": 15, "epic": 20, "legendary": 30}
    [shelf] = (await client.get("/api/v1/marketplace/boosters")).json()
    assert (
        shelf["kind"] == "looks"
        and shelf["guarantee"] == "rare"
        and shelf["sealed"] == 0
        and shelf["left"] is None
    )

    # five looks in the pool, five cards: all of them, the owl a duplicate (10 Coins back, not its price)
    first = await client.post(
        "/api/v1/marketplace/boosters/booster_cosmos/open", headers={"Idempotency-Key": "a"}
    )
    assert first.status_code == 201
    opened = first.json()
    cards = {card["product"]["key"]: card for card in opened["cards"]}
    assert set(cards) == {"night_owl", "early_bird", "comet", "nova", "pulsar"}
    assert cards["night_owl"]["outcome"] == "duplicate" and cards["night_owl"]["refund"] == 10
    assert all(c["outcome"] == "new" and c["refund"] == 0 for k, c in cards.items() if k != "night_owl")
    assert opened["opening"]["price"] == 450 and opened["opening"]["refund"] == 10
    assert await mk.balance("ursula") == 1000 - 450 + 10
    owned = {p["key"]: p["owned"] for p in (await client.get("/api/v1/marketplace/products")).json()}
    assert all(owned[key] for key in cards) and not owned["some_widget"] and not owned["booster_cosmos"]
    mine = (await client.get("/api/v1/me/marketplace/owned")).json()
    assert {r["product_key"] for r in mine if r["origin"] == "booster"} == set(cards) - {"night_owl"}

    # replayed: the same opening, nothing charged twice
    again = await client.post(
        "/api/v1/marketplace/boosters/booster_cosmos/open", headers={"Idempotency-Key": "a"}
    )
    assert again.json()["opening"]["id"] == opened["opening"]["id"] and await mk.balance("ursula") == 560

    # all owned now: five duplicates — 10 + 10 + 15 + 20 + 10 back
    second = (await client.post("/api/v1/marketplace/boosters/booster_cosmos/open")).json()
    assert all(c["outcome"] == "duplicate" for c in second["cards"]) and second["opening"]["refund"] == 65
    assert await mk.balance("ursula") == 560 - 450 + 65
    broke = await client.post("/api/v1/marketplace/boosters/booster_cosmos/open")
    assert broke.status_code == 409 and broke.json()["code"] == "marketplace.insufficient_coins"
    assert await mk.balance("ursula") == 175

    history = (await client.get("/api/v1/marketplace/boosters/openings")).json()
    assert [h["id"] for h in history] == [second["opening"]["id"], opened["opening"]["id"]]
    # #103: each opening is the member's event (their achievements): its cards, the new ones, the rarest
    events = await mk.events("marketplace.booster_opened")
    assert [(e["opening"], e["cards"], e["new"], e["best"], e["price"]) for e in events] == [
        (opened["opening"]["id"], 5, 4, "epic", 450),
        (second["opening"]["id"], 5, 0, "epic", 450),
    ]
    assert history[0]["names"]["en"] == "Booster Cosmos" and len(history[0]["cards"]) == 5
    assert (await client.post("/api/v1/marketplace/boosters/nothing/open")).status_code == 404
    sealed = await client.post("/api/v1/marketplace/boosters/booster_cosmos/open", params={"sealed": "true"})
    assert sealed.status_code == 409 and sealed.json()["code"] == "marketplace.reserve_empty"


async def test_locked_until_its_conditions_then_offered_and_seasons(
    mk: MkHarness, client: AsyncClient
) -> None:
    await look(
        mk,
        "pumpkin",
        "common",
        season="halloween",
        conditions=[{"kind": "min_contribution", "contribution": 5}],
    )
    await look(mk, "snowman", "common", season="christmas")
    await booster(mk, "booster_halloween", 450, season="halloween", cards=1)
    await booster(mk, "booster_christmas", 450, season="christmas", cards=1)
    await mk.coins("ursula", 1000)
    await login(client, "ursula")
    # 1 October: Halloween's booster is on sale, Christmas' is not
    shop = {p["key"] for p in (await client.get("/api/v1/marketplace/products")).json()}
    assert "booster_halloween" in shop and "booster_christmas" not in shop
    assert {b["key"] for b in (await client.get("/api/v1/marketplace/boosters")).json()} == {
        "booster_halloween"
    }
    closed = await client.post("/api/v1/marketplace/boosters/booster_christmas/open")
    assert closed.status_code == 409 and closed.json()["code"] == "marketplace.not_available"

    # its season's looks only — won below its Contribution: held, locked, not usable
    opened = (await client.post("/api/v1/marketplace/boosters/booster_halloween/open")).json()
    [card] = opened["cards"]
    assert card["product"]["key"] == "pumpkin" and card["outcome"] == "new" and card["locked"] is True
    states = {r["product_key"]: r["state"] for r in (await client.get("/api/v1/me/marketplace/owned")).json()}
    assert states["pumpkin"] == "locked"
    pumpkin = (await client.get("/api/v1/marketplace/products/pumpkin")).json()
    assert pumpkin["owned"] is True and pumpkin["locked"] is True
    # its Contribution reached: usable
    async with mk.database.unit_of_work() as uow:
        await mk.economy.writer.record(
            uow.session,
            Entry(
                user_id=mk.people["ursula"],
                value="contribution",
                delta=10,
                kind="grant",
                source_kind="system",
                idempotency_key="contribution:test",
                occurred_at=mk.clock.now(),
            ),
        )
    listed = {p["key"]: p for p in (await client.get("/api/v1/marketplace/products")).json()}
    assert listed["pumpkin"]["owned"] is True and listed["pumpkin"]["locked"] is False
    states = {r["product_key"]: r["state"] for r in (await client.get("/api/v1/me/marketplace/owned")).json()}
    assert states["pumpkin"] == "active"

    # offered (an achievement, a level reward): sealed in the reserve, opened for free even out of season —
    # its duplicate's Coins credited
    await mk.module.grants.grant(mk.p("boss"), mk.people["ursula"], "booster_christmas", "achievement")
    await mk.module.grants.grant(mk.p("boss"), mk.people["ursula"], "booster_halloween", "level 5")
    shelf = {b["key"]: b for b in (await client.get("/api/v1/marketplace/boosters")).json()}
    assert shelf["booster_christmas"]["sealed"] == 1 and shelf["booster_christmas"]["on_sale"] is False
    reserve = {i["product"]["key"]: i for i in (await client.get("/api/v1/marketplace/reserve")).json()}
    assert reserve["booster_christmas"]["booster"] is True and reserve["booster_christmas"]["quantity"] == 1
    used = await client.post("/api/v1/marketplace/reserve/booster_christmas/use")
    assert used.status_code == 409 and used.json()["code"] == "marketplace.open_booster"
    before = await mk.balance("ursula")
    gift = (
        await client.post("/api/v1/marketplace/boosters/booster_christmas/open", params={"sealed": "true"})
    ).json()
    assert gift["opening"]["price"] == 0 and [c["product"]["key"] for c in gift["cards"]] == ["snowman"]
    assert gift["booster"]["sealed"] == 0 and gift["booster"]["on_sale"] is False  # out of the list, as it is
    assert await mk.balance("ursula") == before
    again = (
        await client.post("/api/v1/marketplace/boosters/booster_halloween/open", params={"sealed": "true"})
    ).json()
    assert again["cards"][0]["outcome"] == "duplicate" and again["opening"]["refund"] == 10
    assert await mk.balance("ursula") in (before, before + 10)  # credited when the economy's perks run
    assert (await client.get("/api/v1/marketplace/reserve")).json() == []


async def test_the_reserve(mk: MkHarness, client: AsyncClient) -> None:
    quota = FakeQuota()
    mk.module.capabilities.provide(QUOTA, quota, instance_ref="fake024", owner="module:test", priority=1)
    for key, rarity, units in (("plus_3", "common", 3), ("plus_5", "rare", 5), ("plus_10", "epic", 10)):
        body = {
            **product_def(key, "quota", price_coins=150, payload={"kind": "media_requests", "units": units}),
            "repeatable": True,
            "presentation": {"rarity": rarity},
        }
        await mk.module.catalog.create(mk.p("boss"), body)
        await mk.module.catalog.move(mk.p("boss"), key, "available")
    await look(mk, "night_owl", "common")  # a look: never in the reserve booster
    await booster(mk, "booster_reserve", 300, pool="reserve", cards=3, guarantee="rare")
    await mk.coins("ursula", 1000)
    await login(client, "ursula")
    for _ in range(2):
        opened = (await client.post("/api/v1/marketplace/boosters/booster_reserve/open")).json()
        assert {c["product"]["key"] for c in opened["cards"]} == {"plus_3", "plus_5", "plus_10"}
        assert all(c["outcome"] == "reserve" and c["refund"] == 0 for c in opened["cards"])
    assert await mk.balance("ursula") == 1000 - 2 * 300
    reserve = {
        i["product"]["key"]: i["quantity"] for i in (await client.get("/api/v1/marketplace/reserve")).json()
    }
    assert reserve == {"plus_3": 2, "plus_5": 2, "plus_10": 2}
    assert not quota.units  # kept, not used yet

    used = await client.post("/api/v1/marketplace/reserve/plus_5/use", headers={"Idempotency-Key": "u"})
    assert used.status_code == 201 and used.json()["state"] == "active"
    assert quota.units[mk.people["ursula"]] == 5
    replay = await client.post("/api/v1/marketplace/reserve/plus_5/use", headers={"Idempotency-Key": "u"})
    assert replay.json()["ownership"] == used.json()["ownership"] and quota.units[mk.people["ursula"]] == 5
    await client.post("/api/v1/marketplace/reserve/plus_5/use")
    empty = await client.post("/api/v1/marketplace/reserve/plus_5/use")
    assert empty.status_code == 409 and empty.json()["code"] == "marketplace.reserve_empty"
    reserve = {
        i["product"]["key"]: i["quantity"] for i in (await client.get("/api/v1/marketplace/reserve")).json()
    }
    assert reserve == {"plus_3": 2, "plus_10": 2} and quota.units[mk.people["ursula"]] == 10
    # someone else's reserve is their own
    await login(client, "vera")
    assert (await client.get("/api/v1/marketplace/reserve")).json() == []
    other = await client.post("/api/v1/marketplace/reserve/plus_3/use")
    assert other.status_code == 409 and other.json()["code"] == "marketplace.reserve_empty"


async def test_discovery_opens_three_times(mk: MkHarness, client: AsyncClient) -> None:
    for index in range(4):
        await look(mk, f"look_{index}", "common")
    await booster(mk, "booster_discovery", 120, cards=3, per_member=3)
    await mk.coins("ursula", 1000)
    await login(client, "ursula")
    for left in (2, 1, 0):
        opened = (await client.post("/api/v1/marketplace/boosters/booster_discovery/open")).json()
        assert opened["booster"]["left"] == left and len(opened["cards"]) == 3
    refused = await client.post("/api/v1/marketplace/boosters/booster_discovery/open")
    assert refused.status_code == 409 and refused.json()["code"] == "marketplace.booster_limit"
    # the refused one charged nothing (duplicates of the earlier ones gave a little back)
    history = (await client.get("/api/v1/marketplace/boosters/openings")).json()
    back = sum(h["refund"] for h in history)
    assert len(history) == 3 and await mk.balance("ursula") == 1000 - 3 * 120 + back


async def test_a_look_waiting_for_its_level_is_listed_locked_with_its_level(
    mk: MkHarness, client: AsyncClient
) -> None:
    """#99 — a look won below its level is the member's, yet not wearable: the looks' catalogues list it
    locked with what it waits for (before, it was simply missing from the member's looks)."""
    level = [{"kind": "min_level", "level": 7}]
    await look(mk, "level_neon", "common", kind="level_badge", payload={"style": "neon"}, conditions=level)
    await look(mk, "night_owl", "common", conditions=level)
    await booster(mk, "booster_looks", 100, cards=2)
    await mk.coins("ursula", 1000)
    await login(client, "ursula")
    opened = (await client.post("/api/v1/marketplace/boosters/booster_looks/open")).json()
    assert {c["product"]["key"] for c in opened["cards"]} == {"level_neon", "night_owl"}
    assert all(c["locked"] for c in opened["cards"])

    user = mk.people["ursula"]
    levels = {c["key"]: c for c in (await mk.module.looks.catalog(user))["levels"]}
    assert levels["neon"]["locked"] is True and levels["neon"]["waiting"] == {"level": 7}
    assert "waiting" not in levels["classic"]
    [badge] = await mk.module.looks.owned_items(user, "badge")
    assert badge["key"] == "night_owl" and badge["waiting"] == {"level": 7}


async def test_a_early_unlock_unlocks_an_item_waiting_for_its_level(
    mk: MkHarness, client: AsyncClient
) -> None:
    """#131 — a level pass, bought, waits in the reserve; spent on an item the member holds but may not wear
    yet, it makes it theirs at once — one pass, one item; never on what is not waiting, nor a pack."""
    level = [{"kind": "min_level", "level": 30}]
    await look(mk, "night_owl", "common", conditions=level)
    await look(mk, "early_bird", "common", conditions=level)
    await booster(mk, "booster_looks", 100, cards=2)
    body = {**product_def("early_unlock", "early_unlock", price_coins=2500, payload={}), "repeatable": True}
    await mk.module.catalog.create(mk.p("boss"), body)
    await mk.module.catalog.move(mk.p("boss"), "early_unlock", "available")
    await mk.coins("ursula", 3000)
    await login(client, "ursula")
    await client.post("/api/v1/marketplace/boosters/booster_looks/open")
    bought = await client.post(
        "/api/v1/marketplace/products/early_unlock/acquire", headers={"Idempotency-Key": "p"}
    )
    assert bought.status_code in (200, 201), bought.text
    reserve = {i["product"]["key"]: i for i in (await client.get("/api/v1/marketplace/reserve")).json()}
    assert reserve["early_unlock"]["quantity"] == 1 and reserve["early_unlock"]["early_unlock"] is True
    # used like any other item: refused — it is spent on an item
    plain = await client.post("/api/v1/marketplace/reserve/early_unlock/use")
    assert plain.status_code == 409 and plain.json()["code"] == "marketplace.not_an_early_unlock"
    nothing = await client.post(
        "/api/v1/marketplace/reserve/early_unlock/unlock", json={"target": "booster_looks"}
    )
    assert nothing.status_code == 409 and nothing.json()["code"] == "marketplace.nothing_waiting"

    used = await client.post("/api/v1/marketplace/reserve/early_unlock/unlock", json={"target": "night_owl"})
    assert used.status_code == 201 and used.json()["state"] == "active"
    states = {
        r["product_key"]: r["state"] for r in (await client.get("/api/v1/me/marketplace/purchases")).json()
    }
    assert states["night_owl"] == "active" and states["early_bird"] == "locked"  # one pass, one item
    again = await client.post(
        "/api/v1/marketplace/reserve/early_unlock/unlock", json={"target": "early_bird"}
    )
    assert again.status_code == 409 and again.json()["code"] == "marketplace.reserve_empty"
    assert await mk.balance("ursula") == 3000 - 100 - 2500  # no Coins moved by the pass itself
