"""Automation permissions (T002): ``automation.read`` and ``automation.approve`` declared here,
``automation.manage`` by the core catalog — Admin only in v1; manage/approve sensitive and audited."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:automations"
READ = "automation.read"
MANAGE = "automation.manage"
APPROVE = "automation.approve"


def declare_automation_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(READ) is None:
        registry.declare(READ, "See automations and their executions", sensitive=True, owner=OWNER)
    if registry.get(APPROVE) is None:
        registry.declare(APPROVE, "Approve sensitive automation actions", sensitive=True, owner=OWNER)


declare_automation_permissions()
