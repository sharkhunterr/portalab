"""Dashboard API (T011, T018, T024, T026, T028): ``/dashboard*``, ``/widgets/{key}/data`` and
``/admin/dashboard/*``. ``require()`` comes first so an unavailable module never answers before
authentication/authorization. Writes accept ``If-Match: <layout_version>`` (409 on conflict)."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound, Unavailable, ValidationFailed
from portalab.modules.dashboard.module import DashboardModule
from portalab.modules.dashboard.overlay.overlay import EffectiveInstance
from portalab.modules.dashboard.permissions import DASHBOARD_MANAGE, SELF
from portalab.modules.dashboard.service.service import ArrangedItem, LayoutItem
from portalab.modules.dashboard.tastes import Taste

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


def dashboard_module(request: Request) -> DashboardModule:
    module = getattr(request.app.state, "dashboard_module", None)
    if not isinstance(module, DashboardModule):
        raise Unavailable("The dashboard is not available.", code="dashboard.unavailable")
    return module


Module = Annotated[DashboardModule, Depends(dashboard_module)]
User = Annotated[Principal, require(SELF)]
Manager = Annotated[Principal, require(DASHBOARD_MANAGE)]
IfMatch = Annotated[str | None, Header(alias="If-Match", max_length=32)]


def version_of(if_match: str | None) -> int | None:
    if if_match is None:
        return None
    try:
        return int(if_match.strip().removeprefix("W/").strip('"'))
    except ValueError as exc:
        raise ValidationFailed(
            "If-Match must be a layout version.", code="dashboard.invalid_version"
        ) from exc


class WidgetMeta(BaseModel):
    title_key: str
    description_key: str | None
    icon: str | None
    component_id: str | None
    template: str | None
    refresh_mode: str
    refresh_interval_s: int | None
    min_w: int
    min_h: int
    max_w: int
    max_h: int
    multiple: bool
    config_schema: dict[str, Any]


class GridCellOut(BaseModel):
    x: int
    y: int
    w: int
    h: int


class DashboardInstanceOut(BaseModel):
    id: UUID | None
    widget_key: str
    status: Literal["active", "hidden"]
    position: int
    x: int
    y: int
    w: int
    h: int
    config: dict[str, Any]
    policy: str
    locked: bool
    mandatory: bool
    movable: bool = True  # 027: a pinned widget members may still move / resize
    resizable: bool = True
    removable: bool
    hideable: bool
    available: bool
    widget: WidgetMeta | None
    views: dict[str, GridCellOut] = Field(default_factory=dict)  # 027: tablet/phone places (per_device)


class DashboardOut(BaseModel):
    layout_version: int
    instances: list[DashboardInstanceOut]
    layout_mode: Literal["shared", "per_device"] = "shared"


class LayoutModeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["shared", "per_device"]


class CatalogEntryOut(BaseModel):
    key: str
    placed: bool
    widget: WidgetMeta
    locked: bool = False  # 027: sold in the Marketplace and not owned yet
    product: str | None = None


class AddWidgetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    widget_key: str = Field(min_length=3, max_length=96)
    config: dict[str, Any] = Field(default_factory=dict)
    w: int | None = Field(default=None, ge=1, le=12)
    h: int | None = Field(default=None, ge=1, le=12)
    x: int | None = Field(default=None, ge=0, le=11)  # 027: placed where dropped (else first free slot)
    y: int | None = Field(default=None, ge=0, le=500)


class PatchWidgetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["active", "hidden"] | None = None
    position: int | None = Field(default=None, ge=0, le=500)
    w: int | None = Field(default=None, ge=1, le=12)
    h: int | None = Field(default=None, ge=1, le=12)
    x: int | None = Field(default=None, ge=0, le=11)
    y: int | None = Field(default=None, ge=0, le=500)
    config: dict[str, Any] | None = None


class LayoutItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID | None = None
    widget_key: str = Field(min_length=3, max_length=96)
    w: int = Field(ge=1, le=12)
    h: int = Field(ge=1, le=12)


class LayoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[LayoutItemIn] = Field(max_length=100)


class ArrangementItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID | None = None
    widget_key: str = Field(min_length=3, max_length=96)
    x: int = Field(ge=0, le=11)
    y: int = Field(ge=0, le=500)
    w: int = Field(ge=1, le=12)
    h: int = Field(ge=1, le=12)


class ArrangementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ArrangementItemIn] = Field(max_length=100)


class VersionOut(BaseModel):
    layout_version: int
    id: UUID | None = None


class WidgetPayloadOut(BaseModel):
    state: Literal["available", "partial", "stale", "unavailable", "error", "unauthorized", "no-data"]
    as_of: str | None
    stale_after_s: int | None
    data: dict[str, Any] | None
    partial_reasons: list[str]
    config_invalid: bool


class ChangeItemOut(BaseModel):
    kind: str
    occurred_at: str
    ref: str
    title: str | None
    title_key: str | None
    title_args: dict[str, Any]
    priority: int
    detail: str | None = None


class SummaryOut(BaseModel):
    since: str
    items: list[ChangeItemOut]
    unavailable: list[str]


class SeenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    until: str | None = None


def _meta(module: DashboardModule, key: str) -> WidgetMeta | None:
    widget = module.registry.get(key)
    if widget is None:
        return None
    d = widget.definition
    return WidgetMeta(
        title_key=d.title_key,
        description_key=d.description_key,
        icon=d.icon,
        component_id=d.component_id,
        template=d.template,
        refresh_mode=d.refresh.mode,
        refresh_interval_s=d.refresh.interval_s,
        min_w=d.size.min.w,
        min_h=d.size.min.h,
        max_w=d.size.max.w,
        max_h=d.size.max.h,
        multiple=d.multiple,
        config_schema=dict(d.config_schema),
    )


def _instance(
    module: DashboardModule, instance: EffectiveInstance, views: dict[str, Any] | None = None
) -> DashboardInstanceOut:
    return DashboardInstanceOut(
        views={
            name: GridCellOut(**cell)
            for name, cell in (views or {}).items()
            if name in ("tablet", "phone") and isinstance(cell, dict)
        },
        id=instance.id,
        widget_key=instance.widget_key,
        status=instance.status,
        position=instance.position,
        x=instance.x,
        y=instance.y,
        w=instance.w,
        h=instance.h,
        config=dict(instance.config),
        policy=instance.policy,
        locked=instance.locked,
        mandatory=instance.mandatory,
        movable=instance.movable,
        resizable=instance.resizable,
        removable=instance.removable,
        hideable=instance.hideable,
        available=instance.available,
        widget=_meta(module, instance.widget_key),
    )


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(principal: User, module: Module, response: Response) -> DashboardOut:
    view = await module.service.view(principal)
    response.headers["ETag"] = f'"{view.layout_version}"'
    return DashboardOut(
        layout_version=view.layout_version,
        instances=[
            _instance(module, i, view.views.get(i.id) if i.id is not None else None) for i in view.instances
        ],
        layout_mode=view.layout_mode,
    )


@router.get("/dashboard/catalog", response_model=list[CatalogEntryOut])
async def catalog(principal: User, module: Module) -> list[CatalogEntryOut]:
    out = []
    for definition, placed in await module.service.catalog(principal):
        meta = _meta(module, definition.key)
        if meta is not None:
            out.append(CatalogEntryOut(key=definition.key, placed=placed, widget=meta))
    for definition in await module.service.in_shop(principal):
        meta = _meta(module, definition.key)
        if meta is not None:
            out.append(
                CatalogEntryOut(
                    key=definition.key, placed=False, widget=meta, locked=True, product=definition.product
                )
            )
    return out


@router.get("/dashboard/locked-options")
async def locked_options(principal: User, module: Module) -> dict[str, list[str]]:
    """027: widget settings sold in the shop that this member does not own (``<widget>:<field>=<value>``)."""
    return {"locked": sorted(await module.service.gateway.locked_options(principal))}


@router.post("/dashboard/widgets", response_model=VersionOut, status_code=status.HTTP_201_CREATED)
async def add_widget(
    principal: User, body: AddWidgetIn, module: Module, if_match: IfMatch = None
) -> VersionOut:
    instance_id, version = await module.service.add(
        principal,
        body.widget_key,
        config=body.config,
        w=body.w,
        h=body.h,
        x=body.x,
        y=body.y,
        if_match=version_of(if_match),
    )
    return VersionOut(layout_version=version, id=instance_id)


@router.patch("/dashboard/widgets/{instance_id}", response_model=VersionOut)
async def patch_widget(
    principal: User, instance_id: UUID, body: PatchWidgetIn, module: Module, if_match: IfMatch = None
) -> VersionOut:
    version = await module.service.update(
        principal,
        instance_id,
        status=body.status,
        position=body.position,
        w=body.w,
        h=body.h,
        x=body.x,
        y=body.y,
        config=body.config,
        if_match=version_of(if_match),
    )
    return VersionOut(layout_version=version, id=instance_id)


@router.delete("/dashboard/widgets/{instance_id}", response_model=VersionOut)
async def delete_widget(
    principal: User, instance_id: UUID, module: Module, if_match: IfMatch = None
) -> VersionOut:
    return VersionOut(
        layout_version=await module.service.remove(principal, instance_id, if_match=version_of(if_match))
    )


@router.put("/dashboard/arrangement", response_model=VersionOut)
async def put_arrangement(
    principal: User,
    body: ArrangementIn,
    module: Module,
    if_match: IfMatch = None,
    view: Literal["desktop", "tablet", "phone"] = "desktop",
) -> VersionOut:
    """027 R13: an arrangement in one write (Save) — the desktop one (tablet/phone derive from it), or with
    ``view`` the tablet or phone one of a member who arranges each screen on its own."""
    items = [ArrangedItem(i.id, i.widget_key, i.x, i.y, i.w, i.h) for i in body.items]
    return VersionOut(
        layout_version=await module.service.arrangement(
            principal, items, if_match=version_of(if_match), view=view
        )
    )


@router.put("/dashboard/layout-mode", response_model=VersionOut)
async def put_layout_mode(
    principal: User, body: LayoutModeIn, module: Module, if_match: IfMatch = None
) -> VersionOut:
    """027: one arrangement for every screen, or one per screen (desktop, tablet, phone)."""
    return VersionOut(
        layout_version=await module.service.layout_mode(principal, body.mode, if_match=version_of(if_match))
    )


@router.put("/dashboard/layout", response_model=VersionOut, deprecated=True)
async def put_layout(principal: User, body: LayoutIn, module: Module, if_match: IfMatch = None) -> VersionOut:
    items = [LayoutItem(i.id, i.widget_key, i.w, i.h) for i in body.items]
    return VersionOut(
        layout_version=await module.service.layout(principal, items, if_match=version_of(if_match))
    )


class ResetIn(BaseModel):
    """#347: a dashboard made to the member's tastes (said at the welcome); none: the default one."""

    model_config = ConfigDict(extra="forbid")
    tastes: list[Taste] | None = Field(default=None, max_length=16)


