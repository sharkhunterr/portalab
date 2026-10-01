"""T038 — append-only tables: UPDATE/DELETE rejected by the database; correction rows are inserted."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from portalab.core.append_only import append_only_ddl
from portalab.core.db import Database


async def _setup(database: Database) -> None:
    async with database.engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA ledgertest"))
        await conn.execute(
            text(
                "CREATE TABLE ledgertest.entry (id serial PRIMARY KEY, amount bigint NOT NULL, "
                "reverses integer REFERENCES ledgertest.entry(id))"
            )
        )
        for statement in append_only_ddl("ledgertest", "entry"):
            await conn.execute(text(statement))
        await conn.execute(text("INSERT INTO ledgertest.entry (amount) VALUES (100)"))


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE ledgertest.entry SET amount = 1 WHERE id = 1",
        "DELETE FROM ledgertest.entry WHERE id = 1",
        "TRUNCATE ledgertest.entry",
    ],
)
async def test_mutations_are_rejected(database: Database, statement: str) -> None:
    await _setup(database)
    with pytest.raises(DBAPIError, match="append-only"):
        async with database.engine.begin() as conn:
            await conn.execute(text(statement))
    async with database.engine.connect() as conn:
        assert (
            await conn.execute(text("SELECT amount FROM ledgertest.entry WHERE id = 1"))
        ).scalar_one() == 100


async def test_correction_is_a_new_row(database: Database) -> None:
    await _setup(database)
    async with database.engine.begin() as conn:
        await conn.execute(text("INSERT INTO ledgertest.entry (amount, reverses) VALUES (-100, 1)"))
    async with database.engine.connect() as conn:
        rows = (await conn.execute(text("SELECT amount FROM ledgertest.entry ORDER BY id"))).scalars().all()
    assert rows == [100, -100]
