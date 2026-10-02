"""Roles, groups, grants and assignments (T022; FR-006..012, FR-019, F15).

Every change is a sensitive, audited operation emitting a ``permission.*`` event in the same transaction.
Rules enforced here (and, for reserved permissions, again by a database trigger):

* reserved (Admin-only) permissions are never granted to a role other than ``admin``, to a group or to a user;
* the ``admin`` role is not assignable/revocable here — only the single-Admin transfer moves it (FR-009/012);
  attempts are refused and recorded as ``permission.admin_transfer_attempted``;
* per-user grants are limited to ``user_grantable`` permissions (entitlements such as ``plugin:<key>.use``);
* base roles cannot be deleted; a custom role or group is deleted only when no longer assigned.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.authz.admin_authority.service import AdminAuthorityService
from portalab.modules.authz.models import (
    ADMIN_ROLE_ID,
    SCOPE_KINDS,
    Grant,
    Group,
    Permission,
    Role,
    UserGroup,
    UserRole,
)

_CUSTOM_KEY = re.compile(r"^[a-z][a-z0-9_-]{1,40}$")


class ReservedPermission(ValidationFailed):
    default_code = "authz.reserved_permission"
    default_title = "Reserved permission"


class SoleAdminProtected(Conflict):
    default_code = "authz.sole_admin_protected"
    default_title = "The Admin role moves only by transfer"


@dataclass(frozen=True, slots=True)
class GrantSpec:
    permission_key: str
    effect: str = "allow"
    scope_kind: str = "global"
    scope_ref: str = ""


class GrantService:
    def __init__(
        self,
        database: Database,
        audit: AuditSink,
        events: EventPublisher,
        admin_authority: AdminAuthorityService,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.audit = audit
        self.events = events
        self.admin_authority = admin_authority
        self.clock = clock

    # --- helpers -------------------------------------------------------------------------------------
    async def _record(
        self,
        session: AsyncSession,
        event: str,
        actor: Principal,
        subject: SubjectRef,
        metadata: Mapping[str, Any],
    ) -> None:
        details = {key: str(value) if isinstance(value, UUID) else value for key, value in metadata.items()}
        await self.events.publish(
            session,
            event,
            details,
            occurred_at=utc_now(self.clock),
            actor=actor,
            subject=subject,
            source="authz",
        )
        await self.audit.record(
            session,
            AuditRecord(
                action=event,
                actor=actor,
                resource=ResourceRef(kind=subject.kind, id=subject.id),
                decision="allow",
                result="success",
                context=details,
                sensitive=True,
            ),
        )

    async def _role(self, session: AsyncSession, key_or_id: str | UUID) -> Role:
        statement = (
            select(Role).where(Role.id == key_or_id)
            if isinstance(key_or_id, UUID)
            else select(Role).where(Role.key == key_or_id)
        )
        role = (await session.execute(statement)).scalar_one_or_none()
        if role is None:
            raise NotFound("Unknown role.", code="authz.role_not_found")
        return role

    async def _group(self, session: AsyncSession, key_or_id: str | UUID) -> Group:
        statement = (
            select(Group).where(Group.id == key_or_id)
            if isinstance(key_or_id, UUID)
            else select(Group).where(Group.key == key_or_id)
        )
        group = (await session.execute(statement)).scalar_one_or_none()
        if group is None:
            raise NotFound("Unknown group.", code="authz.group_not_found")
        return group

    async def _check_grant(
        self, session: AsyncSession, holder_kind: str, holder_id: UUID, spec: GrantSpec
    ) -> Permission:
        permission = await session.get(Permission, spec.permission_key)
        if permission is None:
            raise ValidationFailed("Unknown permission.", code="authz.unknown_permission")
        if spec.effect not in ("allow", "deny"):
            raise ValidationFailed("Effect must be allow or deny.", code="authz.invalid_grant")
        if spec.scope_kind not in SCOPE_KINDS:
            raise ValidationFailed("Unknown scope kind.", code="authz.invalid_grant")
        if spec.scope_kind in ("module", "service", "plugin") and not spec.scope_ref:
            raise ValidationFailed("This scope needs a reference.", code="authz.invalid_grant")
        is_admin_role = holder_kind == "role" and holder_id == ADMIN_ROLE_ID
        if permission.reserved and spec.effect == "allow" and not is_admin_role:
            raise ReservedPermission("This permission is reserved to the Admin.")
        if holder_kind == "user" and not permission.user_grantable:
            raise ValidationFailed(
                "This permission cannot be granted to an individual user.", code="authz.not_user_grantable"
            )
        return permission

    # --- roles & groups --------------------------------------------------------------------------------
    async def list_roles(self) -> list[Role]:
        async with self.database.session() as session:
            return list((await session.execute(select(Role).order_by(Role.kind, Role.key))).scalars())

    async def list_groups(self) -> list[Group]:
        async with self.database.session() as session:
            return list((await session.execute(select(Group).order_by(Group.key))).scalars())

    async def create_role(self, actor: Principal, key: str, name: str) -> Role:
        if not _CUSTOM_KEY.fullmatch(key):
            raise ValidationFailed("Invalid role key.", code="authz.invalid_key")
        async with self.database.unit_of_work() as uow:
            role = Role(key=f"custom:{key}", name=name.strip(), kind="custom", system=False)
            uow.session.add(role)
            try:
                await uow.session.flush()
            except IntegrityError as exc:
                raise Conflict("This role already exists.", code="authz.role_exists") from exc
            await self._record(
                uow.session,
                "permission.policy_changed",
                actor,
                SubjectRef("role", str(role.id)),
                {"change": "role_created", "role": role.key},
            )
            return role

    async def rename_role(self, actor: Principal, role_id: UUID, name: str) -> Role:
        async with self.database.unit_of_work() as uow:
            role = await self._role(uow.session, role_id)
            role.name = name.strip()
            await self._record(
                uow.session,
                "permission.policy_changed",
                actor,
                SubjectRef("role", str(role.id)),
                {"change": "role_renamed", "role": role.key},
            )
            return role

    async def delete_role(self, actor: Principal, role_id: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            role = await self._role(uow.session, role_id)
            if role.system:
                raise Conflict("Base roles cannot be deleted.", code="authz.base_role")
            assigned = await uow.session.scalar(
                select(func.count())
                .select_from(UserRole)
                .where(UserRole.role_id == role.id, UserRole.revoked_at.is_(None))
            )
            if assigned:
                raise Conflict("Unassign this role before deleting it.", code="authz.role_assigned")
            await uow.session.execute(
                delete(Grant).where(Grant.holder_kind == "role", Grant.holder_id == role.id)
            )
            await uow.session.execute(delete(UserRole).where(UserRole.role_id == role.id))
            await uow.session.delete(role)
            await self._record(
                uow.session,
                "permission.policy_changed",
                actor,
                SubjectRef("role", str(role_id)),
                {"change": "role_deleted", "role": role.key},
            )

    async def create_group(self, actor: Principal, key: str, name: str, description: str = "") -> Group:
        if not _CUSTOM_KEY.fullmatch(key):
            raise ValidationFailed("Invalid group key.", code="authz.invalid_key")
        async with self.database.unit_of_work() as uow:
            group = Group(key=key, name=name.strip(), description=description.strip())
            uow.session.add(group)
            try:
                await uow.session.flush()
            except IntegrityError as exc:
                raise Conflict("This group already exists.", code="authz.group_exists") from exc
            await self._record(
                uow.session,
                "permission.group_changed",
                actor,
                SubjectRef("group", str(group.id)),
                {"change": "group_created", "group": group.key},
            )
            return group

    async def update_group(
        self, actor: Principal, group_id: UUID, *, name: str | None, description: str | None
    ) -> Group:
        async with self.database.unit_of_work() as uow:
            group = await self._group(uow.session, group_id)
            if name is not None:
                group.name = name.strip()
            if description is not None:
                group.description = description.strip()
            await self._record(
                uow.session,
                "permission.group_changed",
                actor,
                SubjectRef("group", str(group.id)),
                {"change": "group_updated", "group": group.key},
            )
            return group

    async def delete_group(self, actor: Principal, group_id: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            group = await self._group(uow.session, group_id)
            members = await uow.session.scalar(
                select(func.count())
                .select_from(UserGroup)
                .where(UserGroup.group_id == group.id, UserGroup.revoked_at.is_(None))
            )
            if members:
                raise Conflict("Remove the members before deleting the group.", code="authz.group_not_empty")
            await uow.session.execute(
                delete(Grant).where(Grant.holder_kind == "group", Grant.holder_id == group.id)
            )
            await uow.session.execute(delete(UserGroup).where(UserGroup.group_id == group.id))
            await uow.session.delete(group)
            await self._record(
                uow.session,
                "permission.group_changed",
                actor,
                SubjectRef("group", str(group_id)),
                {"change": "group_deleted", "group": group.key},
            )

    # --- grants ----------------------------------------------------------------------------------------
    async def list_grants(self, holder_kind: str, holder_id: UUID) -> list[Grant]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(Grant)
                        .where(Grant.holder_kind == holder_kind, Grant.holder_id == holder_id)
                        .order_by(Grant.permission_key, Grant.scope_kind, Grant.scope_ref)
                    )
                ).scalars()
            )

    async def add_grant(
        self,
        actor: Principal | None,
        holder_kind: str,
        holder_id: UUID,
        spec: GrantSpec,
        *,
        source: str = "admin",
    ) -> Grant:
        async with self.database.unit_of_work() as uow:
            if holder_kind == "role":
                await self._role(uow.session, holder_id)
            elif holder_kind == "group":
                await self._group(uow.session, holder_id)
            await self._check_grant(uow.session, holder_kind, holder_id, spec)
            grant = Grant(
                holder_kind=holder_kind,
                holder_id=holder_id,
                permission_key=spec.permission_key,
                effect=spec.effect,
                scope_kind=spec.scope_kind,
                scope_ref=spec.scope_ref,
                source=source,
                created_by=actor.user_id if actor else None,
                created_at=utc_now(self.clock),
            )
            uow.session.add(grant)
            try:
                await uow.session.flush()
            except IntegrityError as exc:
                if "reserved permission" in str(exc.orig):
                    raise ReservedPermission("This permission is reserved to the Admin.") from exc
                raise Conflict("This grant already exists.", code="authz.grant_exists") from exc
            await self._record(
                uow.session,
                "permission.permission_granted",
                actor or Principal(channel="system"),
                SubjectRef(holder_kind, str(holder_id)),
                {
                    "permission": spec.permission_key,
                    "effect": spec.effect,
                    "scope_kind": spec.scope_kind,
                    "scope_ref": spec.scope_ref,
                    "grant_id": grant.id,
                },
            )
            return grant

    async def remove_grant(self, actor: Principal | None, grant_id: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            grant = await uow.session.get(Grant, grant_id)
            if grant is None:
                raise NotFound("Unknown grant.", code="authz.grant_not_found")
            await uow.session.delete(grant)
            await self._record(
                uow.session,
                "permission.permission_revoked",
                actor or Principal(channel="system"),
                SubjectRef(grant.holder_kind, str(grant.holder_id)),
                {"permission": grant.permission_key, "effect": grant.effect, "grant_id": grant_id},
            )

    async def remove_user_grant(
        self, permission_key: str, user_id: UUID, scope_kind: str, scope_ref: str
    ) -> bool:
        async with self.database.session() as session:
            grant_id = await session.scalar(
                select(Grant.id).where(
                    Grant.holder_kind == "user",
                    Grant.holder_id == user_id,
                    Grant.permission_key == permission_key,
                    Grant.scope_kind == scope_kind,
                    Grant.scope_ref == scope_ref,
                )
            )
        if grant_id is None:
            return False
        await self.remove_grant(None, grant_id)
        return True

    # --- assignments -----------------------------------------------------------------------------------
    async def user_roles(self, user_id: UUID) -> list[Role]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(Role)
                        .join(UserRole, UserRole.role_id == Role.id)
                        .where(UserRole.user_id == user_id, UserRole.revoked_at.is_(None))
                        .order_by(Role.key)
                    )
                ).scalars()
            )

    async def user_groups(self, user_id: UUID) -> list[Group]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(Group)
                        .join(UserGroup, UserGroup.group_id == Group.id)
                        .where(UserGroup.user_id == user_id, UserGroup.revoked_at.is_(None))
                        .order_by(Group.key)
                    )
                ).scalars()
            )

    async def _refuse_admin_role(self, actor: Principal, user_id: UUID) -> None:
        await self.admin_authority.record_refused_attempt(actor, None, user_id, "admin_role_by_assignment")
        raise SoleAdminProtected(
            "The Admin role cannot be granted, delegated or removed by assignment; use the Admin transfer."
        )

    async def assign_role(self, actor: Principal, user_id: UUID, role_key: str) -> None:
        async with self.database.unit_of_work() as uow:
            role = await self._role(uow.session, role_key)
            if role.id == ADMIN_ROLE_ID:
                await self._refuse_admin_role(actor, user_id)
            if role.key == "user":
                return  # every account implicitly holds the base User role
            uow.session.add(
                UserRole(
                    user_id=user_id, role_id=role.id, granted_by=actor.user_id, granted_at=utc_now(self.clock)
                )
            )
            try:
                await uow.session.flush()
            except IntegrityError as exc:
                if "uq_user_roles_active" in str(exc.orig):
                    raise Conflict(
                        "The user already holds this role.", code="authz.already_assigned"
                    ) from exc
                raise NotFound("Unknown user.", code="user.not_found") from exc
            await self._record(
                uow.session,
                "permission.role_assigned",
                actor,
                SubjectRef("user", str(user_id)),
                {"role": role.key},
            )

    async def revoke_role(self, actor: Principal, user_id: UUID, role_key: str) -> None:
        async with self.database.unit_of_work() as uow:
            role = await self._role(uow.session, role_key)
            if role.id == ADMIN_ROLE_ID:
                await self._refuse_admin_role(actor, user_id)
            result = await uow.session.execute(
                update(UserRole)
                .where(
                    UserRole.user_id == user_id, UserRole.role_id == role.id, UserRole.revoked_at.is_(None)
                )
                .values(revoked_at=utc_now(self.clock))
            )
            if not getattr(result, "rowcount", 0):
                raise NotFound("The user does not hold this role.", code="authz.not_assigned")
            await self._record(
                uow.session,
                "permission.role_revoked",
                actor,
                SubjectRef("user", str(user_id)),
                {"role": role.key},
            )

    async def add_member(self, actor: Principal, user_id: UUID, group_key: str) -> None:
        async with self.database.unit_of_work() as uow:
            group = await self._group(uow.session, group_key)
            uow.session.add(
                UserGroup(
                    user_id=user_id,
                    group_id=group.id,
                    granted_by=actor.user_id,
                    granted_at=utc_now(self.clock),
                )
            )
            try:
                await uow.session.flush()
            except IntegrityError as exc:
                if "uq_user_groups_active" in str(exc.orig):
                    raise Conflict("The user is already a member.", code="authz.already_assigned") from exc
                raise NotFound("Unknown user.", code="user.not_found") from exc
            await self._record(
                uow.session,
                "permission.group_changed",
                actor,
                SubjectRef("user", str(user_id)),
                {"change": "member_added", "group": group.key},
            )

    async def remove_member(self, actor: Principal, user_id: UUID, group_key: str) -> None:
        async with self.database.unit_of_work() as uow:
            group = await self._group(uow.session, group_key)
            result = await uow.session.execute(
                update(UserGroup)
                .where(
                    UserGroup.user_id == user_id,
                    UserGroup.group_id == group.id,
                    UserGroup.revoked_at.is_(None),
                )
                .values(revoked_at=utc_now(self.clock))
            )
            if not getattr(result, "rowcount", 0):
                raise NotFound("The user is not a member of this group.", code="authz.not_assigned")
            await self._record(
                uow.session,
                "permission.group_changed",
                actor,
                SubjectRef("user", str(user_id)),
                {"change": "member_removed", "group": group.key},
            )
