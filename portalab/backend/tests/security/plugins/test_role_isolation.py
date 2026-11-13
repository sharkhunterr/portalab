"""023 T013 — a plugin's role cannot read core tables nor other plugins' schemas; it has a statement
timeout; its migrations run with its own role; it has no foreign keys to core tables."""

import pytest
from sqlalchemy import text

from tests.integration.plugins.conftest import PlHarness

pytestmark = pytest.mark.integration
TABLE = {"0001_init.sql": "CREATE TABLE notes (id bigserial PRIMARY KEY, body text NOT NULL)"}


async def test_role_isolation(pl: PlHarness) -> None:
    await pl.installed(pl.package("alpha", migrations=TABLE))
    await pl.installed(pl.package("beta", migrations=TABLE))
    storage = pl.module.storage
    alpha = storage.bound("alpha", 200)
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


ESCAPES = (
    # issue 396: SET LOCAL ROLE is no boundary for SQL the plugin writes — Postgres lets any role the
    # *session* user belongs to be taken back; each of these must stay inside the plugin's role
    "DO $$ BEGIN EXECUTE 'RESET ROLE'; PERFORM count(*) FROM identity.users; END $$",
    "DO $$ BEGIN EXECUTE 'SET ROLE NONE'; PERFORM count(*) FROM identity.users; END $$",
    "SELECT set_config('role', 'none', true), (SELECT count(*) FROM identity.users)",
    "DO $$ BEGIN PERFORM set_config('statement_timeout', '0', true); PERFORM pg_sleep(1); END $$",
)


@pytest.mark.parametrize("attack", ESCAPES)
async def test_a_plugin_cannot_leave_its_role(pl: PlHarness, attack: str) -> None:
    await pl.installed(pl.package("alpha", migrations=TABLE))
    storage = pl.module.storage
    alpha = storage.bound("alpha", 200)
    with pytest.raises(
        Exception, match=r"permission denied|statement timeout|canceling statement|not allowed"
    ):
        await alpha.execute(attack)


async def test_a_plugin_migration_cannot_leave_its_role(pl: PlHarness) -> None:
    escape = {"0001_init.sql": "RESET ROLE; CREATE TABLE identity.hack (id int)"}
    with pytest.raises(Exception, match=r"permission denied|not allowed|refused"):
        await pl.installed(pl.package("alpha", migrations=escape))
    async with pl.database.session() as session:
        made = await session.scalar(text("SELECT to_regclass('identity.hack') IS NOT NULL"))
    assert made is False
