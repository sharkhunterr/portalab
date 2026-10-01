"""Database kernel: async engine, unit of work, schema-per-module declarative bases (data-model.md §1).

Conventions enforced here:
* one PostgreSQL schema per module (``schema_metadata("identity")`` …);
* instants are ``timestamptz`` only (:func:`assert_timezone_aware` is used by the boundary tests);
* a stable naming convention so Alembic autogenerate produces deterministic constraint names.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Any, Self

from sqlalchemy import DateTime, MetaData, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

TZDateTime = DateTime(timezone=True)
"""The only datetime column type allowed (``timestamptz``)."""

_metadata: dict[str, MetaData] = {}


def schema_metadata(schema: str) -> MetaData:
    """Metadata owning PostgreSQL schema ``schema`` (one per module, created once). Modules declare::

    class IdentityBase(DeclarativeBase):
        metadata = schema_metadata("identity")
    """
    if not schema.isidentifier() or schema != schema.lower():
        raise ValueError(f"invalid schema name {schema!r}: lowercase identifier expected")
    if schema not in _metadata:
        _metadata[schema] = MetaData(schema=schema, naming_convention=NAMING_CONVENTION)
    return _metadata[schema]


def all_metadata() -> list[MetaData]:
    """Metadata of every module schema registered so far (models must be imported first)."""
    return list(_metadata.values())


class CoreBase(DeclarativeBase):
    """Declarative base of the kernel's own ``core`` schema."""

    metadata = schema_metadata("core")


def assert_timezone_aware(metadata: MetaData) -> None:
    """Raise if any datetime column is declared without time zone (``timestamp`` is forbidden)."""
    for table in metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, DateTime) and not column.type.timezone:
                raise TypeError(
                    f"{table.fullname}.{column.name} must be timestamptz (DateTime(timezone=True))"
                )


def create_engine(url: str, **kwargs: Any) -> AsyncEngine:
    options: dict[str, Any] = {"pool_pre_ping": True, "future": True}
    options.update(kwargs)
    return create_async_engine(url, **options)


class Database:
    """Engine + session factory shared by the API process and the worker."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.sessions: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, url: str, **kwargs: Any) -> Self:
        return cls(create_engine(url, **kwargs))

    def unit_of_work(self) -> "UnitOfWork":
        return UnitOfWork(self.sessions)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            yield session

    async def ping(self) -> bool:
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            return False
        return True

    async def dispose(self) -> None:
        await self.engine.dispose()


class UnitOfWork:
    """One transaction: commit on success, rollback on any error (no partial writes, plan §7)."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork used outside of its 'async with' block")
        return self._session

    async def __aenter__(self) -> Self:
        self._session = self._sessions()
        await self._session.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session = self.session
        try:
            if exc_type is None:
                await session.commit()
            else:
                await session.rollback()
        finally:
            await session.close()
            self._session = None
