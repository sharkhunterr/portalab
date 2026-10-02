"""i18n API (T013, T017, T019, T031, T039)."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from portalab.capabilities.i18n import LocaleContext
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import NotFound, Unavailable
from portalab.modules.i18n.models import Language
from portalab.modules.i18n.module import I18nModule
from portalab.modules.i18n.permissions import AUTHENTICATED, I18N_MANAGE

router = APIRouter(prefix="/api/v1", tags=["i18n"])


def i18n_module(request: Request) -> I18nModule:
    module = getattr(request.app.state, "i18n_module", None)
    if not isinstance(module, I18nModule):
        raise Unavailable("Languages are not available.", code="i18n.unavailable")
    return module


Module = Annotated[I18nModule, Depends(i18n_module)]
User = Annotated[Principal, require(AUTHENTICATED)]
Manager = Annotated[Principal, require(I18N_MANAGE)]


class EntryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    namespace: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=160)
    language: str = Field(min_length=2, max_length=35)
    message: str = Field(min_length=1, max_length=4000)
    state: Literal["draft", "published", "deprecated"] = "published"


@router.get("/i18n/context")
async def context(principal: User, module: Module) -> dict[str, Any]:
    return (await module.resolver.for_user(principal.user_id)).as_dict()


@router.get("/i18n/languages")
async def languages(_: User, module: Module) -> dict[str, Any]:
    policy = await module.resolver.policy()
    async with module.database.session() as session:
        rows = (await session.execute(select(Language).order_by(Language.code))).scalars().all()
    return {
        "default": policy.default_language,
        "items": [
            {"code": r.code, "name_native": r.name_native, "name_en": r.name_en, "direction": r.direction}
            for r in rows
            if r.code in policy.enabled_languages
        ],
    }


@router.get("/i18n/catalogs/{namespace}")
async def catalog(
    principal: User,
    namespace: str,
    request: Request,
    module: Module,
    lang: str | None = Query(default=None, max_length=35),
) -> Response:
    await module.catalogs.ensure_loaded()
    ctx = await module.resolver.for_user(principal.user_id)
    if lang:
        ctx = LocaleContext(
            language=lang, locale=lang, fallback_chain=ctx.fallback_chain, direction=ctx.direction
        )
    messages, version = module.catalogs.bundle(namespace, ctx)
    etag = f'"{version}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(
        {"namespace": namespace, "language": ctx.language, "version": version, "messages": messages},
        headers={"ETag": etag, "Cache-Control": "private, no-cache"},
    )


@router.get("/admin/i18n/catalog-entries")
async def entries(
    _: Manager, module: Module, namespace: str | None = None, language: str | None = None
) -> dict[str, Any]:
    return {"items": await module.admin.entries(namespace, language)}


@router.put("/admin/i18n/catalog-entries")
async def put_entry(principal: Manager, body: EntryIn, module: Module) -> dict[str, Any]:
    return await module.admin.put(principal, **body.model_dump())


@router.get("/admin/i18n/health")
async def health(_: Manager, module: Module) -> dict[str, Any]:
    return await module.health()


@router.get("/i18n/content/{kind}/{content_id}")
async def content(
    principal: User,
    kind: str,
    content_id: str,
    request: Request,
    module: Module,
    lang: str | None = Query(default=None, max_length=35),
) -> dict[str, Any]:
    registered = module.content_kinds.get(kind)
    # an unknown kind and an unreadable item look the same: existence is never revealed
    if registered is None or not await request.app.state.authorizer.is_allowed(
        principal, registered.read_permission, ResourceRef(kind, content_id)
    ):
        raise NotFound("No such content.", code="i18n.content_not_found")
    ctx = await module.resolver.for_user(principal.user_id)
    if lang:
        ctx = LocaleContext(language=lang, locale=lang, fallback_chain=ctx.fallback_chain)
    found = await module.content.get(kind, content_id, ctx)
    if found is None:
        raise NotFound("No such content.", code="i18n.content_not_found")
    return {
        "content_kind": found.content_kind,
        "content_id": found.content_id,
        "language": found.language,
        "version": found.version,
        "state": found.state,
        "is_fallback": found.is_fallback,
        "source_language": found.source_language,
    }
