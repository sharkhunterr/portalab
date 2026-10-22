"""027: a feedback's history — each reply in its own words (the member's reply keeps them all), read,
closed, reopened, converted (with the ticket's reference) and rewarded, in order."""

from uuid import UUID

import httpx

from tests.integration.identity.helpers import login
from tests.integration.support.conftest import SupportHarness


async def test_history_of_a_feedback(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    await login(client, "ursula")
    sent = await client.post("/api/v1/feedback", json={"form_key": "general", "values": {"message": "Nice"}})
    fid = sent.json()["id"]
    await login(client, "boss")
    base = f"/api/v1/support/feedback/{fid}"
    assert (await client.post(f"{base}/reply", json={"text": "Thanks!"})).status_code == 200
    again = await client.post(f"{base}/reply", json={"text": "Fixed now.", "append": True})
    assert again.json()["reply"] == "Thanks!\n\nFixed now."
    assert (await client.post(f"{base}/dismiss")).status_code == 200
    assert (await client.post(f"{base}/review")).status_code == 200
    given = await client.post(
        f"{base}/rewarded", json={"value": "coins", "amount": 100, "label": "100 Coins"}
    )
    assert given.status_code == 204
    assert (await client.post(f"{base}/convert", json={"target_kind": "ticket"})).status_code == 200

    history = (await client.get(base)).json()["history"]
    assert [e["kind"] for e in history] == [
        "replied",
        "replied",
        "closed",
        "reopened",
        "rewarded",
        "converted",
    ]
    replies = [e["text"] for e in history if e["kind"] == "replied"]
    assert replies == ["Thanks!", "Fixed now."]
    converted = next(e for e in history if e["kind"] == "converted")
    assert converted["detail"]["target"] == "ticket" and converted["detail"]["label"].startswith("T-")
    rewarded = next(e for e in history if e["kind"] == "rewarded")
    assert rewarded["detail"] == {"value": "coins", "amount": 100, "label": "100 Coins"}

    listed = next(f for f in (await client.get("/api/v1/support/feedback")).json() if f["id"] == fid)
    assert listed["rewards"] == ["100 Coins"]

    await login(client, "ursula")  # the member never sees the staff's history, but sees the reward
    assert (await client.get(base)).status_code == 403
    mine = next(f for f in (await client.get("/api/v1/me/feedback")).json() if f["id"] == fid)
    assert mine["rewards"] == ["100 Coins"]


async def test_closing_its_ticket_closes_the_feedback(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    await login(client, "ursula")
    sent = await client.post(
        "/api/v1/feedback",
        json={"form_key": "bug_report", "values": {"what": "Clouds in triangles", "steps": "Open"}},
    )
    fid = sent.json()["id"]
    await login(client, "boss")
    made = await client.post(f"/api/v1/support/feedback/{fid}/convert", json={"target_kind": "ticket"})
    tid = made.json()["ref"].rsplit("/", 1)[1]
    ticket = (await client.get(f"/api/v1/tickets/{tid}")).json()
    assert ticket["feedback"]["id"] == fid and ticket["description"] == "Clouds in triangles\n\nOpen"
    assert ticket["feedback"]["answers"][0]["value"] == "Clouds in triangles"
    for transition in ("start", "resolve", "close"):
        moved = await client.post(f"/api/v1/tickets/{tid}/transition", json={"transition": transition})
        assert moved.status_code == 200, moved.text
    feedback = (await client.get(f"/api/v1/support/feedback/{fid}")).json()
    assert feedback["status"] == "dismissed"
    closed = [e for e in feedback["history"] if e["kind"] == "closed"]
    assert closed and closed[0]["detail"]["ticket"].startswith("T-")
