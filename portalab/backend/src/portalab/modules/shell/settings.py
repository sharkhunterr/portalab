"""Shell settings (T003): admin navigation layout (global) and user navigation preferences (user tier)."""

from typing import Any

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:shell"

SETTINGS: tuple[tuple[str, Any, Any, bool, str], ...] = (
    (
        "shell.navigation.layout",
        dict[str, Any],
        {},
        False,
        "Admin navigation layout: groups, order, pinned entries.",
    ),
    ("shell.navigation.allowUserOrdering", bool, True, False, "Let users reorder their navigation."),
    ("shell.shortcuts.defaults", dict[str, str], {}, False, "Portal default keyboard shortcut overrides."),
    ("shell.navigation.userOrder", list[str], [], True, "Your navigation order."),
    ("shell.shortcuts", dict[str, str], {}, True, "Your keyboard shortcuts."),
    ("shell.sidebarCollapsed", bool, False, True, "Collapse the navigation sidebar."),
    ("shell.navigation.expanded", list[str], [], True, "Navigation sections you keep expanded."),
    ("shell.welcome.dismissedAt", str | None, None, True, "When you dismissed the welcome card."),
)


def declare_shell_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    for key, schema, default, user, description in SETTINGS:
        if key not in known:
            declare(
                scope="global",
                key=key,
                schema=schema,
                default=default,
                user_overridable=user,
                owner=OWNER,
                description=description,
            )


declare_shell_settings()
