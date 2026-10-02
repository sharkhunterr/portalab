"""Catalog synchronisation (T008): declared permissions → ``authz.permissions``, default role grants.

The upsert is idempotent. Default role grants are seeded only when a permission appears for the first
time, so an Admin who later removes a default grant is never overridden at the next start-up. Permissions
whose declaration disappeared (plugin uninstalled) are disabled, never deleted: their grants stop granting
at the next evaluation (FR-023) while history stays intact.
"""

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.permissions import PermissionRegistry
from portalab.core.time import Clock, utc_now
from portalab.modules.authz.models import BASE_ROLE_IDS, Grant, Permission


async def sync_catalog(
    session: AsyncSession, registry: PermissionRegistry, clock: Clock | None = None
) -> int:
    """Upsert every declaration; returns how many permissions were created."""
    now = utc_now(clock)
    existing = set((await session.execute(select(Permission.key))).scalars())
    created = 0
    for declaration in registry.all():
        values = {
            "description": declaration.description,
            "declared_by": declaration.declared_by,
            "sensitive": declaration.sensitive,
            "reserved": declaration.reserved,
            "requires_confirmation": declaration.requires_confirmation,
            "user_grantable": declaration.user_grantable,
        }
        statement = insert(Permission).values(key=declaration.key, enabled=True, created_at=now, **values)
        statement = statement.on_conflict_do_update(index_elements=[Permission.key], set_=values)
        await session.execute(statement)
        if declaration.key in existing:
            continue
        created += 1
        for default in declaration.default_grants:
            await session.execute(
                insert(Grant)
                .values(
                    holder_kind="role",
                    holder_id=BASE_ROLE_IDS[default.role],
                    permission_key=declaration.key,
                    effect="allow",
                    scope_kind=default.scope_kind,
                    scope_ref="",
                    source="default",
                    created_at=now,
                )
                .on_conflict_do_nothing(constraint="uq_grants_holder_scope")
            )
    core_declared = {decl.key for decl in registry.all()}
    stale = existing - core_declared
    if stale:
        await session.execute(
            update(Permission)
            .where(Permission.key.in_(stale), Permission.declared_by.like("plugin:%"))
            .values(enabled=False)
        )
    return created


async def set_plugin_permissions_enabled(session: AsyncSession, plugin_id: str, enabled: bool) -> int:
    """Withdraw (or restore) every permission declared by a plugin; data and grants are kept (FR-023)."""
    result = await session.execute(
        update(Permission).where(Permission.declared_by == f"plugin:{plugin_id}").values(enabled=enabled)
    )
    return int(getattr(result, "rowcount", 0) or 0)
