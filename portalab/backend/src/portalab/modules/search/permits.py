"""Issue 480: which permissions a principal holds, to decide what search *offers* (its sources, the
destinations it lists) — one batch through the engine's ``visible`` (not audited: not an access decision; the
action itself is authorized and audited when it is called), else one check each."""

import asyncio
from collections.abc import Iterable

from portalab.core.authz_port import Authorizer, Principal


async def held(authorizer: Authorizer, principal: Principal, permissions: Iterable[str]) -> set[str]:
    unique = sorted(set(permissions))
    visible = getattr(authorizer, "visible", None)
    if visible is not None:
        try:
            return set(await visible(principal, unique))
        except Exception:
            return set()  # fail closed

    async def allowed(permission: str) -> bool:
        try:
            return await authorizer.is_allowed(principal, permission)
        except Exception:
            return False  # fail closed

    answers = await asyncio.gather(*(allowed(permission) for permission in unique))
    return {permission for permission, ok in zip(unique, answers, strict=True) if ok}
