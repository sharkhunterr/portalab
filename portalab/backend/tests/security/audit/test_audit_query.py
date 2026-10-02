"""021 T017 — ``audit.read`` required; non-Admin readers get redacted context, the Admin full context;
every read is itself audited; export honors filters."""

import json

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.core.audit_port import AuditRecord
from portalab.modules.authz.grants.service import GrantSpec
from portalab.modules.authz.models import BASE_ROLE_IDS, AuditEntry
from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.privacy_fixtures import FullPlatform

pytestmark = pytest.mark.integration


async def test_audit_reading_rules(app: FastAPI, client: httpx.AsyncClient, full: FullPlatform) -> None:
    identity = module_of(app)
    admin_id = await create_user(identity, "boss")
    await make_admin(full, admin_id)
    support_id = await create_user(identity, "helper")
    await create_user(identity, "plain")
    await full.authz.grants.add_grant(None, "role", BASE_ROLE_IDS["support"], GrantSpec("audit.read"))
    async with full.database.unit_of_work():
        pass
    from tests.authz_fixtures import user

    await full.authz.grants.assign_role(user(admin_id), support_id, "support")
    await full.authz.audit.record(
        None, AuditRecord(action="test.secretive", actor=None, context={"note": "detail"})
    )

    await login(client, "plain")
    assert (await client.get("/api/v1/audit")).status_code == 403

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as helper:
        await login(helper, "helper")
        page = (await helper.get("/api/v1/audit", params={"action": "test."})).json()
        assert [item["action"] for item in page["items"]] == ["test.secretive"]
        assert page["items"][0]["context"] == {"redacted": True, "keys": ["note"]}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as boss:
        await login(boss, "boss")
        full_page = (await boss.get("/api/v1/audit", params={"action": "test."})).json()
        assert full_page["items"][0]["context"] == {"note": "detail"}
        export = await boss.get("/api/v1/audit/export", params={"action": "test."})
        lines = [json.loads(line) for line in export.text.splitlines()]
        assert export.headers["content-type"].startswith("application/x-ndjson")
        assert [line["action"] for line in lines] == ["test.secretive"]

    async with full.database.session() as session:
        reads = list(
            (
                await session.execute(
                    select(AuditEntry.action).where(AuditEntry.action.in_(["audit.read", "audit.exported"]))
                )
            ).scalars()
        )
    assert reads.count("audit.read") == 2 and reads.count("audit.exported") == 1


async def test_pagination(app: FastAPI, full: FullPlatform) -> None:
    admin_id = await create_user(module_of(app), "boss")
    await make_admin(full, admin_id)
    for index in range(5):
        await full.authz.audit.record(None, AuditRecord(action=f"page.{index}", actor=None))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as boss:
        await login(boss, "boss")
        first = (await boss.get("/api/v1/audit", params={"action": "page.", "limit": 3})).json()
        second = (
            await boss.get(
                "/api/v1/audit", params={"action": "page.", "limit": 3, "cursor": first["next_cursor"]}
            )
        ).json()
    assert [i["action"] for i in first["items"]] == ["page.4", "page.3", "page.2"]
    assert [i["action"] for i in second["items"]] == ["page.1", "page.0"] and second["next_cursor"] is None
