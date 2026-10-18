"""Confined plugins in the administration (spec 030, contracts/http-api.md): whether this system can confine
them, a plugin's confinement, its grants (revocable at once), its recorded attempts, its outgoing calls and
its secret settings (write-only: their values are never shown again)."""

from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from portalab.core.audit_port import AuditRecord
from portalab.core.authz_port import ResourceRef
from portalab.core.errors import NotFound, ValidationFailed
from portalab.core.time import utc_now
from portalab.modules.plugins.api.admin import Manager, Module, Reader, _confirm
from portalab.modules.plugins.confined.grants import review_items
from portalab.modules.plugins.confined.storage import DB_SECRET
from portalab.modules.plugins.manifest.schema import validate
from portalab.modules.plugins.models import Attempt, NetworkCall, SecretSetting
from portalab.modules.plugins.permissions import MANAGE

router = APIRouter(prefix="/api/v1", tags=["plugins-admin"])


class SecretIn(BaseModel):
    value: str = Field(min_length=1, max_length=4000)
    confirmation: str | None = None


class ConfirmIn(BaseModel):
    confirmation: str | None = None


def _attempt(row: Attempt) -> dict[str, Any]:
    return {
        "kind": row.kind,
        "detail": dict(row.detail or {}),
        "occurred_at": row.occurred_at,
        "version": row.version,
    }


@router.get("/admin/plugins/runtime")
async def runtime(_: Reader, module: Module) -> dict[str, Any]:
    """Can this system confine plugins (Landlock, seccomp), and what the Admin allows otherwise."""
    support = module.runtime.support()
    config = module.config
    return {
        **support.as_dict(),
        "weak_allowed": bool(config.allow_weak_confinement),
        "unconfined": str(config.unconfined),
    }


@router.get("/admin/plugins/{key}/confinement")
async def confinement(_: Reader, key: str, module: Module) -> dict[str, Any]:
    plugin = await module.lifecycle.get(key)
    row = await module.lifecycle.version(key, plugin.current_version)
    manifest = validate(dict(row.manifest))
    since = utc_now(module.clock) - timedelta(hours=24)
    async with module.database.session() as session:
        attempts = (
            await session.execute(
                select(Attempt)
                .where(Attempt.plugin_key == key)
                .order_by(Attempt.occurred_at.desc())
                .limit(20)
            )
        ).scalars()
        calls = (
            await session.execute(
                select(NetworkCall).where(NetworkCall.plugin_key == key, NetworkCall.hour >= since)
            )
        ).scalars()
        secrets_set = {
            s.name
            for s in (
                await session.execute(select(SecretSetting).where(SecretSetting.plugin_key == key))
            ).scalars()
        }
    hosts: dict[str, dict[str, int]] = {}
    for call in calls:
        entry = hosts.setdefault(call.host, {"calls": 0, "refused": 0, "bytes_in": 0, "bytes_out": 0})
        for field in entry:
            entry[field] += int(getattr(call, field))
    warning = None
    if plugin.runtime == "in_process":
        warning = "unconfined"
    elif plugin.confinement and plugin.confinement.get("weak"):
        warning = "weak"
    host = module.runtime.hosts.get(key)
    return {
        "runtime": plugin.runtime,
        "state": plugin.state,
        "running": bool(host is not None and host.state == "running"),
        "confinement": plugin.confinement,
        "warning": warning,
        "requested": review_items(manifest) if manifest.schema_version >= 2 else [],
        "grants": await module.grants.listed(key, plugin.current_version),
        "attempts": [_attempt(a) for a in attempts],
        "network": {"hosts": manifest.network_hosts, "last_24h": hosts},
        "secrets": [
            {"name": s["name"], "description": s.get("description", ""), "set": s["name"] in secrets_set}
            for s in manifest.secret_settings()
        ],
    }


