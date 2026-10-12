"""#81 (proof of concept) — the boosters on sale and a reveal: looks only (never features), each card says
whether it is a duplicate (and the Coins it would give back); nothing is charged or granted."""

from httpx import AsyncClient

from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import MkHarness, product_def, published


async def test_booster_reveal(mk: MkHarness, client: AsyncClient) -> None:
    for key, rarity in (
        ("night_owl", "common"),
        ("early_bird", "common"),
        ("comet", "rare"),
        ("nova", "epic"),
    ):
        body = {**product_def(key, "badge", price_coins=200), "presentation": {"rarity": rarity}}
        await mk.module.catalog.create(mk.p("boss"), body)
        await mk.module.catalog.move(mk.p("boss"), key, "available")
    await published(mk, "pulsar", "title", price_coins=120, payload={"label": "Pulsar"})
    await published(mk, "some_widget", "widget", price_coins=300)  # not a look: never in a booster
    await mk.module.grants.grant(mk.p("boss"), mk.people["ursula"], "night_owl", "gift")
    await login(client, "ursula")
    [booster] = (await client.get("/api/v1/marketplace/boosters")).json()
    assert booster["key"] == "booster_cosmos" and booster["cards"] == 5 and booster["guarantee"] == "rare"
    assert booster["refunds"] == {"common": 10, "rare": 15, "epic": 20, "legendary": 30}
    before = (await client.get("/api/v1/marketplace/products")).json()
    opened = (await client.post("/api/v1/marketplace/boosters/booster_cosmos/reveal")).json()
    keys = [card["product"]["key"] for card in opened["cards"]]
    assert opened["preview"] is True and len(keys) == 5 and len(set(keys)) == 5
    assert "some_widget" not in keys
    owl = next(card for card in opened["cards"] if card["product"]["key"] == "night_owl")
    assert owl["duplicate"] is True and owl["refund"] == 10  # a common one, whatever its price (200)
    assert all(not card["duplicate"] and card["refund"] == 0 for card in opened["cards"] if card is not owl)
    # visual only: nothing changed hands
    after = (await client.get("/api/v1/marketplace/products")).json()
    assert [p["owned"] for p in after] == [p["owned"] for p in before]
    assert (await client.post("/api/v1/marketplace/boosters/nothing/reveal")).status_code == 404
