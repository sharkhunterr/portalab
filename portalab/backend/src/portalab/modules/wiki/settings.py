"""Wiki settings (T002)."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:wiki"


@dataclass(frozen=True, slots=True)
class WikiConfig:
    max_page_bytes: int = 200_000
    history_visibility: str = "editors"  # editors | readers (readers: every wiki reader sees history)


SETTINGS = {"max_page_bytes": "wiki.maxPageBytes", "history_visibility": "wiki.history.visibility"}
_DESCRIPTIONS = {
    "max_page_bytes": "Largest wiki page source accepted (bytes).",
    "history_visibility": "Who sees page history: 'editors' (wiki.history.read) or 'readers'.",
}


def declare_wiki_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    defaults = WikiConfig()
    for name, key in SETTINGS.items():
        if key not in known:
            default = getattr(defaults, name)
            declare(
                scope="global",
                key=key,
                schema=type(default),
                default=default,
                owner=OWNER,
                description=_DESCRIPTIONS[name],
            )


declare_wiki_settings()
