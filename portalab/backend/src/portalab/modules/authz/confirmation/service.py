"""``ConfirmationService`` (T030; R10): single-use, short-lived confirmation tokens for sensitive actions.

A token is bound to the principal, the permission, the resource and a hash of the exact payload, stored
hashed, and consumed once. AI (018) and automation (019) flows use it before performing an action whose
permission ``requires_confirmation``.
"""

import hashlib
import json
import secrets
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Forbidden
from portalab.core.time import Clock, utc_now
from portalab.modules.authz.models import Confirmation
from portalab.modules.authz.observability import metrics


class ConfirmationRequired(Forbidden):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def binding_hash(resource: ResourceRef | None, payload: Any) -> str:
    material = {
        "resource": [resource.kind, resource.id] if resource else None,
        "payload": payload,
    }
    return _hash(json.dumps(material, sort_keys=True, default=str))


class ConfirmationService:
    def __init__(self, database: Database, *, ttl_seconds: int = 300, clock: Clock | None = None) -> None:
        self.database = database
        self.ttl = timedelta(seconds=ttl_seconds)
        self.clock = clock

    async def issue(
        self, principal: Principal, permission: str, resource: ResourceRef | None, payload: Any
    ) -> str:
        subject = principal.acting_for or principal.user_id
        if subject is None:
            raise ConfirmationRequired("Only an identified user can confirm an action.")
        token = secrets.token_urlsafe(32)
        async with self.database.unit_of_work() as uow:
            uow.session.add(
                Confirmation(
                    token_hash=_hash(token),
                    principal_user_id=subject,
                    permission_key=permission,
                    resource_hash=binding_hash(resource, payload),
                    expires_at=utc_now(self.clock) + self.ttl,
                )
            )
        metrics.increment("authz.confirmations.issued")
        return token

    async def consume(
        self, token: str, principal: Principal, permission: str, resource: ResourceRef | None, payload: Any
    ) -> bool:
        subject = principal.acting_for or principal.user_id
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = (
                await uow.session.execute(
                    select(Confirmation).where(Confirmation.token_hash == _hash(token)).with_for_update()
                )
            ).scalar_one_or_none()
            valid = (
                row is not None
                and row.consumed_at is None
                and row.expires_at > now
                and row.principal_user_id == subject
                and row.permission_key == permission
                and row.resource_hash == binding_hash(resource, payload)
            )
            if row is not None and row.consumed_at is None and row.expires_at > now:
                row.consumed_at = now  # any presentation burns the token (no replay, no probing)
        if valid:
            metrics.increment("authz.confirmations.consumed")
        return valid
