"""Administration's own settings (T003)."""

from typing import Any

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:administration"


def declare_admin_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    for key, schema, default, description in (
        ("admin.firstRunLocked", bool, True, "The first-run wizard is closed once completed."),
        ("admin.configHistoryRetentionDays", int, 365, "Days configuration history is kept."),
        ("admin.overviewPanelTimeoutMs", int, 1500, "Time budget of each Control Center panel."),
        # issue 6: the setup assistant — the step it is at, the steps done or skipped, when it was finished
        ("admin.setup.progress", dict[str, Any], {}, "Setup assistant: {step, done, skipped, finished_at}."),
        # issue 410: GitHub's public releases API asked, twice a day at most, whether a newer Portalab is out
        ("admin.updateCheck", bool, True, "Check on GitHub whether a newer Portalab is released."),
    ):
        if key not in known:
            declare(
                scope="global", key=key, schema=schema, default=default, owner=OWNER, description=description
            )


declare_admin_settings()
