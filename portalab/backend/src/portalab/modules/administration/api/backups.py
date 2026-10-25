"""Backups API (issue 247): the administrators save the portal and download its archives
(``configuration.manage``); a new portal's arrival wizard brings one in — answered only while nobody has set
the portal up (then the same answer as any address), its progress until the restore is over."""

import platform
from typing import Annotated, Any

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import public, require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unauthorized, Unavailable, ValidationFailed
from portalab.modules.administration.api.routes import MANAGE, Module
from portalab.modules.administration.backup.archive import FORMAT, Options
from portalab.modules.administration.backup.service import BackupService

router = APIRouter(prefix="/api/v1", tags=["administration"])
Manager = Annotated[Principal, require(MANAGE)]


class CreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passphrase: str = Field(min_length=12, max_length=512)
    history: bool = False
    media: bool = True


class ResetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: str = Field(min_length=1, max_length=120)  # the portal's name, typed again
    password: str = Field(min_length=1, max_length=1024)


class OpenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    passphrase: str = Field(min_length=1, max_length=512)


def _backups(module: Any) -> BackupService:
    service = getattr(module, "backups", None)
    if not isinstance(service, BackupService):
        raise Unavailable("Backups are not available.", code="backup.unavailable")
    return service


@router.get("/admin/backups")
async def list_backups(_: Manager, module: Module) -> dict[str, Any]:
    service = _backups(module)
    return {"archives": service.archives(), "run": service.state()}


@router.post("/admin/backups", status_code=status.HTTP_202_ACCEPTED)
async def create_backup(principal: Manager, body: CreateIn, module: Module) -> dict[str, Any]:
    run = _backups(module).start_create(principal, body.passphrase, Options(body.history, body.media))
    return run.as_dict()


@router.get("/admin/backups/{name}/download")
async def download_backup(_: Manager, name: str, module: Module) -> FileResponse:
    path = _backups(module).path_of(name)
    return FileResponse(path, media_type="application/octet-stream", filename=name)


@router.delete("/admin/backups/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backup(principal: Manager, name: str, module: Module) -> Response:
    await _backups(module).delete(principal, name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- the portal's version, and starting again from scratch -------------------------------------------------
@router.get("/admin/system/version")
async def system_version(_: Manager, module: Module) -> dict[str, Any]:
    """Which Portalab this is: its version, its archives' layout, each module's schema, the database."""
    service = _backups(module)
    heads = sorted(await service.versions.current())
    async with service.database.engine.connect() as conn:
        database = str((await conn.exec_driver_sql("SHOW server_version")).scalar())
    return {
        "portalab": service.portalab,
        "archive_format": FORMAT,
        "python": platform.python_version(),
        "database": f"PostgreSQL {database}",
        "started_at": service.started_at,
        "schema": [{"module": head.rsplit("_", 1)[0], "revision": head} for head in heads],
    }


@router.post("/admin/system/reset", status_code=status.HTTP_202_ACCEPTED)
async def system_reset(principal: Manager, body: ResetIn, request: Request, module: Module) -> dict[str, Any]:
    """Everything erased (the backups kept): typed again, the portal's name; then the password."""
    service = _backups(module)
    if body.confirm.strip().casefold() != (await service.site_name()).strip().casefold():
        raise ValidationFailed("Type the portal's name to confirm.", code="backup.reset_confirm")
    identity = getattr(request.app.state, "identity_module", None)
    if identity is None:
        raise Unavailable("Accounts are not available.", code="identity.unavailable")
    client = request.client.host if request.client else None
    await identity.auth.reauthenticate(principal, body.password, client_ip=client)
    return service.start_reset(principal).as_dict()


# --- the arrival wizard: a new portal brings a backup in ----------------------------------------------------
async def _arrival(module: Any) -> BackupService:
    if await module.first_run.completed() or await module.first_run.admin_exists():
        raise Unauthorized()  # set up: nothing to tell
    return _backups(module)


@router.get("/admin/first-run/import")
@public
async def import_archives(module: Module) -> dict[str, Any]:
    """The archives already on the server (copied into ``<DATA_DIR>/backups``)."""
    return {"archives": (await _arrival(module)).archives()}


@router.post("/admin/first-run/import/upload", status_code=status.HTTP_201_CREATED)
@public
async def import_upload(request: Request, module: Module) -> dict[str, str]:
    """An archive sent from the browser, as the request's body."""
    service = await _arrival(module)
    return {"name": await service.receive(request.stream())}


@router.post("/admin/first-run/import/inspect")
@public
async def import_inspect(body: OpenIn, module: Module) -> dict[str, Any]:
    return await (await _arrival(module)).inspect(body.name, body.passphrase)


@router.post("/admin/first-run/import", status_code=status.HTTP_202_ACCEPTED)
@public
async def import_start(body: OpenIn, module: Module) -> dict[str, Any]:
    service = await _arrival(module)
    await service.inspect(body.name, body.passphrase)  # a wrong passphrase or another version: said now
    return service.start_restore(body.name, body.passphrase).as_dict()


@router.get("/admin/first-run/import/status")
@public
async def import_status(module: Module) -> dict[str, Any]:
    """The restore's progress — answered until it is over, the portal then being set up."""
    service = _backups(module)
    run = service.state()
    if run is None or run["kind"] not in ("restore", "reset"):  # a reset ends on the arrival wizard
        await _arrival(module)
        return {"run": None}
    return {"run": run}
