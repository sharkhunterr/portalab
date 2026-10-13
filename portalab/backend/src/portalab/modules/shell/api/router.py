"""Shell API (T013, T015): ``GET /me/navigation`` (ETag / 304) and the admin layout & diagnostics.
Live updates use the kernel stream (``GET /api/v1/stream``, topic ``navigation.changed``)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable, ValidationFailed
from portalab.modules.shell.module import ShellModule
from portalab.modules.shell.permissions import AUTHENTICATED, SHELL_MANAGE

router = APIRouter(prefix="/api/v1", tags=["shell"])


def shell_module(request: Request) -> ShellModule:
    module = getattr(request.app.state, "shell_module", None)
    if not isinstance(module, ShellModule):
        raise Unavailable("Navigation is not available.", code="shell.unavailable")
    return module


Module = Annotated[ShellModule, Depends(shell_module)]
Manager = Annotated[Principal, require(SHELL_MANAGE)]


class Layout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order: dict[str, int] = Field(default_factory=dict)
    pinned: list[str] = Field(default_factory=list, max_length=50)
    groups_of: dict[str, str] = Field(default_factory=dict)
    group_order: list[str] = Field(default_factory=list, max_length=50)
    section_labels: dict[str, str] = Field(default_factory=dict)  # 027: rename a section (an i18n key)


@router.get("/me/navigation")
async def my_navigation(
    principal: Annotated[Principal, require(AUTHENTICATED)], request: Request, module: Module
) -> Response:
    view = await module.assembler.build(principal)
    await module.flush_diagnostics()
    etag = f'"{view["version"]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(view, headers={"ETag": etag, "Cache-Control": "private, no-cache"})


@router.get("/me/attention")
async def my_attention(
    principal: Annotated[Principal, require(AUTHENTICATED)], module: Module
) -> dict[str, dict[str, int]]:
    """#98: what waits for me, per navigation entry (a purchase to validate, a proposal to moderate…) —
    the badges of the navigation; the shell adds them up for hubs and sections."""
    return {"items": await module.attention(principal)}


@router.get("/admin/shell/layout")
async def get_layout(_: Manager, request: Request, module: Module) -> dict[str, Any]:
    providers = request.app.state.capabilities.system_providers(CONFIG)
    layout = (await providers[0].provider.get("shell.navigation.layout")).value if providers else {}
    return {
        "layout": layout,
        "entries": [c.key for c in module.registry.all() if c.kind == "entry"],
        "sections": [s.key for s in module.registry.sections()],
    }


@router.put("/admin/shell/layout")
async def put_layout(principal: Manager, body: Layout, request: Request, module: Module) -> dict[str, Any]:
    known = {c.key for c in module.registry.all() if c.kind == "entry"}
    sections = {s.key for s in module.registry.sections()}
    unknown = sorted((set(body.order) | set(body.pinned) | set(body.groups_of)) - known)
    unknown += sorted(
        f"section:{key}" for key in (set(body.groups_of.values()) | set(body.section_labels)) - sections
    )
    if unknown:
        raise ValidationFailed(
            "The layout references unknown navigation entries.",
            code="navigation.contribution_invalid",
            extensions={"keys": unknown},
        )
    providers = request.app.state.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
    if not providers:
        raise Unavailable("Configuration is not available.", code="admin.unavailable")
    await providers[0].provider.set_global(
        principal, "shell.navigation.layout", body.model_dump(), reason="navigation layout"
    )
    await module.epochs.bump("module")
    return {"layout": body.model_dump()}


@router.get("/admin/shell/contribution-errors")
async def contribution_errors(_: Manager, module: Module) -> dict[str, Any]:
    await module.flush_diagnostics()
    return {"items": await module.isolator.errors()}
