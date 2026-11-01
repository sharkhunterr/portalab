"""Schema ``news`` (specs/011 data-model): categories, articles with their editorial state, append-only
revisions (only an erased author may be tombstoned) and translations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal, pii


class NewsBase(DeclarativeBase):
    metadata = schema_metadata("news")


class Category(NewsBase):
    __tablename__ = "categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, info=not_personal("category label"))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 027: a category is a channel — described, with an icon, and (``newsletter``) e-mailed to its
    # subscribers (members may unsubscribe from each channel)
    description: Mapped[str] = mapped_column(
        String(300), nullable=False, default="", server_default="", info=not_personal("channel description")
    )
    icon: Mapped[str | None] = mapped_column(String(40))
    newsletter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class Article(NewsBase):
    __tablename__ = "articles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'scheduled', 'published', 'archived', 'deleted')", name="status"
        ),
        Index("ix_articles_published", "status", "published_at"),
        Index("ix_articles_search", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("article title"))
    summary: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_html: Mapped[str] = mapped_column(Text, nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(8), nullable=False)
    plain_text: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("news.categories.id"))
    author_id: Mapped[UUID | None] = mapped_column()  # FK identity.users (migration), SET NULL
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    audience: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    publish_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    published_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    archived_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    featured_from: Mapped[datetime | None] = mapped_column(TZDateTime)
    featured_until: Mapped[datetime | None] = mapped_column(TZDateTime)
    feature_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notify_on_publish: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 027: e-mailed to the channel's subscribers when published (once: ``emailed_at``)
    email_on_publish: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        info=not_personal("whether the article is e-mailed on publication"),
    )
    emailed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    publish_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    search_vector: Mapped[Any] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ArticleRevision(NewsBase):
    __tablename__ = "article_revisions"

    article_id: Mapped[UUID] = mapped_column(ForeignKey("news.articles.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("article title"))
    summary: Mapped[str] = mapped_column(String(600), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[UUID | None] = mapped_column()  # tombstoned (NULL) on erasure
    changed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ArticleTranslation(NewsBase):
    __tablename__ = "article_translations"
    __table_args__ = (CheckConstraint("state IN ('translated', 'machine_draft')", name="state"),)

    article_id: Mapped[UUID] = mapped_column(ForeignKey("news.articles.id"), primary_key=True)
    language: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("article title"))
    summary: Mapped[str] = mapped_column(String(600), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_html: Mapped[str] = mapped_column(Text, nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(8), nullable=False)
    state: Mapped[str] = mapped_column(String(14), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ArticleRead(NewsBase):
    """#48: a member opened a published article (the first time) — for the unread dot and the editors'
    « who read it »."""

    __tablename__ = "article_reads"
    __table_args__ = (Index("ix_article_reads_user", "user_id"),)

    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("news.articles.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(primary_key=True, info=pii("activity"))
    # the row is deleted with the member (``user_id`` is the personal part)
    read_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, info=not_personal("when it was opened, deleted with the member")
    )


class NewsletterSchedule(NewsBase):
    """027: an automatic newsletter — on its cadence the portal writes an article for a channel from what
    the media services report (releases, additions, upcoming) and publishes it (e-mailed when asked)."""

    __tablename__ = "newsletter_schedules"
    __table_args__ = (
        CheckConstraint("kind IN ('releases', 'additions', 'upcoming', 'edition')", name="kind"),
        CheckConstraint("cadence IN ('daily', 'weekly', 'monthly')", name="cadence"),
        CheckConstraint("weekday BETWEEN 0 AND 6 AND hour BETWEEN 0 AND 23", name="when"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False, info=not_personal("schedule name"))
    category_id: Mapped[UUID] = mapped_column(ForeignKey("news.categories.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    media_kinds: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)  # empty: all
    cadence: Mapped[str] = mapped_column(String(10), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0 = Monday
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="fr")
    email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, info=not_personal("whether the newsletter is e-mailed")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    next_run_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    last_article_id: Mapped[UUID | None] = mapped_column()
    # #316: a self-writing edition — drawn with this template, with this notice on top (a maintenance…)
    template_key: Mapped[str | None] = mapped_column(String(64), info=not_personal("an edition's template"))
    notice: Mapped[str | None] = mapped_column(Text, info=not_personal("an edition's notice"))
    # #323: what its editions tell (the contents switched on); none: the template's own sections
    contents: Mapped[list[str] | None] = mapped_column(JSONB, info=not_personal("an edition's contents"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class NewsletterTemplate(NewsBase):
    """#316: an edition's template written by the news desk (the built-in ones live in the code): its look —
    palette, font, header — and its sections, each with its display, order and number of titles."""

    __tablename__ = "newsletter_templates"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, info=not_personal("a template's look and sections")
    )
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class NewsletterEdition(NewsBase):
    """#316: one edition of a self-writing newsletter — what it told (a snapshot), drawn once as an e-mail
    that the portal shows as it is; a preview or a draft until published (then readable by every member) and
    e-mailed when asked. Its pictures are reachable by its token alone (mail clients carry no session)."""

    __tablename__ = "newsletter_editions"
    __table_args__ = (
        CheckConstraint("status IN ('preview', 'draft', 'published')", name="status"),
        UniqueConstraint("token", name="uq_newsletter_editions_token"),
        Index("ix_newsletter_editions_published", "status", "published_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    schedule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("news.newsletter_schedules.id", ondelete="SET NULL")
    )
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("news.categories.id", ondelete="SET NULL"))
    template_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("an edition's title"))
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, info=not_personal("what an edition told: titles and the period's figures")
    )
    html: Mapped[str] = mapped_column(Text, nullable=False, info=not_personal("an edition as an e-mail"))
    text: Mapped[str] = mapped_column(Text, nullable=False, info=not_personal("an edition as plain text"))
    token: Mapped[str] = mapped_column(String(64), nullable=False, info=not_personal("an edition's token"))
    created_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    emailed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Feed(NewsBase):
    """#299: a source of news from elsewhere the editors chose (an RSS or Atom feed): read on its own
    cadence, its items kept a while, filtered by words, shown on « À la une » and linked to the library."""

    __tablename__ = "feeds"
    __table_args__ = (
        CheckConstraint("status IN ('never', 'ok', 'error')", name="status"),
        Index("ix_feeds_due", "enabled", "next_run_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False, info=not_personal("a source's name"))
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    site_url: Mapped[str | None] = mapped_column(String(1000))
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("news.categories.id", ondelete="SET NULL"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # #299: the editors' (on « À la une ») — else only members' own, read for their « Mon fil »
    editorial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    include_words: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    exclude_words: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    refresh_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    next_run_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    last_run_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="never")
    last_error: Mapped[str | None] = mapped_column(String(300), info=not_personal("why the source failed"))
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    etag: Mapped[str | None] = mapped_column(String(200), info=not_personal("the source's version tag"))
    modified: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class FeedItem(NewsBase):
    """#299: one item a source published — its title, a short summary (plain text), its link and picture
    (copied: browsers never call the site), the library titles and people it names; pinned or hidden by the
    editors. Read again from the source when lost: never backed up."""

    __tablename__ = "feed_items"
    __table_args__ = (
        Index("ix_feed_items_published", "published_at"),
        Index("ix_feed_items_feed", "feed_id", "published_at"),
        Index("ix_feed_items_mentions", "mentions", postgresql_using="gin"),
        UniqueConstraint("feed_id", "guid"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    feed_id: Mapped[UUID] = mapped_column(ForeignKey("news.feeds.id", ondelete="CASCADE"), nullable=False)
    guid: Mapped[str] = mapped_column(String(500), nullable=False)
    link: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False, info=not_personal("a news item's title"))
    summary: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    image_key: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    mentions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FeedSubscription(NewsBase):
    """#299: a member's own source, for their « Mon fil » only — private (nobody else sees who reads what);
    the same address read once for everyone who follows it."""

    __tablename__ = "feed_subscriptions"
    __table_args__ = (Index("ix_feed_subscriptions_feed", "feed_id"),)

    user_id: Mapped[UUID] = mapped_column(primary_key=True, info=pii("preference"))
    feed_id: Mapped[UUID] = mapped_column(ForeignKey("news.feeds.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, info=not_personal("when it was followed, deleted with the member")
    )
