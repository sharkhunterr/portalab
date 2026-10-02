"""020 T028 — single-Admin handling on admin surfaces: the transfer flow is identity's (002), admin
permissions are sensitive (audited allow and deny), and no temporary role delegation exists anywhere."""

import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.app.security import api_routes
from portalab.modules.authz.models import AuditEntry, Permission
from tests.authz_fixtures import insert_user, user
from tests.privacy_fixtures import FullPlatform

pytestmark = pytest.mark.integration


async def test_admin_permissions_are_sensitive_and_audited(full: FullPlatform) -> None:
    async with full.database.session() as session:
        rows = {
            p.key: p
            for p in (
                await session.execute(
                    select(Permission).where(Permission.declared_by == "module:administration")
                )
            ).scalars()
        }
    assert set(rows) == {"configuration.manage", "modules.manage", "plugins.manage", "connectors.manage"}
    assert all(row.sensitive for row in rows.values())
    plain = user(await insert_user(full.database))
    assert not await full.authz.engine.is_allowed(plain, "configuration.manage")
    async with full.database.session() as session:
        denied = (
            (
                await session.execute(
                    select(AuditEntry).where(AuditEntry.action == "authorize:configuration.manage")
                )
            )
            .scalars()
            .all()
        )
    assert [entry.decision for entry in denied] == ["deny"]


def test_no_delegation_or_second_transfer_route(app: FastAPI) -> None:
    paths = {route.path for route in api_routes(app.routes)}
    assert "/api/v1/admin/transfer" in paths  # the only Admin hand-over (spec 002)
    assert not [path for path in paths if "delegat" in path or "impersonat" in path]
    schemas = str(app.openapi()["components"]["schemas"]).lower()
    assert "expires_at" not in str(app.openapi()["components"]["schemas"].get("RoleAssignment", {}))
    assert "delegat" not in schemas
