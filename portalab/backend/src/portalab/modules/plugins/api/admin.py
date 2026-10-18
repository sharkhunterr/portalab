"""Plugin administration (T011, T014, T019, T026, T033): ``plugins.read`` to look, ``plugins.manage`` to
install (review object), approve (consent), enable, disable (a cascade needs a confirmation), archive,
update/confirm-restart/rollback and change settings, ``plugins.purge`` (confirmed) to delete data."""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, Forbidden, NotFound, Unavailable, ValidationFailed
from portalab.modules.plugins.lifecycle.service import review_of
from portalab.modules.plugins.manifest.schema import validate
from portalab.modules.plugins.models import Plugin
from portalab.modules.plugins.module import PluginsModule
from portalab.modules.plugins.permissions import MANAGE, PURGE, READ
from portalab.modules.plugins.resolver.resolver import dependents, problems_for

router = APIRouter(prefix="/api/v1", tags=["plugins-admin"])
PACKAGE = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$"


def plugins_module(request: Request) -> PluginsModule:
    module = getattr(request.app.state, "plugins_module", None)
    if not isinstance(module, PluginsModule):
        raise Unavailable("Plugins are not available.", code="plugins.unavailable")
    return module


Module = Annotated[PluginsModule, Depends(plugins_module)]
Reader = Annotated[Principal, require(READ)]
Manager = Annotated[Principal, require(MANAGE)]
Purger = Annotated[Principal, require(PURGE)]


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


class PluginOut(BaseModel):
    key: str
    name: str
    state: str
    version: str
    scope: str
    maturity: str
    source: str
    approved: bool
    needs_restart: bool
    quarantine_reason: str | None
    runtime: str = "declarative"  # 030: declarative, in_process (Portalab's process) or confined
    installed_at: datetime
    updated_at: datetime


class PluginPackageIn(BaseModel):
    package: str = Field(pattern=PACKAGE)


class PluginDisableIn(BaseModel):
    cascade: bool = False
    confirmation: str | None = None


class PluginPurgeIn(BaseModel):
    export: bool = True
    confirmation: str | None = None


