"""021 T004 — one active policy per (subject, class) including class-wide; retention_runs and
audit_checkpoints are append-only."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from portalab.core.db import Database

INSERT_POLICY = text(
    "INSERT INTO privacy.visibility_policies (id, subject_user_id, datum_class, mode, level, reason, set_at) "
    "VALUES (:id, NULL, 'profile_field', 'force_private', 'private', 'r', now())"
)


async def test_one_active_class_wide_policy(database: Database) -> None:
    async with database.engine.begin() as conn:
        await conn.execute(INSERT_POLICY, {"id": uuid4()})
    with pytest.raises(IntegrityError, match="uq_visibility_policies_active"):
        async with database.engine.begin() as conn:
            await conn.execute(INSERT_POLICY, {"id": uuid4()})


@pytest.mark.parametrize(
    ("table", "insert"),
    [
        (
            "privacy.retention_runs",
            "INSERT INTO privacy.retention_runs "
            "(target, data_class, action, rows_affected, cutoff, run_at, status) "
            "VALUES ('t', 'technical', 'delete', 0, now(), now(), 'applied')",
        ),
        (
            "audit.audit_checkpoints",
            "INSERT INTO audit.audit_checkpoints "
            "(from_seq, to_seq, entry_count, batch_hash, prev_checkpoint_hash, "
            "checkpoint_hash, created_at) VALUES (1, 1, 0, 'a', 'b', 'c', now())",
        ),
    ],
)
async def test_append_only(database: Database, table: str, insert: str) -> None:
    async with database.engine.begin() as conn:
        await conn.execute(text(insert))
    for statement in (
        f"UPDATE {table} SET created_at = now()"
        if "checkpoints" in table
        else f"UPDATE {table} SET status = 'x'",
        f"DELETE FROM {table}",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            async with database.engine.begin() as conn:
                await conn.execute(text(statement))
