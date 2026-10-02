"""Request/response bodies of the authorization API (contracts/authz-contracts.md)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ScopeKind = Literal["global", "self", "owned", "module", "service", "plugin"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PermissionOut(BaseModel):
    key: str
    description: str
    declared_by: str
    sensitive: bool
    reserved: bool
    requires_confirmation: bool
    user_grantable: bool
    enabled: bool


class RoleOut(BaseModel):
    id: UUID
    key: str
    name: str
    kind: str
    system: bool


class RoleCreate(Strict):
    key: str = Field(min_length=2, max_length=41, pattern=r"^[a-z][a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=128)


class RolePatch(Strict):
    name: str = Field(min_length=1, max_length=128)


class GroupOut(BaseModel):
    id: UUID
    key: str
    name: str
    description: str


class GroupCreate(Strict):
    key: str = Field(min_length=2, max_length=41, pattern=r"^[a-z][a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)


class GroupPatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)


class GrantIn(Strict):
    permission_key: str = Field(min_length=3, max_length=128)
    effect: Literal["allow", "deny"] = "allow"
    scope_kind: ScopeKind = "global"
    scope_ref: str = Field(default="", max_length=128)


class GrantOut(BaseModel):
    id: UUID
    holder_kind: str
    holder_id: UUID
    permission_key: str
    effect: str
    scope_kind: str
    scope_ref: str
    source: str


class RoleAssignment(Strict):
    role_key: str = Field(min_length=1, max_length=64)


class GroupMembership(Strict):
    group_key: str = Field(min_length=1, max_length=64)


class MyPermissions(BaseModel):
    permissions: list[str]
    roles: list[str]
