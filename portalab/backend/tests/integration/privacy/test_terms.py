"""027 — terms of use: the administrators publish versions; a member who has not accepted the one in force
can do nothing but read and accept it (or sign out, or exercise their rights on their data); a correction that
does not ask for a new acceptance leaves them be; acceptances are exported and erased with the member."""

import httpx
import pytest
from fastapi import FastAPI

from portalab.core.errors import ValidationFailed
from portalab.modules.privacy.terms.service import TermsParticipant
from tests.authz_fixtures import user
from tests.integration.identity.helpers import create_user, login, module_of
from tests.privacy_fixtures import FullPlatform


async def test_members_must_accept_the_terms_in_force(
    app: FastAPI, client: httpx.AsyncClient, full: FullPlatform
) -> None:
    boss = await create_user(module_of(app), "boss")
    member = await create_user(module_of(app), "member")
    await login(client, "member")
    assert (await client.get("/api/v1/me/onboarding")).status_code == 200  # no terms yet: nothing to accept
    assert (await client.get("/api/v1/terms")).json() == {"terms": None}

    with pytest.raises(ValidationFailed):
        await full.privacy.terms.publish(
            user(boss), title=" ", summary="", body_md="x", requires_acceptance=True
        )
    first = await full.privacy.terms.publish(
        user(boss),
        title="Conditions",
        summary="Be kind",
        body_md="# Rules\n\nBe **kind**.<script>x</script>",
        requires_acceptance=False,  # the first terms are always to accept
    )
    assert first.version == 1 and first.requires_acceptance and "<script" not in first.body_html
    assert await full.privacy.terms.must_accept(boss)  # the administrators accept like every member

    blocked = await client.get("/api/v1/me/onboarding")
    assert blocked.status_code == 403 and blocked.json()["code"] == "terms.acceptance_required"
    mine = (await client.get("/api/v1/me/terms")).json()
    assert mine["required"] and mine["accepted_version"] is None and mine["terms"]["version"] == 1
    assert "<strong>kind</strong>" in mine["terms"]["html"]
    assert (await client.get("/api/v1/me")).status_code == 200  # who am I, still answered

    stale = await client.post("/api/v1/me/terms/accept", json={"version": 2})
    assert stale.status_code == 409 and stale.json()["code"] == "terms.outdated"
    accepted = (await client.post("/api/v1/me/terms/accept", json={"version": 1})).json()
    assert accepted["required"] is False and accepted["accepted_version"] == 1
    assert (await client.get("/api/v1/me/onboarding")).status_code == 200

    await full.privacy.terms.publish(
        user(boss), title="Conditions", summary="", body_md="Be kind (typo fixed).", requires_acceptance=False
    )
    assert (await client.get("/api/v1/me/onboarding")).status_code == 200  # a correction asks nothing
    await full.privacy.terms.publish(
        user(boss),
        title="Conditions",
        summary="New rule",
        body_md="Be kind. Share.",
        requires_acceptance=True,
    )
    assert (await client.get("/api/v1/me/onboarding")).status_code == 403  # a new version: accept again
    await full.privacy.terms.set_enabled(user(boss), False)  # optional: the administrators may ask nothing
    assert (await client.get("/api/v1/me/onboarding")).status_code == 200
    assert (await client.get("/api/v1/me/terms")).json()["required"] is False
    await full.privacy.terms.set_enabled(user(boss), True)
    assert (await client.get("/api/v1/me/onboarding")).status_code == 403
    await client.post("/api/v1/me/terms/accept", json={"version": 3})
    assert (await client.get("/api/v1/me/onboarding")).status_code == 200

    history = [(entry.version.version, entry.acceptances) for entry in await full.privacy.terms.history()]
    assert history == [(3, 1), (2, 0), (1, 1)]
    assert await full.privacy.terms.up_to_date() == 1

    participant = TermsParticipant(full.privacy.terms)
    assert [r.data["version"] for r in await participant.export(member)] == [1, 3]
    await participant.erase(member, "final")
    assert await participant.export(member) == []
