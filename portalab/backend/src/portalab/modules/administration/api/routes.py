"""Administration API (T010, T013, T015, T018, T020, T022, T024, T027)."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.administration import default_admin_surfaces
from portalab.core.authorization import current_principal, public, require
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.errors import Forbidden, Unauthorized, Unavailable
from portalab.modules.administration.config.registry import allowed_scopes, is_user_overridable
from portalab.modules.administration.config.service import Change
from portalab.modules.administration.firstrun.service import FirstRunClosed, WizardRequest
from portalab.modules.administration.module import AdministrationModule
from portalab.modules.administration.toggles.service import PERMISSION_BY_KIND

router = APIRouter(prefix="/api/v1", tags=["administration"])
MANAGE = "configuration.manage"


def admin_module(request: Request) -> AdministrationModule:
    module = getattr(request.app.state, "administration_module", None)
    if not isinstance(module, AdministrationModule):
        raise Unavailable("Administration is not available.", code="admin.unavailable")
    return module


Module = Annotated[AdministrationModule, Depends(admin_module)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChangeIn(Strict):
    key: str = Field(min_length=3, max_length=128)
    value: Any = None
    scope: Literal["global", "module", "plugin"] = "global"
    scope_ref: str = Field(default="", max_length=64)
    unset: bool = False


class ChangesIn(Strict):
    changes: list[ChangeIn] = Field(min_length=1, max_length=200)
    reason: str = Field(default="", max_length=256)


class PolicyIn(Strict):
    key: str = Field(min_length=3, max_length=128)
    mode: Literal["default", "lock", "bound"]
    bounds: dict[str, Any] | None = None


class ToggleIn(Strict):
    enabled: bool
    reason: str = Field(default="", max_length=256)


class ImportIn(Strict):
    document: dict[str, Any]
    accept_conflicts: list[str] = Field(default_factory=list, max_length=500)


class WizardIn(Strict):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)
    display_name: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=320)
    settings: dict[str, Any] = Field(default_factory=dict)
    steps: dict[str, Any] = Field(default_factory=dict)


class ReopenIn(Strict):
    reason: str = Field(min_length=1, max_length=256)


def _changes(body: ChangesIn) -> list[Change]:
    return [Change(item.key, item.value, item.scope, item.scope_ref, item.unset) for item in body.changes]


def _kind(declaration: Any) -> dict[str, Any]:
    """027: how the System page edits a setting — its JSON type and, for a choice, the allowed values."""
    try:
        schema = declaration.adapter.json_schema()
    except Exception:
        return {"kind": "json"}
    options = schema.get("anyOf") or []
    if options and any(o.get("type") == "null" for o in options):
        schema = next((o for o in options if o.get("type") != "null"), schema)
    kind = schema.get("type", "json")
    out: dict[str, Any] = {"kind": kind if kind in ("boolean", "integer", "number", "string") else "json"}
    if isinstance(schema.get("enum"), list):
        out["choices"] = schema["enum"]
    return out


@router.get("/admin/config")
async def get_config(module: Module, principal: Principal = require(MANAGE)) -> dict[str, Any]:
    items = []
    for declaration in module.registry.all():
        effective = await module.config.get(declaration.key)
        items.append(
            {
                "key": declaration.key,
                "description": declaration.description,
                "scopes": sorted(allowed_scopes(declaration)),
                "user_overridable": is_user_overridable(declaration),
                "sensitive": declaration.sensitive,
                "default": None if declaration.sensitive else declaration.default,
                "value": module.config.redacted(declaration, effective.value),
                "source": effective.source,
                "owner": declaration.owner,
                "version": declaration.version,
                **_kind(declaration),
            }
        )
    policies = [
        {"id": str(p.id), "key": p.key, "mode": p.mode, "bounds": p.bounds}
        for p in await module.policies.active()
    ]
    return {"settings": items, "policies": policies}


@router.post("/admin/config/validate")
async def validate_config(
    body: ChangesIn, module: Module, principal: Principal = require(MANAGE)
) -> dict[str, Any]:
    preview = await module.config.validate(_changes(body))
    return {"ok": preview.ok, "diff": preview.diff, "warnings": preview.warnings, "errors": preview.errors}


@router.put("/admin/config")
async def apply_config(
    body: ChangesIn,
    module: Module,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None,
    principal: Principal = require(MANAGE),
) -> dict[str, Any]:
    applied = await module.config.apply(
        _changes(body), principal, change_id=idempotency_key, reason=body.reason
    )
    return {"applied": applied}


@router.post("/admin/policies", status_code=status.HTTP_201_CREATED)
async def apply_policy(
    body: PolicyIn, module: Module, principal: Principal = require(MANAGE)
) -> dict[str, Any]:
    policy = await module.policies.apply(principal, body.key, body.mode, body.bounds)
    return {"id": str(policy.id), "key": policy.key, "mode": policy.mode, "bounds": policy.bounds}


@router.delete("/admin/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_policy(policy_id: UUID, module: Module, principal: Principal = require(MANAGE)) -> Response:
    await module.policies.remove(principal, policy_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/preferences")
async def my_preferences(
    module: Module, principal: Principal = require("users.self.manage")
) -> dict[str, Any]:
    assert principal.user_id is not None
    return {"preferences": [_view(view) for view in await module.preferences.views(principal.user_id)]}


def _view(view: Any) -> dict[str, Any]:
    return {
        "key": view.key,
        "value": view.value,
        "source": view.source,
        "locked": view.locked,
        "user_value": view.user_value,
        "user_value_retained": view.user_value_retained,
        "description": view.description,
    }


@router.put("/me/preferences")
async def set_my_preferences(
    body: dict[str, Any], module: Module, principal: Principal = require("users.self.manage")
) -> dict[str, Any]:
    return {"preferences": [_view(view) for view in await module.preferences.set(principal, body)]}


@router.post("/admin/toggles/{kind}/{ref}")
async def toggle(
    kind: Literal["module", "plugin", "connector", "service", "automation"],
    ref: str,
    body: ToggleIn,
    request: Request,
    module: Module,
    principal: Principal = require(MANAGE),
) -> dict[str, Any]:
    authorizer: Authorizer = request.app.state.authorizer
    if not await authorizer.is_allowed(principal, PERMISSION_BY_KIND[kind]):
        raise Forbidden()
    row = await module.toggles.set(principal, kind, ref, body.enabled, body.reason)
    return {"kind": row.kind, "ref": row.ref, "enabled": row.enabled}


@router.post("/admin/config/export")
async def export_config(module: Module, principal: Principal = require(MANAGE)) -> dict[str, Any]:
    return await module.import_export.export(principal)


@router.post("/admin/config/import")
async def import_config(
    body: ImportIn, module: Module, principal: Principal = require(MANAGE)
) -> dict[str, Any]:
    report = await module.import_export.import_(
        principal, body.document, accept_conflicts=body.accept_conflicts
    )
    return {
        "applied": report.applied,
        "unchanged": report.unchanged,
        "conflicts": report.conflicts,
        "errors": report.errors,
    }


@router.get("/admin/first-run")
@public
async def first_run_status(module: Module) -> dict[str, Any]:
    return {"completed": await module.first_run.completed(), "steps": module.first_run.steps()}


@router.post(
    "/admin/first-run", status_code=status.HTTP_201_CREATED, responses={410: {"description": "completed"}}
)
@public
async def first_run(body: WizardIn, request: Request, module: Module) -> dict[str, Any]:
    """Public only while the portal has no Admin; when reopened later, it needs ``configuration.manage``."""
    if await module.first_run.completed():
        raise FirstRunClosed("The portal is already set up.")
    existing_admin = None
    if await module.first_run.admin_exists():  # reopened wizard: only for configuration managers
        principal = await current_principal(request)
        if not principal.is_authenticated:
            raise Unauthorized()
        authorizer: Authorizer = request.app.state.authorizer
        if not await authorizer.is_allowed(principal, MANAGE):
            raise Forbidden()
        existing_admin = principal.user_id
    result = await module.first_run.run(
        WizardRequest(body.login, body.password, body.display_name, body.email, body.settings, body.steps),
        existing_admin=existing_admin,
    )
    return {"admin_id": str(result.admin_id), "steps": dict(result.steps)}


@router.post("/admin/first-run/reopen", status_code=status.HTTP_204_NO_CONTENT)
async def reopen_first_run(
    body: ReopenIn, module: Module, principal: Principal = require(MANAGE)
) -> Response:
    await module.first_run.reopen(principal, body.reason)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/overview")
async def overview(module: Module, principal: Principal = require("users.self.manage")) -> dict[str, Any]:
    panels, actions = await module.control_center.overview(principal)
    return {
        "panels": [{"panel": p.panel, "state": p.state, "data": p.data} for p in panels],
        "required_actions": [
            {
                "id": a.id,
                "title_key": a.title_key,
                "impact": a.impact,
                "criticality": a.criticality,
                "since": a.since.isoformat(),
                "link": a.link,
                "actionable": a.actionable,
            }
            for a in actions
        ],
    }


@router.get("/admin/surfaces")
async def surfaces(
    request: Request, principal: Principal = require("users.self.manage")
) -> list[dict[str, str]]:
    authorizer: Authorizer = request.app.state.authorizer
    visible = []
    for surface in default_admin_surfaces.all():
        if await authorizer.is_allowed(principal, surface.permission):
            visible.append({"key": surface.key, "label_key": surface.label_key, "route": surface.route})
    return visible
