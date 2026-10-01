"""T039 — PII classification registry (data-model.md §3)."""

from uuid import UUID

import pytest
from sqlalchemy import MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.privacy_registry import (
    CLASSIFICATIONS,
    not_personal,
    personal_columns,
    pii,
    unclassified_pii_columns,
)

pytestmark = pytest.mark.unit


class Base(DeclarativeBase):
    metadata = MetaData(schema="piitest")


class Member(Base):
    __tablename__ = "member"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), info=pii("contact"))
    display_name: Mapped[str] = mapped_column(String(64), info=pii("profile", tombstone="deleted-user"))
    bio: Mapped[str | None] = mapped_column(String(500), info=pii("content"))
    theme: Mapped[str | None] = mapped_column(String(32), info=pii("preference"))
    service_name: Mapped[str | None] = mapped_column(
        String(64), info=not_personal("name of a service, not a person")
    )


class Sloppy(Base):
    __tablename__ = "sloppy"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    api_token: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(64))


def test_classification_classes_are_the_documented_set() -> None:
    assert set(CLASSIFICATIONS) == {
        "identifier",
        "contact",
        "profile",
        "preference",
        "activity",
        "content",
        "technical",
    }


def test_unknown_classification_is_rejected() -> None:
    with pytest.raises(ValueError):
        pii("secret-sauce")  # type: ignore[arg-type]


def test_not_personal_requires_a_reason() -> None:
    with pytest.raises(ValueError):
        not_personal("  ")


def test_personal_columns_lists_classified_columns_only() -> None:
    assert personal_columns(Member) == {
        "email": "contact",
        "display_name": "profile",
        "bio": "content",
        "theme": "preference",
    }
    assert personal_columns(Member.__table__) == personal_columns(Member)


def test_unclassified_pii_named_columns_are_detected() -> None:
    offenders = unclassified_pii_columns(Base.metadata)
    assert sorted(offenders) == [
        "piitest.sloppy.api_token",
        "piitest.sloppy.email",
        "piitest.sloppy.ip_address",
    ]
