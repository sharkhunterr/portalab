"""019 T031 — no secrets in definitions, executions or audit; trigger payload bodies never persisted; the
history exposes references only; non-admins cannot read or author; hostile definitions are rejected."""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.automations.conftest import AutoHarness, basic
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_privacy_and_hostile_input(au: AutoHarness, client: AsyncClient) -> None:
    automation = await au.automation("private", basic())
    await au.emit({"value": 4, "label": "my very private note"})
    async with au.database.session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT trigger_ref::text, conditions_trace::text, steps::text "
                    "FROM automations.executions"
                )
            )
        ).all()
        audits = (
            (
                await session.execute(
                    text("SELECT context::text FROM audit.audit_entries WHERE action LIKE 'automation.%'")
                )
            )
            .scalars()
            .all()
        )
    stored = json.dumps([list(r) for r in rows]) + json.dumps(audits)
    assert "my very private note" not in stored and "x" * 100 not in stored
    await login(client, "ursula")
    for method, path in (
        ("GET", "/api/v1/admin/automations"),
        ("GET", f"/api/v1/admin/automations/{automation}"),
        ("POST", "/api/v1/admin/automations"),
    ):
        assert (
            await client.request(method, path, json={"key": "x1", "definition": basic()})
        ).status_code == 403
    await login(client, "boss")
    hostile = [
        basic(name="x" * 1000),
        basic(steps=[{"id": f"s{i}", "action": "test.record"} for i in range(60)]),
        basic(
            conditions={
                "all_of": [
                    {"all_of": [{"all_of": [{"all_of": [{"leaf": "user_is", "params": {"users": []}}]}]}]}
                ]
            }
        ),
        basic(steps=[{"id": "x", "action": "test.record", "params": {"text": "${__import__('os')}"}}]),
    ]
    for definition in hostile:
        response = await client.post(
            "/api/v1/admin/automations", json={"key": "hostile", "definition": definition}
        )
        assert response.status_code == 422, definition
