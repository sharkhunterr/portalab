"""002 T009 — the identity migration: tables, partial unique indexes, append-only history."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from portalab.core.db import Database

TABLES = {
    "users",
    "credentials",
    "sessions",
    "login_throttle",
    "verification_tokens",
    "profiles",
    "profile_fields",
    "account_state_history",
    "deletion_requests",
    "onboarding_progress",
    "export_jobs",
    "external_identities",  # 027: single sign-on accounts linked to members
    "oidc_logins",  # 027: single sign-ons in progress
}

INSERT_USER = (
    "INSERT INTO identity.users (id, login, display_name, display_name_key, state, transition_seq, "
    "state_changed_at, created_at, updated_at) "
    "VALUES (:id, :login, :name, :key, :state, 1, now(), now(), now())"
)


async def _insert_user(
    conn: AsyncConnection, *, login: str | None, key: str | None, state: str = "active"
) -> UUID:
    user_id = uuid4()
    await conn.execute(
        text(INSERT_USER), {"id": user_id, "login": login, "name": key, "key": key, "state": state}
    )
    return user_id


async def test_tables_exist(database: Database) -> None:
    async with database.engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'identity'")
        )
        assert {row[0] for row in rows} == TABLES


async def test_login_and_display_name_key_are_unique_but_nullable(database: Database) -> None:
    async with database.engine.begin() as conn:
        await _insert_user(conn, login="alice", key="alice")
        # tombstoned rows release both values: several NULLs coexist
        await _insert_user(conn, login=None, key=None, state="deleted")
        await _insert_user(conn, login=None, key=None, state="deleted")
    with pytest.raises(IntegrityError, match="uq_users_login"):
        async with database.engine.begin() as conn:
            await _insert_user(conn, login="alice", key="other")
    with pytest.raises(IntegrityError, match="uq_users_display_name_key"):
        async with database.engine.begin() as conn:
            await _insert_user(conn, login="bob", key="alice")


async def test_state_check_constraint(database: Database) -> None:
    with pytest.raises(IntegrityError, match="ck_users_state"):
        async with database.engine.begin() as conn:
            await _insert_user(conn, login="carol", key="carol", state="banned")


async def test_partial_indexes_are_partial(database: Database) -> None:
    async with database.engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'identity'")
        )
        definitions = {row[0]: row[1] for row in rows}
    assert "WHERE (login IS NOT NULL)" in definitions["uq_users_login"]
    assert "WHERE (display_name_key IS NOT NULL)" in definitions["uq_users_display_name_key"]
    assert "pending_deletion" in definitions["ix_users_deletion_due_at"]
    assert "cancelled_at IS NULL" in definitions["uq_deletion_requests_open"]


async def test_account_state_history_is_append_only(database: Database) -> None:
    async with database.engine.begin() as conn:
        user_id = await _insert_user(conn, login="dave", key="dave")
        await conn.execute(
            text(
                "INSERT INTO identity.account_state_history (id, user_id, transition_seq, to_state, "
                "actor_kind, reason, occurred_at, received_at) "
                "VALUES (:id, :user, 1, 'active', 'system', 'test', now(), now())"
            ),
            {"id": uuid4(), "user": user_id},
        )
    for statement in (
        "UPDATE identity.account_state_history SET reason = 'tampered'",
        "DELETE FROM identity.account_state_history",
        "TRUNCATE identity.account_state_history",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            async with database.engine.begin() as conn:
                await conn.execute(text(statement))
