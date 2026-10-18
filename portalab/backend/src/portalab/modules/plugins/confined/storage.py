"""A confined plugin's storage (spec 030, R5): statements run by Portalab, logged in as the plugin's own role.

Spec 023 gave each plugin a schema ``plugin_<key>`` owned by a role without any right outside it. For a
confined plugin that role can log in (a random password, kept encrypted by Portalab, set as a SCRAM verifier
so the password itself is never written anywhere), with three connections at most; Portalab opens a small
pool as that role, so nothing a statement does can bring back Portalab's own role (``RESET ROLE`` returns to
the plugin's). Each request is **one** statement (prepared statements refuse several) whose first word is a
query or a data change, in its own transaction with a statement timeout; results are bounded. Over its quota
the plugin's transactions are read-only (PostgreSQL refuses to switch back after the first query).
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from portalab.core.db import Database
from portalab.core.secrets import SecretBox
from portalab.core.time import utc_now
from portalab.modules.plugins.models import SecretSetting

ALLOWED_FIRST = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE", "WITH", "VALUES", "TABLE", "MERGE"})
MAX_ROWS = 1000
MAX_BYTES = 1024 * 1024
DB_SECRET = "__db"  # noqa: S105 — the name of the row holding it, not a secret
_COMMENTS = re.compile(r"^\s*(?:(?:--[^\n]*\n)|(?:/\*.*?\*/)|\s)*", re.DOTALL)
_IDENT = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class StatementRefused(PermissionError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def first_word(sql: str) -> str:
    rest = _COMMENTS.sub("", sql, count=1)
    match = re.match(r"[A-Za-z]+", rest)
    return match.group(0).upper() if match else ""


def check_statement(sql: str) -> None:
    if not isinstance(sql, str) or not sql.strip():
        raise StatementRefused("denied_statement", "an empty statement")
    if len(sql) > 20_000:
        raise StatementRefused("denied_statement", "a statement longer than 20 000 characters")
    word = first_word(sql)
    if word not in ALLOWED_FIRST:
        raise StatementRefused("denied_statement", f"{word or 'this'} statements are not allowed")


def scram_verifier(password: str, *, iterations: int = 4096) -> str:
    """PostgreSQL's SCRAM-SHA-256 verifier: the server stores this, never the password."""
    salt = secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()

    def b64(raw: bytes) -> str:
        return base64.b64encode(raw).decode()

    return f"SCRAM-SHA-256${iterations}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}"


def _sqlstate(error: DBAPIError) -> str:
    original = getattr(error, "orig", None)
    return str(
        getattr(original, "sqlstate", None)
        or getattr(getattr(original, "__cause__", None), "sqlstate", "")
        or ""
    )


