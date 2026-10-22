"""``PageService`` (T011, T014, T016; R8-R10): wiki pages with optimistic concurrency, append-only revisions,
tree, tags, derived links, publication states, translations — and the read rules every surface shares:

* ``deleted`` pages exist for nobody (links show "deleted");
* drafts are visible to editors only; published and archived pages to ``wiki.read`` holders within the
  page audience (archived pages are flagged, never a dead end);
* saving requires the ``base_version`` the editor started from: a stale base answers 409
  ``wiki.version_conflict`` with a server-side diff; every save appends a revision; restoring creates a new
  revision referencing the restored one — earlier revisions are never touched.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.content.audience import Audience, can_read
from portalab.capabilities.content.render import RENDERER_VERSION, render_markdown
from portalab.capabilities.i18n import normalize_for_search
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.wiki.diffing import compare
from portalab.modules.wiki.models import Page, PageLink, PageTag, PageTranslation, Revision
from portalab.modules.wiki.permissions import WIKI_DELETE, WIKI_EDIT, WIKI_HISTORY, WIKI_PUBLISH, WIKI_READ
from portalab.modules.wiki.settings import WikiConfig

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,158}$")


class PageNotFound(NotFound):
    default_code = "wiki.page_not_found"
    default_title = "Page not found"


class VersionConflict(Conflict):
    default_code = "wiki.version_conflict"
    default_title = "The page changed since you started editing"


class UnsafeMarkdown(ValidationFailed):
    default_code = "content.unsafe_markdown"
    default_title = "This content cannot be saved"


def slugify(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")[:120] or "page"


_SUMMARY_SKIP = re.compile(r"^(#|>|[-*+] |\d+[.)] |\||```|~~~|<|!\[)")
_MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_MARK = re.compile(r"(\*\*|__|\*|`|~~)")


def summary_of(body_md: str, limit: int = 180) -> str:
    """The page's first paragraph of prose, without Markdown, cut at a sentence (or a word) within ``limit``
    — what a card shows under the title."""
    for block in re.split(r"\n\s*\n", body_md.strip()):
        block = block.strip()
        if not block or _SUMMARY_SKIP.match(block):
            continue
        text = re.sub(r"\s+", " ", _MD_MARK.sub("", _MD_LINK.sub(r"\1", block))).strip()
        if len(text) <= limit:
            return text
        cut = text[:limit]
        end = max(cut.rfind(". "), cut.rfind(" : "), cut.rfind("! "), cut.rfind("? "))
        if end >= limit // 2:
            return cut[: end + 1].rstrip(" :")
        return cut.rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return ""


@dataclass(frozen=True, slots=True)
class PageView:
    id: UUID
    slug: str
    title: str
    status: str
    parent_id: UUID | None
    position: int
    version: int
    html: str
    body_md: str
    language: str
    tags: list[str]
    audience: dict[str, Any]
    readable_by_ai: bool
    help_keys: list[str]
    updated_at: datetime
    outline: list[dict[str, Any]] = field(default_factory=list)
    is_translation: bool = False
    translation_missing: bool = False
    source_language: str = "en"
    can_edit: bool = False


@dataclass
class PageInput:
    title: str
    body_md: str
    slug: str | None = None
    parent_id: UUID | None = None
    tags: list[str] = field(default_factory=list)
    audience: dict[str, Any] = field(default_factory=dict)
    readable_by_ai: bool = False
    help_keys: list[str] = field(default_factory=list)
    language: str = "en"
    change_note: str = ""


class PageService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.authorizer = authorizer
        self.capabilities = capabilities
        self.config = config  # callable → WikiConfig
        self.clock = clock

    async def allowed(self, principal: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(principal, permission)
        except Exception:
            return False

    async def readable(self, page: Page, viewer: Principal) -> bool:
        if page.status == "deleted":
            return False
        if page.status == "draft":
            return await self.allowed(viewer, WIKI_EDIT)
        if not await self.allowed(viewer, WIKI_READ):
            return False
        return await self.allowed(viewer, WIKI_EDIT) or await can_read(
            page.audience, viewer, self.authorizer, self.capabilities
        )

    async def _publish(self, session: AsyncSession, action: str, page: Page) -> None:
        await self.events.publish(
            session,
            f"wiki.page_{action}",
            {"page": str(page.id), "version": page.current_version},
            occurred_at=utc_now(self.clock),
            source="wiki",
            dedup_key=f"wiki.{action}:{page.id}:{page.current_version}",
        )

    # --- writes ------------------------------------------------------------------------------------------
    def _render(self, body: str) -> Any:
        config: WikiConfig = self.config()
        if len(body.encode()) > config.max_page_bytes:
            raise UnsafeMarkdown("This page is too large.", extensions={"max_bytes": config.max_page_bytes})
        try:
            return render_markdown(body)
        except Exception as exc:  # renderer failure: the save is refused, the source is kept by the client
            raise UnsafeMarkdown("This content could not be rendered safely.") from exc

    async def _unique_slug(self, session: AsyncSession, wanted: str, page_id: UUID | None = None) -> str:
        base, n = wanted, 2
        while True:
            owner = await session.scalar(select(Page.id).where(Page.slug == wanted))
            if owner is None or owner == page_id:
                return wanted
            wanted, n = f"{base}-{n}"[:160], n + 1

    async def _derived(
        self, session: AsyncSession, page: Page, tags: Sequence[str], links: Sequence[str]
    ) -> None:
        await session.execute(delete(PageTag).where(PageTag.page_id == page.id))
        for tag in sorted({t.strip().lower()[:60] for t in tags if t.strip()}):
            session.add(PageTag(page_id=page.id, tag=tag))
        await session.execute(delete(PageLink).where(PageLink.from_page_id == page.id))
        for ref in sorted(set(links)):
            session.add(PageLink(from_page_id=page.id, target_ref=ref[:260]))

    def _vector(self, title: str, text: str) -> Any:
        return func.to_tsvector("simple", normalize_for_search(f"{title} {title} {text}")[:200_000])

    async def _check_parent(
        self, session: AsyncSession, page_id: UUID | None, parent_id: UUID | None
    ) -> None:
        seen: set[UUID] = set()
        current = parent_id
        while current is not None:
            if current == page_id or current in seen:
                raise ValidationFailed("A page cannot be moved under itself.", code="wiki.invalid_parent")
            seen.add(current)
            parent = await session.get(Page, current)
            if parent is None or parent.status == "deleted":
                raise ValidationFailed("The parent page does not exist.", code="wiki.invalid_parent")
            current = parent.parent_id

    async def create(self, actor: Principal, data: PageInput, *, publish: bool = False) -> PageView:
        if not await self.allowed(actor, WIKI_EDIT):
            raise Forbidden("You cannot write wiki pages.")
        if publish and not await self.allowed(actor, WIKI_PUBLISH):
            raise Forbidden("You cannot publish wiki pages.")
        audience = Audience.model_validate(data.audience or {}).model_dump()
        rendered = self._render(data.body_md)
        now = utc_now(self.clock)
        if data.slug is not None and not _SLUG.match(data.slug):
            raise ValidationFailed("Use lowercase letters, digits and dashes.", code="wiki.invalid_slug")
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await self._check_parent(session, None, data.parent_id)
            slug = await self._unique_slug(session, data.slug or slugify(data.title))
            position = int(
                await session.scalar(select(func.count()).where(Page.parent_id == data.parent_id)) or 0
            )
            page = Page(
                slug=slug,
                parent_id=data.parent_id,
                position=position,
                status="published" if publish else "draft",
                title=data.title.strip()[:200],
                language=data.language,
                current_version=1,
                audience=audience,
                readable_by_ai=data.readable_by_ai,
                help_keys=sorted({k.strip()[:80] for k in data.help_keys if k.strip()}),
                search_vector=self._vector(data.title, rendered.text),
                created_by=actor.acting_for or actor.user_id,
                created_at=now,
                updated_at=now,
            )
            session.add(page)
            await session.flush()
            session.add(
                self._revision(page, data.title, data.body_md, rendered, actor, data.change_note, now)
            )
            await self._derived(session, page, data.tags, rendered.links)
            await self._publish(session, "created", page)
            if publish:
                await self._publish(session, "published", page)
            page_id = page.id
        return await self.view(page_id, actor, warnings=rendered.warnings)

    def _revision(
        self,
        page: Page,
        title: str,
        body: str,
        rendered: Any,
        actor: Principal,
        note: str,
        now: datetime,
        restored: int | None = None,
    ) -> Revision:
        return Revision(
            page_id=page.id,
            version=page.current_version,
            title=title.strip()[:200],
            body_md=body,
            rendered_html=rendered.html,
            renderer_version=rendered.renderer_version,
            plain_text=rendered.text,
            author_id=actor.acting_for or actor.user_id,
            change_note=note[:300],
            restored_from_version=restored,
            created_at=now,
        )

    async def _editable(self, session: AsyncSession, page_id: UUID, actor: Principal) -> Page:
        page = await session.get(Page, page_id, with_for_update=True)
        if page is None or not await self.readable(page, actor):
            raise PageNotFound("This page does not exist.")
        if not await self.allowed(actor, WIKI_EDIT):
            raise Forbidden("You cannot edit wiki pages.")
        return page

    async def update(self, actor: Principal, page_id: UUID, base_version: int, data: PageInput) -> PageView:
        rendered = self._render(data.body_md)
        audience = Audience.model_validate(data.audience or {}).model_dump()
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            page = await self._editable(session, page_id, actor)
            if base_version != page.current_version:
                base = await session.get(Revision, (page.id, base_version))
                current = await session.get(Revision, (page.id, page.current_version))
                raise VersionConflict(
                    "Someone saved this page after you started editing; review the changes and save again.",
                    extensions={
                        "current_version": page.current_version,
                        "diff": compare(base.body_md if base else "", current.body_md if current else ""),
                    },
                )
            if data.parent_id != page.parent_id:
                await self._check_parent(session, page.id, data.parent_id)
                page.parent_id = data.parent_id
            if data.slug and data.slug != page.slug:
                if not _SLUG.match(data.slug):
                    raise ValidationFailed(
                        "Use lowercase letters, digits and dashes.", code="wiki.invalid_slug"
                    )
                page.slug = await self._unique_slug(session, data.slug, page.id)
            page.current_version += 1
            page.title = data.title.strip()[:200]
            page.audience, page.readable_by_ai = audience, data.readable_by_ai
            page.help_keys = sorted({k.strip()[:80] for k in data.help_keys if k.strip()})
            page.search_vector = self._vector(page.title, rendered.text)
            page.updated_at = now
            session.add(
                self._revision(page, data.title, data.body_md, rendered, actor, data.change_note, now)
            )
            await self._derived(session, page, data.tags, rendered.links)
            await self._publish(session, "revised", page)
        return await self.view(page_id, actor, warnings=rendered.warnings)

    async def restore(self, actor: Principal, page_id: UUID, version: int) -> PageView:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            page = await self._editable(session, page_id, actor)
            old = await session.get(Revision, (page.id, version))
            if old is None:
                raise PageNotFound("This version does not exist.")
            rendered = self._render(old.body_md)
            page.current_version += 1
            page.title, page.updated_at = old.title, now
            page.search_vector = self._vector(old.title, rendered.text)
            session.add(
                self._revision(
                    page, old.title, old.body_md, rendered, actor, f"Restored version {version}", now, version
                )
            )
            await self._derived(session, page, await self._tags(session, page.id), rendered.links)
            await self._publish(session, "restored", page)
        return await self.view(page_id, actor)

    async def set_status(self, actor: Principal, page_id: UUID, status: str) -> PageView:
        permission = {
            "published": WIKI_PUBLISH,
            "archived": WIKI_PUBLISH,
            "draft": WIKI_PUBLISH,
            "deleted": WIKI_DELETE,
        }[status]
        async with self.database.unit_of_work() as uow:
            session = uow.session
            page = await session.get(Page, page_id, with_for_update=True)
            if page is None or page.status == "deleted" or not await self.readable(page, actor):
                raise PageNotFound("This page does not exist.")
            if not await self.allowed(actor, permission):
                raise Forbidden("You cannot change the state of this page.")
            if status == "deleted":
                children = await session.scalar(
                    select(func.count()).where(Page.parent_id == page.id, Page.status != "deleted")
                )
                if children:
                    raise Conflict("Move or delete the sub-pages first.", code="wiki.has_children")
            page.status, page.updated_at = status, utc_now(self.clock)
            action = {
                "published": "published",
                "archived": "archived",
                "draft": "revised",
                "deleted": "deleted",
            }[status]
            await self._publish(session, action, page)
        if status == "deleted":
            return PageView(
                page_id, "", "", "deleted", None, 0, 0, "", "", "en", [], {}, False, [], utc_now(self.clock)
            )
        return await self.view(page_id, actor)

    async def move(self, actor: Principal, page_id: UUID, parent_id: UUID | None, position: int) -> PageView:
        async with self.database.unit_of_work() as uow:
            session = uow.session
            page = await self._editable(session, page_id, actor)
            await self._check_parent(session, page.id, parent_id)
            page.parent_id, page.position, page.updated_at = parent_id, max(0, position), utc_now(self.clock)
        return await self.view(page_id, actor)

    async def translate(
        self,
        actor: Principal,
        page_id: UUID,
        language: str,
        title: str,
        body_md: str,
        *,
        machine: bool = False,
    ) -> PageView:
        rendered = self._render(body_md)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            page = await self._editable(session, page_id, actor)
            if language == page.language:
                raise ValidationFailed("This is the page's source language.", code="wiki.invalid_language")
            row = await session.get(PageTranslation, (page.id, language), with_for_update=True)
            values = {
                "title": title.strip()[:200],
                "body_md": body_md,
                "rendered_html": rendered.html,
                "renderer_version": rendered.renderer_version,
                "source_version": page.current_version,
                "state": "machine_draft" if machine else "translated",
                "updated_by": actor.acting_for or actor.user_id,
                "updated_at": utc_now(self.clock),
            }
            if row is None:
                session.add(PageTranslation(page_id=page.id, language=language, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
        return await self.view(page_id, actor, language=language)

    # --- reads ---------------------------------------------------------------------------------------
    async def _tags(self, session: AsyncSession, page_id: UUID) -> list[str]:
        return [
            r[0]
            for r in await session.execute(
                select(PageTag.tag).where(PageTag.page_id == page_id).order_by(PageTag.tag)
            )
        ]

    async def find(self, key: str) -> UUID | None:
        async with self.database.session() as session:
            try:
                found = await session.get(Page, UUID(key))
                if found is not None:
                    return found.id
            except ValueError:
                pass
            found_id: UUID | None = await session.scalar(select(Page.id).where(Page.slug == key))
            return found_id

    async def view(
        self, page_id: UUID, viewer: Principal, *, language: str | None = None, warnings: Sequence[str] = ()
    ) -> PageView:
        async with self.database.session() as session:
            page = await session.get(Page, page_id)
            if page is None or not await self.readable(page, viewer):
                raise PageNotFound("This page does not exist.")
            revision = await session.get(Revision, (page.id, page.current_version))
            translation = (
                await session.get(PageTranslation, (page.id, language))
                if language and language != page.language
                else None
            )
            tags = await self._tags(session, page.id)
        assert revision is not None
        html, title, body = revision.rendered_html, page.title, revision.body_md
        if revision.renderer_version != RENDERER_VERSION:
            html = render_markdown(body).html  # lazy re-render after a renderer upgrade (cache is derived)
        is_translation = False
        if translation is not None and translation.state == "translated":
            html, title, body, is_translation = (
                translation.rendered_html,
                translation.title,
                translation.body_md,
                True,
            )
        outline = [
            {"level": o.level, "text": o.text, "anchor": o.anchor} for o in render_markdown(body).outline
        ]
        return PageView(
            id=page.id,
            slug=page.slug,
            title=title,
            status=page.status,
            parent_id=page.parent_id,
            position=page.position,
            version=page.current_version,
            html=html,
            body_md=body,
            language=language if is_translation and language else page.language,
            tags=tags,
            audience=page.audience,
            readable_by_ai=page.readable_by_ai,
            help_keys=list(page.help_keys),
            updated_at=page.updated_at,
            outline=outline,
            is_translation=is_translation,
            translation_missing=bool(language and language != page.language and not is_translation),
            source_language=page.language,
            can_edit=await self.allowed(viewer, WIKI_EDIT),
        )

    async def tree(self, viewer: Principal) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Page, Revision.body_md)
                    .outerjoin(
                        Revision, (Revision.page_id == Page.id) & (Revision.version == Page.current_version)
                    )
                    .where(Page.status != "deleted")
                    .order_by(Page.position, Page.title)
                )
            ).all()
        bodies = {page.id: body or "" for page, body in rows}
        visible = [p for p, _ in rows if await self.readable(p, viewer)]
        ids = {p.id for p in visible}
        nodes: dict[UUID | None, list[dict[str, Any]]] = {}
        for page in visible:
            parent = page.parent_id if page.parent_id in ids else None
            nodes.setdefault(parent, []).append(
                {
                    "id": str(page.id),
                    "slug": page.slug,
                    "title": page.title,
                    "status": page.status,
                    "summary": summary_of(bodies[page.id]),
                    "children": [],
                }
            )

        def build(parent: UUID | None) -> list[dict[str, Any]]:
            out = nodes.get(parent, [])
            for node in out:
                node["children"] = build(UUID(node["id"]))
            return out

        return build(None)

    async def breadcrumbs(self, page_id: UUID, viewer: Principal) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        async with self.database.session() as session:
            page = await session.get(Page, page_id)
            seen: set[UUID] = set()
            while page is not None and page.parent_id is not None and page.parent_id not in seen:
                seen.add(page.parent_id)
                page = await session.get(Page, page.parent_id)
                if page is not None and await self.readable(page, viewer):
                    out.insert(0, {"id": str(page.id), "slug": page.slug, "title": page.title})
        return out

    async def broken_links(self, viewer: Principal) -> list[dict[str, str]]:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(PageLink.from_page_id, PageLink.target_ref, Page.slug)
                    .join(Page, Page.id == PageLink.from_page_id)
                    .where(Page.status != "deleted", PageLink.target_ref.like("portalab://wiki/%"))
                )
            ).all()
            targets = {r[1].rsplit("/", 1)[-1] for r in rows}
            alive = {
                str(p.id): p
                for p in (
                    await session.execute(
                        select(Page).where(
                            or_(Page.slug.in_(targets), Page.id.in_(_uuids(targets))),
                            Page.status != "deleted",
                        )
                    )
                ).scalars()
            }
            slugs = {p.slug for p in alive.values()}
        return [
            {"page": slug, "target": target}
            for page_id, target, slug in rows
            if target.rsplit("/", 1)[-1] not in alive and target.rsplit("/", 1)[-1] not in slugs
        ]

    # --- history -------------------------------------------------------------------------------------
    async def history_allowed(self, viewer: Principal) -> bool:
        if self.config().history_visibility == "readers":
            return await self.allowed(viewer, WIKI_READ)
        return await self.allowed(viewer, WIKI_HISTORY)

    async def revisions(self, page_id: UUID, viewer: Principal) -> list[Revision]:
        await self._history_guard(page_id, viewer)
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(Revision).where(Revision.page_id == page_id).order_by(Revision.version.desc())
                    )
                )
                .scalars()
                .all()
            )

    async def revision(self, page_id: UUID, version: int, viewer: Principal) -> Revision:
        await self._history_guard(page_id, viewer)
        async with self.database.session() as session:
            row = await session.get(Revision, (page_id, version))
        if row is None:
            raise PageNotFound("This version does not exist.")
        return row

    async def compare(self, page_id: UUID, old: int, new: int, viewer: Principal) -> dict[str, Any]:
        first = await self.revision(page_id, old, viewer)
        second = await self.revision(page_id, new, viewer)
        return {"from": old, "to": new, **compare(first.body_md, second.body_md)}

    async def _history_guard(self, page_id: UUID, viewer: Principal) -> None:
        async with self.database.session() as session:
            page = await session.get(Page, page_id)
        if page is None or not await self.readable(page, viewer):
            raise PageNotFound("This page does not exist.")
        if not await self.history_allowed(viewer):
            raise Forbidden("You cannot see the history of wiki pages.", code="wiki.history_forbidden")


def _uuids(values: set[str]) -> list[UUID]:
    out = []
    for value in values:
        try:
            out.append(UUID(value))
        except ValueError:
            continue
    return out
