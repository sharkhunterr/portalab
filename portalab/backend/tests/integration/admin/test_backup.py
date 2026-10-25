"""Issue 247 — a whole portal saved in one encrypted archive and brought back into a portal with another key:
members, settings and files come back, the secrets are encrypted again with the new key, what is transient
or left out (sessions, media images) does not travel; every schema is sorted for the backup."""

import json
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
        heads=heads,
    )
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

    with pytest.raises(archive.BackupError):
        await archive.restore(
            database,
            data,
            NEW_KEY,
            target,
            PASSPHRASE,
            capabilities=full.identity.capabilities,
            heads={"another"},
        )
