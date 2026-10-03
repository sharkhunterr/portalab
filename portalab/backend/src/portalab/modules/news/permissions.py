"""News permissions: ``news.read|create|modify|publish|delete`` come from the core catalog (003);
``news.archive`` (editors) and ``news.manage_categories`` (administrators) are declared here."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:news"
NEWS_READ = "news.read"
NEWS_CREATE = "news.create"
NEWS_MODIFY = "news.modify"
NEWS_PUBLISH = "news.publish"
NEWS_ARCHIVE = "news.archive"
NEWS_DELETE = "news.delete"
NEWS_CATEGORIES = "news.manage_categories"
SELF = "users.self.manage"


def declare_news_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(NEWS_ARCHIVE) is None:
        registry.declare(
            NEWS_ARCHIVE, "Archive and restore news", sensitive=True, default_roles=("editor",), owner=OWNER
        )
    if registry.get(NEWS_CATEGORIES) is None:
        registry.declare(NEWS_CATEGORIES, "Manage news categories", owner=OWNER)


declare_news_permissions()
