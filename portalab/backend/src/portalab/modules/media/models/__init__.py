"""Schema ``media`` (specs/024-media/data-model.md). Objects are never deleted when a source disappears;
``service_id`` and source references are opaque (no FK outside the module except ``identity.users``)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal, pii

# ``user_id`` columns reference ``identity.users(id)`` through foreign keys created in the migration only.


class MediaBase(DeclarativeBase):
    metadata = schema_metadata("media")


class MediaObject(MediaBase):
    __tablename__ = "objects"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'hidden', 'merged')", name="status"),
        Index("ix_objects_kind_title", "kind", "sort_title"),
        Index("ix_objects_parent", "parent_id", "position"),
        Index(
            "ix_objects_search_text",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.objects.id"))
    position: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_title: Mapped[str] = mapped_column(String(500), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # #92: what the search reads — computed by the database from the title, its series and its people
    search_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="", default="")
    field_provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    merged_into: Mapped[UUID | None] = mapped_column(ForeignKey("media.objects.id"))
    first_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ExternalId(MediaBase):
    __tablename__ = "external_ids"
    __table_args__ = (Index("ix_external_ids_object", "object_id"),)

    scheme: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), primary_key=True)
    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), nullable=False)


class SourceItem(MediaBase):
    __tablename__ = "source_items"
    __table_args__ = (
        UniqueConstraint("service_id", "external_id", name="uq_source_items_service_external"),
        CheckConstraint("availability IN ('available', 'unavailable', 'unknown')", name="availability"),
        Index("ix_source_items_object", "object_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    object_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.objects.id"))
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    availability: Mapped[str] = mapped_column(String(12), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class FieldCandidate(MediaBase):
    __tablename__ = "field_candidates"

    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), primary_key=True)
    field: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(120), primary_key=True)  # ``admin`` = override
    source_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.source_items.id"))
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ObjectTag(MediaBase):
    __tablename__ = "object_tags"
    __table_args__ = (
        CheckConstraint("tag_kind IN ('genre', 'tag', 'keyword', 'person')", name="tag_kind"),
        Index("ix_object_tags_value", "tag_kind", "value"),
    )

    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), primary_key=True)
    tag_kind: Mapped[str] = mapped_column(String(10), primary_key=True)
    value: Mapped[str] = mapped_column(String(120), primary_key=True)


class Credit(MediaBase):
    """#92 — who is behind a title and as what (``author``, ``narrator``, ``director``, ``writer``,
    ``creator``, ``cast``, ``artist``), from the library's fields (``library``) and the metadata provider's
    people (``metadata``, with a portrait); written by the database itself (migration media_0008)."""

    __tablename__ = "credits"
    __table_args__ = (
        CheckConstraint("source IN ('library', 'metadata')", name="source"),
        Index("ix_credits_name", "name"),
        Index(
            "ix_credits_folded",
            "folded",
            postgresql_using="gin",
            postgresql_ops={"folded": "gin_trgm_ops"},
        ),
    )

    object_id: Mapped[UUID] = mapped_column(
        ForeignKey("media.objects.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(
        String(200),
        primary_key=True,
        info=not_personal("a public credit of a published work (cast, director, author), not a member"),
    )
    role: Mapped[str] = mapped_column(String(10), primary_key=True)
    image: Mapped[str | None] = mapped_column(String(300))
    folded: Mapped[str] = mapped_column(Text, nullable=False)  # ``media.search_fold(name)``
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # the billing order
    ref: Mapped[str | None] = mapped_column(String(40))  # the person's id at the provider (TMDB)


class MatchCandidate(MediaBase):
    __tablename__ = "match_candidates"
    __table_args__ = (
        UniqueConstraint("object_a", "object_b", name="uq_match_candidates_pair"),
        CheckConstraint("state IN ('proposed', 'accepted', 'rejected')", name="state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    object_a: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), nullable=False)
    object_b: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class MergeLog(MediaBase):
    """Append-only: every merge/split with the pointers needed to reverse it."""

    __tablename__ = "merge_log"
    __table_args__ = (CheckConstraint("action IN ('merge', 'split')", name="action"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    object_id: Mapped[UUID] = mapped_column(nullable=False)  # surviving / restored object
    other_id: Mapped[UUID] = mapped_column(nullable=False)  # merged-away / split-off object
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Image(MediaBase):
    __tablename__ = "images"
    __table_args__ = (
        UniqueConstraint("object_id", "role", name="uq_images_object_role"),
        CheckConstraint("role IN ('poster', 'backdrop', 'thumb')", name="role"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    blob_key: Mapped[str] = mapped_column(String(200), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(300), nullable=False)
    source_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.source_items.id"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class UserLink(MediaBase):
    __tablename__ = "user_links"
    __table_args__ = (
        UniqueConstraint("service_id", "external_user_id", name="uq_user_links_external"),
        UniqueConstraint("user_id", "service_id", name="uq_user_links_user_service"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    external_user_id: Mapped[str] = mapped_column(
        String(200), nullable=False, info=pii("identifier", tombstone="erased")
    )
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class PlaybackSession(MediaBase):
    __tablename__ = "playback_sessions"
    __table_args__ = (
        CheckConstraint(
            "state IN ('playing', 'paused', 'buffering', 'stopped', 'stale', 'interrupted')", name="state"
        ),
        Index("ix_playback_sessions_user", "user_id", "updated_at"),
    )

    session_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID | None] = mapped_column()
    external_user_id: Mapped[str | None] = mapped_column(String(200), info=pii("activity"))
    object_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.objects.id"))
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    position_s: Mapped[float] = mapped_column(Float, nullable=False)
    max_position_s: Mapped[float] = mapped_column(Float, nullable=False)
    duration_s: Mapped[float | None] = mapped_column(Float)
    device: Mapped[str | None] = mapped_column(String(120), info=pii("activity"))
    # #47: what the source calls it, for a session the library cannot resolve (live TV)
    title: Mapped[str | None] = mapped_column(String(500))
    subtitle: Mapped[str | None] = mapped_column(String(500))
    channel: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    as_of: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    last_event_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    start_position_s: Mapped[float | None] = mapped_column(Float)  # #94: where this sitting began
    state_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    ended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class HistoryEntry(MediaBase):
    """Rebuildable projection of playback events (the 007 event stream is the record)."""

    __tablename__ = "history_entries"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_history_entries_event"),
        CheckConstraint("kind IN ('session', 'progress', 'finished')", name="kind"),
        Index("ix_history_entries_user", "user_id", "occurred_at"),
        Index("ix_history_entries_object", "object_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    event_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    session_key: Mapped[str | None] = mapped_column(String(300))
    position_from_s: Mapped[float] = mapped_column(Float, nullable=False)
    position_to_s: Mapped[float] = mapped_column(Float, nullable=False)
    consumed_s: Mapped[float] = mapped_column(Float, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class UserProgress(MediaBase):
    __tablename__ = "user_progress"
    __table_args__ = (CheckConstraint("state IN ('in_progress', 'finished')", name="state"),)

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), primary_key=True)
    resume_position_s: Mapped[float] = mapped_column(Float, nullable=False)
    percent: Mapped[float] = mapped_column(Float, nullable=False)
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    last_occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class BookPosition(MediaBase):
    """#20, #21: where a member stopped in a book, in the portal's own listening or reading — per format
    (``audio``, ``epub``, ``pdf``, ``cbx``): a position in seconds (audio), an EPUB CFI or a page number.
    Kept here for every member; written back to the service too when it keeps the member's progress."""

    __tablename__ = "book_positions"
    __table_args__ = (Index("ix_book_positions_user", "user_id", "updated_at"),)

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), primary_key=True)
    format: Mapped[str] = mapped_column(String(8), primary_key=True)
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    file_ref: Mapped[str | None] = mapped_column(String(80))
    position: Mapped[str] = mapped_column(String(2000), nullable=False)
    track: Mapped[int | None] = mapped_column(Integer)
    percent: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    event_at: Mapped[datetime | None] = mapped_column(TZDateTime)  # the last progress event published
    # #94: the sitting under way — its session, where and when it began (the minutes it counts)
    session_ref: Mapped[str | None] = mapped_column(String(64))
    session_start_s: Mapped[float | None] = mapped_column(Float)
    session_started_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    # #256: the sitting over (its minutes counted, once) — and the minutes it had reached, for ending it
    # when the member's page went away without a word
    session_ended_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    session_watched_s: Mapped[float | None] = mapped_column(Float)


