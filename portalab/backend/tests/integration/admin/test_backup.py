"""Issue 247 — a whole portal saved in one encrypted archive and brought back into a portal with another key:
members, settings and files come back, the secrets are encrypted again with the new key, what is transient
or left out (sessions, media images) does not travel; every schema is sorted for the backup."""

import asyncio
import json
from collections.abc import Iterable
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text

from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.secrets import SecretBox
from portalab.modules.administration.backup import archive
from portalab.modules.administration.backup.catalog import category_of
from portalab.modules.administration.config.service import Change
from portalab.modules.notifications import (
    settings as _notifications,  # noqa: F401 — declares the SMTP password
)
from portalab.modules.notifications.settings import SMTP_PASSWORD
from tests.authz_fixtures import TEST_APPLICATION_KEY
from tests.integration.identity.helpers import create_user, module_of
from tests.privacy_fixtures import make_full_platform

pytestmark = pytest.mark.integration

NEW_KEY = b"another-portal-application-key-0123456789"


class Same:
    """This portal's schema as the test says it compares with the archive's."""

    def __init__(self, heads: set[str], answer: str = "same") -> None:
        self.heads, self.answer = heads, answer

    async def current(self) -> set[str]:
        return self.heads

    async def compare(self, archive_heads: Iterable[str]) -> str:
        return self.answer

    async def prepare(self, archive_heads: Iterable[str]) -> None:
        raise AssertionError("not for the same schema")

    async def finish(self) -> None:
        raise AssertionError("not for the same schema")


PASSPHRASE = "correct horse battery staple"


async def test_every_schema_is_sorted(database: Database) -> None:
    async with database.session() as session:
        schemas = (
            await session.execute(
                text(
                    "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg\\_%' "
                    "AND nspname NOT IN ('information_schema', 'public')"
                )
            )
        ).scalars()
        unsorted = [s for s in schemas if category_of(f"{s}.any") is None]
    assert unsorted == [], f"declare these schemas in backup/catalog.py: {unsorted}"


async def test_round_trip_into_another_portal(database: Database, heads: set[str], tmp_path: Path) -> None:
    data = tmp_path / "data"
    full = make_full_platform(database, data / "blobs")
    await full.authz.catalog.sync()
    from portalab.app.main import create_app

    app = create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        static_dir=None,
    )
    alice: UUID = await create_user(module_of(app), "alice")
    config = full.administration.config
    await config.apply([Change(SMTP_PASSWORD, "s3cret-smtp")], Principal(user_id=alice), reason="t")
    (data / "blobs" / "avatars").mkdir(parents=True)
    (data / "blobs" / "avatars" / "alice.webp").write_bytes(b"avatar")
    (data / "blobs" / "media").mkdir(parents=True)
    (data / "blobs" / "media" / "poster.jpg").write_bytes(b"poster")
    async with database.unit_of_work() as uow:
        await uow.session.execute(
            text(
                "INSERT INTO identity.sessions (id, user_id, token_hash, created_at, last_seen_at, "
                "expires_at) SELECT gen_random_uuid(), :u, 'h', now(), now(), now() + interval '1 day'"
            ),
            {"u": alice},
        )

    target = data / "backups" / f"test{archive.SUFFIX}"
    manifest = await archive.create(
        database,
        data,
        TEST_APPLICATION_KEY,
        target,
        PASSPHRASE,
        options=archive.Options(history=False, media=False),
        heads=heads,
        site="Test",
    )
    assert manifest.counts["members"] >= 1
    names = {t["name"] for t in manifest.tables}
    assert "identity.users" in names and "identity.sessions" not in names and "core.job" not in names
    assert archive.inspect(target, PASSPHRASE)["site"] == "Test"
    assert [f["name"] for f in manifest.folders] == ["blobs/avatars"]

    # the new portal: what was there is gone, another key
    async with database.unit_of_work() as uow:
        await uow.session.execute(
            text("UPDATE identity.users SET login = 'someone-else' WHERE login = 'alice'")
        )
    (data / "blobs" / "avatars" / "alice.webp").unlink()
    result = await archive.restore(
        database,
        data,
        NEW_KEY,
        target,
        PASSPHRASE,
        capabilities=full.identity.capabilities,
        versions=Same(heads),
    )
    assert result["compatibility"] == "same"
    assert result["secrets"]["rewritten"] >= 1 and result["secrets"]["unreadable"] == 0
    async with database.session() as session:
        login = await session.scalar(text("SELECT login FROM identity.users WHERE id = :u"), {"u": alice})
        stored = await session.scalar(
            text("SELECT value FROM config.settings WHERE key = :k AND scope = 'global'"),
            {"k": SMTP_PASSWORD},
        )
        sessions = await session.scalar(text("SELECT count(*) FROM identity.sessions"))
    assert login == "alice"
    plain = SecretBox(NEW_KEY).decrypt(stored["enc"], context=f"config:{SMTP_PASSWORD}").reveal()
    assert json.loads(plain) == "s3cret-smtp"
    assert sessions == 0
    assert (data / "blobs" / "avatars" / "alice.webp").read_bytes() == b"avatar"
    assert (data / "blobs" / "media" / "poster.jpg").exists()  # not in the archive: left as it was

    with pytest.raises(archive.BackupError) as refused:  # saved by a later Portalab
        await archive.restore(
            database,
            data,
            NEW_KEY,
            target,
            PASSPHRASE,
            capabilities=full.identity.capabilities,
            versions=Same(heads, answer="newer"),
        )
    assert refused.value.code == "backup.newer"


