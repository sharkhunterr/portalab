"""018 T005 — schema ``ai``: tables, ``(conversation_id, seq)`` unique, pending-action states, foreign keys
only intra-module or to ``identity.users``."""

import pytest
from sqlalchemy import text

from portalab.core.db import Database

pytestmark = pytest.mark.integration


async def test_schema(database: Database) -> None:
    async with database.session() as session:
        tables = set(
            (await session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'ai'"))).scalars()
        )
        foreign = set(
            (
                await session.execute(
                    text(
                        "SELECT confrelid::regclass::text FROM pg_constraint c JOIN pg_namespace n "
                        "ON n.oid = c.connamespace WHERE n.nspname = 'ai' AND contype = 'f'"
                    )
                )
            ).scalars()
        )
        unique = set(
            (
                await session.execute(
                    text(
                        "SELECT conname FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
                        "WHERE n.nspname = 'ai' AND contype IN ('u', 'c')"
                    )
                )
            ).scalars()
        )
    assert {"conversations", "messages", "pending_actions", "usage_daily"} <= tables
    assert all(f == "identity.users" or f.startswith("ai.") for f in foreign)
    assert {"uq_messages_seq", "ck_pending_actions_status", "ck_messages_role"} <= unique
    async with database.session() as session:
        with pytest.raises(Exception, match="ck_pending_actions_status"):
            await session.execute(
                text(
                    "INSERT INTO ai.pending_actions (id, user_id, tool, params, params_hash, summary, "
                    "status, created_at, expires_at) VALUES (gen_random_uuid(), gen_random_uuid(), 't', "
                    "'{}', 'h', 's', 'bogus', now(), now())"
                )
            )
