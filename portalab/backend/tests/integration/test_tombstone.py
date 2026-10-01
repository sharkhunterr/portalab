"""T040 — registry-driven tombstone: scrubs classified PII only, keeps id and foreign keys, idempotent."""

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, MetaData, String, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import Database
from portalab.core.privacy_registry import not_personal, pii
from portalab.core.tombstone import scrub, tombstone


class Base(DeclarativeBase):
    metadata = MetaData(schema="tombtest")


class Person(Base):
    __tablename__ = "person"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), info=pii("contact"))
    display_name: Mapped[str] = mapped_column(String(64), info=pii("profile", tombstone="deleted-user"))
    bio: Mapped[str | None] = mapped_column(String(500), info=pii("content"))
    sponsor_id: Mapped[UUID | None] = mapped_column(ForeignKey("tombtest.person.id"), info=pii("identifier"))
    kind: Mapped[str] = mapped_column(String(16), info=not_personal("account kind enum"))


class Note(Base):
    __tablename__ = "note"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("tombtest.person.id"))
    body: Mapped[str | None] = mapped_column(String(500), info=pii("content"))
    topic: Mapped[str] = mapped_column(String(64), info=not_personal("topic label"))


async def _setup(database: Database) -> tuple[UUID, UUID]:
    async with database.engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA tombtest"))
        await conn.run_sync(Base.metadata.create_all)
    sponsor, member = uuid4(), uuid4()
    async with database.unit_of_work() as uow:
        uow.session.add(Person(id=sponsor, email="s@example.org", display_name="Sponsor", kind="user"))
        await uow.session.flush()
        uow.session.add(
            Person(
                id=member,
                email="m@example.org",
                display_name="Member",
                bio="hi",
                sponsor_id=sponsor,
                kind="user",
            )
        )
        await uow.session.flush()
        uow.session.add(Note(id=uuid4(), author_id=member, body="private thoughts", topic="general"))
    return sponsor, member


async def test_tombstone_scrubs_pii_and_keeps_identity_and_links(database: Database) -> None:
    sponsor, member = await _setup(database)
    async with database.unit_of_work() as uow:
        scrubbed = await tombstone(uow.session, Person.__table__, member)
    assert scrubbed == 1
    async with database.session() as session:
        person = (await session.execute(select(Person).where(Person.id == member))).scalar_one()
        assert person.id == member
        assert person.email is None
        assert person.bio is None
        assert person.display_name == "deleted-user"
        assert person.sponsor_id == sponsor  # foreign keys are never scrubbed
        assert person.kind == "user"
        other = (await session.execute(select(Person).where(Person.id == sponsor))).scalar_one()
        assert other.email == "s@example.org"


async def test_tombstone_is_idempotent(database: Database) -> None:
    _, member = await _setup(database)
    for _ in range(2):
        async with database.unit_of_work() as uow:
            await tombstone(uow.session, Person.__table__, member)
    async with database.session() as session:
        person = (await session.execute(select(Person).where(Person.id == member))).scalar_one()
    assert (person.email, person.bio, person.display_name) == (None, None, "deleted-user")


async def test_scrub_walks_dependent_rows_by_user_reference(database: Database) -> None:
    _, member = await _setup(database)
    async with database.unit_of_work() as uow:
        rows = await scrub(uow.session, Note.__table__, where=Note.__table__.c.author_id == member)
    assert rows == 1
    async with database.session() as session:
        note = (await session.execute(select(Note))).scalar_one()
    assert note.body is None
    assert note.author_id == member
    assert note.topic == "general"
