"""Issue 392 — a backup brought into a new portal block by block: the blocks ticked and what they need, the
Admin's account always, the other members only when asked for; what the members left out made is handed to the
Admin, what was theirs stays out; no combination leaves a row pointing at nothing; every block ticked gives
the whole portal, as before."""

import json
import random
import secrets
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from portalab.app.demo_seed import seed_demo
from portalab.app.migrations import expected_heads
from portalab.app.wiring import Platform, wire_platform
from portalab.capabilities.catalog import new_registry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.secrets import SecretBox
from portalab.modules.administration.backup import archive
from portalab.modules.administration.backup.blocks import (
    ALWAYS,
    ALWAYS_MODULES,
    BLOCKS,
    MEMBER_COLUMNS,
    MEMBER_TABLES,
    MEMBERS,
    close,
    needed,
)
from portalab.modules.administration.backup.catalog import category_of
from portalab.modules.administration.config.service import Change
from portalab.modules.notifications.settings import SMTP_PASSWORD
from tests.integration.admin.test_backup import PASSPHRASE, Same
from tests.integration.conftest import _with_database, create_database, drop_database

pytestmark = pytest.mark.integration

CAPABILITIES = new_registry()
SOURCE_KEY = secrets.token_bytes(32)
HEADS = expected_heads("postgresql+asyncpg://unused/unused")
NEW_KEY = secrets.token_bytes(32)
MODULES = Path(__file__).parents[3] / "src" / "portalab" / "modules"
# a column naming a member, by its name (its type a uuid)
MEMBER_LIKE = ("user", "member", "author", "actor", "owner", "creator", "recipient", "requester", "assignee")


def _dsn(url: str) -> str:
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


# --- the catalog -------------------------------------------------------------------------------------------
async def test_every_schema_and_module_belongs_to_a_block(database: Database) -> None:
    async with database.session() as session:
        schemas = set(
            (
                await session.execute(
                    text(
                        "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg\\_%' "
                        "AND nspname NOT IN ('information_schema', 'public')"
                    )
                )
            ).scalars()
        )
    sorted_schemas = set(ALWAYS) | {s for b in BLOCKS for s in b.schemas}
    assert schemas - sorted_schemas == set(), "sort these schemas in backup/blocks.py"
    modules = {p.name for p in MODULES.iterdir() if p.is_dir() and not p.name.startswith("_")}
    sorted_modules = set(ALWAYS_MODULES) | {m for b in BLOCKS for m in b.modules}
    assert modules - sorted_modules == set(), "sort these modules (their settings) in backup/blocks.py"


async def test_every_column_naming_a_member_is_sorted(migrated_db_url: str) -> None:
    conn = await asyncpg.connect(_dsn(migrated_db_url))
    try:
        columns = await conn.fetch(
            """
            SELECT n.nspname || '.' || c.relname AS tbl, a.attname AS col
              FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE c.relkind IN ('r', 'p') AND NOT c.relispartition AND a.attnum > 0 AND NOT a.attisdropped
               AND a.atttypid = 'uuid'::regtype AND n.nspname NOT IN ('identity')
               AND NOT EXISTS (
                   SELECT 1 FROM pg_constraint k WHERE k.contype = 'f' AND k.conrelid = c.oid
                      AND a.attnum = ANY (k.conkey))
            """
        )
    finally:
        await conn.close()
    unsorted = [
        f"{r['tbl']}.{r['col']}"
        for r in columns
        if category_of(r["tbl"]) in ("data", "history", "media")
        and (any(word in r["col"] for word in MEMBER_LIKE) or r["col"].endswith("_by"))
        and (r["tbl"], r["col"]) not in MEMBER_COLUMNS
        and r["tbl"] not in MEMBER_TABLES
    ]
    assert unsorted == [], f"say in backup/blocks.py MEMBER_COLUMNS what becomes of: {unsorted}"


