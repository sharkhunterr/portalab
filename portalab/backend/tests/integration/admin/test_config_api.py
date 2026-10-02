"""020 T011/T012 — set/get across scopes, 422 on invalid values, sensitive values write-only (never returned,
logged or exported), history + audit entry with redacted values; validate has no side effects; apply is
idempotent per Idempotency-Key and emits ``admin.config_changed`` once."""

import io
import logging

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.core.event_port import OutboxEvent
from portalab.core.logging import JsonFormatter
from portalab.modules.administration.models import Setting, SettingHistory
from portalab.modules.authz.models import AuditEntry
from tests.authz_fixtures import make_admin
from tests.integration.admin.settings_fixture import test_settings  # noqa: F401 — fixture
from tests.integration.identity.helpers import create_user, login, module_of
from tests.privacy_fixtures import FullPlatform

pytestmark = pytest.mark.usefixtures("test_settings")


async def _admin(app: FastAPI, full: FullPlatform, client: httpx.AsyncClient) -> None:
    admin_id = await create_user(module_of(app), "boss")
    await make_admin(full, admin_id)
    await login(client, "boss")


async def test_set_get_and_sensitive_write_only(
    app: FastAPI, client: httpx.AsyncClient, full: FullPlatform
) -> None:
    await _admin(app, full, client)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logging.getLogger().addHandler(handler)
    try:
        response = await client.put(
            "/api/v1/admin/config",
            json={
                "changes": [
                    {"key": "demo.pageSize", "value": 50},
                    {"key": "demo.apiToken", "value": "s3cr3t-value"},
                ]
            },
        )
        assert response.status_code == 200 and response.json() == {"applied": True}
        config = (await client.get("/api/v1/admin/config")).json()
    finally:
        logging.getLogger().removeHandler(handler)
    items = {item["key"]: item for item in config["settings"]}
    assert items["demo.pageSize"]["value"] == 50 and items["demo.pageSize"]["source"] == "global"
    assert items["demo.apiToken"]["value"] == "***" and items["demo.apiToken"]["sensitive"]
    assert (await full.administration.config.get("demo.apiToken")).value == "s3cr3t-value"  # internal read
    async with full.database.session() as session:
        stored = (
            await session.execute(select(Setting.value).where(Setting.key == "demo.apiToken"))
        ).scalar_one()
        history = (await session.execute(select(SettingHistory))).scalars().all()
        audit_contexts = (
            (
                await session.execute(
                    select(AuditEntry.context).where(AuditEntry.action == "admin.config_changed")
                )
            )
            .scalars()
            .all()
        )
    assert "s3cr3t-value" not in str(stored) and str(stored).startswith("{'enc': 'v1:")
    assert {(h.key, str(h.new_value_redacted)) for h in history} >= {
        ("demo.apiToken", "***"),
        ("demo.pageSize", "50"),
    }
    assert "s3cr3t-value" not in str(audit_contexts) and "s3cr3t-value" not in stream.getvalue()
    export = (await client.post("/api/v1/admin/config/export")).json()
    assert (
        "demo.apiToken" not in {entry["key"] for entry in export["settings"]}
        and export["format_version"] == 1
    )

    invalid = await client.put(
        "/api/v1/admin/config", json={"changes": [{"key": "demo.pageSize", "value": "many"}]}
    )
    assert invalid.status_code == 422 and invalid.json()["code"] == "admin.invalid_value"
    unknown = await client.put("/api/v1/admin/config", json={"changes": [{"key": "demo.nope", "value": 1}]})
    assert unknown.status_code == 404
    scope = await client.put(
        "/api/v1/admin/config",
        json={"changes": [{"key": "demo.pageSize", "value": 1, "scope": "plugin", "scope_ref": "x"}]},
    )
    assert scope.status_code == 422 and scope.json()["code"] == "admin.scope_not_allowed"


async def test_validate_then_idempotent_apply(
    app: FastAPI, client: httpx.AsyncClient, full: FullPlatform
) -> None:
    await _admin(app, full, client)
    body = {"changes": [{"key": "demo.pageSize", "value": 30}]}
    preview = (await client.post("/api/v1/admin/config/validate", json=body)).json()
    assert preview["ok"] and preview["diff"] == [
        {"key": "demo.pageSize", "scope": "global", "before": None, "after": 30}
    ]
    assert (await full.administration.config.get("demo.pageSize")).value == 20  # no side effect
    bad = (
        await client.post(
            "/api/v1/admin/config/validate", json={"changes": [{"key": "demo.pageSize", "value": "x"}]}
        )
    ).json()
    assert not bad["ok"] and bad["errors"][0]["code"] == "admin.invalid_value"
    for _ in range(2):
        response = await client.put(
            "/api/v1/admin/config", json=body, headers={"Idempotency-Key": "change-42"}
        )
    assert response.json() == {"applied": False}  # retry: nothing re-applied
    async with full.database.session() as session:
        events = (
            (
                await session.execute(
                    select(OutboxEvent.type).where(OutboxEvent.type == "admin.config_changed")
                )
            )
            .scalars()
            .all()
        )
    assert len(events) == 1
    assert (await full.administration.config.get("demo.pageSize")).value == 30


async def test_requires_configuration_manage(app: FastAPI, client: httpx.AsyncClient) -> None:
    await create_user(module_of(app), "plain")
    await login(client, "plain")
    assert (await client.get("/api/v1/admin/config")).status_code == 403
