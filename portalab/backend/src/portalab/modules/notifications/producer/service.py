"""``Producer`` (T008; R1, R4, R13): the single entry point that turns a ``CommunicationRequest`` into a
stored communication and its per-recipient deliveries.

* the category must be declared; an alert needs priority ≥ high; parameters are reference values, never
  secrets (same check as jobs/events);
* the audience is resolved **under the caller's authority**: a user may notify themself; targeting other
  users, permission holders or a role needs ``notifications.send_to_audience`` (and, for a permission
  audience, holding that permission); everyone needs ``notifications.broadcast``; the system may target
  anyone. Automations act for their author (the principal carries ``acting_for``);
* idempotent per ``(source, dedup_key)``.
"""

from collections.abc import Callable, Sequence
from dataclasses import asdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.identity_directory import CONTACT
from portalab.capabilities.notifications import (
    AllAuthenticated,
    AudienceSpec,
    CategoryRegistry,
    CommunicationRef,
    CommunicationRequest,
    Role,
    Users,
    WithPermission,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.user_grants import ROLES_CAPABILITY
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.errors import Forbidden, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.queue import check_payload
from portalab.core.time import Clock, utc_now
from portalab.modules.notifications.models import Communication
from portalab.modules.notifications.observability import log, metrics
from portalab.modules.notifications.permissions import NOTIFICATIONS_BROADCAST, SEND_TO_AUDIENCE

Fanout = Callable[[Communication, Sequence[UUID]], Any]


class CategoryUnknown(ValidationFailed):
    default_code = "notifications.category_unknown"
    default_title = "Unknown notification category"


class InvalidCommunication(ValidationFailed):
    default_code = "notifications.invalid"
    default_title = "Invalid communication"


class AudienceForbidden(Forbidden):
    default_code = "notifications.audience_forbidden"
    default_title = "You cannot send to this audience"


def audience_json(audience: AudienceSpec) -> dict[str, Any]:
    data: dict[str, Any] = {"type": type(audience).__name__}
    for name, value in asdict(audience).items():
        data[name] = [str(v) for v in value] if isinstance(value, tuple) else value
    return data


class Producer:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        categories: CategoryRegistry,
        fanout: Fanout,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.authorizer = authorizer
        self.capabilities = capabilities
        self.categories = categories
        self.fanout = fanout
        self.clock = clock

    def _provider(self, name: str) -> Any | None:
        try:
            providers = self.capabilities.system_providers(name)
        except Exception:
            return None
        return providers[0].provider if providers else None

    def validate(self, request: CommunicationRequest) -> None:
        if self.categories.get(request.category) is None:
            raise CategoryUnknown(f"Unknown category {request.category!r}.")
        if request.kind == "alert" and request.priority not in ("high", "critical"):
            raise InvalidCommunication("An alert has priority high or critical.")
        if not request.dedup_key.strip() or len(request.dedup_key) > 200:
            raise InvalidCommunication("A communication needs a deduplication key (≤ 200 characters).")
        if ":" not in request.template_key:
            raise InvalidCommunication("Templates are catalog keys 'namespace:key'.")
        if request.action_url is not None and (
            not request.action_url.startswith("/") or request.action_url.startswith("//")
        ):
            raise InvalidCommunication("Action links stay inside the portal.")
        try:
            check_payload(dict(request.params), "params")
        except ValueError as exc:
            raise InvalidCommunication(str(exc)) from exc

    async def authorize(self, request: CommunicationRequest, caller: Principal | None) -> None:
        if caller is None or caller.channel == "system":
            return
        audience = request.audience
        user = caller.acting_for or caller.user_id
        if isinstance(audience, Users) and set(audience.ids) <= {user}:
            return
        if isinstance(audience, AllAuthenticated):
            if not await self.authorizer.is_allowed(caller, NOTIFICATIONS_BROADCAST):
                raise AudienceForbidden("Broadcasting needs notifications.broadcast.")
            return
        if not await self.authorizer.is_allowed(caller, SEND_TO_AUDIENCE):
            raise AudienceForbidden("Sending to an audience needs notifications.send_to_audience.")
        if isinstance(audience, WithPermission) and not await self.authorizer.is_allowed(
            caller, audience.permission
        ):
            raise AudienceForbidden("You cannot target holders of a permission you do not have.")

    async def recipients(self, audience: AudienceSpec) -> list[UUID]:
        contact = self._provider(CONTACT)
        active = list(await contact.active_user_ids()) if contact is not None else []
        if isinstance(audience, Users):
            return list(dict.fromkeys(audience.ids))
        if isinstance(audience, AllAuthenticated):
            return active
        if isinstance(audience, WithPermission):
            return [u for u in active if await self._allowed(Principal(user_id=u), audience.permission)]
        if isinstance(audience, Role):
            roles = self._provider(ROLES_CAPABILITY)
            if roles is None:
                return []
            return [u for u in active if audience.role in await roles.roles_of(u)]
        return []

    async def _allowed(self, principal: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(principal, permission)
        except Exception:
            return False

    async def send(
        self, request: CommunicationRequest, *, caller: Principal | None = None
    ) -> CommunicationRef:
        self.validate(request)
        await self.authorize(request, caller)
        now = utc_now(self.clock)
        produced_by = (
            "system" if caller is None else str(caller.acting_for or caller.user_id or caller.channel)
        )
        required = request.required_permission or (
            request.audience.permission if isinstance(request.audience, WithPermission) else None
        )
        async with self.database.unit_of_work() as uow:
            inserted = (
                await uow.session.execute(
                    insert(Communication)
                    .values(
                        kind=request.kind,
                        category=request.category,
                        priority=request.priority,
                        source=request.source,
                        source_ref=request.source_ref,
                        dedup_key=request.dedup_key,
                        template_key=request.template_key,
                        params=dict(request.params),
                        subject_ref=request.subject_ref,
                        audience_spec=audience_json(request.audience),
                        required_permission=required,
                        produced_by=produced_by[:80],
                        valid_until=request.valid_until,
                        action_url=request.action_url,
                        email_body=dict(request.email_body) if request.email_body else None,
                        recipients=0,
                        created_at=now,
                    )
                    .on_conflict_do_nothing(constraint="uq_communications_source_dedup")
                    .returning(Communication.id)
                )
            ).scalar_one_or_none()
            if inserted is None:
                existing = await uow.session.scalar(
                    select(Communication.id).where(
                        Communication.source == request.source, Communication.dedup_key == request.dedup_key
                    )
                )
                metrics.increment("notifications.duplicates")
                assert existing is not None
                return CommunicationRef(existing, False)
        recipients = await self.recipients(request.audience)
        async with self.database.session() as session:
            communication = await session.get(Communication, inserted)
        assert communication is not None
        delivered = await self.fanout(communication, recipients)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Communication, inserted)
            if row is not None:
                row.recipients = int(delivered or 0)
            await self.events.publish(
                uow.session,
                "notification.sent",
                {
                    "communication": str(inserted),
                    "category": request.category,
                    "kind": request.kind,
                    "recipients": int(delivered or 0),
                },
                occurred_at=now,
                actor=caller,
                source="notifications",
                dedup_key=f"notification.sent:{inserted}",
            )
        metrics.increment(f"notifications.sent.{request.kind}")
        log.info(
            "communication produced", extra={"category": request.category, "recipients": int(delivered or 0)}
        )
        return CommunicationRef(inserted, True, int(delivered or 0))
