"""012 T027 — voter identities never exposed; IDOR on proposals and participations; moderation audited;
erasure removes votes (counts decremented), withdraws participations, drops feed entries and detaches the
proposer; XSS corpus in proposal bodies and help notes stays inert."""

import re
from dataclasses import replace

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.modules.community.privacy.participant import CommunityParticipant
from tests.integration.community.conftest import CoHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration
XSS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "[x](javascript:alert(1))",
    '<a href="javascript:alert(1)">x</a>',
    "<svg onload=alert(1)>",
]


async def test_privacy_idor_erasure_xss(co: CoHarness, client: AsyncClient) -> None:
    await login(client, "ursula")
    pending = (
        await client.post("/api/v1/community/proposals", json={"title": "Secret", "body_md": "x"})
    ).json()
    co.module.config = replace(co.module.config, proposals_moderation=False)
    body = "\n\n".join(XSS)
    proposal = (
        await client.post("/api/v1/community/proposals", json={"title": "XSS", "body_md": body})
    ).json()
    rendered = proposal["rendered_html"]
    assert "<script" not in rendered and "<svg" not in rendered and "<img" not in rendered
    assert not re.search(r"<[a-z][^>]*\son[a-z]+\s*=", rendered)  # no live event handler
    assert not re.search(r"<a\b[^>]*href=[\"']?javascript:", rendered)  # escaped text is inert
    help_set = await client.put(
        f"/api/v1/community/proposals/{proposal['id']}/help", json={"help_wanted": True, "note": XSS[0]}
    )
    assert help_set.json()["help_note"] == XSS[0]  # stored as text, rendered as text by the client

    for name in ("ulrich", "vera"):
        await login(client, name)
        await client.post(f"/api/v1/community/proposals/{proposal['id']}/vote")
    await login(client, "ulrich")
    joined = (
        await client.post(
            f"/api/v1/community/proposals/{proposal['id']}/participation", json={"role": "tester"}
        )
    ).json()
    assert (await client.get(f"/api/v1/community/proposals/{pending['id']}")).status_code == 404  # IDOR
    for method, path in (
        ("PATCH", f"/api/v1/community/proposals/{proposal['id']}"),
        ("POST", f"/api/v1/community/proposals/{proposal['id']}/withdraw"),
        ("PUT", f"/api/v1/community/proposals/{proposal['id']}/help"),
        ("POST", f"/api/v1/community/proposals/{proposal['id']}/participations/{joined['id']}/recognize"),
    ):
        response = await client.request(
            method, path, json={"title": "x", "body_md": "", "tags": [], "help_wanted": False}
        )
        assert response.status_code in (403, 404), (method, path, response.status_code)
    detail = await client.get(f"/api/v1/community/proposals/{proposal['id']}")
    assert detail.json()["votes"] == 2
    assert str(co.people["vera"]) not in detail.text  # voters never listed
    for path in (
        "/api/v1/admin/community/moderation",
        f"/api/v1/admin/community/moderation/proposals/{pending['id']}/approve",
    ):
        assert (
            await client.request("GET" if path.endswith("moderation") else "POST", path, json={})
        ).status_code == 403

    participant = CommunityParticipant(co.database)
    exported = {r.category for r in await participant.export(co.people["ulrich"])}
    assert {"community.vote", "community.participation"} <= exported
    await participant.erase(co.people["ulrich"], "final")
    await participant.erase(co.people["ursula"], "final")
    async with co.database.session() as session:
        count = await session.scalar(
            text("SELECT count FROM community.vote_counts WHERE proposal_id = :p"), {"p": proposal["id"]}
        )
        votes = await session.scalar(
            text("SELECT count(*) FROM community.votes WHERE user_id = :u"), {"u": co.people["ulrich"]}
        )
        status = await session.scalar(
            text("SELECT status FROM community.participations WHERE id = :i"), {"i": joined["id"]}
        )
        proposer = await session.scalar(
            text("SELECT proposer_id FROM community.proposals WHERE id = :p"), {"p": proposal["id"]}
        )
    assert (count, votes, status, proposer) == (1, 0, "withdrawn", None)