@router.post("/dashboard/reset", response_model=VersionOut)
async def reset(
    principal: User,
    module: Module,
    if_match: IfMatch = None,
    body: ResetIn | None = None,
) -> VersionOut:
    """027: back to the default dashboard (the starter layout and the pinned widgets); #347: to taste."""
    tastes = frozenset(body.tastes) if body and body.tastes is not None else None
    return VersionOut(
        layout_version=await module.service.reset(principal, if_match=version_of(if_match), tastes=tastes)
    )


@router.post("/dashboard/starter")
async def apply_starter(principal: User, module: Module) -> dict[str, bool]:
    return {"applied": await module.service.apply_starter(principal)}


@router.get("/widgets/{key}/data", response_model=WidgetPayloadOut)
async def widget_data(
    principal: User,
    key: Annotated[str, Path(max_length=96)],
    module: Module,
    instance: Annotated[UUID | None, Query()] = None,
    preview: Annotated[bool, Query()] = False,
) -> WidgetPayloadOut:
    """027: ``preview`` — a widget's miniature in the catalog or the shop, before it is bought (the
    permission still applies; nothing is stored)."""
    stored = None
    if instance is not None:
        instance_key, stored = await module.service.stored_config(principal, instance)
        if instance_key != key:
            raise NotFound("This widget is not on your dashboard.", code="dashboard.instance_not_found")
    else:
        stored = module.service.imposed_config(key)  # issue 250: pinned with its settings, no row yet
    payload = await module.gateway.load(
        key, principal, await _locale(module, principal), stored, preview=preview and instance is None
    )
    if payload is None:
        raise NotFound("This widget does not exist.", code="dashboard.widget_not_found")
    return WidgetPayloadOut(
        state=payload.state,
        as_of=payload.as_of.isoformat() if payload.as_of else None,
        stale_after_s=payload.stale_after_s,
        data=dict(payload.data) if payload.data is not None and payload.state != "unauthorized" else None,
        partial_reasons=list(payload.partial_reasons),
        config_invalid=payload.config_invalid,
    )


