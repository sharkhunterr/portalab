"""#316 — self-writing editions: a template's sections filled with what the portal knows of the period
(its figures and most watched works, what arrived, came out or comes next, the news desk's articles, a
notice), kept as a snapshot and drawn once (HTML and text); a preview or a draft until published —
then every member reads it in the portal — and e-mailed to the channel's subscribers when asked."""

import re
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import delete, func, select

from portalab.capabilities.identity_directory import CONTACT
from portalab.capabilities.media import DIGEST, EDITION, DigestItem
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.notifications.layout import site_brand
from portalab.core.db import Database
from portalab.core.errors import NotFound, ValidationFailed
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.news.editions.render import render
from portalab.modules.news.editions.template import (
    BUILTIN,
    DEFAULT_CHARTS,
    Section,
    TemplateDefinition,
    compose,
)
from portalab.modules.news.models import Article, Category, NewsletterEdition, NewsletterTemplate
from portalab.modules.news.newsletters import CATEGORY, PORTAL_URL, Newsletters, _provider
from portalab.modules.news.permissions import NEWS_READ
from portalab.modules.news.settings import NEWSLETTER_ON

LIMIT = 60  # titles asked of the library per section, before each section keeps its own number
PREVIEW_KEEP = timedelta(days=1)
log = get_logger("portalab.news")


# #325: what an e-mail's subject may say — each variable, in English and in French
VARIABLES = {
    "site": "site",
    "date": "date",
    "day": "day",
    "jour": "day",
    "week": "week",
    "semaine": "week",
    "month": "month",
    "mois": "month",
    "year": "year",
    "année": "year",
    "annee": "year",
    "period": "period",
    "période": "period",
    "periode": "period",
    "number": "number",
    "numéro": "number",
    "numero": "number",
    "channel": "channel",
    "chaîne": "channel",
    "chaine": "channel",
}
VARIABLE = re.compile(r"\{([^{}]{1,12})\}")


def subject_of(pattern: str, values: Mapping[str, str]) -> str:
    """The subject with its variables replaced — an unknown one stays as written (never code)."""

    def one(match: re.Match[str]) -> str:
        name = VARIABLES.get(match.group(1).strip().lower())
        return values.get(name, match.group(0)) if name else match.group(0)

    return " ".join(VARIABLE.sub(one, pattern).split())[:200]


class TemplateNotFound(NotFound):
    default_code = "news.template_not_found"
    default_title = "Newsletter template not found"


class EditionNotFound(NotFound):
    default_code = "news.edition_not_found"
    default_title = "Newsletter edition not found"


# the kinds of titles each group gathers — #323: the audiobooks apart from the books
GROUPS: dict[str, tuple[str, ...]] = {
    "movie": ("movie",),
    "series": ("series", "episode", "season"),
    "book": ("book",),
    "audiobook": ("audiobook",),
    "game": ("game",),
    "album": ("album", "track"),
}


def _kinds(media: Sequence[str]) -> set[str]:
    return {kind for group in media for kind in GROUPS.get(group, ())}


