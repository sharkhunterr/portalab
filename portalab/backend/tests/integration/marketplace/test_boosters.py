"""#81 — boosters for real: those on sale (with their odds, refunds and openings left), opening one charges
its price, grants the looks not owned yet, gives the duplicates' Coins back at once (a fixed amount per
rarity) and is replayed by its ``Idempotency-Key``; the reserve booster fills the reserve (items stack,
never a duplicate), using an item grants it as a purchase would; Discovery opens three times per member."""

from typing import Any

from httpx import AsyncClient

from portalab.capabilities.media_core import QUOTA
from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import FakeQuota, MkHarness, product_def, published


async def look(mk: MkHarness, key: str, rarity: str, kind: str = "badge", **version: Any) -> None:
    body = {
        **product_def(key, kind, price_coins=200, **version),
        "presentation": {"rarity": rarity},
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
    await mk.module.grants.grant(mk.p("boss"), mk.people["ursula"], "night_owl", "gift")
    await mk.coins("ursula", 1000)
    await login(client, "ursula")

    shelf = {b["key"]: b for b in (await client.get("/api/v1/marketplace/boosters")).json()}
    assert {
        "booster_cosmos",
        "booster_legend",
        "booster_prestige",
        "booster_reserve",
        "booster_discovery",
    } <= set(shelf)
    cosmos = shelf["booster_cosmos"]
    assert cosmos["cards"] == 5 and cosmos["guarantee"] == "rare" and cosmos["kind"] == "looks"
    assert cosmos["refunds"] == {"common": 10, "rare": 15, "epic": 20, "legendary": 30}
    assert shelf["booster_reserve"]["kind"] == "reserve" and shelf["booster_discovery"]["left"] == 3

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
    assert all(owned[key] for key in cards) and not owned["some_widget"]
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
    assert history[0]["names"]["en"] == "Cosmos booster" and len(history[0]["cards"]) == 5
    assert (await client.post("/api/v1/marketplace/boosters/nothing/open")).status_code == 404


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
    await mk.coins("ursula", 1000)
    await login(client, "ursula")
    for left in (2, 1, 0):
        opened = (await client.post("/api/v1/marketplace/boosters/booster_discovery/open")).json()
        assert opened["booster"]["left"] == left and len(opened["cards"]) == 3
    refused = await client.post("/api/v1/marketplace/boosters/booster_discovery/open")
    assert refused.status_code == 409 and refused.json()["code"] == "marketplace.booster_limit"
    # the refused one charged nothing (duplicates of the earlier ones gave a little back)
    spent = 3 * 120
    history = (await client.get("/api/v1/marketplace/boosters/openings")).json()
    back = sum(h["refund"] for h in history)
    assert len(history) == 3 and await mk.balance("ursula") == 1000 - spent + back
