"""Authorization API (T023): catalog, roles, groups, grants, assignments, own effective permissions.

Every management route requires ``users.roles.manage`` (reserved to the Admin, sensitive ⇒ audited by the
engine) and each change is audited again with its outcome by the services. ``/me/permissions`` is a UI hint
only: the server stays the authority on every action.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.authz.api.schemas import (
    GrantIn,
    GrantOut,
    GroupCreate,
    GroupMembership,
    GroupOut,
    GroupPatch,
    MyPermissions,
    PermissionOut,
    RoleAssignment,
    RoleCreate,
    RoleOut,
    RolePatch,
)
from portalab.modules.authz.grants.service import GrantSpec
from portalab.modules.authz.models import Grant, Group, Permission, Role
from portalab.modules.authz.module import AuthzModule

router = APIRouter(prefix="/api/v1", tags=["authz"])
MANAGE = "users.roles.manage"


def authz_module(request: Request) -> AuthzModule:
    module = getattr(request.app.state, "authz_module", None)
    if not isinstance(module, AuthzModule):
        raise Unavailable("Authorization is not available.", code="authz.unavailable")
    return module


Module = Annotated[AuthzModule, Depends(authz_module)]
NO_CONTENT = status.HTTP_204_NO_CONTENT


def _role(role: Role) -> RoleOut:
    return RoleOut(id=role.id, key=role.key, name=role.name, kind=role.kind, system=role.system)


def _group(group: Group) -> GroupOut:
    return GroupOut(id=group.id, key=group.key, name=group.name, description=group.description)


def _grant(grant: Grant) -> GrantOut:
    return GrantOut(
        id=grant.id,
        holder_kind=grant.holder_kind,
        holder_id=grant.holder_id,
        permission_key=grant.permission_key,
        effect=grant.effect,
        scope_kind=grant.scope_kind,
        scope_ref=grant.scope_ref,
        source=grant.source,
    )


@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(module: Module, principal: Principal = require(MANAGE)) -> list[PermissionOut]:
    from sqlalchemy import select

    await module.catalog.ensure()
    async with module.database.session() as session:
        rows = (await session.execute(select(Permission).order_by(Permission.key))).scalars().all()
    return [
        PermissionOut(
            key=row.key,
            description=row.description,
            declared_by=row.declared_by,
            sensitive=row.sensitive,
            reserved=row.reserved,
            requires_confirmation=row.requires_confirmation,
            user_grantable=row.user_grantable,
            enabled=row.enabled,
        )
        for row in rows
    ]


# --- roles -------------------------------------------------------------------------------------------
@router.get("/roles", response_model=list[RoleOut])
async def list_roles(module: Module, principal: Principal = require(MANAGE)) -> list[RoleOut]:
    return [_role(role) for role in await module.grants.list_roles()]


@router.post("/roles", status_code=status.HTTP_201_CREATED, response_model=RoleOut)
async def create_role(body: RoleCreate, module: Module, principal: Principal = require(MANAGE)) -> RoleOut:
    return _role(await module.grants.create_role(principal, body.key, body.name))


@router.patch("/roles/{role_id}", response_model=RoleOut)
async def rename_role(
    role_id: UUID, body: RolePatch, module: Module, principal: Principal = require(MANAGE)
) -> RoleOut:
    return _role(await module.grants.rename_role(principal, role_id, body.name))


@router.delete("/roles/{role_id}", status_code=NO_CONTENT)
async def delete_role(role_id: UUID, module: Module, principal: Principal = require(MANAGE)) -> Response:
    await module.grants.delete_role(principal, role_id)
    return Response(status_code=NO_CONTENT)


@router.get("/roles/{role_id}/grants", response_model=list[GrantOut])
async def role_grants(
    role_id: UUID, module: Module, principal: Principal = require(MANAGE)
) -> list[GrantOut]:
    return [_grant(grant) for grant in await module.grants.list_grants("role", role_id)]


@router.post(
    "/roles/{role_id}/grants",
    status_code=status.HTTP_201_CREATED,
    response_model=GrantOut,
    responses={422: {"description": "authz.reserved_permission"}},
)
async def add_role_grant(
    role_id: UUID, body: GrantIn, module: Module, principal: Principal = require(MANAGE)
) -> GrantOut:
    spec = GrantSpec(body.permission_key, body.effect, body.scope_kind, body.scope_ref)
    return _grant(await module.grants.add_grant(principal, "role", role_id, spec))


# --- groups ------------------------------------------------------------------------------------------
@router.get("/groups", response_model=list[GroupOut])
async def list_groups(module: Module, principal: Principal = require(MANAGE)) -> list[GroupOut]:
    return [_group(group) for group in await module.grants.list_groups()]


@router.post("/groups", status_code=status.HTTP_201_CREATED, response_model=GroupOut)
async def create_group(body: GroupCreate, module: Module, principal: Principal = require(MANAGE)) -> GroupOut:
    return _group(await module.grants.create_group(principal, body.key, body.name, body.description))


@router.patch("/groups/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: UUID, body: GroupPatch, module: Module, principal: Principal = require(MANAGE)
) -> GroupOut:
    group = await module.grants.update_group(
        principal, group_id, name=body.name, description=body.description
    )
    return _group(group)


@router.delete("/groups/{group_id}", status_code=NO_CONTENT)
async def delete_group(group_id: UUID, module: Module, principal: Principal = require(MANAGE)) -> Response:
    await module.grants.delete_group(principal, group_id)
    return Response(status_code=NO_CONTENT)


@router.get("/groups/{group_id}/grants", response_model=list[GrantOut])
async def group_grants(
    group_id: UUID, module: Module, principal: Principal = require(MANAGE)
) -> list[GrantOut]:
    return [_grant(grant) for grant in await module.grants.list_grants("group", group_id)]


@router.post(
    "/groups/{group_id}/grants",
    status_code=status.HTTP_201_CREATED,
    response_model=GrantOut,
    responses={422: {"description": "authz.reserved_permission"}},
)
async def add_group_grant(
    group_id: UUID, body: GrantIn, module: Module, principal: Principal = require(MANAGE)
) -> GrantOut:
    spec = GrantSpec(body.permission_key, body.effect, body.scope_kind, body.scope_ref)
    return _grant(await module.grants.add_grant(principal, "group", group_id, spec))


@router.delete("/grants/{grant_id}", status_code=NO_CONTENT)
async def remove_grant(grant_id: UUID, module: Module, principal: Principal = require(MANAGE)) -> Response:
    await module.grants.remove_grant(principal, grant_id)
    return Response(status_code=NO_CONTENT)


# --- assignments -------------------------------------------------------------------------------------
@router.get("/users/{user_id}/roles", response_model=list[RoleOut])
async def user_roles(user_id: UUID, module: Module, principal: Principal = require(MANAGE)) -> list[RoleOut]:
    return [_role(role) for role in await module.grants.user_roles(user_id)]


@router.post(
    "/users/{user_id}/roles",
    status_code=NO_CONTENT,
    responses={409: {"description": "authz.sole_admin_protected"}},
)
async def assign_role(
    user_id: UUID, body: RoleAssignment, module: Module, principal: Principal = require(MANAGE)
) -> Response:
    await module.grants.assign_role(principal, user_id, body.role_key)
    return Response(status_code=NO_CONTENT)


@router.delete(
    "/users/{user_id}/roles/{role_key}",
    status_code=NO_CONTENT,
    responses={409: {"description": "authz.sole_admin_protected"}},
)
async def revoke_role(
    user_id: UUID, role_key: str, module: Module, principal: Principal = require(MANAGE)
) -> Response:
    await module.grants.revoke_role(principal, user_id, role_key)
    return Response(status_code=NO_CONTENT)


@router.get("/users/{user_id}/groups", response_model=list[GroupOut])
async def user_groups(
    user_id: UUID, module: Module, principal: Principal = require(MANAGE)
) -> list[GroupOut]:
    return [_group(group) for group in await module.grants.user_groups(user_id)]


@router.post("/users/{user_id}/groups", status_code=NO_CONTENT)
async def add_member(
    user_id: UUID, body: GroupMembership, module: Module, principal: Principal = require(MANAGE)
) -> Response:
    await module.grants.add_member(principal, user_id, body.group_key)
    return Response(status_code=NO_CONTENT)


@router.delete("/users/{user_id}/groups/{group_key}", status_code=NO_CONTENT)
async def remove_member(
    user_id: UUID, group_key: str, module: Module, principal: Principal = require(MANAGE)
) -> Response:
    await module.grants.remove_member(principal, user_id, group_key)
    return Response(status_code=NO_CONTENT)


@router.get("/me/permissions", response_model=MyPermissions)
async def my_permissions(
    module: Module, principal: Principal = require("users.self.manage")
) -> MyPermissions:
    assert principal.user_id is not None
    roles = ["user", *(role.key for role in await module.grants.user_roles(principal.user_id))]
    return MyPermissions(
        permissions=await module.engine.effective_permissions(principal), roles=sorted(set(roles))
    )
