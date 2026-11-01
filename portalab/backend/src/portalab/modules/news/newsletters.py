"""Newsletters (027): the news desk's channels (its categories) can be e-mailed to their subscribers — every
member, minus those who unsubscribed from that channel (``news.newsletter.optOut``) or from newsletter
e-mails altogether (their notification preferences) — and some newsletters write themselves: on its
cadence a schedule turns what the media services report (what came out, what arrived, what comes next)
into an article of its channel, published and e-mailed when asked.

The e-mail is the article itself (its sanitized HTML), sent through the notification centre so delivery,
retries and opt-outs stay in one place; links point to the portal's public address."""

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.i18n import RENDERER, LocaleContext
from portalab.capabilities.identity_directory import CONTACT
from portalab.capabilities.media import DIGEST, DigestItem
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.notifications.layout import ACCENT, SOFT, Brand, button, dress, site_brand
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import NotFound, ValidationFailed
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.news.articles import ArticleInput, ArticleService
from portalab.modules.news.editions.template import DEFAULT_CONTENTS
from portalab.modules.news.models import Article, Category, NewsletterEdition, NewsletterSchedule
from portalab.modules.news.permissions import NEWS_READ
from portalab.modules.news.settings import NEWSLETTER_ON

OPT_OUT = "news.newsletter.optOut"
CATEGORY = "news.newsletter"
PORTAL_URL = "notifications.email.portalUrl"
ZONE = "i18n.defaultTimeZone"
KINDS = ("releases", "additions", "upcoming", "edition")  # #316: « edition » — drawn with a template
CADENCES = {"daily": 1, "weekly": 7, "monthly": 30}
GROUPS = (
    ("movie", ("movie",)),
    ("series", ("series", "episode", "season")),
    ("book", ("book", "audiobook")),
    ("game", ("game",)),
    ("album", ("album", "track")),
)
log = get_logger("portalab.news")


class ScheduleNotFound(NotFound):
    default_code = "news.schedule_not_found"
    default_title = "Newsletter schedule not found"


def _provider(capabilities: CapabilityRegistry, name: str) -> Any | None:
    try:
        providers = capabilities.system_providers(name)
    except Exception:
        return None
    return providers[0].provider if providers else None


def email_html(
    title: str,
    body_html: str,
    portal: str,
    channel: str,
    unsubscribe: str,
    *,
    brand: Brand | None = None,
    read: tuple[str, str] | None = None,
    language: str = "en",
) -> str:
    """#320: the article as an e-mail in Portalab's look — its channel over its title, the article itself,
    the way to read it in the portal and to unsubscribe."""
    absolute = re.sub(r'(href|src)="/', rf'\1="{portal}/', body_html) if portal else body_html
    # the article's own markup keeps its words readable on the night card: its links in the accent
    absolute = re.sub(r"<a ", f'<a style="color:{ACCENT}" ', absolute)
    return dress(
        brand or Brand(portal=portal),
        title=title,
        body_html=f'<div style="color:{SOFT}">{absolute}</div>' + (button(*read) if read else ""),
        kicker=channel,
        note=unsubscribe,
        language=language,
    )


def next_run(cadence: str, weekday: int, hour: int, after: datetime, zone: ZoneInfo) -> datetime:
    """The next time the schedule writes its newsletter, strictly after ``after``."""
    local = after.astimezone(zone)
    candidate = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if cadence == "daily":
        if candidate <= local:
            candidate += timedelta(days=1)
    elif cadence == "weekly":
        candidate += timedelta(days=(weekday - candidate.weekday()) % 7)
        if candidate <= local:
            candidate += timedelta(days=7)
    else:  # monthly: the first ``weekday`` of the month
        first = candidate.replace(day=1)
        candidate = first + timedelta(days=(weekday - first.weekday()) % 7)
        if candidate <= local:
            month = (first + timedelta(days=32)).replace(day=1)
            candidate = month + timedelta(days=(weekday - month.weekday()) % 7)
    return candidate.astimezone(ZoneInfo("UTC"))


