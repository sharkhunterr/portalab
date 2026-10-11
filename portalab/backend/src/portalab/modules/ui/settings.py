"""UI settings (T003, T019): admin policy (global) and the user's ``ui.*`` preferences (user tier, CD-011).

User values are validated by their schema (ranges, enums); the theme choice is also checked against the
enabled and allowed themes by a dynamic validator registered at wiring. When a policy narrows, Administration
keeps the stored user value and reports the effective one (``user_value_retained``)."""

from typing import Annotated, Any, Literal, cast

from pydantic import Field

from portalab.capabilities.themes import (
    AMBIENTS,
    CELEBRATIONS,
    LEVEL_UPS,
    NOTIFICATION_ANIMATIONS,
    NOTIFICATION_STYLES,
    PALETTES,
    UNIVERSE_THEMES,
)
from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:ui"


def _one_of(values: tuple[str, ...]) -> Any:
    """``Literal[...]`` of a tuple of values (the cosmetics keys are shared constants)."""
    return cast(Any, Literal)[values]


BUILTIN_KEYS = (
    "portalab-dark",
    "portalab-light",
    "orbit",
    "studio",
    "light",
    "dark",
    "high-contrast",
    *UNIVERSE_THEMES,  # 027: universe themes (built in, most sold in the shop)
)
DEFAULT_THEME = "portalab"  # a theme family (spec 027 R8): resolved to its member for the color mode

GLOBAL_SETTINGS: tuple[tuple[str, Any, Any, str], ...] = (
    ("ui.allowedThemes", list[str], list(BUILTIN_KEYS), "Themes users may choose."),
    ("ui.defaultTheme", str, DEFAULT_THEME, "Theme (or theme family) used when the user has not chosen one."),
    ("ui.textScale.min", Annotated[float, Field(ge=0.5, le=1.0)], 0.85, "Smallest text scale allowed."),
    ("ui.textScale.max", Annotated[float, Field(ge=1.0, le=3.0)], 2.0, "Largest text scale allowed."),
    ("ui.forceReducedMotion", bool, False, "Force reduced motion for everyone."),
)

USER_SETTINGS: tuple[tuple[str, Any, Any, str], ...] = (
    ("ui.theme", str | None, None, "Preferred theme (empty: the portal default)."),
    ("ui.density", Literal["compact", "comfortable", "spacious"], "comfortable", "Spacing density."),
    ("ui.textScale", Annotated[float, Field(ge=0.85, le=2.0)], 1.0, "Text size multiplier."),
    ("ui.contrast", Literal["default", "high"], "default", "High contrast overrides the theme."),
    ("ui.reducedMotion", Literal["system", "on", "off"], "system", "Reduce animations."),
    ("ui.soundEnabled", bool, True, "Play notification sounds."),
    (
        "ui.notificationPosition",
        Literal["top-end", "top-start", "bottom-end", "bottom-start"],
        "top-end",
        "Where notifications appear.",
    ),
    ("ui.notificationDurationSeconds", Annotated[int, Field(ge=2, le=60)], 6, "How long notifications stay."),
    (
        "ui.notificationStyle",
        _one_of(("theme", *NOTIFICATION_STYLES)),
        "theme",
        "Notification style (shape and layout; theme: the theme's); some are sold in the shop (027).",
    ),
    (
        "ui.palette",
        _one_of(PALETTES),
        "theme",
        "Colour palette over the theme (027); some palettes are sold in the shop.",
    ),
    (
        "ui.notificationAnimation",
        _one_of(("theme", *NOTIFICATION_ANIMATIONS)),
        "theme",
        "How notifications enter (theme: the theme's); some animations are sold in the shop (027).",
    ),
    (
        "ui.ambient",
        _one_of(("theme", *AMBIENTS)),
        "theme",
        "Animated layer behind the portal (theme: the theme's); some are sold in the shop (027).",
    ),
    (
        "ui.levelUp",
        _one_of(("theme", *LEVEL_UPS)),
        "theme",
        "How a level-up is shown (027; theme: the theme's own); some are sold in the shop.",
    ),
    (
        "ui.celebration",
        _one_of(("theme", *CELEBRATIONS)),
        "theme",
        "Celebration effect for rewards (theme: the theme's); some are sold in the shop (027).",
    ),
    ("ui.layoutPresets", dict[str, Any], {}, "Saved layout presets (dashboard layouts are owned by 009)."),
    ("ui.campaignThemes", Literal["allow", "ignore"], "allow", "Apply campaign theme overlays."),
    ("ui.colorMode", Literal["dark", "light", "system"], "dark", "Light or dark variant of a theme family."),
    # #68, #70: where the « live weather » ambience looks at the sky — each member's own place, the value
    # the administrators set as everyone's default (empty: no weather asked)
    (
        "ui.weather.latitude",
        Annotated[float, Field(ge=-90, le=90)] | None,
        None,
        "Latitude of the place whose weather the « live weather » ambience shows (Open-Meteo).",
    ),
    (
        "ui.weather.longitude",
        Annotated[float, Field(ge=-180, le=180)] | None,
        None,
        "Longitude of the place whose weather the « live weather » ambience shows (Open-Meteo).",
    ),
    ("ui.weather.place", Annotated[str, Field(max_length=120)] | None, None, "Name of that place, as shown."),
)


def declare_ui_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    for key, schema, default, description in GLOBAL_SETTINGS:
        if key not in known:
            declare(
                scope="global", key=key, schema=schema, default=default, owner=OWNER, description=description
            )
    for key, schema, default, description in USER_SETTINGS:
        if key not in known:
            declare(
                scope="global",
                key=key,
                schema=schema,
                default=default,
                user_overridable=True,
                owner=OWNER,
                description=description,
            )


declare_ui_settings()
