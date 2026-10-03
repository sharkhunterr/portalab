"""AI permissions: ``ai.use`` belongs to the core catalog (003, granted to users); ``ai.manage`` configures
the provider, limits and MCP allow-list — audited and **forbidden to the AI itself**."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:ai"
AI_USE = "ai.use"
AI_MANAGE = "ai.manage"


def declare_ai_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(AI_MANAGE) is None:
        registry.declare(
            AI_MANAGE, "Configure the AI assistant (provider, limits, MCP)", sensitive=True, owner=OWNER
        )


declare_ai_permissions()
