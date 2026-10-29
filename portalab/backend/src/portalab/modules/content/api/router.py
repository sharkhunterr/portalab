"""Content helper API: asset upload/read, per-viewer link resolution and the render preview used by the
editors (same pipeline and sanitizer as saved content)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.content.render import render_markdown_async
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.content.module import ContentModule
from portalab.modules.content.permissions import SELF
from portalab.modules.content.service import MAX_BYTES, UnsafeAsset

router = APIRouter(prefix="/api/v1", tags=["content"])


def content_module(request: Request) -> ContentModule:
    module = getattr(request.app.state, "content_module", None)
    if not isinstance(module, ContentModule):
        raise Unavailable("Content is not available.", code="content.unavailable")
    return module


Module = Annotated[ContentModule, Depends(content_module)]
User = Annotated[Principal, require(SELF)]


class ContentAssetOut(BaseModel):
    id: UUID
    owner_ref: str
    content_type: str
    filename: str
    size: int
    markdown: str


class ContentLinkResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refs: list[str] = Field(max_length=200)


class ContentResolvedLinkOut(BaseModel):
    ref: str
    state: str
    title: str | None
    url: str | None


class ContentRenderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    markdown: str = Field(max_length=500_000)


class ContentOutlineOut(BaseModel):
    level: int
    text: str
    anchor: str


class ContentRenderOut(BaseModel):
    html: str
    outline: list[ContentOutlineOut]
    links: list[str]
    warnings: list[str]


@router.post(
    "/content/assets",
    response_model=ContentAssetOut,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                t: {"schema": {"type": "string", "format": "binary"}}
                for t in ("image/png", "image/jpeg", "image/webp", "image/gif")
            },
        }
    },
)
async def upload(
    principal: User,
    request: Request,
    module: Module,
    owner_ref: Annotated[str, Query(max_length=260)],
    filename: Annotated[str, Query(max_length=200)] = "image",
) -> ContentAssetOut:
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise UnsafeAsset("The file is too large.", extensions={"reason": "too_large"})
    view = await module.service.upload(bytes(data), filename, owner_ref, principal)
    return ContentAssetOut(**{k: getattr(view, k) for k in ContentAssetOut.model_fields})


@router.get("/content/assets/{asset_id}")
async def read_asset(principal: User, asset_id: UUID, module: Module) -> Response:
    data, content_type = await module.service.read(asset_id, principal)
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.post("/content/links/resolve", response_model=list[ContentResolvedLinkOut])
async def resolve(
    principal: User, body: ContentLinkResolveIn, module: Module
) -> list[ContentResolvedLinkOut]:
    return [
        ContentResolvedLinkOut(ref=r.ref, state=r.state, title=r.title, url=r.url)
        for r in await module.service.resolve(body.refs, principal)
    ]


@router.post("/content/render", response_model=ContentRenderOut)
async def preview(principal: User, body: ContentRenderIn, module: Module) -> ContentRenderOut:
    rendered = await render_markdown_async(
        body.markdown, allow_external_images=module.config.allow_external_images
    )
    return ContentRenderOut(
        html=rendered.html,
        outline=[ContentOutlineOut(level=o.level, text=o.text, anchor=o.anchor) for o in rendered.outline],
        links=list(rendered.links),
        warnings=list(rendered.warnings),
    )
