"""Audience of a news article or wiki page (R6, OQ-53 default): everyone who may read the domain, or only
holders of given roles or of a permission — evaluated server-side for every read surface (list, detail,
search, featured, calendar, notifications, links)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.user_grants import ROLES_CAPABILITY
from portalab.core.authz_port import Authorizer, Principal


class Audience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["all", "roles", "permission"] = "all"
    refs: list[str] = Field(default_factory=list, max_length=20)


async def can_read(
    audience: Audience | dict[str, object] | None,
    viewer: Principal,
    authorizer: Authorizer,
    capabilities: CapabilityRegistry,
) -> bool:
    spec = audience if isinstance(audience, Audience) else Audience.model_validate(audience or {})
    if spec.mode == "all" or viewer.channel == "system":
        return True
    if spec.mode == "permission":
        for permission in spec.refs:
            try:
                if await authorizer.is_allowed(viewer, permission):
                    return True
            except Exception:  # noqa: S112 — an unknown permission simply grants nothing
                continue
        return False
    user: UUID | None = viewer.acting_for or viewer.user_id
    if user is None:
        return False
    try:
        providers = capabilities.system_providers(ROLES_CAPABILITY)
    except Exception:
        return False
    if not providers:
        return False
    roles: frozenset[str] = await providers[0].provider.roles_of(user)
    return bool(roles & set(spec.refs))
