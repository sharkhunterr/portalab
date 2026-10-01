"""T020 — PostgreSQL fixtures for integration tests (risk R-C: real PostgreSQL only, never SQLite).

``PORTALAB_TEST_DATABASE_URL`` points at a PostgreSQL *maintenance* database (CI service container or local
compose). Every test gets its own database:
* ``empty_db_url``    — a brand-new empty database;
* ``migrated_db_url`` — a copy of a template database migrated once per session to all heads.
Without the variable, integration tests are skipped locally; CI sets ``PORTALAB_REQUIRE_DB=1`` so a missing
database fails the pipeline instead of silently skipping.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from portalab.app.migrations import expected_heads, upgrade
from portalab.core.db import Database
from portalab.core.settings import normalize_database_url

ADMIN_URL_ENV = "PORTALAB_TEST_DATABASE_URL"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def admin_url() -> str:
    url = os.environ.get(ADMIN_URL_ENV)
    if not url:
        if os.environ.get("PORTALAB_REQUIRE_DB") == "1":
            pytest.fail(f"{ADMIN_URL_ENV} is required (PORTALAB_REQUIRE_DB=1)")
        pytest.skip(f"integration tests need {ADMIN_URL_ENV} (real PostgreSQL)")
    return normalize_database_url(url)


def _asyncpg_dsn(url: str) -> str:
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


def _with_database(url: str, name: str) -> str:
    return make_url(url).set(database=name).render_as_string(hide_password=False)


async def _admin_execute(admin: str, sql: str) -> None:
    conn = await asyncpg.connect(_asyncpg_dsn(admin))
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


async def create_database(admin: str, *, template: str | None = None) -> str:
    name = f"portalab_test_{uuid4().hex[:12]}"
    template_sql = f' TEMPLATE "{template}"' if template else ""
    await _admin_execute(admin, f'CREATE DATABASE "{name}"{template_sql}')
    return name


async def drop_database(admin: str, name: str) -> None:
    await _admin_execute(admin, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture(scope="session")
def migrated_template(admin_url: str) -> Iterator[str]:
    name = asyncio.run(create_database(admin_url))
    try:
        upgrade(_with_database(admin_url, name))
        yield name
    finally:
        asyncio.run(drop_database(admin_url, name))


@pytest.fixture
async def empty_db_url(admin_url: str) -> AsyncIterator[str]:
    name = await create_database(admin_url)
    try:
        yield _with_database(admin_url, name)
    finally:
        await drop_database(admin_url, name)


@pytest.fixture
async def migrated_db_url(admin_url: str, migrated_template: str) -> AsyncIterator[str]:
    name = await create_database(admin_url, template=migrated_template)
    try:
        yield _with_database(admin_url, name)
    finally:
        await drop_database(admin_url, name)


@pytest.fixture
async def database(migrated_db_url: str) -> AsyncIterator[Database]:
    db = Database.from_url(migrated_db_url, poolclass=NullPool)
    try:
        yield db
    finally:
        await db.dispose()


@pytest.fixture(scope="session")
def heads() -> set[str]:
    return expected_heads("postgresql+asyncpg://unused/unused")