def test_older_layouts_are_read_and_newer_refused() -> None:
    old = {"format": 1, "heads": ["x"], "tables": []}
    assert archive.upgrade_manifest(dict(old))["format"] == archive.FORMAT
    with pytest.raises(archive.BackupError) as refused:
        archive.upgrade_manifest({"format": archive.FORMAT + 1})
    assert refused.value.code == "backup.newer"


async def test_an_archive_of_an_older_schema_is_migrated_up(
    empty_db_url: str, migrated_db_url: str, heads: set[str], tmp_path: Path
) -> None:
    """Saved by a previous version (one module a revision behind): the new portal is brought back to that
    schema, the data loaded, then migrated up to this version — the data it held is still there."""
    from portalab.app.backup_versions import SchemaVersions
    from portalab.app.migrations import script, upgrade
    from portalab.capabilities.catalog import new_registry

    tree = script()
    behind = next(
        h for h in sorted(heads) if isinstance(tree.get_revision(h).down_revision, str)
    )  # a module's last revision, one step back
    older = (heads - {behind}) | {str(tree.get_revision(behind).down_revision)}
    for head in sorted(older):
        await asyncio.to_thread(upgrade, empty_db_url, head)
    source = Database.from_url(empty_db_url)
    target = Database.from_url(migrated_db_url)
    try:
        async with source.unit_of_work() as uow:
            await uow.session.execute(
                text(
                    "INSERT INTO config.settings (id, key, scope, scope_ref, value, schema_version, "
                    "updated_at) VALUES (gen_random_uuid(), 'ui.defaultTheme', 'global', '', '\"nova\"', 1, "
                    "now())"
                )
            )
        old_versions = SchemaVersions(source, empty_db_url)
        saved_heads = await old_versions.current()
        assert saved_heads != heads
        file = tmp_path / f"older{archive.SUFFIX}"
        await archive.create(
            source,
            tmp_path / "source",
            TEST_APPLICATION_KEY,
            file,
            PASSPHRASE,
            options=archive.Options(),
            heads=saved_heads,
            site="Old",
        )
        versions = SchemaVersions(target, migrated_db_url)
        assert await versions.compare(saved_heads) == "older"
        assert await old_versions.compare(heads) == "newer"
        result = await archive.restore(
            target,
            tmp_path / "target",
            NEW_KEY,
            file,
            PASSPHRASE,
            capabilities=new_registry(),
            versions=versions,
        )
        assert result["compatibility"] == "older"
        assert await versions.current() == heads
        async with target.session() as session:
            theme = await session.scalar(
                text("SELECT value FROM config.settings WHERE key = 'ui.defaultTheme' AND scope = 'global'")
            )
        assert theme == "nova"
    finally:
        await source.dispose()
        await target.dispose()
