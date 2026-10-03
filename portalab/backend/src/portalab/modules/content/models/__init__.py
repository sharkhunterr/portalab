"""Schema ``content``: uploaded assets (sniffed, re-encoded) bound to the object that owns them."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import pii


class ContentBase(DeclarativeBase):
    metadata = schema_metadata("content")


class Asset(ContentBase):
    __tablename__ = "assets"
    __table_args__ = (Index("ix_assets_owner", "owner_ref"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    owner_ref: Mapped[str] = mapped_column(String(260), nullable=False)  # ``portalab://wiki/<id>``
    blob_key: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(120), nullable=False, info=pii("content", tombstone="file"))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_by: Mapped[UUID | None] = mapped_column()  # FK identity.users (migration), SET NULL on erasure
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
