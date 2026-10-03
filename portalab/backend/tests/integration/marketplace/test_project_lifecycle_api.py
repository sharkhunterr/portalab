"""015 T008 — Community ``register`` creates one project per proposal; promote/open/validate/transition/
abandon need ``projects.manage``, a confirmation where Coins move, and are audited; every change appends
history and emits ``project.status_changed`` (dedup ``(project, seq)``); validation is the Admin's gate,
informed by (never bound to) votes or funding."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.capabilities.marketplace import LIFECYCLE, ProjectLifecycle
from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import RULES, MkHarness

pytestmark = pytest.mark.integration


async def confirmed(client: AsyncClient, path: str, body: dict[str, object]) -> dict[str, object]:
    first = await client.post(path, json=body)
    assert first.status_code == 409 and first.json()["code"] == "authz.confirmation_required", first.text
    second = await client.post(path, json={**body, "confirmation": first.json()["confirmation"]})
    assert second.status_code == 200, second.text
    return second.json()  # type: ignore[no-any-return]


async def test_register_and_transitions(mk: MkHarness, client: AsyncClient) -> None:
    [provider] = mk.module.capabilities.system_providers(LIFECYCLE)
    lifecycle = provider.provider
    assert isinstance(lifecycle, ProjectLifecycle)
    ref = await lifecycle.register("proposal-1", mk.people["ursula"], "Dark mode")
    again = await lifecycle.register("proposal-1", mk.people["ursula"], "Dark mode (renamed)")
    assert ref.id == again.id and ref.state == "idea"
    assert await lifecycle.accepts_votes("proposal-1") and await lifecycle.state("missing") is None
    summary = await lifecycle.funding_summary("proposal-1")
    assert summary is not None and not summary.accepts_funding and summary.reserved == 0

    project = f"/api/v1/admin/projects/{ref.id}"
    await login(client, "ursula")
    assert (await client.post(f"{project}/promote", json={})).status_code == 403
    await login(client, "boss")
    assert (await client.post(f"{project}/open", json={"rules": RULES})).status_code == 409  # idea → open
    assert (await client.post(f"{project}/promote", json={"reason": "Popular"})).json()["state"] == "proposal"
    opened = (await client.post(f"{project}/open", json={"rules": RULES, "note": "Funding is open"})).json()
    assert opened["state"] == "open" and opened["funding_rules"]["max_funding_per_user"] == 200
    stale = await client.post(f"{project}/transition", json={"to": "validation", "version": 1})
    assert stale.status_code == 409 and stale.json()["code"] == "project.version_conflict"
    assert (await client.post(f"{project}/transition", json={"to": "validation"})).json()[
        "state"
    ] == "validation"
    approved = await confirmed(client, f"{project}/validate", {"approve": True, "reason": "Feasible"})
    assert approved["state"] == "development" and not approved["accepts_votes"]
    assert (await client.post(f"{project}/transition", json={"to": "beta"})).json()["state"] == "beta"
    released = await confirmed(client, f"{project}/transition", {"to": "released"})
    assert released["state"] == "released"
    assert [h["to_state"] for h in released["history"]] == [
        "idea",
        "proposal",
        "open",
        "validation",
        "development",
        "beta",
        "released",
    ]
    assert released["notes"] == [
        {"state": "open", "note": "Funding is open", "at": released["notes"][0]["at"]}
    ]
    assert (await client.post(f"{project}/abandon", json={})).status_code == 409  # terminal

    other = await lifecycle.register("proposal-2", mk.people["ulrich"], "Rejected idea")
    rejected = await confirmed(
        client, f"/api/v1/admin/projects/{other.id}/reject", {"reason": "Out of scope"}
    )
    assert rejected["state"] == "rejected" and not await lifecycle.accepts_votes("proposal-2")

    changes = await mk.events("project.status_changed")
    assert [c["seq"] for c in changes if c["project"] == str(ref.id)] == [1, 2, 3, 4, 5, 6, 7]
    async with mk.database.session() as session:
        audited = await session.scalar(
            text("SELECT count(*) FROM audit.audit_entries WHERE action = 'project.transitioned'")
        )
    assert audited == 7  # six forward moves plus the rejection

    await login(client, "vera")
    public = (await client.get(f"/api/v1/projects/{ref.id}")).json()
    assert public["state"] == "released" and public["totals"]["funders"] == 0
    assert {p["title"] for p in (await client.get("/api/v1/projects")).json()} == {
        "Dark mode",
        "Rejected idea",
    }
    assert [
        p["title"] for p in (await client.get("/api/v1/projects", params={"state": "rejected"})).json()
    ] == ["Rejected idea"]