@router.get("/admin/plugins/{key}/attempts")
async def attempts(
    _: Reader,
    key: str,
    module: Module,
    before: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    await module.lifecycle.get(key)
    query = select(Attempt).where(Attempt.plugin_key == key)
    if before is not None:
        query = query.where(Attempt.occurred_at < before)
    async with module.database.session() as session:
        rows = list(
            (await session.execute(query.order_by(Attempt.occurred_at.desc()).limit(limit))).scalars()
        )
    return {
        "items": [_attempt(a) for a in rows],
        "next": rows[-1].occurred_at if len(rows) == limit else None,
    }


@router.post("/admin/plugins/{key}/grants/{capability}/revoke")
async def revoke(
    principal: Manager, key: str, capability: str, body: ConfirmIn, module: Module
) -> dict[str, Any]:
    plugin = await module.lifecycle.get(key)
    await _confirm(module, principal, MANAGE, key, {"revoke": capability}, body.confirmation)
    await module.grants.revoke(principal, key, plugin.current_version, capability)
    return {"revoked": capability}


async def _secret_setting(module: Any, key: str, name: str) -> None:
    plugin = await module.lifecycle.get(key)
    row = await module.lifecycle.version(key, plugin.current_version)
    names = {s["name"] for s in validate(dict(row.manifest)).secret_settings()}
    if name not in names or name == DB_SECRET:
        raise NotFound("This plugin has no such secret setting.", code="plugin.secret_not_found")


@router.put("/admin/plugins/{key}/secrets/{name}", status_code=204)
async def set_secret(principal: Manager, key: str, name: str, body: SecretIn, module: Module) -> None:
    await _secret_setting(module, key, name)
    await _confirm(module, principal, MANAGE, key, {"secret": name}, body.confirmation)
    box = module.runtime.box
    if box is None:
        raise ValidationFailed("Secrets cannot be kept without the application key.", code="plugin.no_key")
    async with module.database.unit_of_work() as uow:
        session = uow.session
        row = await session.get(SecretSetting, (key, name))
        ciphertext = box.encrypt(body.value, context=f"plugins.setting:{key}:{name}")
        now = utc_now(module.clock)
        actor = principal.acting_for or principal.user_id
        if row is None:
            session.add(
                SecretSetting(
                    plugin_key=key, name=name, ciphertext=ciphertext, updated_by=actor, updated_at=now
                )
            )
        else:
            row.ciphertext, row.updated_by, row.updated_at = ciphertext, actor, now
        await module.audit.record(
            session,
            AuditRecord(
                action="plugin.secret_set",
                actor=principal,
                resource=ResourceRef("plugin", key),
                decision="allow",
                context={"setting": name},  # never the value
                sensitive=True,
            ),
        )


@router.post("/admin/plugins/{key}/secrets/{name}/clear", status_code=204)
async def clear_secret(principal: Manager, key: str, name: str, body: ConfirmIn, module: Module) -> None:
    await _secret_setting(module, key, name)
    await _confirm(module, principal, MANAGE, key, {"clear_secret": name}, body.confirmation)
    async with module.database.unit_of_work() as uow:
        session = uow.session
        row = await session.get(SecretSetting, (key, name))
        if row is not None:
            await session.delete(row)
        await module.audit.record(
            session,
            AuditRecord(
                action="plugin.secret_cleared",
                actor=principal,
                resource=ResourceRef("plugin", key),
                decision="allow",
                context={"setting": name},
                sensitive=True,
            ),
        )


@router.post("/admin/plugins/{key}/versions/{version}/grants")
async def grant_version(principal: Manager, key: str, version: str, module: Module) -> dict[str, Any]:
    """Accept what a version (an update waiting to be confirmed) asks: its review's capabilities, granted."""
    await module.lifecycle.get(key)
    row = await module.lifecycle.version(key, version)
    manifest = validate(dict(row.manifest))
    granted = await module.grants.grant_all(principal, key, version, manifest)
    return {"version": version, "granted": granted}