class Newsletters:
    def __init__(
        self,
        database: Database,
        articles: ArticleService,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.articles = articles
        self.capabilities = capabilities
        self.clock = clock
        self.editions: Any = None  # #316: the self-writing editions (set by the module)

    def _provider_of(self, name: str) -> Any | None:
        return _provider(self.capabilities, name)

    # --- settings ------------------------------------------------------------------------------------
    async def _setting(self, key: str, default: Any, user: UUID | None = None) -> Any:
        reader = _provider(self.capabilities, CONFIG)
        if reader is None:
            return default
        try:
            value = (await reader.get(key, user_id=user)).value
        except Exception:
            return default
        return default if value is None else value

    async def _zone(self) -> ZoneInfo:
        try:
            return ZoneInfo(str(await self._setting(ZONE, "UTC")))
        except (ZoneInfoNotFoundError, ValueError):
            return ZoneInfo("UTC")

    def _t(self, key: str, language: str, args: Mapping[str, Any] | None = None) -> str:
        renderer = _provider(self.capabilities, RENDERER)
        if renderer is None:
            return key
        return str(renderer.t(key, LocaleContext(language=language, locale=language), args, namespace="news"))

    # --- channels and subscriptions ------------------------------------------------------------------
    async def channels(self) -> list[Category]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(Category)
                        .where(Category.enabled.is_(True), Category.newsletter.is_(True))
                        .order_by(Category.position, Category.name)
                    )
                ).scalars()
            )

    async def opted_out(self, user: UUID) -> set[str]:
        value = await self._setting(OPT_OUT, [], user)
        return {str(v) for v in value} if isinstance(value, list) else set()

    # --- #326: the automatic newsletters, each subscribed until left --------------------------------------
    @staticmethod
    def auto_key(schedule_id: UUID) -> str:
        """An automatic newsletter's key among a member's subscriptions (« auto:<id> »)."""
        return f"auto:{schedule_id}"

    async def automatic(self) -> list[NewsletterSchedule]:
        """The automatic newsletters members receive: editions, switched on, e-mailed."""
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(NewsletterSchedule)
                        .where(
                            NewsletterSchedule.kind == "edition",
                            NewsletterSchedule.enabled.is_(True),
                            NewsletterSchedule.email.is_(True),
                        )
                        .order_by(NewsletterSchedule.name)
                    )
                ).scalars()
            )

    def when(self, schedule: NewsletterSchedule, language: str) -> str:
        """« every Friday at 18:00 »: when a newsletter goes out, in the member's language."""
        try:
            from babel.dates import get_day_names

            day = str(get_day_names("wide", locale=language)[schedule.weekday])
        except Exception:
            day = str(schedule.weekday)
        return self._t(
            f"subscriptions.when.{schedule.cadence}", language, {"day": day, "hour": schedule.hour}
        )

    async def received(self, user: UUID, schedule: NewsletterSchedule, out: set[str] | None = None) -> bool:
        """Whether a member receives an automatic newsletter: neither it nor its channel left."""
        left = out if out is not None else await self.opted_out(user)
        async with self.database.session() as session:
            category = await session.get(Category, schedule.category_id)
        return self.auto_key(schedule.id) not in left and (category is None or category.key not in left)

    async def subscribers(self, schedule: NewsletterSchedule) -> int:
        contact = _provider(self.capabilities, CONTACT)
        if contact is None:
            return 0
        return sum([1 for u in await contact.active_user_ids() if await self.received(u, schedule)])

    async def language_of(self, user: UUID) -> str:
        """A member's interface language, else the portal's."""
        own = await self._setting("i18n.language", None, user)
        return str(own or await self._setting("i18n.defaultLanguage", "en") or "en")

    async def subscriptions(self, user: UUID, language: str | None = None) -> list[dict[str, Any]]:
        language = language or await self.language_of(user)
        out = await self.opted_out(user)
        channels = await self.channels()
        names = {c.id: c for c in channels}
        automatic = []
        for schedule in await self.automatic():
            channel = names.get(schedule.category_id)
            async with self.database.session() as session:
                latest = await session.scalar(
                    select(NewsletterEdition.title)
                    .where(
                        NewsletterEdition.schedule_id == schedule.id, NewsletterEdition.status == "published"
                    )
                    .order_by(NewsletterEdition.published_at.desc())
                    .limit(1)
                )
            automatic.append(
                {
                    "key": self.auto_key(schedule.id),
                    "kind": "automatic",
                    "name": latest or (channel.name if channel else schedule.name),
                    "description": self.when(schedule, language),
                    "icon": "sparkles",
                    "channel": channel.key if channel else None,
                    # leaving the channel leaves its newsletters too
                    "subscribed": self.auto_key(schedule.id) not in out
                    and (channel is None or channel.key not in out),
                }
            )
        return automatic + [
            {
                "key": c.key,
                "kind": "channel",
                "name": c.name,
                "description": c.description,
                "icon": c.icon,
                "channel": None,
                "subscribed": c.key not in out,
            }
            for c in channels
        ]

    async def set_subscriptions(self, principal: Principal, changes: Mapping[str, bool]) -> None:
        user = principal.acting_for or principal.user_id
        if user is None:
            raise NotFound()
        known = {c.key for c in await self.channels()} | {self.auto_key(s.id) for s in await self.automatic()}
        out = await self.opted_out(user)
        for key, subscribed in changes.items():
            if key not in known:
                raise ValidationFailed("Unknown channel.", code="news.unknown_channel")
            if subscribed:
                out.discard(key)
            else:
                out.add(key)
        from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY

        writer = _provider(self.capabilities, CONFIG_WRITER_CAPABILITY)
        if writer is None:
            raise ValidationFailed("Preferences cannot be saved right now.", code="news.unavailable")
        await writer.set_user(principal, OPT_OUT, sorted(out))

    # --- e-mailing an article -----------------------------------------------------------------------
    async def email_article(self, row: Article) -> int:
        """E-mail a published article of a newsletter channel to the channel's subscribers, once."""
        async with self.database.session() as session:
            category = await session.get(Category, row.category_id) if row.category_id else None
        if category is None or not category.newsletter or row.audience.get("mode", "all") != "all":
            return 0  # only channels sent by e-mail, to everyone who may read them
        if not await self._setting(NEWSLETTER_ON, True):
            return 0  # issue 246: the newsletters are switched off
        notify = _provider(self.capabilities, NOTIFY)
        contact = _provider(self.capabilities, CONTACT)
        if notify is None or contact is None:
            return 0
        users = [u for u in await contact.active_user_ids() if category.key not in await self.opted_out(u)]
        portal = str(await self._setting(PORTAL_URL, "")).rstrip("/")
        link = f"{portal}/news/{row.slug}" if portal else f"/news/{row.slug}"
        unsubscribe_url = f"{portal}/settings/notifications#newsletters" if portal else ""
        language = row.language or "en"
        unsubscribe = self._t(
            "newsletter.unsubscribe", language, {"channel": category.name, "link": unsubscribe_url or "—"}
        )
        if users:
            await notify.send(
                CommunicationRequest(
                    category=CATEGORY,
                    template_key="news:notify.newsletter",
                    audience=Users(tuple(users)),
                    dedup_key=f"news.newsletter:{row.id}:{row.publish_seq}",
                    params={"title": row.title[:200], "channel": category.name[:120]},
                    source="module",
                    subject_ref=f"news:{row.id}",
                    required_permission=NEWS_READ,
                    action_url=f"/news/{row.slug}",
                    email_body={
                        "subject": row.title[:200],
                        "text": f"{row.title}\n\n{row.plain_text}\n\n{link}\n\n{unsubscribe}"[:100_000],
                        "html": email_html(
                            row.title,
                            row.rendered_html,
                            portal,
                            category.name,
                            unsubscribe,
                            brand=await site_brand(self._provider_of, portal, language),
                            read=(self._t("newsletter.read", language), link) if portal else None,
                            language=language,
                        ),
                    },
                )
            )
        async with self.database.unit_of_work() as uow:
            stored = await uow.session.get(Article, row.id, with_for_update=True)
            if stored is not None:
                stored.emailed_at = utc_now(self.clock)
        return len(users)

    # --- automatic newsletters -----------------------------------------------------------------------
    async def schedules(self) -> list[NewsletterSchedule]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(select(NewsletterSchedule).order_by(NewsletterSchedule.name))
                ).scalars()
            )

    async def _validate(self, session: Any, values: Mapping[str, Any]) -> None:
        if values.get("kind") not in KINDS or values.get("cadence") not in CADENCES:
            raise ValidationFailed("Unknown newsletter kind or cadence.", code="news.invalid_schedule")
        category = await session.get(Category, values.get("category_id"))
        if category is None or not category.enabled:
            raise ValidationFailed("This channel does not exist.", code="news.invalid_category")
        if values.get("kind") == "edition" and self.editions is not None:  # #316: drawn with a template
            await self.editions.template(str(values.get("template_key") or "portalab"))

    async def save_schedule(self, schedule_id: UUID | None, values: Mapping[str, Any]) -> NewsletterSchedule:
        now = utc_now(self.clock)
        zone = await self._zone()
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await self._validate(session, values)
            if schedule_id is None:
                row = NewsletterSchedule(created_at=now, updated_at=now, **values)
                session.add(row)
            else:
                found = await session.get(NewsletterSchedule, schedule_id, with_for_update=True)
                if found is None:
                    raise ScheduleNotFound("This newsletter schedule does not exist.")
                row = found
                for key, value in values.items():
                    setattr(row, key, value)
                row.updated_at = now
            row.next_run_at = next_run(row.cadence, row.weekday, row.hour, now, zone)
            await session.flush()
            return row

    async def delete_schedule(self, schedule_id: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(NewsletterSchedule, schedule_id)
            if row is None:
                raise ScheduleNotFound("This newsletter schedule does not exist.")
            await uow.session.delete(row)

    async def _items(self, schedule: NewsletterSchedule, now: datetime) -> list[DigestItem]:
        digest = _provider(self.capabilities, DIGEST)
        if digest is None:
            return []
        days = CADENCES.get(schedule.cadence, 7)
        today = now.date()
        if schedule.kind == "releases":
            items = await digest.releases(today - timedelta(days=days), today, 60)
        elif schedule.kind == "additions":
            items = await digest.additions(now - timedelta(days=days), 60)
        else:
            items = await digest.upcoming(today + timedelta(days=days), 60)
        wanted = set(schedule.media_kinds or [])
        if wanted:
            groups = {kind for key, kinds in GROUPS if key in wanted for kind in kinds}
            items = [i for i in items if i.kind in groups]
        return list(items)

    def _day(self, value: str, language: str) -> str:
        try:
            from babel.dates import format_date

            return str(format_date(date.fromisoformat(value[:10]), "d MMM", locale=language))
        except Exception:
            return value[:10]

    def compose(
        self, schedule: NewsletterSchedule, items: Sequence[DigestItem], now: datetime
    ) -> tuple[str, str, str]:
        """Title, summary and Markdown body of the newsletter (in the schedule's language)."""
        language = schedule.language or "en"
        title = self._t(
            f"newsletter.title.{schedule.kind}.{schedule.cadence}",
            language,
            {"date": self._day(now.date().isoformat(), language)},
        )
        summary = self._t(f"newsletter.intro.{schedule.kind}", language, {"count": len(items)})
        lines = [summary, ""]
        for group, kinds in GROUPS:
            chosen = [i for i in items if i.kind in kinds]
            if not chosen:
                continue
            lines.append(f"### {self._t(f'newsletter.group.{group}', language)}")
            lines.append("")
            for item in chosen:
                extra = f" · {item.detail}" if item.detail else ""
                lines.append(f"- [**{item.title}**]({item.route}) — {self._day(item.date, language)}{extra}")
            lines.append("")
        return title[:200], summary[:600], "\n".join(lines).strip()

    async def generate(self, schedule_id: UUID, *, force: bool = False) -> Article | NewsletterEdition | None:
        """Write, publish (and e-mail) one newsletter; nothing is written when there is nothing to tell.
        #316: an « edition » schedule writes an edition with its template instead of an article."""
        now = utc_now(self.clock)
        zone = await self._zone()
        async with self.database.session() as session:
            schedule = await session.get(NewsletterSchedule, schedule_id)
        if schedule is None:
            raise ScheduleNotFound("This newsletter schedule does not exist.")
        if not force and (not schedule.enabled or (schedule.next_run_at and schedule.next_run_at > now)):
            return None
        if schedule.kind == "edition" and self.editions is not None:
            edition = await self.editions.create(
                schedule.template_key or "portalab",
                days=schedule.days or CADENCES.get(schedule.cadence, 7),
                language=schedule.language,
                notice=schedule.notice,
                category_id=schedule.category_id,
                schedule_id=schedule.id,
                # #325: no choice saved — the usual contents, as the form shows them
                contents=schedule.contents if schedule.contents is not None else DEFAULT_CONTENTS,
                charts=schedule.charts,
                subject=schedule.subject,
            )
            edition = await self.editions.publish(edition.id, email=schedule.email)
            async with self.database.unit_of_work() as uow:
                row = await uow.session.get(NewsletterSchedule, schedule_id, with_for_update=True)
                if row is not None:
                    row.last_run_at = now
                    row.next_run_at = next_run(row.cadence, row.weekday, row.hour, now, zone)
            return edition  # type: ignore[no-any-return]
        items = await self._items(schedule, now)
        article: Article | None = None
        if items:
            title, summary, body = self.compose(schedule, items, now)
            draft = await self.articles.create(
                None,
                ArticleInput(
                    title=title,
                    body_md=body,
                    summary=summary,
                    category_id=schedule.category_id,
                    language=schedule.language,
                    email_on_publish=schedule.email,
                ),
            )
            article = await self.articles.transition(None, draft.id, "publish")
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(NewsletterSchedule, schedule_id, with_for_update=True)
            if row is not None:
                row.last_run_at = now
                row.next_run_at = next_run(row.cadence, row.weekday, row.hour, now, zone)
                if article is not None:
                    row.last_article_id = article.id
        return article

    async def run_due(self) -> int:
        if not await self._setting(NEWSLETTER_ON, True):
            return 0  # issue 246: the newsletters are switched off
        now = utc_now(self.clock)
        async with self.database.session() as session:
            due = list(
                (
                    await session.execute(
                        select(NewsletterSchedule.id).where(
                            NewsletterSchedule.enabled.is_(True), NewsletterSchedule.next_run_at <= now
                        )
                    )
                ).scalars()
            )
        written = 0
        for schedule_id in due:
            try:
                written += 1 if await self.generate(schedule_id) is not None else 0
            except Exception:
                log.warning("automatic newsletter not written")
        return written