class PluginSettingsIn(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


def plugin_out(plugin: Plugin) -> PluginOut:
    return PluginOut(
        key=plugin.key,
        name=plugin.name,
        state=plugin.state,
        version=plugin.current_version,
        scope=plugin.scope,
        maturity=plugin.maturity,
        source=plugin.source,
        approved=plugin.approved,
        needs_restart=plugin.needs_restart,
        quarantine_reason=plugin.quarantine_reason,
        runtime=plugin.runtime,
        installed_at=plugin.installed_at,
        updated_at=plugin.updated_at,
    )


async def _confirm(
    module: PluginsModule,
    principal: Principal,
    permission: str,
    key: str,
    payload: dict[str, Any],
    token: str | None,
) -> None:
    providers = module.capabilities.system_providers(CONFIRMATIONS)
    if not providers:
        raise Unavailable("Confirmations are not available.", code="authz.unavailable")
    confirmations = providers[0].provider
    resource = ResourceRef("plugin", key)
    if token is None:
        issued = await confirmations.issue(principal, permission, resource, payload)
        raise ConfirmationRequired("Confirm this change.", extensions={"confirmation": issued, **payload})
    if not await confirmations.consume(token, principal, permission, resource, payload):
        raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")


def _available(module: PluginsModule, package: str) -> Path:
    path = (module.store.available / package).resolve()
    if module.store.available.resolve() not in path.parents or not path.exists():
        raise NotFound("No such package in plugins/available.", code="plugin.package_not_found")
    return path


@router.get("/admin/plugins", response_model=list[PluginOut])
async def list_plugins(_: Reader, module: Module) -> list[PluginOut]:
    return [plugin_out(p) for p in await module.lifecycle.all()]


@router.get("/admin/plugins/discovery")
async def discovery(_: Reader, module: Module) -> list[dict[str, Any]]:
    return await module.discovery.available()


@router.post("/admin/plugins/install", status_code=201)
async def install(principal: Manager, body: PluginPackageIn, module: Module) -> dict[str, Any]:
    plugin, review = await module.lifecycle.install(
        principal, _available(module, body.package), origin="local_dir"
    )
    return {"plugin": plugin_out(plugin).model_dump(mode="json"), "review": review}


@router.post(
    "/admin/plugins/upload",
    status_code=201,
    openapi_extra={
        "requestBody": {"content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}}}
    },
)
async def upload(
    principal: Manager, module: Module, request: Request, filename: Annotated[str, Query(pattern=PACKAGE)]
) -> dict[str, Any]:
    """Raw ``application/zip`` body (no multipart); the package lands in ``plugins/available``."""
    if not filename.endswith(".zip"):
        raise ValidationFailed("Upload a .zip plugin package.", code="plugin.invalid_package")
    body = await request.body()
    if len(body) > 20 * 1024 * 1024:
        raise ValidationFailed("The package is too large.", code="plugin.invalid_package")
    module.store.available.mkdir(parents=True, exist_ok=True)
    target = module.store.available / filename
    target.write_bytes(body)
    plugin, review = await module.lifecycle.install(principal, target, origin="admin_upload")
    return {"plugin": plugin_out(plugin).model_dump(mode="json"), "review": review}


@router.get("/admin/plugins/{key}")
async def detail(_: Reader, key: str, module: Module) -> dict[str, Any]:
    plugin = await module.lifecycle.get(key)
    row = await module.lifecycle.version(key, plugin.current_version)
    manifests = await module.lifecycle.manifests()
    enabled = await module.lifecycle.enabled_keys()
    return {
        "plugin": plugin_out(plugin).model_dump(mode="json"),
        "review": review_of(validate(dict(row.manifest)), row.sha256),
        "deprecation_notice": row.manifest.get("deprecation_notice"),
        "dependencies": [p.detail for p in problems_for(key, manifests, enabled)] if key in manifests else [],
        "dependents": dependents(key, manifests, enabled) if key in manifests else [],
    }


@router.get("/admin/plugins/{key}/diagnostics")
async def diagnostics(_: Reader, key: str, module: Module) -> dict[str, Any]:
    await module.lifecycle.get(key)
    entries = await module.ledger.entries(key)
    stats = await module.guard.stats(key)
    return {
        "contributions": [
            {
                "point": e.point,
                "id": e.contribution_id,
                "state": e.state,
                "priority": e.priority,
                "detail": e.detail,
            }
            for e in entries
            if e.state != "removed"
        ],
        "conflicts": [
            {"point": e.point, "id": e.contribution_id, "detail": e.detail}
            for e in entries
            if e.state == "conflict"
        ],
        "errors": [
            {
                "window_start": s.window_start.isoformat(),
                "kind": s.kind,
                "count": s.count,
                "last": s.last_sample,
            }
            for s in stats[:20]
        ],
    }


@router.post("/admin/plugins/{key}/approve", response_model=PluginOut)
async def approve(principal: Manager, key: str, module: Module) -> PluginOut:
    return plugin_out(await module.lifecycle.approve(principal, key))


@router.post("/admin/plugins/{key}/enable", response_model=PluginOut)
async def enable(principal: Manager, key: str, module: Module) -> PluginOut:
    return plugin_out(await module.lifecycle.enable(principal, key))


@router.post("/admin/plugins/{key}/disable")
async def disable(principal: Manager, key: str, body: PluginDisableIn, module: Module) -> dict[str, Any]:
    if body.cascade:
        chain = dependents(key, await module.lifecycle.manifests(), await module.lifecycle.enabled_keys())
        if chain:
            await _confirm(module, principal, MANAGE, key, {"cascade": chain}, body.confirmation)
    return {"disabled": await module.lifecycle.disable(principal, key, cascade=body.cascade)}


@router.post("/admin/plugins/{key}/archive", response_model=PluginOut)
async def archive(principal: Manager, key: str, module: Module) -> PluginOut:
    return plugin_out(await module.lifecycle.archive(principal, key))


@router.put("/admin/plugins/{key}/settings")
async def settings(principal: Manager, key: str, body: PluginSettingsIn, module: Module) -> dict[str, Any]:
    await module.lifecycle.get(key)
    providers = module.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
    if not providers:
        raise Unavailable("Settings are not available.", code="admin.unavailable")
    for name, value in body.values.items():
        await providers[0].provider.set_global(
            principal, f"plugin.{key}.{name}", value, reason="plugin settings"
        )
    return {"updated": sorted(body.values)}


@router.post("/admin/plugins/{key}/update")
async def stage_update(principal: Manager, key: str, body: PluginPackageIn, module: Module) -> dict[str, Any]:
    run = await module.updates.stage(principal, key, _available(module, body.package))
    return {"status": run.status, "from": run.from_version, "to": run.to_version}


@router.post("/admin/plugins/{key}/update/confirm-restart")
async def confirm_restart(principal: Manager, key: str, module: Module) -> dict[str, Any]:
    run = await module.updates.confirm_restart(principal, key)
    return {"status": run.status, "probation_until": run.probation_until}


@router.post("/admin/plugins/{key}/rollback")
async def rollback(principal: Manager, key: str, module: Module) -> dict[str, Any]:
    run = await module.updates.rollback(principal, key)
    return {"status": run.status, "version": run.from_version}


@router.post("/admin/plugins/{key}/purge")
async def purge(principal: Purger, key: str, body: PluginPurgeIn, module: Module) -> dict[str, Any]:
    await module.lifecycle.get(key)
    await _confirm(module, principal, PURGE, key, {"export": body.export}, body.confirmation)
    row = await module.purges.purge(principal, key, export=body.export)
    return {"exported": row.exported, "export_ref": row.export_ref, "schema_dropped": row.schema_dropped}
