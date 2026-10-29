"""Wiki API (contracts/content-contracts.md): tree, pages, editing with ``base_version``, publication
states, move, history/compare/restore, translations, contextual help and the broken-link report."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.capabilities.content.audience import Audience
from portalab.core.audit_port import AuditRecord
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, Forbidden, Unavailable
from portalab.modules.wiki.module import WikiModule
from portalab.modules.wiki.pages import PageInput, PageNotFound, PageView
from portalab.modules.wiki.permissions import SELF, WIKI_DELETE, WIKI_EDIT, WIKI_PUBLISH, WIKI_READ

router = APIRouter(prefix="/api/v1", tags=["wiki"])


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


def wiki_module(request: Request) -> WikiModule:
    module = getattr(request.app.state, "wiki_module", None)
    if not isinstance(module, WikiModule):
        raise Unavailable("The wiki is not available.", code="wiki.unavailable")
    return module


Module = Annotated[WikiModule, Depends(wiki_module)]
Reader = Annotated[Principal, require(WIKI_READ)]
Editor = Annotated[Principal, require(WIKI_EDIT)]
Publisher = Annotated[Principal, require(WIKI_PUBLISH)]
Deleter = Annotated[Principal, require(WIKI_DELETE)]
User = Annotated[Principal, require(SELF)]


class WikiPageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    body_md: str = Field(default="", max_length=1_000_000)
    slug: str | None = Field(default=None, max_length=160)
    parent_id: UUID | None = None
    tags: list[str] = Field(default_factory=list, max_length=30)
    audience: Audience = Field(default_factory=Audience)
    readable_by_ai: bool = False
    help_keys: list[str] = Field(default_factory=list, max_length=20)
    language: str = Field(default="en", max_length=16)
    change_note: str = Field(default="", max_length=300)
    publish: bool = False


class WikiPageUpdateIn(WikiPageIn):
    base_version: int = Field(ge=1)


class WikiPageOut(BaseModel):
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
    source_language: str
    is_translation: bool
    translation_missing: bool
    tags: list[str]
    audience: dict[str, Any]
    readable_by_ai: bool
    help_keys: list[str]
    updated_at: datetime
    outline: list[dict[str, Any]]
    breadcrumbs: list[dict[str, str]] = Field(default_factory=list)
    can_edit: bool
    warnings: list[str] = Field(default_factory=list)


class WikiMoveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_id: UUID | None = None
    position: int = Field(default=0, ge=0, le=10_000)


class WikiRestoreIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


class WikiDeleteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: str | None = None


class WikiTranslationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    body_md: str = Field(max_length=1_000_000)
    machine: bool = False


class WikiRevisionOut(BaseModel):
    version: int
    title: str
    change_note: str
    restored_from_version: int | None
    author_id: UUID | None
    created_at: datetime


class WikiRevisionDetail(WikiRevisionOut):
    body_md: str
    html: str


class WikiHelpHitOut(BaseModel):
    ref: str
    title: str
    excerpt: str
    url: str


def _out(
    view: PageView, breadcrumbs: list[dict[str, str]] | None = None, warnings: list[str] | None = None
) -> WikiPageOut:
    return WikiPageOut(
        id=view.id,
        slug=view.slug,
        title=view.title,
        status=view.status,
        parent_id=view.parent_id,
        position=view.position,
        version=view.version,
        html=view.html,
        body_md=view.body_md,
        language=view.language,
        source_language=view.source_language,
        is_translation=view.is_translation,
        translation_missing=view.translation_missing,
        tags=view.tags,
        audience=view.audience,
        readable_by_ai=view.readable_by_ai,
        help_keys=view.help_keys,
        updated_at=view.updated_at,
        outline=view.outline,
        breadcrumbs=breadcrumbs or [],
        can_edit=view.can_edit,
        warnings=warnings or [],
    )


def _input(body: WikiPageIn) -> PageInput:
    return PageInput(
        title=body.title,
        body_md=body.body_md,
        slug=body.slug,
        parent_id=body.parent_id,
        tags=body.tags,
        audience=body.audience.model_dump(),
        readable_by_ai=body.readable_by_ai,
        help_keys=body.help_keys,
        language=body.language,
        change_note=body.change_note,
    )


async def _audit(
    module: WikiModule, principal: Principal, action: str, page: UUID, context: dict[str, Any]
) -> None:
    async with module.database.unit_of_work() as uow:
        await module.audit.record(
            uow.session,
            AuditRecord(
                action=action,
                actor=principal,
                resource=ResourceRef("wiki_page", str(page)),
                decision="allow",
                result="success",
                context=context,
                sensitive=True,
            ),
        )


@router.get("/wiki/tree")
async def tree(principal: Reader, module: Module) -> list[dict[str, Any]]:
    return await module.pages.tree(principal)


@router.get("/wiki/pages/{key}", response_model=WikiPageOut)
async def get_page(
    principal: Reader, key: str, module: Module, lang: Annotated[str | None, Query(max_length=16)] = None
) -> WikiPageOut:
    page_id = await module.pages.find(key)
    if page_id is None:
        raise PageNotFound("This page does not exist.")
    view = await module.pages.view(page_id, principal, language=lang)
    return _out(view, await module.pages.breadcrumbs(page_id, principal))


@router.post("/wiki/pages", response_model=WikiPageOut, status_code=status.HTTP_201_CREATED)
async def create_page(principal: Editor, body: WikiPageIn, module: Module) -> WikiPageOut:
    view = await module.pages.create(principal, _input(body), publish=body.publish)
    return _out(view)


@router.put("/wiki/pages/{page_id}", response_model=WikiPageOut)
async def update_page(
    principal: Editor, page_id: UUID, body: WikiPageUpdateIn, module: Module
) -> WikiPageOut:
    from portalab.capabilities.content.render import render_markdown_async

    view = await module.pages.update(principal, page_id, body.base_version, _input(body))
    return _out(view, warnings=list((await render_markdown_async(body.body_md)).warnings))


@router.post("/wiki/pages/{page_id}/move", response_model=WikiPageOut)
async def move_page(principal: Editor, page_id: UUID, body: WikiMoveIn, module: Module) -> WikiPageOut:
    return _out(await module.pages.move(principal, page_id, body.parent_id, body.position))


@router.post("/wiki/pages/{page_id}/restore", response_model=WikiPageOut)
async def restore_page(principal: Editor, page_id: UUID, body: WikiRestoreIn, module: Module) -> WikiPageOut:
    view = await module.pages.restore(principal, page_id, body.version)
    await _audit(module, principal, "wiki.page_restored", page_id, {"version": body.version})
    return _out(view)


@router.post("/wiki/pages/{page_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(principal: Deleter, page_id: UUID, body: WikiDeleteIn, module: Module) -> Response:
    providers = module.capabilities.system_providers(CONFIRMATIONS)
    if not providers:
        raise Unavailable("Confirmations are not available.", code="authz.unavailable")
    confirmations = providers[0].provider
    resource, payload = ResourceRef("wiki_page", str(page_id)), {"delete": str(page_id)}
    if body.confirmation is None:
        issued = await confirmations.issue(principal, WIKI_DELETE, resource, payload)
        raise ConfirmationRequired(
            "Deleting a page cannot be undone. Confirm to continue.", extensions={"confirmation": issued}
        )
    if not await confirmations.consume(body.confirmation, principal, WIKI_DELETE, resource, payload):
        raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")
    await module.pages.set_status(principal, page_id, "deleted")
    await _audit(module, principal, "wiki.page_deleted", page_id, {})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/wiki/pages/{page_id}/revisions", response_model=list[WikiRevisionOut])
async def revisions(principal: Reader, page_id: UUID, module: Module) -> list[WikiRevisionOut]:
    rows = await module.pages.revisions(page_id, principal)
    return [
        WikiRevisionOut(
            version=r.version,
            title=r.title,
            change_note=r.change_note,
            restored_from_version=r.restored_from_version,
            author_id=r.author_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/wiki/pages/{page_id}/revisions/{version}", response_model=WikiRevisionDetail)
async def revision(principal: Reader, page_id: UUID, version: int, module: Module) -> WikiRevisionDetail:
    r = await module.pages.revision(page_id, version, principal)
    return WikiRevisionDetail(
        version=r.version,
        title=r.title,
        change_note=r.change_note,
        restored_from_version=r.restored_from_version,
        author_id=r.author_id,
        created_at=r.created_at,
        body_md=r.body_md,
        html=r.rendered_html,
    )


@router.get("/wiki/pages/{page_id}/compare")
async def compare_versions(
    principal: Reader,
    page_id: UUID,
    module: Module,
    from_version: Annotated[int, Query(alias="from", ge=1)],
    to_version: Annotated[int, Query(alias="to", ge=1)],
) -> dict[str, Any]:
    return await module.pages.compare(page_id, from_version, to_version, principal)


@router.put("/wiki/pages/{page_id}/translations/{language}", response_model=WikiPageOut)
async def put_translation(
    principal: Editor, page_id: UUID, language: str, body: WikiTranslationIn, module: Module
) -> WikiPageOut:
    view = await module.pages.translate(
        principal, page_id, language[:16], body.title, body.body_md, machine=body.machine
    )
    return _out(view)


@router.get("/help", response_model=list[WikiHelpHitOut])
async def help_pages(
    principal: User, module: Module, key: Annotated[str, Query(min_length=1, max_length=80)]
) -> list[WikiHelpHitOut]:
    hits = await module.knowledge.for_context(key, principal)
    return [WikiHelpHitOut(ref=h.ref, title=h.title, excerpt=h.excerpt, url=h.url) for h in hits]


@router.get("/admin/wiki/broken-links")
async def broken_links(principal: Editor, module: Module) -> list[dict[str, str]]:
    return await module.pages.broken_links(principal)


@router.post("/wiki/pages/{page_id}/{action}", response_model=WikiPageOut)
async def page_action(
    principal: Publisher, page_id: UUID, action: Literal["publish", "archive", "unpublish"], module: Module
) -> WikiPageOut:
    target = {"publish": "published", "archive": "archived", "unpublish": "draft"}[action]
    view = await module.pages.set_status(principal, page_id, target)
    await _audit(module, principal, f"wiki.page_{target}", page_id, {})
    return _out(view)
