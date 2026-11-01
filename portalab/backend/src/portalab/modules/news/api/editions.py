"""#316 — self-writing newsletter editions: the news desk's templates (the built-in ones read-only), previews
and drafts, publishing (and e-mailing); members read the published editions in the portal, as the e-mail
itself (its page, framed by the portal and confined there); mail clients fetch an edition's pictures by its
token alone."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import public
from portalab.core.errors import NotFound
from portalab.modules.news.api.router import Module, NewslettersOn, Publisher, Reader
from portalab.modules.news.editions.template import (
    CHARTS,
    CONTENTS,
    DEFAULT_CHARTS,
    DEFAULT_CONTENTS,
    Chart,
    Content,
    TemplateDefinition,
)
from portalab.modules.news.models import NewsletterEdition

router = APIRouter(prefix="/api/v1", tags=["news"])

KEY = r"^[a-z0-9][a-z0-9_-]{1,62}$"
# the edition's page in the portal: its own styles and the pictures only, no script, no form, framed by the
# portal alone; its links open in the portal (or apart)
PAGE_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; img-src 'self' https: data:; style-src 'unsafe-inline'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'self'; sandbox allow-popups allow-popups-to-escape-sandbox "
        "allow-top-navigation-by-user-activation"
    ),
    "X-Frame-Options": "SAMEORIGIN",
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
}


class TemplateOut(BaseModel):
    key: str
    builtin: bool
    definition: TemplateDefinition


class EditionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_key: str = Field(pattern=KEY)
    days: int = Field(default=7, ge=1, le=90)
    language: str = Field(default="fr", max_length=16)
    notice: str | None = Field(default=None, max_length=2000)
    category_id: UUID | None = None
    contents: list[Content] | None = Field(default=None, max_length=14)  # #323: what it tells
    charts: list[Chart] | None = Field(default=None, max_length=6)  # #324: its statistics' charts
    subject: str | None = Field(default=None, max_length=200)  # #325: its e-mail's subject, with variables


class PreviewIn(EditionIn):
    definition: TemplateDefinition | None = None  # a template being written, not saved yet


class PublishIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: bool = False


class EditionOut(BaseModel):
    id: UUID
    title: str
    template_key: str
    status: str
    language: str
    days: int
    preheader: str | None
    category_id: UUID | None
    schedule_id: UUID | None
    created_at: datetime
    published_at: datetime | None
    emailed_at: datetime | None
    recipients: int


def _framed(row: NewsletterEdition) -> Response:
    """The edition's page in the portal: its links and pictures on the portal itself (the e-mail keeps the
    public address — a portal reached otherwise, on the local network, still shows its pictures)."""
    html = row.html
    portal = str((row.data or {}).get("portal") or "").rstrip("/")
    if portal:
        html = html.replace(f'="{portal}/', '="/')
    return Response(html, media_type="text/html; charset=utf-8", headers=PAGE_HEADERS)


def _edition(row: NewsletterEdition) -> EditionOut:
    return EditionOut(
        id=row.id,
        title=row.title,
        template_key=row.template_key,
        status=row.status,
        language=row.language,
        days=row.days,
        preheader=(row.data or {}).get("preheader"),
        category_id=row.category_id,
        schedule_id=row.schedule_id,
        created_at=row.created_at,
        published_at=row.published_at,
        emailed_at=row.emailed_at,
        recipients=row.recipients,
    )


# --- templates -------------------------------------------------------------------------------------------
@router.get("/admin/news/newsletter-templates", response_model=list[TemplateOut], dependencies=NewslettersOn)
async def templates(principal: Publisher, module: Module) -> list[TemplateOut]:
    """The built-in templates first (the interface names them in its language), then the news desk's own."""
    return [
        TemplateOut(key=key, builtin=builtin, definition=definition)
        for key, definition, builtin in await module.editions.templates()
    ]


@router.put("/admin/news/newsletter-templates/{key}", response_model=TemplateOut, dependencies=NewslettersOn)
async def put_template(
    principal: Publisher, key: Annotated[str, Path(pattern=KEY)], body: TemplateDefinition, module: Module
) -> TemplateOut:
    await module.editions.save_template(key, body)
    return TemplateOut(key=key, builtin=False, definition=body)


