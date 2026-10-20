"""Tool catalog (T009, T018): what the assistant may *offer* a principal.

A tool is offered only when it is not disabled by the Admin, allowed by the turn's policy (chat, read-only
facades…), not ``ai_forbidden`` and **authorized for the AI principal acting for the user**. Sensitivity is
validated against the permission registry: a permission that requires confirmation makes the tool
``sensitive``; permissions reserved to people (admin transfer, roles, security, AI configuration,
event-store mutation) make it ``ai_forbidden`` — whatever the tool declares."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, replace

from portalab.capabilities.ai import AITool, AIToolRegistry, Sensitivity, ToolSpec, default_ai_tools
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.permissions import PermissionRegistry, default_permissions
from portalab.modules.ai.observability import log
from portalab.modules.ai.principal import ai_principal

AI_FORBIDDEN_PERMISSIONS = frozenset(
    {"ai.manage", "users.admin.transfer", "users.roles.manage", "security.manage", "events.manage"}
)


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    name: str
    sensitivities: frozenset[str]
    allow: frozenset[str] | None = None  # explicit tool subset (facades)


CHAT = ToolPolicy("chat", frozenset({"read", "write", "sensitive"}))
READ_ONLY = ToolPolicy("read_only", frozenset({"read"}))
NO_TOOLS = ToolPolicy("none", frozenset())


def wire_name(name: str) -> str:
    """Providers accept ``[A-Za-z0-9_-]`` function names: ``wiki.search`` travels as ``wiki__search``."""
    return name.replace(".", "__")


def tool_spec(tool: AITool) -> ToolSpec:
    return ToolSpec(wire_name(tool.name), tool.description, tool.params_schema)


class ToolCatalog:
    def __init__(
        self,
        authorizer: Authorizer,
        *,
        registry: AIToolRegistry = default_ai_tools,
        permissions: PermissionRegistry = default_permissions,
        disabled: Callable[[], Iterable[str]] = tuple,
        external: Callable[[], Iterable[AITool]] = tuple,
        refresh: Callable[[], Awaitable[None]] | None = None,
        reserved: Callable[[], Iterable[str]] = tuple,
    ) -> None:
        self.reserved = reserved  # issue 173: tools offered only to the members who bought them
        self.refresh = refresh
        self.authorizer = authorizer
        self.registry = registry
        self.permissions = permissions
        self.disabled = disabled
        self.external = external

    def effective_sensitivity(self, tool: AITool) -> Sensitivity:
        if tool.sensitivity == "ai_forbidden" or tool.required_permission in AI_FORBIDDEN_PERMISSIONS:
            return "ai_forbidden"
        declaration = self.permissions.get(tool.required_permission)
        if declaration is not None and declaration.requires_confirmation and tool.sensitivity != "sensitive":
            return "sensitive"
        return tool.sensitivity

    def all(self) -> list[AITool]:
        tools = {t.name: t for t in self.registry.all()}
        for tool in self.external():
            tools.setdefault(tool.name, tool)
        return [replace(t, sensitivity=self.effective_sensitivity(t)) for _, t in sorted(tools.items())]

    async def _allowed(self, principal: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(principal, permission)
        except Exception:
            return False

    async def for_principal(
        self, principal: Principal, policy: ToolPolicy = CHAT, *, reserved: bool = False
    ) -> dict[str, AITool]:
        if self.refresh is not None and policy.sensitivities:
            try:
                await self.refresh()
            except Exception:
                log.warning("external ai tools not refreshed")  # optional: their tools are omitted
        disabled = set(self.disabled())
        if not reserved:
            disabled |= set(self.reserved())
        candidates = [
            t
            for t in self.all()
            if t.name not in disabled
            and t.sensitivity != "ai_forbidden"
            and t.sensitivity in policy.sensitivities
            and (policy.allow is None or t.name in policy.allow)
        ]
        acting = ai_principal(principal)
        allowed = await asyncio.gather(*(self._allowed(acting, t.required_permission) for t in candidates))
        return {t.name: t for t, ok in zip(candidates, allowed, strict=True) if ok}
