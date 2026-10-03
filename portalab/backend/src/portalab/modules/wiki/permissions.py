"""Wiki permissions: ``wiki.read|edit|publish|delete`` are core-catalog permissions (003);
``wiki.history.read`` (history and comparison) is declared here, granted to editors by default."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:wiki"
WIKI_READ = "wiki.read"
WIKI_EDIT = "wiki.edit"
WIKI_PUBLISH = "wiki.publish"
WIKI_DELETE = "wiki.delete"
WIKI_HISTORY = "wiki.history.read"
SELF = "users.self.manage"


def declare_wiki_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(WIKI_HISTORY) is None:
        registry.declare(
            WIKI_HISTORY,
            "Read wiki page history and compare versions",
            default_roles=("editor", "support"),
            owner=OWNER,
        )


declare_wiki_permissions()
