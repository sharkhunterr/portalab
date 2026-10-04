"""``UserLinkService`` (T022; R7): which portal user an account on a service is. A user claims an account;
the claim is **verified** through the service when its playback provider supports ``verify_user``,
otherwise by an Admin. Only verified links attribute activity — unlinked or unverified activity is kept as
*unlinked* and never attributed (no matching on display names)."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from portalab.capabilities.media import PLAYBACK, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.errors import Conflict, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.media.identity.resolver import MediaNotFound
from portalab.modules.media.insights.ingest import attribute
from portalab.modules.media.models import UserLink


class LinkUnverified(ValidationFailed):
    default_code = "media.link_unverified"
    default_title = "The account link could not be verified"


class LinkTaken(Conflict):
    default_code = "media.link_taken"
    default_title = "This account is already linked"


@dataclass(frozen=True, slots=True)
class LinkView:
    id: UUID
    service_id: UUID
    external_user_id: str
    verified: bool
    created_at: datetime


def _view(row: UserLink) -> LinkView:
    return LinkView(row.id, row.service_id, row.external_user_id, row.verified, row.created_at)


class UserLinkService:
    def __init__(self, database: Database, capabilities: CapabilityRegistry, *, clock: Clock | None = None):
        self.database = database
        self.capabilities = capabilities
        self.clock = clock

    def _playback(self, service_id: UUID) -> Any | None:
        try:
            providers = self.capabilities.system_providers(PLAYBACK)
        except Exception:
            return None
        return next((p.provider for p in providers if p.instance_ref == str(service_id)), None)

    async def mine(self, user: UUID) -> list[LinkView]:
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(UserLink).where(UserLink.user_id == user).order_by(UserLink.created_at)
                    )
                )
                .scalars()
                .all()
            )
        return [_view(r) for r in rows]

    async def claim(
        self, user: UUID, service_id: UUID, external_user_id: str, *, verified: bool = False
    ) -> LinkView:
        external = external_user_id.strip()
        if not external or len(external) > 200:
            raise ValidationFailed("Give the account identifier on that service.", code="media.invalid")
        try:
            async with self.database.unit_of_work() as uow:
                row = UserLink(
                    user_id=user,
                    service_id=service_id,
                    external_user_id=external,
                    verified=verified,
                    created_at=utc_now(self.clock),
                )
                uow.session.add(row)
                await uow.session.flush()
                return _view(row)
        except IntegrityError as exc:
            raise LinkTaken("This account (or this service) is already linked.") from exc

    async def verify(self, user: UUID | None, link_id: UUID, proof: str | None) -> LinkView:
        """Verify through the service (``verify_user``) — or as an Admin when ``user`` is ``None``."""
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(UserLink, link_id, with_for_update=True)
            if row is None or (user is not None and row.user_id != user):
                raise MediaNotFound("This link does not exist.")
            if user is not None:
                provider = self._playback(row.service_id)
                check = getattr(provider, "verify_user", None)
                if check is None or not proof:
                    raise LinkUnverified("This service cannot verify accounts; ask an administrator.")
                try:
                    ok = bool(unwrap(await asyncio.wait_for(check(row.external_user_id, proof), timeout=10)))
                except Exception as exc:
                    raise LinkUnverified("The service could not verify this account.") from exc
                if not ok:
                    raise LinkUnverified("The service did not confirm this account.")
            row.verified = True
            await attribute(uow.session, row.service_id, row.external_user_id, row.user_id)
            return _view(row)

    async def remove(self, user: UUID, link_id: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            removed = (
                await uow.session.execute(
                    delete(UserLink)
                    .where(UserLink.id == link_id, UserLink.user_id == user)
                    .returning(UserLink.service_id, UserLink.external_user_id)
                )
            ).first()
            if removed is None:
                raise MediaNotFound("This link does not exist.")
            await attribute(uow.session, removed[0], removed[1], None)

    async def resolve(self, service_id: UUID, external_user_id: str | None) -> UUID | None:
        if not external_user_id:
            return None
        async with self.database.session() as session:
            return (
                await session.execute(
                    select(UserLink.user_id).where(
                        UserLink.service_id == service_id,
                        UserLink.external_user_id == external_user_id,
                        UserLink.verified.is_(True),
                    )
                )
            ).scalar_one_or_none()