def test_a_block_brings_what_it_needs() -> None:
    assert close(["marketplace"]).blocks == {"marketplace", "gamification"}
    assert close(["statistics"]).blocks == {"statistics", "media", "services"}
    assert needed(["marketplace", "automations"]) == {
        "gamification": ["marketplace"],
        "services": ["automations"],
    }
    with pytest.raises(ValueError):
        close(["nothing-of-the-kind"])


# --- bringing blocks in ------------------------------------------------------------------------------------
@pytest.fixture
async def fresh_portals(admin_url: str, migrated_template: str) -> AsyncIterator[Any]:
    """New portals, each its own database migrated to this version (dropped afterwards)."""
    made: list[tuple[str, Database]] = []

    async def new() -> Database:
        name = await create_database(admin_url, template=migrated_template)
        db = Database.from_url(_with_database(admin_url, name), poolclass=NullPool)
        made.append((name, db))
        return db

    try:
        yield new
    finally:
        for name, db in made:
            await db.dispose()
            await drop_database(admin_url, name)


async def _seeded(database: Database, tmp_path: Path) -> tuple[Platform, UUID]:
    platform = wire_platform(
        database, data_dir=tmp_path / "data", capabilities=CAPABILITIES, secret_key=SOURCE_KEY
    )
    await platform.authz.catalog.sync()
    await platform.refresh_config()
    admin = await platform.identity.bootstrap.create_first_admin(
        login="admin", password=secrets.token_urlsafe(16), display_name="Admin", email=None
    )
    report = await seed_demo(platform, users_file=tmp_path / "secrets" / "demo_users")
    assert report.ok, report.steps
    await platform.administration.config.apply(
        [Change(SMTP_PASSWORD, "s3cret-smtp")], Principal(user_id=admin), reason="t"
    )
    # the demo grants nothing (#94): the members earn something of their own
    async with database.session() as session:
        people = list(
            (
                await session.execute(text("SELECT id FROM identity.users WHERE id <> :a"), {"a": admin})
            ).scalars()
        )
    for index, member in enumerate(people[:3]):
        for value in ("xp", "coins"):
            await platform.gamification.rewards.grant_manual(
                Principal(user_id=admin),
                member,
                value,
                25,
                reason="earned",
                idempotency_key=f"{value}-{index}",
            )
    return platform, admin


async def _count(db: Database, table: str, where: str = "true") -> int:
    async with db.session() as session:
        return int(await session.scalar(text(f"SELECT count(*) FROM {table} WHERE {where}")) or 0)


# what belongs to the members themselves
THEIRS = (
    "gamification.transactions",
    "gamification.balances",
    "gamification.user_achievements",
    "marketplace.ownerships",
    "community.participations",
)


async def _theirs(db: Database) -> dict[str, int]:
    return {table: await _count(db, table) for table in THEIRS}


async def _dangling(db: Database) -> list[str]:
    """Every foreign key's rows pointing at nothing (the load sets the checks aside: this is what replaces
    them)."""
    async with db.session() as session:
        keys = (
            await session.execute(
                text(
                    """
                    SELECT k.conrelid::regclass::text AS src, k.confrelid::regclass::text AS dst,
                           array_agg(a.attname ORDER BY x.n) AS cols,
                           array_agg(b.attname ORDER BY x.n) AS refs
                      FROM pg_constraint k
                      CROSS JOIN LATERAL unnest(k.conkey, k.confkey) WITH ORDINALITY AS x(s, d, n)
                      JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = x.s
                      JOIN pg_attribute b ON b.attrelid = k.confrelid AND b.attnum = x.d
                      JOIN pg_class c ON c.oid = k.conrelid
                     WHERE k.contype = 'f' AND NOT c.relispartition
                     GROUP BY k.oid, k.conrelid, k.confrelid
                    """
                )
            )
        ).all()
        found = []
        for src, dst, cols, refs in keys:
            match = " AND ".join(f'p."{r}" = t."{c}"' for c, r in zip(cols, refs, strict=True))
            filled = " AND ".join(f't."{c}" IS NOT NULL' for c in cols)
            sql = (
                f"SELECT count(*) FROM {src} t WHERE {filled} "
                f"AND NOT EXISTS (SELECT 1 FROM {dst} p WHERE {match})"
            )
            if await session.scalar(text(sql)):
                found.append(f"{src}({', '.join(cols)}) -> {dst}")
    return found