async def _locale(module: DashboardModule, principal: Principal) -> Any:
    from portalab.capabilities.i18n import RESOLVER, LocaleContext

    try:
        providers = module.capabilities.system_providers(RESOLVER)
        if providers:
            return await providers[0].provider.for_user(principal.user_id)
    except Exception:
        return LocaleContext()
    return LocaleContext()


@router.get("/dashboard/since-last-login", response_model=SummaryOut)
async def since_last_login(principal: User, module: Module) -> SummaryOut:
    summary = await module.summary.summary(principal, await _locale(module, principal))
    return SummaryOut(
        since=summary.since.isoformat(),
        items=[
            ChangeItemOut(
                kind=i.kind,
                occurred_at=i.occurred_at.isoformat(),
                ref=i.ref,
                title=i.title,
                title_key=i.title_key,
                title_args=dict(i.title_args),
                priority=i.priority,
                detail=i.detail,
            )
            for i in summary.items
        ],
        unavailable=summary.unavailable,
    )


@router.post("/dashboard/since-last-login/seen")
async def summary_seen(principal: User, body: SeenIn, module: Module) -> dict[str, str]:
    from datetime import datetime

    until = None
    if body.until:
        try:
            until = datetime.fromisoformat(body.until)
        except ValueError as exc:
            raise ValidationFailed("Invalid date.", code="dashboard.invalid_date") from exc
        if until.tzinfo is None:
            raise ValidationFailed("The date needs a time zone.", code="dashboard.invalid_date")
    return {"since": (await module.summary.seen(principal, until)).isoformat()}


