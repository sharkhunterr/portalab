"""002 T041 — the export bundle contains the user's contributor records, never credentials, tokens or other
users' private data; only the owner reads it; it expires."""

import json
from collections.abc import Sequence
from datetime import timedelta
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.privacy_participants import EXPORT_CAPABILITY, ExportRecord
from portalab.core.event_port import OutboxEvent
from portalab.core.time import FixedClock
from portalab.modules.identity.services.sessions import hash_token
from tests.integration.identity.helpers import PASSWORD, create_user, login, module_of

pytestmark = pytest.mark.integration


class LeakyContributor:
    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        return [ExportRecord("connector", {"api_token": "abc123456"})]


async def _build_pending(app: FastAPI, export_id: str) -> None:
    await module_of(app).exports.build(UUID(export_id))


async def test_bundle_contents_and_ownership(
    app: FastAPI, client: httpx.AsyncClient, clock: FixedClock
) -> None:
    module = module_of(app)
    alice = await create_user(module, "alice", display_name="Alice")
    await create_user(module, "bob", display_name="Bob")
    bob_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://portal.test")
    async with bob_client:
        await login(bob_client, "bob")
        await bob_client.patch("/api/v1/me/profile", json={"fields": {"diary": {"value": "bob private"}}})

        response = await login(client, "alice")
        session_token = client.cookies.get("__Host-portalab_session")
        await client.patch(
            "/api/v1/me/profile", json={"fields": {"bio": {"value": "alice bio", "visibility": "public"}}}
        )
        requested = await client.post("/api/v1/me/export")
        assert requested.status_code == 202 and requested.json()["status"] == "queued"
        export_id = requested.json()["id"]
        await _build_pending(app, export_id)

        status = (await client.get(f"/api/v1/me/export/{export_id}")).json()
        assert status["status"] == "ready" and status["expires_at"]
        download = await client.get(f"/api/v1/me/export/{export_id}/content")
        assert download.status_code == 200
        assert "attachment" in download.headers["content-disposition"]
        bundle = json.loads(download.content)

        # another user can neither see nor download it
        assert (await bob_client.get(f"/api/v1/me/export/{export_id}")).status_code == 404
        assert (await bob_client.get(f"/api/v1/me/export/{export_id}/content")).status_code == 404

    assert bundle["subject"] == str(alice)
    categories = {record["category"] for section in bundle["sections"] for record in section["records"]}
    assert {"account", "profile_field", "session", "account_state_history"} <= categories
    text = download.text
    assert "alice bio" in text
    assert "bob private" not in text and "Bob" not in text
    assert session_token and session_token not in text and hash_token(session_token) not in text
    assert response.json()["csrf_token"] not in text
    assert "argon2" not in text and "$argon2id$" not in text
    assert PASSWORD not in text

    async with module.ctx.database.session() as session:
        events = list((await session.execute(select(OutboxEvent.type))).scalars())
    assert "user.data_export_requested" in events and "user.data_exported" in events
    assert "user.data_export_requested" in module.ctx.audit.actions()  # type: ignore[attr-defined]

    clock.advance(timedelta(hours=module.ctx.config.export_ttl_hours, seconds=1))
    await login(client, "alice")  # the session itself expired meanwhile
    assert (await client.get(f"/api/v1/me/export/{export_id}/content")).status_code == 404
    await module.exports.expire(UUID(export_id))
    assert (await client.get(f"/api/v1/me/export/{export_id}")).json()["status"] == "expired"


async def test_a_contributor_leaking_secrets_fails_the_export(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    module = module_of(app)
    module.ctx.capabilities.provide(EXPORT_CAPABILITY, LeakyContributor(), instance_ref="leaky", owner="test")
    await create_user(module, "carol")
    await login(client, "carol")
    export_id = (await client.post("/api/v1/me/export")).json()["id"]
    with pytest.raises(ValueError, match="secrets"):
        await _build_pending(app, export_id)
    assert (await client.get(f"/api/v1/me/export/{export_id}")).json()["status"] == "queued"