@router.delete(
    "/admin/news/newsletter-templates/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=NewslettersOn,
)
async def delete_template(
    principal: Publisher, key: Annotated[str, Path(pattern=KEY)], module: Module
) -> Response:
    await module.editions.delete_template(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class ContentsOut(BaseModel):
    contents: list[str]
    defaults: list[str]
    charts: list[str]  # #324: the statistics' charts, and the usual ones
    chart_defaults: list[str]


@router.get("/admin/news/newsletter-contents", response_model=ContentsOut, dependencies=NewslettersOn)
async def contents(principal: Publisher) -> ContentsOut:
    """#323: what an edition may tell, in its order, and what is switched on by default."""
    return ContentsOut(
        contents=list(CONTENTS),
        defaults=list(DEFAULT_CONTENTS),
        charts=list(CHARTS),
        chart_defaults=list(DEFAULT_CHARTS),
    )


# --- editions (the news desk) --------------------------------------------------------------------------
@router.post("/admin/news/newsletter-editions/preview", response_model=EditionOut, dependencies=NewslettersOn)
async def preview(principal: Publisher, body: PreviewIn, module: Module) -> EditionOut:
    """What the template would write now — its page at ``…/{id}/page`` (kept until the next preview)."""
    row = await module.editions.create(
        body.template_key,
        days=body.days,
        language=body.language,
        notice=body.notice,
        category_id=body.category_id,
        status="preview",
        created_by=principal.user_id,
        definition=body.definition,
        contents=body.contents,
        charts=body.charts,
        subject=body.subject,
    )
    return _edition(row)


@router.post(
    "/admin/news/newsletter-editions",
    response_model=EditionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=NewslettersOn,
)
async def create_edition(principal: Publisher, body: EditionIn, module: Module) -> EditionOut:
    row = await module.editions.create(
        body.template_key,
        days=body.days,
        language=body.language,
        notice=body.notice,
        category_id=body.category_id,
        created_by=principal.user_id,
        contents=body.contents,
        charts=body.charts,
        subject=body.subject,
    )
    return _edition(row)


@router.get("/admin/news/newsletter-editions", response_model=list[EditionOut], dependencies=NewslettersOn)
async def all_editions(principal: Publisher, module: Module) -> list[EditionOut]:
    return [_edition(row) for row in await module.editions.listing(published_only=False)]


@router.post(
    "/admin/news/newsletter-editions/{edition_id}/publish",
    response_model=EditionOut,
    dependencies=NewslettersOn,
)
async def publish_edition(
    principal: Publisher, edition_id: UUID, body: PublishIn, module: Module
) -> EditionOut:
    return _edition(await module.editions.publish(edition_id, email=body.email))


@router.delete(
    "/admin/news/newsletter-editions/{edition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=NewslettersOn,
)
async def delete_edition(principal: Publisher, edition_id: UUID, module: Module) -> Response:
    await module.editions.delete(edition_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/admin/news/newsletter-editions/{edition_id}/page",
    response_class=Response,
    dependencies=NewslettersOn,
)
async def draft_page(principal: Publisher, edition_id: UUID, module: Module) -> Response:
    """Any edition's page — a preview, a draft — for the news desk."""
    return _framed(await module.editions.get(edition_id))


@router.post("/admin/news/newsletter-editions/{edition_id}/test", dependencies=NewslettersOn)
async def test_edition(
    principal: Publisher, edition_id: UUID, module: Module, request: Request
) -> dict[str, bool]:
    """#317: the edition e-mailed to me alone, as the members would get it."""
    if principal.user_id is None:
        raise NotFound("No account.", code="news.no_account")
    row = await module.editions.get(edition_id)
    base = str(request.base_url).rstrip("/")
    return {"sent": await module.editions.send_test(row, principal.user_id, base)}


# --- editions (the members) ---------------------------------------------------------------------------
async def _published(module: Module, edition_id: UUID) -> NewsletterEdition:
    row = await module.editions.get(edition_id)
    if row.status != "published":
        raise NotFound("This edition does not exist.", code="news.edition_not_found")
    return row


@router.get("/news/editions", response_model=list[EditionOut], dependencies=NewslettersOn)
async def editions(principal: Reader, module: Module) -> list[EditionOut]:
    return [_edition(row) for row in await module.editions.listing(published_only=True)]


@router.get("/news/editions/{edition_id}", response_model=EditionOut, dependencies=NewslettersOn)
async def edition(principal: Reader, edition_id: UUID, module: Module) -> EditionOut:
    return _edition(await _published(module, edition_id))


@router.get("/news/editions/{edition_id}/page", response_class=Response, dependencies=NewslettersOn)
async def edition_page(principal: Reader, edition_id: UUID, module: Module) -> Response:
    """The edition as it was e-mailed — the portal frames it."""
    return _framed(await _published(module, edition_id))


@router.get("/newsletters/pictures/{token}/{image_id}", include_in_schema=False)
@public
async def edition_picture(
    module: Module,
    token: Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{20,64}$")],
    image_id: Annotated[str, Path(pattern=r"^[0-9a-fA-F-]{36}$")],
) -> Response:
    """A picture of an edition, for the mail clients (no session): the edition's token is the key, and only
    the pictures it shows answer."""
    data = await module.editions.picture(token, image_id.lower())
    if data is None:
        raise NotFound("No picture.", code="news.picture_not_found")
    return Response(
        data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=604800", "X-Content-Type-Options": "nosniff"},
    )
