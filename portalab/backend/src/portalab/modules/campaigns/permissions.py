"""Campaign permissions (T002): ``campaigns.read`` (default user grant) and ``campaigns.manage`` (core
catalog; Admin, sensitive, audited)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:campaigns"
READ = "campaigns.read"
MANAGE = "campaigns.manage"


def declare_campaign_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(READ) is None:
        registry.declare(READ, "See campaigns and their schedules", default_roles=("user",), owner=OWNER)


declare_campaign_permissions()
