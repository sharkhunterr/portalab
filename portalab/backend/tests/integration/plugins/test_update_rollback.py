"""023 T025 — stage → compatibility → expand-only migration → ``pending_restart`` → restart → probation:
a clean probation finishes the update; a failing probation, a load failure or a failed migration rolls
back to the previous package with the data intact (``plugin.update_failed`` / ``plugin.rolled_back``);
destructive migration steps are refused; every version stays recorded."""

from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import text

from portalab.core.errors import Conflict, ValidationFailed
from tests.integration.plugins.conftest import SYSTEM, PlHarness

pytestmark = pytest.mark.integration
V1 = {"0001_init.sql": "CREATE TABLE notes (id bigserial PRIMARY KEY, body text NOT NULL)"}
V2 = {**V1, "0002_tags.sql": "ALTER TABLE notes ADD COLUMN tag text"}
DESTRUCTIVE = {**V2, "0003_drop.sql": "ALTER TABLE notes DROP COLUMN tag"}
CODE = """
from portalab.sdk import PluginContext


def register(ctx: PluginContext) -> None:
    ctx.permission("view", "See notes")
"""
BROKEN = """
from portalab.sdk import PluginContext


def register(ctx: PluginContext) -> None:
    raise RuntimeError("v4 is broken")
"""


async def events(pl: PlHarness, name: str) -> int:
    async with pl.database.session() as session:
        return int(
            await session.scalar(text("SELECT count(*) FROM events.events WHERE type = :t"), {"t": name}) or 0
        )


async def test_update_probation_and_rollbacks(pl: PlHarness) -> None:
    await pl.installed(pl.package("notes", "1.0.0", code=CODE, migrations=V1))
    db = pl.module.storage.bound("notes", 1000)
    await db.execute("INSERT INTO notes (body) VALUES ('kept')")
    with pytest.raises(Conflict):
        await pl.module.updates.stage(SYSTEM, "notes", pl.package("notes", "0.9.0", code=CODE, migrations=V1))

    run = await pl.module.updates.stage(
        SYSTEM, "notes", pl.package("notes", "2.0.0", code=CODE, migrations=V2)
    )
    assert run.status == "pending_restart"
    plugin = await pl.module.lifecycle.get("notes")
    assert plugin.state == "update_pending" and plugin.needs_restart and plugin.current_version == "1.0.0"
    run = await pl.module.updates.confirm_restart(SYSTEM, "notes")
    assert run.status == "probation" and (await pl.module.lifecycle.get("notes")).current_version == "2.0.0"
    pl.clock.advance(timedelta(minutes=pl.module.config.update_probation_minutes + 1))
    assert await pl.module.updates.probation() == 1
    assert await events(pl, "plugin.updated") == 1
    assert [r["tag"] for r in await db.execute("SELECT tag FROM notes")] == [None]  # expanded, data kept

    with pytest.raises(ValidationFailed) as refused:
        await pl.module.updates.stage(
            SYSTEM, "notes", pl.package("notes", "3.0.0", code=CODE, migrations=DESTRUCTIVE)
        )
    assert refused.value.code == "plugin.migration_refused"
    assert await events(pl, "plugin.update_failed") == 1
    assert (await pl.module.lifecycle.get("notes")).current_version == "2.0.0"

    await pl.module.updates.stage(SYSTEM, "notes", pl.package("notes", "4.0.0", code=BROKEN, migrations=V2))
    run = await pl.module.updates.confirm_restart(SYSTEM, "notes")  # loading 4.0.0 fails: back to 2.0.0
    assert run.status == "rolled_back" and (await pl.module.lifecycle.get("notes")).current_version == "2.0.0"
    assert await events(pl, "plugin.rolled_back") == 1

    pl.module.config = replace(pl.module.config, error_threshold=100)
    await pl.module.updates.stage(SYSTEM, "notes", pl.package("notes", "5.0.0", code=CODE, migrations=V2))
    await pl.module.updates.confirm_restart(SYSTEM, "notes")
    await pl.module.guard.record("notes", "route", "probation error")
    pl.clock.advance(timedelta(minutes=pl.module.config.update_probation_minutes + 1))
    await pl.module.updates.probation()
    assert (await pl.module.lifecycle.get("notes")).current_version == "2.0.0"
    assert await events(pl, "plugin.rolled_back") == 2
    assert [r["body"] for r in await db.execute("SELECT body FROM notes")] == ["kept"]
    async with pl.database.session() as session:
        versions = (
            (
                await session.execute(
                    text(
                        "SELECT version FROM plugins.versions "
                        "WHERE plugin_key = 'notes' ORDER BY installed_at, version"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert set(versions) == {"1.0.0", "2.0.0", "3.0.0", "4.0.0", "5.0.0"}
