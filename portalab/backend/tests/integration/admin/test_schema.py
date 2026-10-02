"""020 T004 — unique (key, scope, scope_ref); setting_history append-only; exactly one first_run row."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from portalab.core.db import Database

INSERT = text(
    "INSERT INTO config.settings (id, key, scope, scope_ref, value, schema_version, updated_at) "
    "VALUES (:id, 'demo.k', 'global', '', '1', 1, now())"
)


async def test_unique_key_scope(database: Database) -> None:
    async with database.engine.begin() as conn:
        await conn.execute(INSERT, {"id": uuid4()})
    with pytest.raises(IntegrityError, match="uq_settings_key_scope"):
        async with database.engine.begin() as conn:
            await conn.execute(INSERT, {"id": uuid4()})


async def test_history_append_only_and_single_first_run(database: Database) -> None:
    async with database.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO config.setting_history "
                "(key, scope, scope_ref_hash, actor_id, changed_at, reason) "
                "VALUES ('k', 'global', '', NULL, now(), '')"
            )
        )
        assert (await conn.execute(text("SELECT count(*) FROM admin.first_run"))).scalar() == 1
    with pytest.raises(DBAPIError, match="append-only"):
        async with database.engine.begin() as conn:
            await conn.execute(text("DELETE FROM config.setting_history"))
    with pytest.raises(IntegrityError, match="ck_first_run_single_row"):
        async with database.engine.begin() as conn:
            await conn.execute(text("INSERT INTO admin.first_run (id) VALUES (2)"))
