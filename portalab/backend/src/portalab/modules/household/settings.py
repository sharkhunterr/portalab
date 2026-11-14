"""Household settings — declared to the Administration configuration system (spec 032). The module itself is
switched on or off in the module manager."""

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:household"
MAX_KEY = "household.maxProfiles"


def declare_household_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    if MAX_KEY not in {declaration.key for declaration in catalog.all()}:
        declare(
            scope="global",
            key=MAX_KEY,
            schema=int,
            default=8,
            owner=OWNER,
            description="How many profiles one account may hold (1 to 20).",
        )


declare_household_settings()
