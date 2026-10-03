"""023 T013 — a plugin's role cannot read core tables nor other plugins' schemas; it has a statement
timeout; its migrations run with its own role; it has no foreign keys to core tables."""

import pytest
from sqlalchemy import text

from portalab.modules.plugins.db.plugin_db import RoleBoundDb
from tests.integration.plugins.conftest import PlHarness

pytestmark = pytest.mark.integration
TABLE = {"0001_init.sql": "CREATE TABLE notes (id bigserial PRIMARY KEY, body text NOT NULL)"}


async def test_role_isolation(pl: PlHarness) -> None:
    await pl.installed(pl.package("alpha", migrations=TABLE))
    await pl.installed(pl.package("beta", migrations=TABLE))
    storage = pl.module.storage
    alpha = RoleBoundDb(pl.database, storage.role("alpha"), storage.schema("alpha"), 200)
    await alpha.execute("INSERT INTO notes (body) VALUES (:b)", {"b": "mine"})
    assert [dict(r) for r in await alpha.execute("SELECT body FROM notes")] == [{"body": "mine"}]
    for forbidden in (
        "SELECT count(*) FROM identity.users",
        "SELECT count(*) FROM plugins.plugins",
        "SELECT count(*) FROM plugin_beta.notes",
        "CREATE TABLE identity.hack (id int)",
    ):
        with pytest.raises(Exception, match="permission denied"):
            await alpha.execute(forbidden)
    with pytest.raises(Exception, match=r"statement timeout|canceling statement"):
        await alpha.execute("SELECT pg_sleep(1)")
    async with pl.database.session() as session:
        owner = await session.scalar(
            text("SELECT tableowner FROM pg_tables WHERE schemaname = 'plugin_alpha' AND tablename = 'notes'")
        )
        foreign = await session.scalar(
            text(
                "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
                "WHERE n.nspname = 'plugin_alpha' AND contype = 'f'"
            )
        )
    assert owner == storage.role("alpha") and foreign == 0
