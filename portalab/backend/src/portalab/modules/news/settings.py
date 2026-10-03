"""News settings (T002)."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:news"


@dataclass(frozen=True, slots=True)
class NewsConfig:
    max_featured: int = 3
    default_audience: str = "all"


SETTINGS = {"max_featured": "news.maxFeatured", "default_audience": "news.defaultAudience"}
_DESCRIPTIONS = {
    "max_featured": "How many articles the featured surface shows at most.",
    "default_audience": "Audience of new articles ('all' readers by default).",
}


def declare_news_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    defaults = NewsConfig()
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


declare_news_settings()