class QuotaUnits(MediaBase):
    __tablename__ = "request_quota_units"
    __table_args__ = (CheckConstraint("units_remaining >= 0", name="units_remaining"),)

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    units_remaining: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class QuotaLedger(MediaBase):
    """Append-only ledger of extra request units (credited by 015, consumed by requests)."""

    __tablename__ = "request_quota_ledger"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_request_quota_ledger_idempotency"),
        CheckConstraint("reason IN ('purchase', 'refund', 'consumption', 'admin')", name="reason"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    delta: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(12), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class RescueLedger(MediaBase):
    """#57: a member's rescues — credited by the shop (``purchase``), spent saving a title from the cleanup
    tool's deletion (``rescue``, with the title). The balance is the sum of ``delta``."""

    __tablename__ = "rescues"
    __table_args__ = (
        UniqueConstraint("source_ref", name="uq_rescues_source_ref"),
        CheckConstraint("reason IN ('purchase', 'rescue', 'admin')", name="reason"),
        Index("ix_rescues_user", "user_id"),
        Index("ix_rescues_object", "object_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(12), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    object_id: Mapped[UUID | None] = mapped_column()
    title: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class RadioCreditLedger(MediaBase):
    """Issue 184: a member's requests to the radio's DJ — credits bought in the shop (``purchase``, +N), each
    request (``ask``: 0 when free, -1 when a credit paid for it). The balance is the sum of ``delta``; the
    free requests of the day are the day's ``ask`` rows at 0."""

    __tablename__ = "radio_credits"
    __table_args__ = (
        UniqueConstraint("source_ref", name="uq_radio_credits_source_ref"),
        CheckConstraint("reason IN ('purchase', 'ask', 'admin')", name="reason"),
        Index("ix_radio_credits_user", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(12), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class RadioSitting(MediaBase):
    """Issue 259: a member's sitting in front of the radio — the seconds the stream was relayed to them,
    across the streams it took (the player opens a new one at each play). It ends once nothing more was heard
    for a while, and its minutes then count, once (``media.radio_listened``)."""

    __tablename__ = "radio_sittings"
    __table_args__ = (
        Index("ix_radio_sittings_user", "user_id", "updated_at"),
        Index("ix_radio_sittings_open", "updated_at", postgresql_where=text("ended_at IS NULL")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    seconds: Mapped[float] = mapped_column(Float, nullable=False)
    started_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class TasteVerdict(MediaBase):
    """Issue 190: what a member said of a work — ``like``, ``dislike`` (not for me) or ``later`` (to watch,
    read or play later). One per member and work (a film, a series, a book, a game…: an episode's goes to its
    series); it weighs on their taste beside what the services tell they watched, read and played."""

    __tablename__ = "taste"
    __table_args__ = (
        CheckConstraint("verdict IN ('like', 'dislike', 'later')", name="verdict"),
        Index("ix_taste_user", "user_id", "verdict", "updated_at"),
    )

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    object_id: Mapped[UUID] = mapped_column(
        ForeignKey("media.objects.id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(String(8), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class MediaRequest(MediaBase):
    __tablename__ = "requests"
    __table_args__ = (
        UniqueConstraint("service_id", "external_request_id", name="uq_requests_service_external"),
        UniqueConstraint("idempotency_key", name="uq_requests_idempotency"),
        CheckConstraint(
            "state IN ('pending', 'approved', 'declined', 'processing', 'available', 'failed', 'cancelled')",
            name="state",
        ),
        Index("ix_requests_requester", "requester_user_id", "requested_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    object_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.objects.id"))
    external_ref: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # ids, kind, title
    requester_user_id: Mapped[UUID | None] = mapped_column()
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    external_request_id: Mapped[str | None] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    source_state: Mapped[str] = mapped_column(String(60), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    counted: Mapped[str] = mapped_column(String(10), nullable=False)  # ``base`` or ``extra`` quota
    requested_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Activity(MediaBase):
    """027 — one play or reading session as a source recorded it (raw history, Telemetra-style): ingested
    from ``media.activity_history`` providers (backfill, then incremental) and from ended live sessions of
    services without a history. ``counted`` is false for a row another source of the same ``family``
    reports better (Tautulli over Plex), so statistics never count a play twice."""

    __tablename__ = "activity"
    __table_args__ = (
        UniqueConstraint("service_id", "ref", name="uq_activity_service_ref"),
        CheckConstraint(
            "kind IN ('movie', 'episode', 'live', 'track', 'book', 'audiobook', 'game', 'other')", name="kind"
        ),
        Index("ix_activity_started", "started_at"),
        Index("ix_activity_user", "user_id", "started_at"),
        Index("ix_activity_work", "work_id", "started_at"),
        Index("ix_activity_family", "family", "priority", "started_at"),
        Index("ix_activity_external_user", "service_id", "external_user_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    ref: Mapped[str] = mapped_column(String(200), nullable=False)
    family: Mapped[str | None] = mapped_column(String(40))
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    counted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    external_user_id: Mapped[str] = mapped_column(
        String(200), nullable=False, info=pii("activity", tombstone="erased")
    )
    user_id: Mapped[UUID | None] = mapped_column()
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_title: Mapped[str | None] = mapped_column(String(500))
    object_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.objects.id", ondelete="SET NULL"))
    work_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.objects.id", ondelete="SET NULL"))
    item_external_id: Mapped[str | None] = mapped_column(String(200))
    ids: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    stopped_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    watched_s: Mapped[float] = mapped_column(Float, nullable=False)
    duration_s: Mapped[float | None] = mapped_column(Float)
    progress: Mapped[float | None] = mapped_column(Float)
    device: Mapped[str | None] = mapped_column(String(120), info=pii("activity"))
    platform: Mapped[str | None] = mapped_column(String(60))
    stream: Mapped[str | None] = mapped_column(String(12))  # direct, copy, transcode (027)
    quality: Mapped[str | None] = mapped_column(String(12))  # 4k, 1080p, 720p, sd (027)
    received_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    # #94: when this play was turned into the progression's ``media.playback_finished`` (the live watch
    # missed it) — at most once
    rewarded_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class ActivityCursor(MediaBase):
    """027 — where the history ingestion of one service stands: the backfill page cursor, then the
    incremental watermark (latest play seen)."""

    __tablename__ = "activity_cursors"
    __table_args__ = (CheckConstraint("mode IN ('backfill', 'incremental')", name="mode"),)

    service_id: Mapped[UUID] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(12), nullable=False)  # ``history`` or ``sessions``
    mode: Mapped[str] = mapped_column(String(12), nullable=False)
    cursor: Mapped[str | None] = mapped_column(String(200))
    watermark: Mapped[datetime | None] = mapped_column(TZDateTime)
    items: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    backfilled_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    last_run_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    last_error: Mapped[str | None] = mapped_column(String(300))


class ActivityDaily(MediaBase):
    """027 — precomputed per day, member and kind (rebuilt for the days that changed)."""

    __tablename__ = "activity_daily"
    __table_args__ = (Index("ix_activity_daily_user", "user_key", "day"),)

    day: Mapped[datetime] = mapped_column(TZDateTime, primary_key=True)  # midnight UTC of the day
    user_key: Mapped[UUID] = mapped_column(primary_key=True)  # the member, or the nil UUID when unknown
    kind: Mapped[str] = mapped_column(String(12), primary_key=True)
    plays: Mapped[int] = mapped_column(Integer, nullable=False)
    completed: Mapped[int] = mapped_column(Integer, nullable=False)
    seconds: Mapped[float] = mapped_column(Float, nullable=False)
    works: Mapped[int] = mapped_column(Integer, nullable=False)


class ActivityDirtyDay(MediaBase):
    """027 — days whose aggregates must be rebuilt (new rows, a linked account, a superseded source)."""

    __tablename__ = "activity_dirty_days"

    day: Mapped[datetime] = mapped_column(TZDateTime, primary_key=True)


class ObjectMetadata(MediaBase):
    """027 — what a metadata provider (TMDB…) knows about a film or a series: backdrop, cast, saga,
    budget, revenue… (``data`` follows ``MetadataRecord``); ``missing`` when the provider found nothing."""

    __tablename__ = "object_metadata"
    __table_args__ = (
        CheckConstraint("status IN ('found', 'missing', 'error')", name="status"),
        Index("ix_object_metadata_fetched", "status", "fetched_at"),
    )

    object_id: Mapped[UUID] = mapped_column(
        ForeignKey("media.objects.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)  # the provider's service id
    status: Mapped[str] = mapped_column(String(8), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fetched_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class TaskProgress(MediaBase):
    """027 — live progress of a background task (history of one service, metadata enrichment), for the
    spinners and progress bars of the statistics sources panel."""

    __tablename__ = "task_progress"

    task: Mapped[str] = mapped_column(String(80), primary_key=True)  # ``history:<service>``, ``metadata``
    running_since: Mapped[datetime | None] = mapped_column(TZDateTime)
    done: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
