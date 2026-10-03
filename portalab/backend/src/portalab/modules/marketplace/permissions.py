"""Marketplace permissions (T002): ``marketplace.read`` and ``marketplace.purchase`` (granted to users;
funding a project also requires an active account), ``marketplace.grant|revoke|refund|audit`` and
``projects.manage`` (Admin; sensitive, audited). ``marketplace.manage`` is a core permission."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:marketplace"
READ = "marketplace.read"
PURCHASE = "marketplace.purchase"
MANAGE = "marketplace.manage"
GRANT = "marketplace.grant"
REVOKE = "marketplace.revoke"
REFUND = "marketplace.refund"
AUDIT = "marketplace.audit"
PROJECTS_MANAGE = "projects.manage"


def declare_marketplace_permissions(registry: PermissionRegistry = default_permissions) -> None:
    for key, description, sensitive, roles in (
        (READ, "Browse the Marketplace and community projects", False, ("user",)),
        (PURCHASE, "Acquire products and fund community projects with Coins", False, ("user",)),
        (GRANT, "Grant Marketplace products", True, ()),
        (REVOKE, "Revoke Marketplace products", True, ()),
        (REFUND, "Refund Marketplace purchases", True, ()),
        (AUDIT, "Read the Marketplace audit", True, ()),
        (PROJECTS_MANAGE, "Move community projects through their lifecycle", True, ()),
    ):
        if registry.get(key) is None:
            registry.declare(key, description, sensitive=sensitive, default_roles=roles, owner=OWNER)


declare_marketplace_permissions()