async def _restore(
    target: Database, path: Path, data: Path, platform: Platform, blocks: list[str] | None
) -> dict:
    owners = {d.key: d.owner for d in platform.administration.registry.all()}
    return await archive.restore(
        target,
        data,
        NEW_KEY,
        path,
        PASSPHRASE,
        capabilities=CAPABILITIES,
        versions=Same(HEADS),
        selection=None if blocks is None else close(blocks),
        setting_owner=owners.get,
    )


async def test_a_new_portal_takes_only_the_blocks_ticked(
    database: Database, heads: set[str], fresh_portals: Any, tmp_path: Path
) -> None:
    platform, admin = await _seeded(database, tmp_path)
    members = await _count(database, "identity.users")
    products = await _count(database, "marketplace.products")
    quests = await _count(database, "gamification.quests")
    theirs = await _theirs(database)
    assert members > 1 and products and quests and sum(theirs.values()), theirs
    path = tmp_path / f"portal{archive.SUFFIX}"
    await archive.create(
        database,
        tmp_path / "data",
        SOURCE_KEY,
        path,
        PASSPHRASE,
        options=archive.Options(),
        heads=heads,
        site="Demo",
    )

    # the marketplace, its e-mail settings — without the members: the Admin alone, owning what they made
    target = await fresh_portals()
    result = await _restore(target, path, tmp_path / "new", platform, ["marketplace", "notifications"])
    assert result["selection"] == ["gamification", "marketplace", "notifications"]
    assert await _count(target, "identity.users") == 1
    assert await _count(target, "identity.users", f"id = '{admin}'") == 1
    assert await _count(target, "authz.admin_singleton", f"current_admin_user_id = '{admin}'") == 1
    assert await _count(target, "marketplace.products") == products
    assert await _count(target, "marketplace.products", f"created_by <> '{admin}'") == 0
    assert await _count(target, "gamification.quests") == quests
    assert sum((await _theirs(target)).values()) == 0
    assert await _count(target, "wiki.pages") == 0 and await _count(target, "news.articles") == 0
    async with target.session() as session:
        stored = await session.scalar(
            text("SELECT value FROM config.settings WHERE key = :k AND scope = 'global'"),
            {"k": SMTP_PASSWORD},
        )
    plain = SecretBox(NEW_KEY).decrypt(stored["enc"], context=f"config:{SMTP_PASSWORD}").reveal()
    assert json.loads(plain) == "s3cret-smtp"
    assert await _dangling(target) == []

    # with the members: they come back with what is theirs
    target = await fresh_portals()
    await _restore(target, path, tmp_path / "new2", platform, ["marketplace", MEMBERS])
    assert await _count(target, "identity.users") == members
    assert await _theirs(target) == theirs
    assert await _dangling(target) == []

    # every block ticked: the whole portal, as a restore without a choice
    everything = await fresh_portals()
    await _restore(everything, path, tmp_path / "new3", platform, [b.key for b in BLOCKS])
    whole = await fresh_portals()
    await _restore(whole, path, tmp_path / "new4", platform, None)
    for table in (
        "identity.users",
        "marketplace.ownerships",
        "wiki.pages",
        "config.settings",
        "events.events",
    ):
        assert await _count(everything, table) == await _count(whole, table), table

    # any other choice: never a row pointing at nothing
    pick = random.Random(392)  # noqa: S311 — reproducible choices, not a secret
    for index in range(4):
        blocks = pick.sample([b.key for b in BLOCKS], pick.randint(1, 6))
        target = await fresh_portals()
        await _restore(target, path, tmp_path / f"random{index}", platform, blocks)
        assert await _dangling(target) == [], blocks
