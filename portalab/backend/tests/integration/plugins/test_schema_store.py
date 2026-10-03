"""023 T006 — schema: tables and append-only ``versions``/``purges``; the package checksum is verified on
load (a tampered package is refused); versions stay on disk for rollback; unsafe archives are refused."""

import zipfile

import pytest
from sqlalchemy import text

from portalab.core.errors import ValidationFailed
from tests.integration.plugins.conftest import SYSTEM, PlHarness

pytestmark = pytest.mark.integration


async def test_schema_and_store(pl: PlHarness) -> None:
    source = pl.package("tiny", "1.0.0", manifest={"extension_points": ["nav"]})
    key = await pl.installed(source, enable=False)
    async with pl.database.session() as session:
        tables = set(
            (
                await session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'plugins'"))
            ).scalars()
        )
        foreign = set(
            (
                await session.execute(
                    text(
                        "SELECT confrelid::regclass::text FROM pg_constraint c JOIN pg_namespace n "
                        "ON n.oid = c.connamespace WHERE n.nspname = 'plugins' AND contype = 'f'"
                    )
                )
            ).scalars()
        )
    assert {
        "plugins",
        "versions",
        "contributions",
        "reviews",
        "error_stats",
        "purges",
        "update_runs",
    } <= tables
    assert all(f == "identity.users" or f.startswith("plugins.") for f in foreign)
    async with pl.database.session() as session:
        with pytest.raises(Exception, match="append-only"):
            await session.execute(text("UPDATE plugins.versions SET sha256 = 'x'"))
    installed = pl.root / "installed" / key / "1.0.0"
    assert (installed / "plugin.toml").is_file()
    (installed / "plugin.toml").write_text((installed / "plugin.toml").read_text() + "\n# tampered\n")
    with pytest.raises(ValidationFailed) as refused:
        await pl.module.lifecycle.enable(SYSTEM, key)
    assert refused.value.code == "plugin.tampered"

    evil = pl.root / "available" / "evil.zip"
    with zipfile.ZipFile(evil, "w") as archive:
        archive.writestr("plugin.toml", 'key = "evil"\nname = "Evil"\nversion = "1.0.0"\n')
        archive.writestr("../../escape.txt", "x")
    with pytest.raises(ValidationFailed):
        await pl.module.lifecycle.install(SYSTEM, evil)
    assert not (pl.root.parent / "escape.txt").exists()
