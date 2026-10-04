"""UI API (T015, T037): the user's theme catalog (policy-filtered) and the admin theme registry."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.ui.module import UiModule
from portalab.modules.ui.permissions import APPEARANCE_MANAGE
from portalab.modules.ui.themes.service import theme_out

router = APIRouter(prefix="/api/v1", tags=["ui"])


def ui_module(request: Request) -> UiModule:
    module = getattr(request.app.state, "ui_module", None)
    if not isinstance(module, UiModule):
        raise Unavailable("Themes are not available.", code="ui.unavailable")
    return module


Module = Annotated[UiModule, Depends(ui_module)]
Manager = Annotated[Principal, require(APPEARANCE_MANAGE)]


class ThemeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: dict[str, Any]


class ThemePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: dict[str, Any] | None = None
    enabled: bool | None = None


@router.get("/ui/themes")
async def themes(
    principal: Annotated[Principal, require("users.self.manage")], module: Module
) -> dict[str, Any]:
    return await module.themes.catalog(principal.user_id)


@router.get("/admin/ui/themes")
async def all_themes(_: Manager, module: Module) -> dict[str, Any]:
    return {"items": [theme_out(row, admin=True) for row in await module.themes.all()]}


@router.post("/admin/ui/themes", status_code=status.HTTP_201_CREATED)
async def register_theme(principal: Manager, body: ThemeIn, module: Module) -> dict[str, Any]:
    return await module.themes.register(principal, body.definition)


@router.patch("/admin/ui/themes/{key}")
async def update_theme(principal: Manager, key: str, body: ThemePatch, module: Module) -> dict[str, Any]:
    return await module.themes.update(principal, key, definition=body.definition, enabled=body.enabled)


@router.get("/admin/ui/themes/{key}/floor-report")
async def floor(_: Manager, key: str, module: Module) -> dict[str, Any]:
    row = await module.themes.get(key)
    return {"key": row.key, "report": row.floor_report}


@router.post("/admin/ui/themes/check")
async def check_theme(_: Manager, body: ThemeIn, module: Module) -> dict[str, Any]:
    """Dry run: validate and compute the floor report without registering."""
    from portalab.modules.ui.themes.definition import floor_report, validate_definition

    theme, errors = validate_definition(body.definition)
    return {"errors": errors, "report": floor_report(theme) if theme else None}
