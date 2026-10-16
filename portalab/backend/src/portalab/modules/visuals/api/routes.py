"""Visual packs API (spec 028).

Members: ``GET /visuals/active`` (the elements their interface loads), the files of the live packs, and the
sandbox page pack scripts run in (a session is needed for all three: nothing of a pack reaches a visitor).
The Admin (``visuals.manage``, reserved): the packs, their versions and every step of their workflow, the
inbox read again, an upload, a GitHub address, the updates on offer, the Test step's measures, the Review
draft, publication, refusal, switching a pack off and on, rollback, removal, purge — and every version's
files, to show them before they are validated.
"""

import mimetypes
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound, Unavailable, ValidationFailed
from portalab.modules.visuals.module import VisualsModule
from portalab.modules.visuals.sandbox import DOCUMENT
from portalab.modules.visuals.sandbox import HEADERS as SANDBOX_HEADERS
from portalab.modules.visuals.service import VisualPacks

members = APIRouter(prefix="/api/v1", tags=["visuals"])
admin = APIRouter(prefix="/api/v1", tags=["visuals"])
Manager = Annotated[Principal, require("visuals.manage")]
Member = Annotated[Principal, require("users.self.manage")]

# a pack's files are served with a type chosen by their extension, never by their content
TYPES = {
    ".css": "text/css",
    ".glsl": "text/plain",
    ".frag": "text/plain",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".json": "application/json",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".webm": "video/webm",
    ".mp4": "video/mp4",
}
INLINE = (".css", ".glsl", ".frag", ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif",
          ".woff2", ".woff", ".ttf", ".otf", ".mp3", ".ogg", ".wav", ".webm", ".mp4")  # fmt: skip
# a pack's file opened on its own (an SVG, a page someone links to) runs nothing and reaches nothing: a
# sandboxed document of an opaque origin; read by Portalab only (never by another site)
FILE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; img-src data:; style-src 'unsafe-inline'; sandbox",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def visuals_module(request: Request) -> VisualsModule:
    module = request.app.state._state.get("visuals_module")
    if not isinstance(module, VisualsModule):
        raise Unavailable("Visual packs are not available.", code="ui.visuals_unavailable")
    return module


def visual_packs(module: Annotated[VisualsModule, Depends(visuals_module)]) -> VisualPacks:
    return module.packs


Packs = Annotated[VisualPacks, Depends(visual_packs)]


def _file(path: Path | None, *, live: bool) -> FileResponse:
    if path is None:
        raise NotFound("This file is not available.", code="ui.visual_file_not_found")
    suffix = path.suffix.lower()
    kind = TYPES.get(suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {
        **FILE_HEADERS,
        # its folder is its fingerprint: it never changes (a version not validated yet is not kept)
        "Cache-Control": "private, max-age=31536000, immutable" if live else "private, no-store",
        "Content-Disposition": "inline" if suffix in INLINE else "attachment",
    }
    return FileResponse(path, media_type=kind, headers=headers)


@members.get("/visuals/sandbox", include_in_schema=False)
async def sandbox(_: Member) -> HTMLResponse:
    """The page a pack's script runs in (framed by the interface, sandboxed): it holds nothing, yet only a
    member's interface may load it (028: nothing answers a visitor but signing in)."""
    return HTMLResponse(DOCUMENT, headers=SANDBOX_HEADERS)


class ActiveOut(BaseModel):
    epoch: int
    elements: list[dict[str, Any]]
    withheld: dict[
        str, list[str]
    ] = {}  # Portalab's own looks whose pack is off: their wearers see the default


@members.get("/visuals/active", response_model=ActiveOut)
async def active(_: Member, packs: Packs, request: Request, response: Response) -> Any:
    manifest = await packs.active()
    tag = f'"{manifest["epoch"]}"'
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers={"ETag": tag, "Cache-Control": "private, no-cache"})
    response.headers["ETag"] = tag
    response.headers["Cache-Control"] = "private, no-cache"
    return manifest


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pack: str = Field(max_length=48)
    sha: str = Field(min_length=16, max_length=64)
    element: str = Field(max_length=64)
    reason: Literal["timeout", "error", "unresponsive"]


@members.post("/visuals/reports", status_code=204)
async def report(principal: Member, packs: Packs, body: ReportIn) -> None:
    """A pack's element failed in this member's page (counted for the administrators, an hour apart)."""
    await packs.report_failure(principal, body.pack, body.sha, body.element, body.reason)


@members.get("/visuals/files/{pack}/{sha}/{name:path}")
async def live_file(_: Member, packs: Packs, pack: str, sha: str, name: str) -> FileResponse:
    return _file(await packs.served(pack, sha, name, manager=False), live=True)


@admin.get("/admin/visuals/files/{pack}/{sha}/{name:path}")
async def any_file(_: Manager, packs: Packs, pack: str, sha: str, name: str) -> FileResponse:
    return _file(await packs.served(pack, sha, name, manager=True), live=False)


