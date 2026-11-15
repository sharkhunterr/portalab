"""Issue 457: Portalab's own member guide, shipped with each release and kept in the wiki.

The guide (``docs/member-guide/<language>/*.md``, a small header then Markdown) is written in English and
French. Each page is installed as one wiki page — the English text its source, the French its translation —
so every member reads it in their language. Its screenshots are files of the release, served read-only
(``portalab-guide:<language>/<name>``), never copied into the database.

- **Installed while the wiki module is on and the guide switched on** (``wiki.guide.enabled``, on by
  default). Each start (and each change of the switch) brings the pages in line with the release.
- **The administrator's word wins**: a page whose history holds any revision not written by the guide, or a
  translation saved by someone, is never written over again; a page the administrator deleted is not
  brought back (until the guide is switched off and on again).
- **Switched off**: the pages the guide still owns are deleted; those the administrator changed stay theirs.
- Pages imported by hand before (``scripts/wiki_import.py``, change note « Guide du membre ») are adopted.
- The site's currency replaces « Coins ». One process at a time (an advisory lock); idempotent.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.content.audience import Audience
from portalab.capabilities.i18n import SITE_TERMS
from portalab.capabilities.plugins import TOGGLE_WRITER
from portalab.core.authz_port import Principal
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.wiki.models import GuidePage, Page, PageTranslation, Revision

log = get_logger("portalab.wiki.guide")

SOURCE = "en"  # the pages' source language; the others are translations
GUIDE_NOTE = "Portalab member guide"  # every revision the guide writes carries it
IMPORTED_NOTES = ("Guide du membre",)  # pages imported by hand before issue 457 (scripts/wiki_import.py)
SYSTEM = Principal(channel="system")
LOCK = 457_000_457  # pg advisory lock: one synchronisation at a time across processes
IMAGE_GUIDE = Path("/app/guide")
_SHOT = re.compile(r"!\[([^\]]*)\]\(shot:([a-z0-9][a-z0-9-]*)\)")
_HEADER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
_LANGUAGE = re.compile(r"^[a-z]{2}$")


def guide_root(env: Mapping[str, str] | None = None) -> Path | None:
    """Where the guide is: ``PORTALAB_GUIDE_DIR``, the image's folder, or the repository's (development)."""
    configured = (env if env is not None else os.environ).get("PORTALAB_GUIDE_DIR")
    if configured:
        return Path(configured)
    if IMAGE_GUIDE.is_dir():
        return IMAGE_GUIDE
    repository = Path(__file__).resolve().parents[5] / "docs" / "member-guide"
    return repository if repository.is_dir() else None


def shot_path(root: Path | None, language: str, name: str) -> Path | None:
    """A screenshot of the guide, or ``None`` — never a file outside ``images/<language>/``."""
    if root is None or not _LANGUAGE.match(language) or not _NAME.match(name):
        return None
    folder = (root / "images" / language).resolve()
    path = (folder / f"{name}.jpg").resolve()
    return path if path.parent == folder and path.is_file() else None


@dataclass
class GuideText:
    title: str
    body: str
    tags: list[str]


@dataclass
class GuideDoc:
    slug: str
    position: int
    parent: str | None
    help_keys: list[str]
    texts: dict[str, GuideText] = field(default_factory=dict)


def _header(raw: str) -> tuple[dict[str, Any], str]:
    match = _HEADER.match(raw)
    if not match:
        raise ValueError("no header")
    values: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            values[key.strip()] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
        else:
            values[key.strip()] = value.strip("'\"")
    return values, raw[match.end() :].strip() + "\n"


def read_guide(root: Path) -> list[GuideDoc]:
    """The guide's pages, parents first; a page needs its English text (its source)."""
    docs: dict[str, GuideDoc] = {}
    for folder in sorted(p for p in root.iterdir() if p.is_dir() and _LANGUAGE.match(p.name)):
        for file in sorted(folder.glob("*.md")):
            try:
                values, body = _header(file.read_text(encoding="utf-8"))
                slug = str(values["slug"])
            except (KeyError, ValueError, OSError):
                log.warning("guide page left out: %s", file.name)
                continue
            doc = docs.setdefault(
                slug,
                GuideDoc(
                    slug=slug,
                    position=int(values.get("position") or 0),
                    parent=values.get("parent") or None,
                    help_keys=list(values.get("help_keys") or []),
                ),
            )
            doc.texts[folder.name] = GuideText(
                str(values.get("title") or slug), body, list(values.get("tags") or [])
            )
    pages = [doc for doc in docs.values() if SOURCE in doc.texts]
    top = next((doc.slug for doc in pages if doc.parent == "none"), None)
    for doc in pages:
        # no parent named: under the guide's top page (the one whose parent is « none »)
        doc.parent = None if doc.parent == "none" or doc.slug == top else (doc.parent or top)

    def depth(doc: GuideDoc, seen: int = 0) -> int:
        parent = next((d for d in pages if d.slug == doc.parent), None)
        return 0 if parent is None or seen > 10 else 1 + depth(parent, seen + 1)

    return sorted(pages, key=lambda doc: (depth(doc), doc.position, doc.slug))


