"""#98 — the shop's console for administrators: what is going on (purchases, Coins, grants, the best
sellers, the latest activity), the catalogue a page at a time, a member's inventory, an item taken out of
the history, the seasons' weeks; and in the economy, Coins taken back (never below zero), an entry
cancelled, the economy at a glance."""

import pytest
from httpx import AsyncClient

from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import MkHarness, confirmed, published

pytestmark = pytest.mark.integration


async def test_console(mk: MkHarness, client: AsyncClient) -> None:
    await published(mk, "owl", "badge", price_coins=40, payload={"label": "Owl"})
    await published(mk, "fox", "badge", price_coins=30, payload={"label": "Fox"})
    await mk.coins("ursula", 200)
    await login(client, "ursula")
    owl = (await client.post("/api/v1/marketplace/products/owl/acquire")).json()
    await login(client, "boss")
    await confirmed(
        client,
        "POST",
        "/api/v1/admin/marketplace/grants",
        {"user_id": str(mk.people["ulrich"]), "product": "fox", "reason": "Welcome gift"},
    )

    overview = (await client.get("/api/v1/admin/marketplace/overview", params={"days": 7})).json()
    assert (overview["purchases"], overview["coins_spent"], overview["grants"]) == (1, 40, 1)
    assert overview["buyers"] == 1 and overview["items_owned"] == 2
    assert overview["top"][0]["key"] == "owl" and len(overview["series"]) == 7
    assert {a["kind"] for a in overview["activity"]} == {"purchase", "grant"}

    page = (await client.get("/api/v1/admin/marketplace/catalog", params={"limit": 1})).json()
    assert len(page["items"]) == 1 and page["total"] >= 2 and page["types"]["badge"] >= 2
    found = (await client.get("/api/v1/admin/marketplace/catalog", params={"q": "owl"})).json()
    assert [p["key"] for p in found["items"]] == ["owl"]

    url = f"/api/v1/admin/marketplace/members/{mk.people['ursula']}/inventory"
    [item] = (await client.get(url)).json()
    assert (item["product"], item["origin"], item["price_paid"], item["state"]) == (
        "owl",
        "purchase",
        40,
        "active",
    )
    removed = await client.request(
        "DELETE", f"/api/v1/admin/marketplace/ownerships/{owl['id']}", json={"reason": "Test purchase"}
    )
    assert removed.status_code == 204 and (await client.get(url)).json() == []
    assert await mk.balance("ursula") == 160  # taken out of the history, no Coins move

    seasons = (await client.get("/api/v1/admin/marketplace/seasons")).json()
    assert seasons and {"key", "start", "end", "now"} <= set(seasons[0])

    taken = await client.post(
        "/api/v1/admin/gamification/manual-withdrawals",
        json={"user_id": str(mk.people["ursula"]), "value": "coins", "amount": 50, "reason": "Too many"},
    )
    assert taken.status_code == 200 and await mk.balance("ursula") == 110
    too_much = await client.post(
        "/api/v1/admin/gamification/manual-withdrawals",
        json={"user_id": str(mk.people["vera"]), "value": "coins", "amount": 50, "reason": "Nothing"},
    )
    assert too_much.status_code == 422 and too_much.json()["code"] == "economy.nothing_to_take"
    tx = taken.json()["transaction"]["id"]
    back = await client.post(f"/api/v1/admin/economy/transactions/{tx}/reverse", json={"reason": "Mistake"})
    assert back.status_code == 200 and await mk.balance("ursula") == 160
    again = await client.post(f"/api/v1/admin/economy/transactions/{tx}/reverse", json={"reason": "Twice"})
    assert again.json()["code"] == "economy.already_reversed"

    summary = (await client.get("/api/v1/admin/economy/summary", params={"days": 7})).json()
    assert summary["coins_in_circulation"] == 160 and summary["coins_spent"] >= 40
    assert summary["holders"][0]["user_id"] == str(mk.people["ursula"])


async def test_a_purchase_to_validate_is_a_badge(mk: MkHarness) -> None:
    """#98: a purchase waiting for an administrator's decision is a badge on « To handle » — for those who
    may decide it; a member sees nothing."""
    from portalab.modules.marketplace.attention import ShopAttention

    form = [{"key": "title", "type": "text", "labels": {"en": "Film"}, "required": True}]
    await published(
        mk, "film_4k", "special_request", price_coins=300, payload={"form": form, "deadline_days": 5}
    )
    await mk.coins("ursula", 500)
    ursula = mk.p("ursula")
    ownership = await mk.module.purchases.acquire(ursula, "film_4k", "r1")
    await mk.module.activation.configure(ursula, ownership.id, {"title": "Dune"})
    attention = ShopAttention(mk.database, mk.module.authorizer)
    assert await attention.counts(mk.p("boss")) == {"marketplace.admin_requests": 1}
    assert await attention.counts(ursula) == {}
