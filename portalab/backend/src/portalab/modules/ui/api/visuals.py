"""Visual packs API (issue 1, POC).

Members: ``GET /visuals/active`` (the elements their interface loads) and the files of the published packs
switched on. Administrators (``appearance.manage``): the packs, their versions and reports, the inbox read
again, an upload, a GitHub address, the updates on offer, the sandbox's measures, validation (with the
economy decided per element), rejection, switching a pack off and on, rollback — and every version's files,
to show them before they are validated.
"""

import mimetypes
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import public, require
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound, Unavailable, ValidationFailed
from portalab.modules.ui.api.router import ui_module
from portalab.modules.ui.module import UiModule
from portalab.modules.ui.permissions import APPEARANCE_MANAGE
from portalab.modules.ui.visuals.sandbox import DOCUMENT
from portalab.modules.ui.visuals.sandbox import HEADERS as SANDBOX_HEADERS
from portalab.modules.ui.visuals.service import VisualPacks

router = APIRouter(prefix="/api/v1", tags=["ui"])
Manager = Annotated[Principal, require(APPEARANCE_MANAGE)]
Member = Annotated[Principal, require("users.self.manage")]
TYPES = {".glsl": "text/plain", ".frag": "text/plain", ".mjs": "text/javascript", ".js": "text/javascript"}


def visual_packs(module: Annotated[UiModule, Depends(ui_module)]) -> VisualPacks:
    if module.visuals is None:
        raise Unavailable("Visual packs are not available.", code="ui.visuals_unavailable")
    return module.visuals


Packs = Annotated[VisualPacks, Depends(visual_packs)]


# a pack's file opened on its own (an SVG, a page someone links to) runs nothing and reaches nothing: a
# sandboxed document of an opaque origin; read by Portalab only (never by another site)
FILE_HEADERS = {
    "Cache-Control": "private, max-age=31536000, immutable",  # its folder is its fingerprint: never changes
    "Content-Security-Policy": "default-src 'none'; img-src data:; style-src 'unsafe-inline'; sandbox",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
}


def _file(path: Any) -> FileResponse:
    if path is None:
        raise NotFound("This file is not available.", code="ui.visual_file_not_found")
    kind = TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=kind, headers=FILE_HEADERS)


@router.get("/visuals/sandbox", include_in_schema=False)
@public
async def sandbox() -> HTMLResponse:
    """The page a pack's script runs in (framed by the interface, sandboxed): public — it holds nothing."""
    return HTMLResponse(DOCUMENT, headers=SANDBOX_HEADERS)


@router.get("/visuals/active")
async def active(_: Member, packs: Packs) -> dict[str, Any]:
    return packs.active()


@router.get("/visuals/files/{pack}/{sha}/{name:path}")
async def live_file(_: Member, packs: Packs, pack: str, sha: str, name: str) -> FileResponse:
    return _file(packs.served(pack, sha, name, manager=False))


@router.get("/admin/visuals/files/{pack}/{sha}/{name:path}")
async def any_file(_: Manager, packs: Packs, pack: str, sha: str, name: str) -> FileResponse:
    return _file(packs.served(pack, sha, name, manager=True))


@router.get("/admin/visuals")
async def listing(_: Manager, packs: Packs) -> dict[str, Any]:
    return {"packs": packs.listing(), "inbox": str(packs.store.inbox)}


@router.post("/admin/visuals/scan")
async def scan(principal: Manager, packs: Packs) -> dict[str, Any]:
    return await packs.scan(principal)


@router.post(
    "/admin/visuals/upload",
    status_code=201,
    openapi_extra={
        "requestBody": {"content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}}}
    },
)
async def upload(
    principal: Manager, packs: Packs, request: Request, filename: Annotated[str, Query(max_length=120)]
) -> dict[str, Any]:
    """A raw ``application/zip`` body (no multipart)."""
    body = await request.body()
    if not body:
        raise ValidationFailed("Send a .zip pack.", code="ui.visual_pack_invalid")
    return asdict(await packs.upload(filename, body, principal))


class GitHubIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(max_length=300)


@router.post("/admin/visuals/github", status_code=201)
async def github(principal: Manager, packs: Packs, body: GitHubIn) -> dict[str, Any]:
    return asdict(await packs.from_github(body.url, principal))


@router.post("/admin/visuals/updates")
async def updates(_: Manager, packs: Packs) -> dict[str, Any]:
    return {"updates": await packs.check_updates()}


@router.get("/admin/visuals/{pack}/{version}")
async def detail(_: Manager, packs: Packs, pack: str, version: str) -> dict[str, Any]:
    return packs.detail(pack, version)


class SimulationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[dict[str, Any]] = Field(max_length=200)


@router.post("/admin/visuals/{pack}/{version}/simulation", status_code=204)
async def simulation(_: Manager, packs: Packs, pack: str, version: str, body: SimulationIn) -> None:
    packs.record_simulation(pack, version, body.results)


class ApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # per product key: what the administrator changed (price, rarity, level, supply, collection, icon)
    economy: dict[str, dict[str, Any]] = Field(default_factory=dict)
    accept_script: bool = False


@router.post("/admin/visuals/{pack}/{version}/approve")
async def approve(
    principal: Manager, packs: Packs, pack: str, version: str, body: ApproveIn
) -> dict[str, Any]:
    return await packs.approve(principal, pack, version, body.economy, accept_script=body.accept_script)


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=500)


@router.post("/admin/visuals/{pack}/{version}/reject", status_code=204)
async def reject(principal: Manager, packs: Packs, pack: str, version: str, body: RejectIn) -> None:
    await packs.reject(pack, version, body.reason, principal)


class SwitchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


@router.post("/admin/visuals/{pack}/switch", status_code=204)
async def switch(principal: Manager, packs: Packs, pack: str, body: SwitchIn) -> None:
    await packs.switch(principal, pack, body.enabled)


@router.post("/admin/visuals/{pack}/{version}/rollback")
async def rollback(principal: Manager, packs: Packs, pack: str, version: str) -> dict[str, Any]:
    return await packs.rollback(principal, pack, version)