@dataclass
class GuideReport:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    adopted: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)  # changed by the administrator: theirs
    removed: list[str] = field(default_factory=list)
    skipped: str = ""

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated or self.adopted or self.removed)

    def lines(self) -> list[str]:
        out = [
            f"{name}: {', '.join(items)}"
            for name, items in (
                ("created", self.created),
                ("updated", self.updated),
                ("adopted", self.adopted),
                ("kept (changed by the administrator)", self.kept),
                ("removed", self.removed),
            )
            if items
        ]
        return out or [self.skipped or "unchanged"]


class GuideSync:
    def __init__(
        self, pages: Any, capabilities: Any, root: Path | None, *, clock: Clock | None = None
    ) -> None:
        self.pages = pages  # PageService: its renderer, revisions, derived data and events
        self.database = pages.database
        self.capabilities = capabilities
        self.root = root
        self.clock = clock

    # --- what the portal says ------------------------------------------------------------------------
    async def _wiki_on(self) -> bool:
        providers = self.capabilities.system_providers(TOGGLE_WRITER)
        if not providers:
            return True  # no module manager (tests, a bare portal): the wiki is there
        try:
            return bool(await providers[0].provider.is_enabled("module", "wiki"))
        except Exception:
            return False

    def _currency(self, language: str) -> tuple[str | None, str | None]:
        try:
            providers = self.capabilities.system_providers(SITE_TERMS)
            terms = providers[0].provider.terms(language) if providers else None
        except Exception:
            terms = None
        return (terms.currency_one, terms.currency_other) if terms is not None else (None, None)

    def localized(self, doc: GuideDoc, language: str) -> GuideText:
        """A page's text as installed: the site's currency, the screenshots as the release's files."""
        source = doc.texts[language]
        one, other = self._currency(language)

        def words(value: str) -> str:
            if other:
                value = re.sub(r"\bCoins\b", other, value)
            if one:
                value = re.sub(r"\bCoin\b", one, value)
            return value

        def shot(match: re.Match[str]) -> str:
            alt, name = match.groups()
            for candidate in (language, SOURCE, *sorted(doc.texts)):
                if shot_path(self.root, candidate, name):
                    return f"![{alt}](portalab-guide:{candidate}/{name})"
            return ""  # a screenshot the release does not have: left out

        return GuideText(words(source.title), _SHOT.sub(shot, words(source.body)), source.tags)

    # --- the synchronisation --------------------------------------------------------------------------
    async def run(self, enabled: bool = True) -> GuideReport:
        report = GuideReport()
        if self.root is None or not self.root.is_dir():
            report.skipped = "no guide in this build"
            return report
        if not await self._wiki_on():
            report.skipped = "the wiki module is off"
            return report
        docs = read_guide(self.root) if enabled else []
        async with self.database.unit_of_work() as uow:
            session = uow.session
            if not await session.scalar(text(f"SELECT pg_try_advisory_xact_lock({LOCK})")):
                report.skipped = "another process is synchronising the guide"
                return report
            rows = {row.slug: row for row in (await session.scalars(select(GuidePage))).all()}
            if not enabled:
                await self._remove(session, rows, report)
                return report
            ids: dict[str, Any] = {}
            for doc in docs:
                await self._one(session, doc, rows.get(doc.slug), ids, report)
        return report

    async def _ours(self, session: AsyncSession, page: Page) -> bool:
        """Every revision of the page written by the guide (or by its import before issue 457)."""
        notes = (await session.scalars(select(Revision.change_note).where(Revision.page_id == page.id))).all()
        return bool(notes) and all(n.startswith(GUIDE_NOTE) or n in IMPORTED_NOTES for n in notes)

    async def _one(
        self,
        session: AsyncSession,
        doc: GuideDoc,
        row: GuidePage | None,
        ids: dict[str, Any],
        report: GuideReport,
    ) -> None:
        now = utc_now(self.clock)
        page = await session.scalar(select(Page).where(Page.slug == doc.slug).with_for_update())
        if row is not None and row.state == "dismissed":
            if page is not None:
                ids[doc.slug] = page.id
            return
        if page is not None and not await self._ours(session, page):
            if row is None or row.state == "removed":
                return  # a page of the administrator's own under this name: never touched
            report.kept.append(doc.slug)  # changed by its administrator: theirs from now on
            ids[doc.slug] = page.id
            return
        if page is not None and page.status == "deleted" and row is not None and row.state == "installed":
            row.state, row.updated_at = "dismissed", now  # deleted by its administrator
            return
        parent_id = ids.get(doc.parent) if doc.parent else None
        source = self.localized(doc, SOURCE)
        tags = sorted({t for text_ in doc.texts.values() for t in text_.tags})
        if page is None:
            page = await self._create(session, doc, source, parent_id, tags, now)
            report.created.append(doc.slug)
        else:
            adopted = row is None or row.state == "removed"
            changed = await self._revise(session, page, doc, source, parent_id, tags, now)
            if adopted:
                report.adopted.append(doc.slug)
            elif changed:
                report.updated.append(doc.slug)
        ids[doc.slug] = page.id
        for language in sorted(doc.texts):
            if language != SOURCE:
                await self._translate(session, page, language, self.localized(doc, language), now)
        if row is None:
            session.add(GuidePage(slug=doc.slug, page_id=page.id, state="installed", updated_at=now))
        else:
            row.page_id, row.state, row.updated_at = page.id, "installed", now

    async def _create(
        self,
        session: AsyncSession,
        doc: GuideDoc,
        source: GuideText,
        parent_id: Any,
        tags: list[str],
        now: Any,
    ) -> Page:
        rendered = await self.pages._render(source.body)
        page = Page(
            slug=doc.slug,
            parent_id=parent_id,
            position=doc.position,
            status="published",
            title=source.title.strip()[:200],
            language=SOURCE,
            current_version=1,
            audience=Audience().model_dump(),
            readable_by_ai=True,
            help_keys=sorted(set(doc.help_keys)),
            search_vector=self.pages._vector(source.title, rendered.text),
            created_by=None,
            created_at=now,
            updated_at=now,
        )
        session.add(page)
        await session.flush()
        session.add(self.pages._revision(page, source.title, source.body, rendered, SYSTEM, GUIDE_NOTE, now))
        await self.pages._derived(session, page, tags, rendered.links)
        await self.pages._publish(session, "created", page)
        await self.pages._publish(session, "published", page)
        return page

    async def _revise(
        self,
        session: AsyncSession,
        page: Page,
        doc: GuideDoc,
        source: GuideText,
        parent_id: Any,
        tags: list[str],
        now: Any,
    ) -> bool:
        current = await session.get(Revision, (page.id, page.current_version))
        same = (
            current is not None
            and page.language == SOURCE
            and current.title == source.title.strip()[:200]
            and current.body_md.strip() == source.body.strip()
            and sorted(page.help_keys) == sorted(set(doc.help_keys))
        )
        revived = page.status != "published"
        page.parent_id, page.position = parent_id, doc.position
        if revived:
            page.status, page.updated_at = "published", now
            await self.pages._publish(session, "published", page)
        if same:
            return revived
        rendered = await self.pages._render(source.body)
        page.language = SOURCE  # an adopted page imported in French: English is its source now
        page.current_version += 1
        page.title = source.title.strip()[:200]
        page.audience, page.readable_by_ai = Audience().model_dump(), True
        page.help_keys = sorted(set(doc.help_keys))
        page.search_vector = self.pages._vector(page.title, rendered.text)
        page.updated_at = now
        session.add(self.pages._revision(page, source.title, source.body, rendered, SYSTEM, GUIDE_NOTE, now))
        await self.pages._derived(session, page, tags, rendered.links)
        await self.pages._publish(session, "revised", page)
        return True

    async def _translate(
        self, session: AsyncSession, page: Page, language: str, value: GuideText, now: Any
    ) -> None:
        row = await session.get(PageTranslation, (page.id, language), with_for_update=True)
        if row is not None and row.updated_by is not None:
            return  # saved by someone: theirs
        if (
            row is not None
            and row.title == value.title.strip()[:200]
            and row.body_md.strip() == value.body.strip()
            and row.source_version == page.current_version
        ):
            return
        rendered = await self.pages._render(value.body)
        values = {
            "title": value.title.strip()[:200],
            "body_md": value.body,
            "rendered_html": rendered.html,
            "renderer_version": rendered.renderer_version,
            "source_version": page.current_version,
            "state": "translated",
            "updated_by": None,
            "updated_at": now,
        }
        if row is None:
            session.add(PageTranslation(page_id=page.id, language=language, **values))
        else:
            for key, item in values.items():
                setattr(row, key, item)

    async def _remove(self, session: AsyncSession, rows: dict[str, GuidePage], report: GuideReport) -> None:
        """The guide switched off: the pages it still owns go, deepest first; the others stay theirs."""
        now = utc_now(self.clock)
        pages = {
            row.slug: await session.get(Page, row.page_id, with_for_update=True)
            for row in rows.values()
            if row.page_id is not None
        }

        def depth(page: Page | None) -> int:
            level, current = 0, page
            while current is not None and current.parent_id is not None and level < 10:
                current = next(
                    (p for p in pages.values() if p is not None and p.id == current.parent_id), None
                )
                level += 1
            return level

        for slug, page in sorted(pages.items(), key=lambda item: -depth(item[1])):
            row = rows[slug]
            if page is None or page.status == "deleted":
                row.state, row.updated_at = "removed", now
                continue
            if not await self._ours(session, page):
                report.kept.append(slug)
                continue
            children = await session.scalar(
                select(func.count()).where(Page.parent_id == page.id, Page.status != "deleted")
            )
            if children:
                report.kept.append(slug)  # holds pages of its administrator's
                continue
            page.status, page.updated_at = "deleted", now
            await self.pages._publish(session, "deleted", page)
            row.state, row.updated_at = "removed", now
            report.removed.append(slug)
        for row in rows.values():
            if row.page_id is None:
                row.state, row.updated_at = "removed", now
