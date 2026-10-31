"""News settings (T002)."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:news"
NEWSLETTER_ON = "news.newsletter.enabled"


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

    if NEWSLETTER_ON not in known:  # issue 246: the newsletters may be switched off (the arrival wizard)
        declare(
            scope="global",
            key=NEWSLETTER_ON,
            schema=bool,
            default=True,
            owner=OWNER,
            description="Newsletters on.",
        )
    if "news.newsletter.optOut" not in known:  # 027: the newsletter channels a member does not want
        declare(
            scope="global",
            key="news.newsletter.optOut",
            schema=list[str],
            default=[],
            user_overridable=True,
            owner=OWNER,
            description="Newsletter channels I do not want to receive by e-mail.",
        )

    # #299: the news sources — a source on the local network only when allowed; how long items are kept
    if "news.feeds.allowPrivateHosts" not in known:
        declare(
            scope="global",
            key="news.feeds.allowPrivateHosts",
            schema=bool,
            default=False,
            owner=OWNER,
            description="News sources may be on the local network (private addresses).",
        )
    if "news.feeds.retentionDays" not in known:
        declare(
            scope="global",
            key="news.feeds.retentionDays",
            schema=int,
            default=30,
            owner=OWNER,
            description="Days the news sources' items are kept (pinned ones stay).",
        )


declare_news_settings()
