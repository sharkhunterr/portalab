"""``authz.user_grants`` provider: entitlement grants held by one user (F15)."""

from uuid import UUID

from portalab.core.errors import Conflict
from portalab.modules.authz.grants.service import GrantService, GrantSpec


class UserGrantsProvider:
    def __init__(self, service: GrantService) -> None:
        self.service = service

    async def grant(
        self,
        user_id: UUID,
        permission_key: str,
        *,
        scope_kind: str = "global",
        scope_ref: str = "",
        source: str,
    ) -> None:
        try:
            await self.service.add_grant(
                None,
                "user",
                user_id,
                GrantSpec(permission_key, "allow", scope_kind, scope_ref),
                source=source,
            )
        except Conflict as exc:
            if exc.code != "authz.grant_exists":
                raise
            # already granted: the call is idempotent

    async def revoke(
        self, user_id: UUID, permission_key: str, *, scope_kind: str = "global", scope_ref: str = ""
    ) -> bool:
        return await self.service.remove_user_grant(permission_key, user_id, scope_kind, scope_ref)
