"""UI API (T015, T037): the user's theme catalog (policy-filtered) and the admin theme registry."""

from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import public, require
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound, Unavailable
from portalab.modules.ui.module import UiModule
from portalab.modules.ui.permissions import APPEARANCE_MANAGE, SITE_MANAGE
from portalab.modules.ui.site import MAX_IMAGE_BYTES, InvalidSiteIdentity
from portalab.modules.ui.themes.service import theme_out
from portalab.modules.ui.weather import KEEP_SECONDS

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


@router.get("/ui/notification-looks")
async def notification_looks(
    principal: Annotated[Principal, require("users.self.manage")], module: Module
) -> dict[str, Any]:
    """027: the notification styles and animations, those sold in the shop marked locked unless owned."""
    return await module.looks.catalog(principal.user_id)


@router.get("/ui/plugin-looks")
async def plugin_looks(
    principal: Annotated[Principal, require("users.self.manage")], module: Module
) -> list[dict[str, Any]]:
    """030: the kinds of visuals plugins add, each with the member's looks and those the shop sells."""
    return await module.looks.plugin_catalog(principal.user_id)


class PlaceOut(BaseModel):
    name: str | None = None
    latitude: float
    longitude: float
    own: bool = False  # the member's own place (else the portal's default)


class FoundOut(BaseModel):
    name: str
    label: str  # what is saved and shown
    latitude: float
    longitude: float
    region: str | None = None
    country: str | None = None
    country_code: str | None = None
    population: int | None = None


class WeatherOut(BaseModel):
    condition: str | None
    intensity: str | None = None
    code: int | None = None
    is_day: bool = True
    phase: str | None = None  # dawn, day, dusk, night — at the place
    temperature: float | None = None
    feels_like: float | None = None
    humidity: float | None = None
    cloud_cover: float | None = None
    precipitation: float | None = None
    wind_speed: float | None = None
    wind_gusts: float | None = None
    wind_direction: float | None = None
    windy: bool = False
    visibility: float | None = None
    local_time: str | None = None
    sunrise: str | None = None
    sunset: str | None = None
    timezone: str | None = None
    fetched_at: str | None = None  # when the server last asked the forecast
    refresh_minutes: int = KEEP_SECONDS // 60  # how often it asks again
    place: PlaceOut | None = None


@router.get("/ui/weather", response_model=WeatherOut)
async def weather(
    principal: Annotated[Principal, require("users.self.manage")], module: Module
) -> WeatherOut:
    """#68, #70, #88: the sky over the member's place (or everyone's default), for the « live weather »
    ambience — none until a place is set."""
    now = await module.weather.now(principal.user_id)
    if now is None:
        return WeatherOut(condition=None)
    place, sky = now
    where = PlaceOut(name=place.name, latitude=place.latitude, longitude=place.longitude, own=place.own)
    if sky is None:
        return WeatherOut(condition=None, place=where)
    return WeatherOut(**asdict(sky), place=where)


@router.get("/ui/weather/places", response_model=list[FoundOut])
async def weather_places(
    _: Annotated[Principal, require("users.self.manage")],
    module: Module,
    q: Annotated[str, Query(min_length=2, max_length=80)],
    language: Annotated[str, Query(pattern="^[a-z]{2}$")] = "en",
) -> list[FoundOut]:
    """#70: places matching a name, for a member to choose where their weather comes from."""
    return [FoundOut(**asdict(p)) for p in await module.weather.places(q, language)]


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


# --- issue 159: the site's identity ---------------------------------------------------------------------
SiteManager = Annotated[Principal, require(SITE_MANAGE)]
IMAGE_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            t: {"schema": {"type": "string", "format": "binary"}}
            for t in ("image/png", "image/jpeg", "image/webp", "image/gif")
        },
    }
}


class SiteCurrency(BaseModel):
    model_config = ConfigDict(extra="forbid")
    one: str | None = Field(default=None, max_length=60)
    other: str | None = Field(default=None, max_length=60)


class SiteOut(BaseModel):
    name: str
    short_name: str
    custom: bool
    tagline: dict[str, str]
    currency: dict[str, SiteCurrency]
    currency_short: str | None
    currency_icon: str | None
    logo: str | None
    icon: str | None
    version: int


class SiteAdminOut(BaseModel):
    name: str | None
    short_name: str | None
    default_name: str
    custom: bool
    tagline: dict[str, str]
    currency: dict[str, SiteCurrency]
    currency_short: str | None
    currency_icon: str | None
    logo: str | None
    icon: str | None
    version: int


class SiteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=80)
    short_name: str | None = Field(default=None, max_length=40)
    tagline: dict[str, str] = Field(default_factory=dict)
    currency: dict[str, SiteCurrency] = Field(default_factory=dict)
    currency_short: str | None = Field(default=None, max_length=40)
    currency_icon: str | None = Field(default=None, max_length=40)


@router.get("/auth/site", response_model=SiteOut)
@public
async def site(module: Module) -> dict[str, Any]:
    """The site's name, slogan, images and currency — the sign-in page shows them, so they are public."""
    return await module.site.public()


async def _site_image(module: UiModule, which: str) -> Response:
    found = await module.site.image(which)
    if found is None:
        raise NotFound("No image.", code="ui.site_image_missing")
    data, kind = found
    return Response(
        data,
        media_type=kind,
        headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/auth/site/logo", response_class=Response)
@public
async def site_logo(module: Module) -> Response:
    return await _site_image(module, "logo")


@router.get("/auth/site/icon", response_class=Response)
@public
async def site_icon(module: Module) -> Response:
    return await _site_image(module, "icon")


@router.get("/auth/site/manifest", response_class=JSONResponse)
@public
async def site_manifest(module: Module) -> JSONResponse:
    """The home-screen manifest: the site's name and icon (installed on a phone, it is the site's)."""
    identity = await module.site.public()
    icons = (
        [{"src": identity["icon"], "sizes": "512x512", "type": "image/png", "purpose": "any"}]
        if identity["icon"]
        else [  # Portalab's own (frontend/public, rendered from assets/icon.svg)
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ]
    )
    return JSONResponse(
        {
            "name": identity["name"],
            "short_name": identity["short_name"],
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "icons": icons,
        },
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/admin/site", response_model=SiteAdminOut)
async def site_admin(_: SiteManager, module: Module) -> dict[str, Any]:
    return await module.site.admin()


@router.put("/admin/site", response_model=SiteAdminOut)
async def site_update(principal: SiteManager, body: SiteIn, module: Module) -> dict[str, Any]:
    return await module.site.update(principal, body.model_dump())


@router.delete("/admin/site", response_model=SiteAdminOut)
async def site_reset(principal: SiteManager, module: Module) -> dict[str, Any]:
    """Portalab's own name, slogan, images and currency back."""
    return await module.site.reset(principal)


async def _body(request: Request) -> bytes:
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_IMAGE_BYTES:
            raise InvalidSiteIdentity("The image is larger than 2 MiB.", extensions={"reason": "too_large"})
    return bytes(data)


@router.put("/admin/site/{which}", response_model=SiteAdminOut, openapi_extra=IMAGE_BODY)
async def site_image_set(
    principal: SiteManager, which: Literal["logo", "icon"], request: Request, module: Module
) -> dict[str, Any]:
    return await module.site.set_image(principal, which, await _body(request))


@router.delete("/admin/site/{which}", response_model=SiteAdminOut)
async def site_image_remove(
    principal: SiteManager, which: Literal["logo", "icon"], module: Module
) -> dict[str, Any]:
    return await module.site.remove_image(principal, which)
