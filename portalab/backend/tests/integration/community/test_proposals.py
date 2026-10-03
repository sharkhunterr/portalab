"""012 T021 — proposals: any active account may propose; moderation (on by default) keeps a proposal
``pending_moderation`` (proposer and moderators only) until approved, then visible and votable; Markdown is
sanitized; a project proposal registers its lifecycle in 015 and never stores the state; ``project.created``
once; edit until votable, withdraw; Support's conversion keeps ``provenance_ref`` (idempotent) and only
``project`` proposals get a funding lifecycle."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text

from portalab.capabilities.support import PROPOSALS
from portalab.modules.identity.domain.state_machine import AccountState
from tests.integration.community.conftest import CoHarness, with_marketplace
from tests.integration.identity.helpers import login, module_of, set_state

pytestmark = pytest.mark.integration
BODY = {
    "kind": "project",
    "title": "Dark mode",
    "body_md": "Please **add** it <script>alert(1)</script>",
    "tags": ["UI", "ui"],
}


async def test_moderated_lifecycle(co: CoHarness, client: AsyncClient, app: FastAPI) -> None:
    marketplace = with_marketplace(co)
    await login(client, "ursula")
    created = await client.post("/api/v1/community/proposals", json=BODY)
    assert created.status_code == 201, created.text
    proposal = created.json()
    assert proposal["status"] == "pending_moderation" and proposal["tags"] == ["ui"]
    assert "<script>" not in proposal["rendered_html"] and "<strong>add</strong>" in proposal["rendered_html"]
    assert proposal["lifecycle"]["state"] == "idea"  # read from 015, not stored here
    path = f"/api/v1/community/proposals/{proposal['id']}"
    edited = await client.patch(path, json={"title": "Dark mode everywhere", "body_md": "x", "tags": []})
    assert edited.json()["title"] == "Dark mode everywhere"
    assert (await client.post(f"{path}/vote")).json()["code"] == "community.voting_closed"

    await login(client, "ulrich")
    assert (await client.get(path)).status_code == 404  # pending: invisible to other members
    assert (await client.get("/api/v1/admin/community/moderation")).status_code == 403
    await login(client, "mona")
    assert [p["id"] for p in (await client.get("/api/v1/admin/community/moderation")).json()] == [
        proposal["id"]
    ]
    approved = await client.post(
        f"/api/v1/admin/community/moderation/proposals/{proposal['id']}/approve", json={"reason": "Good idea"}
    )
    assert approved.json()["status"] == "open"
    again = await client.post(
        f"/api/v1/admin/community/moderation/proposals/{proposal['id']}/approve", json={}
    )
    assert again.status_code == 409

    await login(client, "ursula")
    assert (
        await client.patch(path, json={"title": "Late edit", "body_md": "", "tags": []})
    ).status_code == 409
    await login(client, "ulrich")
    listed = (await client.get("/api/v1/community/proposals")).json()
    assert [p["title"] for p in listed] == ["Dark mode everywhere"] and listed[0]["body_md"] is None

    rejected = (await client.post("/api/v1/community/proposals", json={**BODY, "title": "Spam"})).json()
    await login(client, "mona")
    await client.post(
        f"/api/v1/admin/community/moderation/proposals/{rejected['id']}/reject", json={"reason": "No"}
    )
    await login(client, "ulrich")
    withdrawn = await client.post(f"/api/v1/community/proposals/{rejected['id']}/withdraw")
    assert withdrawn.status_code == 409

    async with co.database.session() as session:
        created_events = (
            (
                await session.execute(
                    text("SELECT payload->>'proposal' FROM events.events WHERE type = 'project.created'")
                )
            )
            .scalars()
            .all()
        )
        lifecycle = await session.scalar(
            text("SELECT state FROM marketplace.projects WHERE proposal_ref = :p"), {"p": proposal["id"]}
        )
        moderation = (
            (await session.execute(text("SELECT decision FROM community.moderation_log ORDER BY created_at")))
            .scalars()
            .all()
        )
        audits = await session.scalar(
            text("SELECT count(*) FROM audit.audit_entries WHERE action LIKE 'community.proposal_%'")
        )
    assert created_events == [proposal["id"]] and lifecycle == "idea"
    assert moderation == ["approved", "rejected"] and audits == 2
    assert marketplace is not None

    await set_state(module_of(app), co.people["vera"], AccountState.SUSPENDED)
    from portalab.core.errors import Forbidden

    with pytest.raises(Forbidden):  # a suspended account cannot propose
        await co.module.proposals.create(co.p("vera"), "feature", "Hidden", "")


async def test_moderation_off_and_support_conversion(co: CoHarness, client: AsyncClient) -> None:
    from dataclasses import replace

    co.module.config = replace(co.module.config, proposals_moderation=False)
    with_marketplace(co)
    await login(client, "ulrich")
    proposal = (await client.post("/api/v1/community/proposals", json={**BODY, "kind": "feature"})).json()
    assert proposal["status"] == "open" and proposal["lifecycle"] == {"state": "none"}

    [port] = co.module.capabilities.system_providers(PROPOSALS)
    first = await port.provider.create(
        "project", "From feedback", "Body", co.people["ursula"], "feedback:42", co.p("mona")
    )
    second = await port.provider.create(
        "project", "From feedback", "Body", co.people["ursula"], "feedback:42", co.p("mona")
    )
    assert first == second
    async with co.database.session() as session:
        row = (
            await session.execute(
                text(
                    "SELECT proposer_id, provenance_ref, lifecycle_ref FROM community.proposals WHERE id = :i"
                ),
                {"i": first},
            )
        ).one()
        projects = await session.scalar(text("SELECT count(*) FROM marketplace.projects"))
    assert (
        row.proposer_id == co.people["ursula"] and row.provenance_ref == "feedback:42" and row.lifecycle_ref
    )
    assert projects == 1  # only the project proposal got a funding lifecycle
