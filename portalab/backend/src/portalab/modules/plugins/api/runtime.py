"""Plugin runtime surface (T022, T032): declarative pages, image assets and plugin-declared routes under
``/api/v1/plugins/<key>/…`` — **default-deny**: a route exists only if the plugin declared it with a
permission, which is checked for every call (the dispatcher itself needs a signed-in member); calls are
rate limited and run inside the PluginGuard. Assets are images only, with a strict CSP."""

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from portalab.capabilities.content.render import render_markdown
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Forbidden, NotFound
from portalab.modules.plugins.api.admin import Module
from portalab.sdk.pages import DataBlock, FormBlock, MarkdownBlock

router = APIRouter(prefix="/api/v1", tags=["plugins"])
Member = Annotated[Principal, require("users.self.manage")]
IMAGES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _block(block: Any) -> dict[str, Any]:
    if isinstance(block, MarkdownBlock):
        return {"kind": "markdown", "html": render_markdown(block.text).html}
    if isinstance(block, DataBlock):
        return {
            "kind": block.kind,
            "title_key": block.title_key,
            "data": block.data,
            "columns": list(block.columns),
            "chart": block.chart,
        }
    if isinstance(block, FormBlock):
        return {
            "kind": "form",
            "title_key": block.title_key,
            "schema": block.schema,
            "action": block.action,
            "submit_key": block.submit_key,
        }
    return {"kind": "unknown"}


async def _live(module: Any, key: str) -> None:
    plugin = await module.lifecycle.get(key)
    if plugin.state != "enabled":
        raise NotFound("This plugin is not available.", code="plugin.not_available")


@router.get("/plugins/pages")
async def pages(principal: Member, request: Request, module: Module) -> list[dict[str, Any]]:
    authorizer = request.app.state.authorizer
    out = []
    for plugin in await module.lifecycle.all():
        if plugin.state != "enabled":
            continue
        for page in module.registries.pages.of(plugin.key):
            if await authorizer.is_allowed(principal, page.required_permission):
                out.append({"plugin": plugin.key, "key": page.key, "title_key": page.title_key})
    return out


@router.get("/plugins/{key}/pages/{page}")
async def page(principal: Member, key: str, page: str, request: Request, module: Module) -> dict[str, Any]:
    await _live(module, key)
    definition = module.registries.pages.get(key, page)
    if definition is None:
        raise NotFound("No such page.", code="plugin.page_not_found")
    if not await request.app.state.authorizer.is_allowed(principal, definition.required_permission):
        raise NotFound("No such page.", code="plugin.page_not_found")  # hide existence
    return {
        "plugin": key,
        "key": definition.key,
        "title_key": definition.title_key,
        "blocks": [_block(b) for b in definition.blocks],
    }


@router.get("/plugins/{key}/assets/{path:path}")
async def asset(principal: Member, key: str, path: str, module: Module) -> FileResponse:
    await _live(module, key)
    plugin = await module.lifecycle.get(key)
    root = (module.store.target(key, plugin.current_version) / "assets").resolve()
    target = (root / path).resolve()
    suffix = Path(path).suffix.lower()
    if root not in target.parents or suffix not in IMAGES or not target.is_file():
        raise NotFound("No such asset.", code="plugin.asset_not_found")
    return FileResponse(
        target,
        media_type=IMAGES[suffix],
        headers={"Content-Security-Policy": "default-src 'none'", "X-Content-Type-Options": "nosniff"},
    )


async def _dispatch(
    method: str, principal: Principal, key: str, path: str, request: Request, module: Any
) -> Any:
    await _live(module, key)
    route = module.registries.routes.get(key, method, path.strip("/"))
    if route is None:
        raise NotFound("No such plugin route.", code="plugin.route_not_found")
    if not await request.app.state.authorizer.is_allowed(principal, route.permission):
        raise Forbidden("You cannot use this plugin action.", code="plugin.forbidden")
    module.guard.check_rate(key)
    body = None
    if method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = None
        if body is not None and not isinstance(body, dict):
            body = None
        if body is not None and len(str(body)) > 64_000:
            raise Forbidden("The payload is too large.", code="plugin.payload_too_large")
    query = dict(request.query_params)
    registered = module.runtime.registered.get(key)
    meta = registered.routes.get((method, path.strip("/"))) if registered is not None else None
    if meta is not None and meta["exposure"] == "committing" and meta.get("describe") is not None:
        # 030 (R6): confirmed by the member in Portalab's own dialog, with the exact content, first
        token = request.headers.get("X-Portalab-Confirmation") or (body or {}).get("confirmation")
        body = {k: v for k, v in (body or {}).items() if k != "confirmation"} if body is not None else None
        describe = meta["describe"]
        clean = body
        await module.confirmations.require(
            user_id=principal.user_id,
            plugin=key,
            route=f"{method} {path.strip('/')}",
            body=clean,
            token=str(token) if token else None,
            describe=lambda: module.guard.run(key, "route", describe, principal, query, clean),
        )
    return await route.handler(principal, query, body)


@router.get("/plugins/{key}/{path:path}")
async def plugin_get(principal: Member, key: str, path: str, request: Request, module: Module) -> Any:
    return await _dispatch("GET", principal, key, path, request, module)


@router.post("/plugins/{key}/{path:path}")
async def plugin_post(principal: Member, key: str, path: str, request: Request, module: Module) -> Any:
    return await _dispatch("POST", principal, key, path, request, module)