@admin.get("/admin/visuals")
async def listing(_: Manager, packs: Packs) -> dict[str, Any]:
    return {"packs": await packs.listing(), "inbox": str(packs.store.inbox)}


@admin.post("/admin/visuals/scan")
async def scan(principal: Manager, packs: Packs) -> dict[str, Any]:
    return await packs.scan(principal)


@admin.post(
    "/admin/visuals/upload",
    status_code=201,
    openapi_extra={
        "requestBody": {"content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}}}
    },
)
async def upload(
    principal: Manager, packs: Packs, request: Request, filename: Annotated[str, Query(max_length=120)]
) -> dict[str, Any]:
    """A raw ``application/zip`` body (no multipart), 20 MB at most."""
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 20 * 1024 * 1024:
            raise ValidationFailed("The pack is too large (20 MB at most).", code="ui.visual_pack_invalid")
    if not body:
        raise ValidationFailed("Send a .zip pack.", code="ui.visual_pack_invalid")
    imported = await packs.upload(filename, bytes(body), principal)
    return {"pack": imported.pack, "version": imported.version, "sha": imported.sha, "new": imported.new}


class GitHubIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(max_length=300)


@admin.post("/admin/visuals/github", status_code=201)
async def github(principal: Manager, packs: Packs, body: GitHubIn) -> dict[str, Any]:
    imported = await packs.from_github(body.url, principal)
    return {"pack": imported.pack, "version": imported.version, "sha": imported.sha, "new": imported.new}


@admin.post("/admin/visuals/updates")
async def updates(_: Manager, packs: Packs) -> dict[str, Any]:
    return {"updates": await packs.check_updates()}


@admin.get("/admin/visuals/{pack}/{version}")
async def detail(_: Manager, packs: Packs, pack: str, version: str) -> dict[str, Any]:
    return await packs.detail(pack, version)


class MeasuresIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[dict[str, Any]] = Field(max_length=200)


@admin.post("/admin/visuals/{pack}/{version}/measures", status_code=204)
async def measures(principal: Manager, packs: Packs, pack: str, version: str, body: MeasuresIn) -> None:
    await packs.record_measures(principal, pack, version, body.results)


class Confirmations(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scripts: bool = False
    replaces: list[str] = Field(default_factory=list, max_length=200)  # ``<type>:<look>``
    contracts: list[str] = Field(default_factory=list, max_length=20)


class DraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # per product key: what the administrator changed (price, rarity, level, supply, collection, icon, season)
    economy: dict[str, dict[str, Any]] = Field(default_factory=dict)
    bindings: dict[str, str | None] = Field(default_factory=dict)
    confirmations: Confirmations = Field(default_factory=Confirmations)


@admin.put("/admin/visuals/{pack}/{version}/draft")
async def draft(principal: Manager, packs: Packs, pack: str, version: str, body: DraftIn) -> dict[str, Any]:
    return await packs.save_draft(principal, pack, version, body.model_dump())


class PublishIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    economy: dict[str, dict[str, Any]] = Field(default_factory=dict)
    confirmations: Confirmations = Field(default_factory=Confirmations)


@admin.post("/admin/visuals/{pack}/{version}/publish")
async def publish(
    principal: Manager, packs: Packs, pack: str, version: str, body: PublishIn
) -> dict[str, Any]:
    return await packs.publish(principal, pack, version, body.economy, body.confirmations.model_dump())


class RefuseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=500)


@admin.post("/admin/visuals/{pack}/{version}/refuse", status_code=204)
async def refuse(principal: Manager, packs: Packs, pack: str, version: str, body: RefuseIn) -> None:
    await packs.refuse(principal, pack, version, body.reason)


class StateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["enabled", "disabled"]


@admin.post("/admin/visuals/builtin/state")
async def builtin_state(principal: Manager, packs: Packs, body: StateIn) -> dict[str, Any]:
    """Portalab's whole catalog switched on — or off, the socle staying on."""
    return {"changed": await packs.set_builtin_state(principal, body.state == "enabled")}


@admin.post("/admin/visuals/{pack}/state", status_code=204)
async def state(principal: Manager, packs: Packs, pack: str, body: StateIn) -> None:
    await packs.set_state(principal, pack, body.state == "enabled")


@admin.post("/admin/visuals/{pack}/remove")
async def remove(principal: Manager, packs: Packs, pack: str) -> dict[str, Any]:
    return await packs.remove(principal, pack)


@admin.post("/admin/visuals/{pack}/{version}/rollback")
async def rollback(principal: Manager, packs: Packs, pack: str, version: str) -> dict[str, Any]:
    return await packs.rollback(principal, pack, version)


@admin.post("/admin/visuals/{pack}/{version}/purge", status_code=204)
async def purge(principal: Manager, packs: Packs, pack: str, version: str) -> None:
    await packs.purge(principal, pack, version)