class Editions:
    def __init__(self, database: Database, newsletters: Newsletters, *, clock: Clock | None = None) -> None:
        self.database = database
        self.newsletters = newsletters
        self.capabilities = newsletters.capabilities
        self.clock = clock

    # --- templates -----------------------------------------------------------------------------------
    async def templates(self) -> list[tuple[str, TemplateDefinition, bool]]:
        """Every template: the built-in ones first, then the news desk's own."""
        async with self.database.session() as session:
            rows = (
                await session.execute(select(NewsletterTemplate).order_by(NewsletterTemplate.key))
            ).scalars()
            own = []
            for row in rows:
                try:
                    own.append((row.key, TemplateDefinition.model_validate(row.definition), False))
                except ValidationError:
                    log.warning("newsletter template unreadable")
        return [(key, definition, True) for key, definition in BUILTIN.items()] + own

    async def template(self, key: str) -> TemplateDefinition:
        if key in BUILTIN:
            return BUILTIN[key]
        async with self.database.session() as session:
            row = await session.get(NewsletterTemplate, key)
        if row is None:
            raise TemplateNotFound("This template does not exist.")
        return TemplateDefinition.model_validate(row.definition)

    async def save_template(self, key: str, definition: TemplateDefinition) -> None:
        if key in BUILTIN:
            raise ValidationFailed("A built-in template cannot be changed.", code="news.template_builtin")
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(NewsletterTemplate, key, with_for_update=True)
            if row is None:
                uow.session.add(
                    NewsletterTemplate(
                        key=key, definition=definition.model_dump(mode="json"), created_at=now, updated_at=now
                    )
                )
            else:
                row.definition = definition.model_dump(mode="json")
                row.updated_at = now

    async def delete_template(self, key: str) -> None:
        if key in BUILTIN:
            raise ValidationFailed("A built-in template cannot be deleted.", code="news.template_builtin")
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(NewsletterTemplate, key)
            if row is None:
                raise TemplateNotFound("This template does not exist.")
            await uow.session.delete(row)

    # --- what an edition tells -----------------------------------------------------------------------
    def _day(self, value: str | date | None, language: str, form: str = "d MMM") -> str:
        if not value:
            return ""
        try:
            from babel.dates import format_date

            day = value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
            return str(format_date(day, form, locale=language))
        except Exception:
            return str(value)[:10]

    def _item(
        self, item: DigestItem, language: str, extra: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        out = asdict(item)
        out["genres"] = list(item.genres)
        out["day"] = self._day(item.date, language)
        out.update(extra or {})
        return out

    def _title(self, section: Section, language: str) -> str:
        if section.title:
            return section.title
        if section.kind == "additions" and len(section.media) == 1:  # #323: « Nouveaux films »…
            return self.newsletters._t(f"edition.heading.{section.media[0]}", language)
        base = self.newsletters._t(f"edition.section.{section.kind}", language)
        if not section.media or section.kind in ("tv", "upcoming"):
            return base
        names = ", ".join(self.newsletters._t(f"edition.group.{m}", language) for m in section.media)
        return f"{base} · {names}"

    async def collect(
        self, template: TemplateDefinition, *, days: int, language: str, notice: str | None, brand: str
    ) -> dict[str, Any]:
        now = utc_now(self.clock)
        today = now.date()
        digest = _provider(self.capabilities, DIGEST)
        source = _provider(self.capabilities, EDITION)
        tops = max([s.limit for s in template.sections if s.kind == "top"] or [5])
        period: dict[str, Any] = {}
        if source is not None and any(s.kind in ("stats", "top") for s in template.sections):
            try:
                zone = await self.newsletters._zone()  # #324: the hours of the day, the portal's own
                period = await source.period(days, top=tops, tz=str(zone))
            except Exception:
                log.warning("edition figures unavailable")
        cache: dict[str, list[DigestItem]] = {}

        async def titles(asked: str) -> list[DigestItem]:
            kind = "upcoming" if asked == "tv" else asked  # the TV programme reads the same calendar
            if kind not in cache:
                if digest is None:
                    cache[kind] = []
                elif kind == "additions":
                    cache[kind] = await digest.additions(now - timedelta(days=days), LIMIT)
                elif kind == "releases":
                    cache[kind] = await digest.releases(today - timedelta(days=days), today, LIMIT)
                elif kind == "requests":  # #323: what members asked for
                    try:
                        cache[kind] = await source.requests(days, LIMIT) if source is not None else []
                    except Exception:
                        log.warning("edition requests unavailable")
                        cache[kind] = []
                else:  # « upcoming », and « tv »: the same calendar
                    cache[kind] = await digest.upcoming(today + timedelta(days=days), LIMIT)
            return cache[kind]

        sections: list[dict[str, Any]] = []
        pictures: set[str] = set()
        for section in template.sections:
            items: list[dict[str, Any]] = []
            if section.kind in ("additions", "releases", "upcoming", "requests", "tv"):
                found = await titles(section.kind)
                media = ["series"] if section.kind == "tv" else section.media  # #323: the episodes airing
                if media:
                    wanted = _kinds(media)
                    found = [i for i in found if i.kind in wanted]
                items = [self._item(i, language) for i in found[: section.limit]]
                if section.kind == "requests":  # each request says where it stands
                    for item in items:
                        item["detail"] = self.newsletters._t(f"edition.request.{item['detail']}", language)
            elif section.kind == "top":
                ranked = period.get("top") or []
                if section.media:
                    wanted = _kinds(section.media)
                    ranked = [r for r in ranked if r["item"].kind in wanted]
                items = [
                    self._item(r["item"], language, {"plays": r["plays"], "seconds": r["seconds"]})
                    for r in ranked[: section.limit]
                ]
            elif section.kind == "articles":
                items = await self._articles(now - timedelta(days=days), section.limit, language)
            pictures |= {str(i["picture"]) for i in items if i.get("picture")}
            sections.append({"kind": section.kind, "title": self._title(section, language), "items": items})
        totals = period.get("totals") or {}
        stats = (
            {
                **totals,
                "previous": period.get("previous") or {},
                "by_kind": period.get("by_kind") or [],
                # #324: what the charts draw, their labels in the edition's language
                **self._charts(period, language),
            }
            if totals
            else None
        )
        count = sum(len(s["items"]) for s in sections if s["kind"] in ("additions", "releases"))
        start = today - timedelta(days=days)
        return {
            "site": brand,
            "language": language,
            "days": days,
            "notice": (notice or "").strip() or None,
            "stats": stats,
            "sections": sections,
            "pictures": sorted(pictures),
            "day": self._day(today, language, "d MMMM y"),
            "period_label": self.newsletters._t(
                "edition.period",
                language,
                {"start": self._day(start, language), "end": self._day(today, language)},
            ),
            "preheader": self.newsletters._t(
                "edition.preheader",
                language,
                {"count": count, "hours": round(float(totals.get("seconds") or 0) / 3600)},
            ),
        }

    def _charts(self, period: Mapping[str, Any], language: str) -> dict[str, Any]:
        """#324: the charts' series in hours, with their labels (a few dates, the days, some hours)."""
        points = (period.get("timeline") or {}).get("points") or []
        count = len(points)
        marks = {0, count // 2, count - 1} if count else set()
        try:
            from babel.dates import get_day_names

            days = get_day_names("abbreviated", locale=language)
            weekday_names = [str(days[i]) for i in range(7)]
        except Exception:
            weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        def hours(seconds: float) -> float:
            return round(float(seconds) / 3600, 1)

        return {
            "activity": {
                "values": [hours(p["seconds"]) for p in points],
                "labels": [
                    self._day(p["date"], language) if i in marks else "" for i, p in enumerate(points)
                ],
            },
            "weekdays": {
                "values": [hours(s) for s in period.get("weekdays") or []],
                "labels": weekday_names,
            },
            "hours": {
                "values": [hours(s) for s in period.get("hours") or []],
                "labels": [f"{h} h" if h % 6 == 0 else "" for h in range(24)],
            },
            "genres": [{"name": g["name"], "hours": hours(g["seconds"])} for g in period.get("genres") or []],
        }

    async def _variables(
        self,
        now: datetime,
        language: str,
        days: int,
        *,
        brand: str,
        channel: str | None,
        schedule_id: UUID | None,
        period: Mapping[str, Any],
    ) -> dict[str, str]:
        """#325: the subject's variables — the site, the day (long and short), the ISO week, the month, the
        year, the period, the edition's number (its schedule's), the channel."""
        local = now.astimezone(await self.newsletters._zone()).date()
        number = 1
        if schedule_id is not None:
            async with self.database.session() as session:
                number += int(
                    await session.scalar(
                        select(func.count())
                        .select_from(NewsletterEdition)
                        .where(
                            NewsletterEdition.schedule_id == schedule_id,
                            NewsletterEdition.status == "published",
                        )
                    )
                    or 0
                )
        return {
            "site": brand,
            "date": self._day(local, language, "d MMMM y"),
            "day": self._day(local, language, "d MMM"),
            "week": str(local.isocalendar().week),
            "month": self._day(local, language, "MMMM"),
            "year": str(local.year),
            "period": str(period.get("period_label") or ""),
            "number": str(number),
            "channel": channel or "",
        }

    async def _articles(self, since: datetime, limit: int, language: str) -> list[dict[str, Any]]:
        """The news desk's articles of the period, the ones every member may read."""
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Article)
                    .where(Article.status == "published", Article.published_at >= since)
                    .order_by(Article.published_at.desc())
                    .limit(limit * 3)
                )
            ).scalars()
            found = [r for r in rows if (r.audience or {}).get("mode", "all") == "all"][:limit]
        return [
            {
                "title": r.title,
                "kind": "article",
                "route": f"/news/{r.slug}",
                "summary": r.summary,
                "day": self._day(r.published_at.date() if r.published_at else None, language),
            }
            for r in found
        ]

    # --- editions ------------------------------------------------------------------------------------
    async def _portal(self) -> str:
        return str(await self.newsletters._setting(PORTAL_URL, "")).rstrip("/")

    async def create(
        self,
        template_key: str,
        *,
        days: int,
        language: str,
        notice: str | None = None,
        category_id: UUID | None = None,
        schedule_id: UUID | None = None,
        status: str = "draft",
        created_by: UUID | None = None,
        definition: TemplateDefinition | None = None,
        contents: Sequence[str] | None = None,
        charts: Sequence[str] | None = None,
        subject: str | None = None,
    ) -> NewsletterEdition:
        """Write an edition (a preview of an unsaved template when ``definition`` is given) — #323: telling
        the ``contents`` asked, in the template's look (else the template's own sections)."""
        template = definition or await self.template(template_key)
        if contents is not None:
            template = compose(template, list(contents))
        now = utc_now(self.clock)
        channel = None
        if category_id is not None:
            async with self.database.session() as session:
                found = await session.get(Category, category_id)
            if found is None:
                raise ValidationFailed("This channel does not exist.", code="news.invalid_category")
            channel = found.name
        # #320: the name over the title — the template's, else the site's own
        site = await site_brand(lambda name: _provider(self.capabilities, name), "", language)
        brand = template.brand or site.name or channel or "Portalab"
        snapshot = await self.collect(template, days=days, language=language, notice=notice, brand=brand)
        edition_id = UUID(int=0)
        token = secrets.token_urlsafe(32)
        title = self.newsletters._t("edition.title", language, {"site": brand, "date": snapshot["day"]})
        if subject and subject.strip():  # #325: the subject the news desk wrote, its variables filled
            title = (
                subject_of(
                    subject,
                    await self._variables(
                        now,
                        language,
                        days,
                        brand=brand,
                        channel=channel,
                        schedule_id=schedule_id,
                        period=snapshot,
                    ),
                )
                or title
            )
        headline = self.newsletters._t("edition.headline", language, {"date": snapshot["day"]})
        snapshot.update(
            {"title": title, "headline": headline, "portal": await self._portal(), "token": token}
        )
        async with self.database.unit_of_work() as uow:
            session = uow.session
            if status == "preview":  # a preview replaces the previous ones (and none outlives a day)
                await session.execute(
                    delete(NewsletterEdition).where(
                        NewsletterEdition.status == "preview",
                        (NewsletterEdition.created_by == created_by)
                        | (NewsletterEdition.created_at < now - PREVIEW_KEEP),
                    )
                )
            row = NewsletterEdition(
                schedule_id=schedule_id,
                category_id=category_id,
                template_key=template_key,
                title=title[:200],
                language=language,
                days=days,
                status=status,
                data={},
                html="",
                text="",
                token=token,
                created_by=created_by,
                created_at=now,
            )
            session.add(row)
            await session.flush()
            edition_id = row.id
            snapshot["page"] = f"/news/editions/{edition_id}"
            snapshot["contents"] = list(contents) if contents is not None else None
            snapshot["charts"] = list(charts) if charts is not None else list(DEFAULT_CHARTS)  # #324
            row.data = snapshot
            row.html, row.text = render(
                template, snapshot, lambda key, args: self.newsletters._t(key, language, args)
            )
            await session.flush()
            return row

    async def get(self, edition_id: UUID) -> NewsletterEdition:
        async with self.database.session() as session:
            row = await session.get(NewsletterEdition, edition_id)
        if row is None:
            raise EditionNotFound("This edition does not exist.")
        return row

    async def listing(self, *, published_only: bool, limit: int = 50) -> list[NewsletterEdition]:
        stmt = select(NewsletterEdition)
        stmt = (
            stmt.where(NewsletterEdition.status == "published").order_by(
                NewsletterEdition.published_at.desc()
            )
            if published_only
            else stmt.where(NewsletterEdition.status != "preview").order_by(
                NewsletterEdition.created_at.desc()
            )
        )
        async with self.database.session() as session:
            return list((await session.execute(stmt.limit(limit))).scalars())

    async def publish(self, edition_id: UUID, *, email: bool) -> NewsletterEdition:
        """Readable by every member from now on; e-mailed once when asked."""
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(NewsletterEdition, edition_id, with_for_update=True)
            if row is None or row.status == "preview":
                raise EditionNotFound("This edition does not exist.")
            if row.status != "published":
                row.status = "published"
                row.published_at = now
        edition = await self.get(edition_id)
        if email and edition.emailed_at is None:
            await self.email(edition)
            edition = await self.get(edition_id)
        return edition

    async def delete(self, edition_id: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(NewsletterEdition, edition_id)
            if row is None:
                raise EditionNotFound("This edition does not exist.")
            await uow.session.delete(row)

    async def email(self, edition: NewsletterEdition) -> int:
        """The edition itself as the e-mail, to every member but those who left its channel (or all
        newsletters)."""
        if not await self.newsletters._setting(NEWSLETTER_ON, True):
            return 0
        notify = _provider(self.capabilities, NOTIFY)
        contact = _provider(self.capabilities, CONTACT)
        if notify is None or contact is None:
            return 0
        channel_key, channel_name = None, str(edition.data.get("site") or "")
        if edition.category_id is not None:
            async with self.database.session() as session:
                category = await session.get(Category, edition.category_id)
            if category is not None:
                channel_key, channel_name = category.key, category.name
        users = [
            u
            for u in await contact.active_user_ids()
            if channel_key is None or channel_key not in await self.newsletters.opted_out(u)
        ]
        if users:
            await notify.send(
                CommunicationRequest(
                    category=CATEGORY,
                    template_key="news:notify.newsletter",
                    audience=Users(tuple(users)),
                    dedup_key=f"news.edition:{edition.id}",
                    params={"title": edition.title[:200], "channel": channel_name[:120]},
                    source="module",
                    subject_ref=f"news-edition:{edition.id}",
                    required_permission=NEWS_READ,
                    action_url=f"/news/editions/{edition.id}",
                    email_body={
                        "subject": edition.title[:200],
                        "text": edition.text[:100_000],
                        "html": edition.html,
                    },
                )
            )
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(NewsletterEdition, edition.id, with_for_update=True)
            if row is not None:
                row.emailed_at = utc_now(self.clock)
                row.recipients = len(users)
        return len(users)

    # --- the real e-mail, to its reader alone (#317) ------------------------------------------------------
    @staticmethod
    def _absolute(html: str, base: str) -> str:
        """The portal's own addresses made whole (an edition written without the portal's address)."""
        return re.sub(r'(href|src)="/', rf'\1="{base}/', html) if base else html

    async def send_test(self, edition: NewsletterEdition, user: UUID, base: str) -> bool:
        """The edition to its reader alone, as the members would get it (each test a new e-mail)."""
        notify = _provider(self.capabilities, NOTIFY)
        if notify is None:
            return False
        html = edition.html if await self._portal() else self._absolute(edition.html, base)
        await notify.send(
            CommunicationRequest(
                category=CATEGORY,
                template_key="news:notify.newsletter",
                audience=Users((user,)),
                dedup_key=f"news.edition-test:{edition.id}:{secrets.token_hex(6)}",
                params={"title": edition.title[:200], "channel": str(edition.data.get("site") or "")[:120]},
                source="module",
                subject_ref=f"news-edition:{edition.id}",
                required_permission=NEWS_READ,
                action_url=f"/news/editions/{edition.id}",
                email_body={"subject": f"[Test] {edition.title}"[:200], "text": edition.text, "html": html},
            )
        )
        return True

    async def picture(self, token: str, image_id: str) -> bytes | None:
        """A picture an edition shows, by the edition's token (mail clients carry no session) — only those."""
        async with self.database.session() as session:
            row = (
                await session.execute(select(NewsletterEdition).where(NewsletterEdition.token == token))
            ).scalar_one_or_none()
        if row is None or image_id not in (row.data.get("pictures") or []):
            return None
        source = _provider(self.capabilities, EDITION)
        return await source.picture(image_id) if source is not None else None
