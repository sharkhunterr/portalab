"""003 T004 — authz/audit schemas: single active Admin assignment, reserved-permission trigger,
append-only audit entries, seeded base roles and Admin singleton."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from portalab.core.db import Database
from portalab.modules.authz.models import ADMIN_ROLE_ID, BASE_ROLE_IDS
from tests.authz_fixtures import AuthzPlatform, insert_user


async def test_seeded_roles_and_singleton(database: Database) -> None:
    async with database.engine.connect() as conn:
        roles = dict((await conn.execute(text("SELECT key, id FROM authz.roles WHERE system"))).all())
        singleton = (
            await conn.execute(text("SELECT id, current_admin_user_id FROM authz.admin_singleton"))
        ).all()
    assert roles == BASE_ROLE_IDS
    assert [tuple(row) for row in singleton] == [(1, None)]


async def test_at_most_one_active_admin_assignment(database: Database) -> None:
    first, second = await insert_user(database), await insert_user(database)
    insert = text(
        "INSERT INTO authz.user_roles (id, user_id, role_id, granted_at) VALUES (:id, :user, :role, now())"
    )
    async with database.engine.begin() as conn:
        await conn.execute(insert, {"id": uuid4(), "user": first, "role": ADMIN_ROLE_ID})
    with pytest.raises(IntegrityError, match="uq_user_roles_single_admin"):
        async with database.engine.begin() as conn:
            await conn.execute(insert, {"id": uuid4(), "user": second, "role": ADMIN_ROLE_ID})
    async with database.engine.begin() as conn:  # a revoked assignment frees the slot
        await conn.execute(text("UPDATE authz.user_roles SET revoked_at = now()"))
        await conn.execute(insert, {"id": uuid4(), "user": second, "role": ADMIN_ROLE_ID})


async def test_reserved_permission_trigger(platform: AuthzPlatform) -> None:
    insert = text(
        "INSERT INTO authz.grants (id, holder_kind, holder_id, permission_key, effect, scope_kind, "
        "scope_ref, "
        "source, created_at) VALUES (:id, :kind, :holder, :key, 'allow', 'global', '', 'test', now())"
    )
    with pytest.raises(DBAPIError, match="reserved permission"):
        async with platform.database.engine.begin() as conn:
            await conn.execute(
                insert,
                {
                    "id": uuid4(),
                    "kind": "role",
                    "holder": BASE_ROLE_IDS["editor"],
                    "key": "users.admin.transfer",
                },
            )
    async with platform.database.engine.begin() as conn:  # the Admin role itself may hold it
        await conn.execute(
            insert, {"id": uuid4(), "kind": "role", "holder": ADMIN_ROLE_ID, "key": "users.admin.transfer"}
        )


async def test_audit_entries_are_append_only(database: Database) -> None:
    async with database.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO audit.audit_entries (id, occurred_at, received_at, actor_kind, action, "
                "decision, "
                "result) VALUES (:id, now(), now(), 'system', 'test', 'n/a', 'n/a')"
            ),
            {"id": uuid4()},
        )
    for statement in (
        "UPDATE audit.audit_entries SET action = 'tampered'",
        "DELETE FROM audit.audit_entries",
        "TRUNCATE audit.audit_entries",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            async with database.engine.begin() as conn:
                await conn.execute(text(statement))
