"""Core permission catalog (spec 003 T009, "Illustrative Permission Catalog"; names per CD-033).

Domain specs refine these with finer keys when they are implemented. Reserved = Admin-only (never granted to
another role, group, plugin or user); sensitive = every allow and deny is audited; requires_confirmation =
AI/automation callers need an explicit confirmation token (spec 018/019 flows).
"""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "core"

# key, description, sensitive, reserved, requires_confirmation, default roles
CORE_PERMISSIONS: tuple[tuple[str, str, bool, bool, bool, tuple[str | tuple[str, str], ...]], ...] = (
    # users / identity (spec 002)
    ("users.read", "View users and profiles within visibility", False, False, False, ("user",)),
    (
        "users.self.manage",
        "Manage one's own profile, export and deletion",
        False,
        False,
        False,
        (("user", "self"),),
    ),
    ("users.manage", "Administer accounts (create, suspend, reactivate, delete)", True, False, False, ()),
    ("users.roles.manage", "Manage roles, groups, grants and assignments", True, True, False, ()),
    ("users.admin.transfer", "Transfer the single Admin role", True, True, True, ()),
    # content: read / create / modify / publish / delete are distinct (FR-016..018)
    ("news.read", "Read news", False, False, False, ("user",)),
    ("news.create", "Write news drafts", False, False, False, ("editor",)),
    ("news.modify", "Edit news", False, False, False, ("editor",)),
    ("news.publish", "Publish news", True, False, False, ("editor",)),
    ("news.delete", "Delete news", True, False, True, ()),
    ("wiki.read", "Read the wiki", False, False, False, ("user",)),
    ("wiki.edit", "Create and edit wiki pages", False, False, False, ("editor", "support")),
    ("wiki.publish", "Publish wiki pages", True, False, False, ("editor",)),
    ("wiki.delete", "Delete wiki pages", True, False, True, ()),
    # services / infrastructure
    ("services.read", "View connected services and their status", False, False, False, ("user",)),
    ("services.manage", "Configure services and run destructive service actions", True, False, True, ()),
    ("infrastructure.read", "View infrastructure metrics", False, False, False, ("support",)),
    # AI
    ("ai.use", "Use the AI assistant within one's own permissions", False, False, False, ("user",)),
    # marketplace / economy
    ("marketplace.manage", "Manage the Marketplace catalog, refunds and funding", True, False, False, ()),
    ("economy.manage", "Change economy rules", True, False, True, ()),
    # gamification
    ("gamification.manage", "Manage reward and progression rules", True, False, False, ()),
    ("rewards.grant", "Grant manual rewards", True, False, True, ()),
    ("campaigns.manage", "Manage campaigns and events", True, False, False, ()),
    # support
    ("tickets.create", "Open support tickets", False, False, False, ("user",)),
    ("tickets.manage", "Handle support tickets", False, False, False, ("support",)),
    ("incidents.manage", "Declare and manage incidents", True, False, False, ("support",)),
    ("feedback.read", "Read user feedback", False, False, False, ("support",)),
    # statistics
    ("statistics.read", "View statistics within privacy constraints", False, False, False, ("user",)),
    ("statistics.manage", "Manage statistics and unlockable statistics", True, False, False, ()),
    # events / automation
    ("events.manage", "Manage the event store (quarantine, replay)", True, False, True, ()),
    ("automation.manage", "Author and manage automations", True, False, False, ()),
    # security / audit / live stream
    ("security.manage", "Change security and visibility policies", True, True, False, ()),
    ("audit.read", "Read the audit log", True, False, False, ()),
    ("stream.subscribe", "Receive live updates", False, False, False, ("user",)),
)


def declare_core_permissions(registry: PermissionRegistry = default_permissions) -> None:
    for key, description, sensitive, reserved, confirm, roles in CORE_PERMISSIONS:
        registry.declare(
            key,
            description,
            sensitive=sensitive,
            reserved=reserved,
            requires_confirmation=confirm,
            default_roles=roles,
            owner=OWNER,
        )


declare_core_permissions()
