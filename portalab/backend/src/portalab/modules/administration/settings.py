"""Administration's own settings (T003)."""

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:administration"


def declare_admin_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    for key, schema, default, description in (
        ("admin.firstRunLocked", bool, True, "The first-run wizard is closed once completed."),
        ("admin.configHistoryRetentionDays", int, 365, "Days configuration history is kept."),
        ("admin.overviewPanelTimeoutMs", int, 1500, "Time budget of each Control Center panel."),
    ):
        if key not in known:
            declare(
                scope="global", key=key, schema=schema, default=default, owner=OWNER, description=description
            )


declare_admin_settings()