class PluginDatabase:
    """The storage of every confined plugin of this process."""

    def __init__(self, database: Database, box: SecretBox | None, *, role_prefix: str = "plugin_") -> None:
        self.database = database
        self.box = box
        self.role_prefix = role_prefix
        self._engines: dict[str, AsyncEngine] = {}
        self._read_only: dict[str, bool] = {}
        self._measured: dict[str, float] = {}

    def role(self, key: str) -> str:
        role = f"{self.role_prefix}{key}"
        if not _IDENT.match(role):
            raise ValueError("unsafe plugin key")
        return role

    def schema(self, key: str) -> str:
        return f"plugin_{key}"

    async def _password(self, key: str) -> str:
        if self.box is None:
            raise RuntimeError("no application key to keep the plugin's database password")
        context = f"plugins.db:{key}"
        async with self.database.session() as session:
            row = await session.get(SecretSetting, (key, DB_SECRET))
            if row is not None:
                return self.box.decrypt(row.ciphertext, context=context).reveal()
        password = secrets.token_urlsafe(32)
        role = self.role(key)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            connection = await session.connection()  # the verifier holds colons: no bind parameters here
            await connection.exec_driver_sql(
                f"ALTER ROLE \"{role}\" LOGIN CONNECTION LIMIT 3 PASSWORD '{scram_verifier(password)}'"
            )
            session.add(
                SecretSetting(
                    plugin_key=key,
                    name=DB_SECRET,
                    ciphertext=self.box.encrypt(password, context=context),
                    updated_at=utc_now(),
                )
            )
        return password

    async def engine(self, key: str, timeout_ms: int) -> AsyncEngine:
        engine = self._engines.get(key)
        if engine is not None:
            return engine
        password = await self._password(key)
        url = make_url(str(self.database.engine.url.render_as_string(hide_password=False)))
        url = url.set(username=self.role(key), password=password)
        engine = create_async_engine(
            url,
            pool_size=2,
            max_overflow=0,
            pool_pre_ping=False,
            connect_args={
                "server_settings": {
                    "search_path": f'"{self.schema(key)}"',
                    "statement_timeout": str(int(timeout_ms)),
                    "idle_in_transaction_session_timeout": "10000",
                    "application_name": f"portalab-plugin-{key}"[:63],
                },
                "command_timeout": max(1.0, timeout_ms / 1000 + 1),
            },
        )
        self._engines[key] = engine
        return engine

    async def usage_bytes(self, key: str) -> int:
        async with self.database.session() as session:
            value = await session.scalar(
                text(
                    "SELECT coalesce(sum(pg_total_relation_size(c.oid)), 0) FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = :schema "
                    "AND c.relkind IN ('r', 'm', 't')"
                ),
                {"schema": self.schema(key)},
            )
        return int(value or 0)

    async def over_quota(self, key: str, quota_mb: int) -> bool:
        now = time.monotonic()
        if now - self._measured.get(key, 0.0) > 30:
            self._measured[key] = now
            self._read_only[key] = await self.usage_bytes(key) > quota_mb * 1024 * 1024
        return self._read_only.get(key, False)

    async def execute(
        self, key: str, sql: str, params: Mapping[str, Any] | None, *, timeout_ms: int, quota_mb: int
    ) -> dict[str, Any]:
        check_statement(sql)
        read_only = await self.over_quota(key, quota_mb)
        engine = await self.engine(key, timeout_ms)
        async with engine.connect() as conn:
            try:
                answer = await self._run(conn, sql, params, timeout_ms, read_only)
            finally:
                # nothing a statement left behind (a session setting, an advisory lock) outlives the call
                await conn.rollback()
                await conn.execute(text("RESET ALL"))
                await conn.execute(text("SELECT pg_advisory_unlock_all()"))
                await conn.commit()
        return answer

    async def _run(
        self, conn: Any, sql: str, params: Mapping[str, Any] | None, timeout_ms: int, read_only: bool
    ) -> dict[str, Any]:
        try:
            async with conn.begin():
                if read_only:
                    await conn.execute(text("SET TRANSACTION READ ONLY"))
                await conn.execute(text(f"SET LOCAL statement_timeout = {int(timeout_ms)}"))
                result = await conn.execute(text(sql), dict(params or {}))
                rows: list[dict[str, Any]] = []
                size = 0
                if result.returns_rows:
                    for row in result.mappings():
                        if len(rows) >= MAX_ROWS:
                            break
                        item = dict(row)
                        size += len(json.dumps(item, default=str))
                        if size > MAX_BYTES:
                            raise StatementRefused("oversize", "the result is larger than 1 MiB")
                        rows.append(item)
                rowcount = len(rows) if result.returns_rows else int(result.rowcount or 0)
        except DBAPIError as error:
            state = _sqlstate(error)
            if state == "25006":
                raise StatementRefused("storage_quota", "the plugin's storage is full (read only)") from None
            if state in ("42501", "42P01", "3F000") or state.startswith("28"):
                # no right outside its schema (or what it named is not there for it)
                raise StatementRefused("denied_statement", f"refused by the database ({state})") from None
            if state == "57014":
                raise StatementRefused("timeout", "the statement took too long") from None
            raise StatementRefused("failed", f"the statement failed ({state or 'error'})") from None
        # each call its own answer (calls run concurrently: nothing is kept on the instance)
        return {"rows": rows, "rowcount": rowcount, "read_only": read_only}

    async def close(self, key: str | None = None) -> None:
        keys = [key] if key else list(self._engines)
        for name in keys:
            engine = self._engines.pop(name, None)
            if engine is not None:
                await engine.dispose()

    async def forget_password(self, key: str) -> None:
        """The role cannot log in any more (plugin disabled or removed)."""
        await self.close(key)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            exists = await session.scalar(
                text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": self.role(key)}
            )
            if exists is not None:
                await session.execute(text(f'ALTER ROLE "{self.role(key)}" NOLOGIN PASSWORD NULL'))
            row = await session.get(SecretSetting, (key, DB_SECRET))
            if row is not None:
                await session.delete(row)