@router.get("/admin/dashboard/policies")
async def get_policies(_: Manager, module: Module) -> dict[str, Any]:
    return await module.admin_settings()


@router.put("/admin/dashboard/policies")
async def put_policies(principal: Manager, body: dict[str, dict[str, Any]], module: Module) -> dict[str, Any]:
    await module.set_policies(principal, body)
    return await module.admin_settings()


@router.get("/admin/dashboard/starter")
async def get_starter(_: Manager, module: Module) -> dict[str, Any]:
    return {"starter": (await module.admin_settings())["starter"]}


@router.put("/admin/dashboard/starter")
async def put_starter(principal: Manager, body: list[dict[str, Any]], module: Module) -> dict[str, Any]:
    await module.set_starter(principal, body)
    return {"starter": module.config.starter_layout}


class PlaceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: int = Field(ge=0, le=11)
    y: int = Field(ge=0, le=500)
    w: int = Field(ge=1, le=12)
    h: int = Field(ge=1, le=12)


class CompositionItemIn(BaseModel):
    """Issue 250: one widget of the default dashboard — its place on a computer (12 columns), its settings,
    how far it is locked, and (optionally) its own place on a tablet and a phone."""

    model_config = ConfigDict(extra="forbid")
    widget_key: str = Field(max_length=96)
    x: int = Field(ge=0, le=11)
    y: int = Field(ge=0, le=500)
    w: int = Field(ge=1, le=12)
    h: int = Field(ge=1, le=12)
    config: dict[str, Any] = Field(default_factory=dict)
    lock: Literal["free", "always", "locked"] = "free"
    move: bool = False
    resize: bool = False
    tablet: PlaceIn | None = None
    phone: PlaceIn | None = None
    roles: list[str] | None = None
    # #347: the play profiles a free widget is shown to (none: every member)
    profiles: list[Literal["none", "progression", "collector", "full"]] | None = Field(
        default=None, max_length=4
    )


class CompositionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CompositionItemIn] = Field(max_length=200)
    disabled: list[str] = Field(default_factory=list, max_length=500)


@router.get("/admin/dashboard/composition")
async def get_composition(_: Manager, module: Module) -> dict[str, Any]:
    """Issue 250: the default dashboard as the administrator composes it."""
    return await module.composition()


@router.put("/admin/dashboard/composition")
async def put_composition(principal: Manager, body: CompositionIn, module: Module) -> dict[str, Any]:
    keys = [item.widget_key for item in body.items]
    if len(set(keys)) != len(keys):
        raise ValidationFailed("A widget is placed once.", code="dashboard.invalid_policy")
    await module.set_composition(
        principal, [item.model_dump(exclude_none=True) for item in body.items], list(body.disabled)
    )
    return await module.composition()
