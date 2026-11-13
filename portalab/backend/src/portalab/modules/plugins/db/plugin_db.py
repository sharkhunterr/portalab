"""Per-plugin data isolation (T014; R3): schema ``plugin_<key>`` owned by a dedicated PostgreSQL role with
no rights on core schemas, so core tables are unreachable (core data only through capabilities).

Issue 396: a plugin's SQL runs on **its own connections, signed in as its role** (those of its confined
storage, spec 030: its password kept encrypted, a SCRAM verifier on the server) — never on the portal's with
``SET ROLE``, which the plugin's own SQL could undo (``RESET ROLE``: Postgres lets a session take back any
role its signed-in user belongs to); every statement is bounded in time by the portal, whatever it sets.
Plugin migrations are ordered SQL files run the same way and tracked in its own schema; during an update
only *expand* steps are accepted (no drop, rename, truncate or delete)."""

import asyncio
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from portalab.core.db import Database
from portalab.core.errors import ValidationFailed

DESTRUCTIVE = re.compile(r"\b(DROP|TRUNCATE|RENAME|DELETE\s+FROM)\b", re.IGNORECASE)
MIGRATION = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


class MigrationRefused(ValidationFailed):
    default_code = "plugin.migration_refused"
    default_title = "Migration refused"


def _ident(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value):
        raise ValueError(f"unsafe identifier {value!r}")
    return f'"{value}"'


class PluginStorage:
    def __init__(self, database: Database, *, role_prefix: str = "plugin_") -> None:
        self.database = database
        self.role_prefix = role_prefix
        # issue 396: the plugin's own connections (set by the module: the confined storage's), and how to
        # close them before its role goes
        self.login: Callable[[str], Awaitable[AsyncEngine]] | None = None
        self.release: Callable[[str], Awaitable[None]] | None = None

    async def engine(self, key: str) -> AsyncEngine:
        if self.login is None:
            raise RuntimeError("a plugin's SQL needs its own connections")
        return await self.login(key)

    def bound(self, key: str, timeout_ms: int) -> "RoleBoundDb":
        """``ctx.db`` for the plugin ``key``."""
        return RoleBoundDb(lambda: self.engine(key), self.schema(key), timeout_ms)

    def schema(self, key: str) -> str:
        return f"plugin_{key}"

    def role(self, key: str) -> str:
        return f"{self.role_prefix}{key}"

    async def provision(self, key: str, statement_timeout_ms: int) -> None:
        role, schema = _ident(self.role(key)), _ident(self.schema(key))
        async with self.database.unit_of_work() as uow:
            session = uow.session
            exists = await session.scalar(
                text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": self.role(key)}
            )
            if exists is None:
                await session.execute(text(f"CREATE ROLE {role} NOLOGIN NOINHERIT"))
            await session.execute(text(f"GRANT {role} TO CURRENT_USER"))
            await session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema} AUTHORIZATION {role}"))
            await session.execute(
                text(f"ALTER ROLE {role} SET statement_timeout = {int(statement_timeout_ms)}")
            )
            await session.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS {schema}.portalab_migrations "
                    "(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
                )
            )
            await session.execute(text(f"ALTER TABLE {schema}.portalab_migrations OWNER TO {role}"))

    async def exists(self, key: str) -> bool:
        async with self.database.session() as session:
            found = await session.scalar(
                text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"),
                {"s": self.schema(key)},
            )
        return found is not None

    async def migrate(self, key: str, package: Path, folder: str | None, *, expand_only: bool) -> list[str]:
        """Apply the package's pending SQL migrations with the plugin role; returns the applied versions."""
        if not folder:
            return []
        directory = package / folder
        if not directory.is_dir():
            return []
        files = sorted(p for p in directory.iterdir() if MIGRATION.match(p.name))
        applied: list[str] = []
        schema = _ident(self.schema(key))
        engine = await self.engine(key)
        async with engine.begin() as conn:  # signed in as the plugin's role: it cannot leave it
            await conn.execute(text(f"SET LOCAL search_path = {schema}"))
            done = set(
                (await conn.execute(text(f"SELECT version FROM {schema}.portalab_migrations"))).scalars()  # noqa: S608 — identifiers checked by _ident  # nosec B608
            )
            for path in files:
                version = path.name.split("_", 1)[0]
                if version in done:
                    continue
                sql = path.read_text(encoding="utf-8")
                if expand_only and DESTRUCTIVE.search(sql):
                    raise MigrationRefused(
                        "An update may only add (expand); destructive steps come in a later version.",
                        extensions={"migration": path.name},
                    )
                for statement in (s.strip() for s in sql.split(";")):
                    if statement:
                        await conn.execute(text(statement))
                await conn.execute(
                    text(f"INSERT INTO {schema}.portalab_migrations (version) VALUES (:v)"),  # noqa: S608  # nosec B608
                    {"v": version},
                )
                applied.append(version)
        return applied

    async def export(self, key: str) -> dict[str, list[dict[str, Any]]]:
        schema = self.schema(key)
        out: dict[str, list[dict[str, Any]]] = {}
        async with self.database.session() as session:
            tables = (
                (
                    await session.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = :s ORDER BY table_name"
                        ),
                        {"s": schema},
                    )
                )
                .scalars()
                .all()
            )
            for table in tables:
                rows = await session.execute(text(f"SELECT * FROM {_ident(schema)}.{_ident(table)}"))  # noqa: S608 — identifiers checked by _ident  # nosec B608
                out[table] = [{k: str(v) for k, v in r._mapping.items()} for r in rows]
        return out

    async def drop(self, key: str) -> None:
        role, schema = _ident(self.role(key)), _ident(self.schema(key))
        if self.release is not None:
            await self.release(key)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await session.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            exists = await session.scalar(
                text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": self.role(key)}
            )
            if exists is not None:
                await session.execute(text(f"DROP OWNED BY {role}"))
                await session.execute(text(f"DROP ROLE {role}"))


class RoleBoundDb:
    """``ctx.db`` (SDK ``PluginDb``): the plugin's SQL on its own connections (issue 396), in its schema,
    each statement bounded in time by the portal even if the plugin changes its ``statement_timeout``."""

    def __init__(self, engine: Callable[[], Awaitable[AsyncEngine]], schema: str, timeout_ms: int) -> None:
        self.engine = engine
        self.schema = _ident(schema)
        self.timeout_ms = int(timeout_ms)

    async def execute(self, sql: str, params: Mapping[str, Any] | None = None) -> Sequence[Mapping[str, Any]]:
        engine = await self.engine()
        async with engine.begin() as conn:
            await conn.execute(text(f"SET LOCAL statement_timeout = {self.timeout_ms}"))
            await conn.execute(text(f"SET LOCAL search_path = {self.schema}"))
            async with asyncio.timeout(self.timeout_ms / 1000 + 1):
                result = await conn.execute(text(sql), dict(params or {}))
                return [dict(r._mapping) for r in result] if getattr(result, "returns_rows", False) else []
