"""Permission declarations — how core, modules and plugins *declare* permissions (spec 003 R3, FR-021..023).

Declaration only, in code, at import time: the authorization module (spec 003) upserts the catalog into
``authz.permissions`` and evaluates grants. Keys follow ``domain.action[.scope]`` (``users.self.manage``) or,
for plugins, ``plugin:<key>.<action>``. Plugins can never declare reserved (Admin-only) permissions, and
reserved permissions never get default role grants. Registrations are owner-tagged so a disabled plugin's
contributions disappear with ``unregister(owner)`` (spec 023 conformance sweep, F20).
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

BASE_ROLES: tuple[str, ...] = ("user", "support", "moderator", "editor", "admin")
DEFAULT_GRANTABLE_ROLES: tuple[str, ...] = ("user", "support", "moderator", "editor")
SCOPE_KINDS: tuple[str, ...] = ("global", "self", "owned", "module", "service", "plugin")

_KEY = re.compile(r"^(plugin:[a-z][a-z0-9_-]*|[a-z][a-z0-9_]*)(\.[a-z][a-z0-9_]*)+$")


class PermissionDeclarationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DefaultGrant:
    role: str
    scope_kind: str = "global"


@dataclass(frozen=True, slots=True)
class PermissionDeclaration:
    key: str
    description: str
    sensitive: bool = False
    reserved: bool = False
    requires_confirmation: bool = False
    user_grantable: bool = False
    default_grants: tuple[DefaultGrant, ...] = field(default_factory=tuple)
    owner: str = "core"

    @property
    def declared_by(self) -> str:
        return self.owner


class PermissionRegistry:
    def __init__(self) -> None:
        self._declarations: dict[str, PermissionDeclaration] = {}

    def declare(
        self,
        key: str,
        description: str,
        *,
        sensitive: bool = False,
        reserved: bool = False,
        requires_confirmation: bool = False,
        user_grantable: bool = False,
        default_roles: Iterable[str | tuple[str, str]] = (),
        owner: str = "core",
    ) -> PermissionDeclaration:
        if not _KEY.fullmatch(key):
            raise PermissionDeclarationError(f"permission key {key!r} must look like 'domain.action[.scope]'")
        if not description.strip():
            raise PermissionDeclarationError(f"permission {key!r} needs a description")
        is_plugin = owner.startswith("plugin:")
        if is_plugin and reserved:
            raise PermissionDeclarationError("plugins cannot declare reserved (Admin-only) permissions")
        if is_plugin and not key.startswith(f"plugin:{owner.removeprefix('plugin:')}."):
            raise PermissionDeclarationError(f"plugin permissions are namespaced 'plugin:<key>.*' ({key!r})")
        if reserved and user_grantable:
            raise PermissionDeclarationError("a reserved permission cannot be granted to individual users")
        grants: list[DefaultGrant] = []
        for item in default_roles:
            role, scope = (item, "global") if isinstance(item, str) else item
            if role not in DEFAULT_GRANTABLE_ROLES:
                raise PermissionDeclarationError(f"default role {role!r} is not a grantable base role")
            if scope not in SCOPE_KINDS:
                raise PermissionDeclarationError(f"unknown scope kind {scope!r}")
            grants.append(DefaultGrant(role, scope))
        if reserved and grants:
            raise PermissionDeclarationError(
                "reserved permissions belong to the Admin only (no default roles)"
            )
        declaration = PermissionDeclaration(
            key=key,
            description=description.strip(),
            sensitive=sensitive,
            reserved=reserved,
            requires_confirmation=requires_confirmation,
            user_grantable=user_grantable,
            default_grants=tuple(grants),
            owner=owner,
        )
        existing = self._declarations.get(key)
        if existing is not None and existing != declaration:
            raise PermissionDeclarationError(f"permission {key!r} is already declared differently")
        self._declarations[key] = declaration
        return declaration

    def get(self, key: str) -> PermissionDeclaration | None:
        return self._declarations.get(key)

    def all(self) -> list[PermissionDeclaration]:
        return [self._declarations[key] for key in sorted(self._declarations)]

    def keys(self) -> set[str]:
        return set(self._declarations)

    def unregister(self, owner: str) -> int:
        doomed = [key for key, decl in self._declarations.items() if decl.owner == owner]
        for key in doomed:
            del self._declarations[key]
        return len(doomed)


default_permissions = PermissionRegistry()

declare_permission: Callable[..., PermissionDeclaration] = default_permissions.declare
"""Shortcut: ``declare_permission("tickets.create", "Open a ticket", default_roles=["user"])``."""
