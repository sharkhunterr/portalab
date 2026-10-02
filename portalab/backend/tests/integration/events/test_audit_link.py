"""007 T025/T026 — a sensitive action produces one event and one audit entry sharing ``event_id``; the audit
entry stays in ``audit.audit_entries``."""

from sqlalchemy import select

from portalab.core.authz_port import Principal
from portalab.modules.authz.models import AuditEntry
from portalab.modules.events.models import Event
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.module import IdentityModule
from portalab.modules.identity.services.common import admin_actor
from tests.events_fixtures import EventsHarness
from tests.integration.identity.helpers import create_user


async def test_event_and_audit_share_the_id(ev: EventsHarness) -> None:
    import portalab.modules.identity.event_types  # noqa: F401 — user.* types

    for event_type in ("user.created", "user.suspended"):
        from portalab.capabilities.events import default_event_types

        ev.types.register(default_event_types.get(event_type))  # type: ignore[arg-type]
    ev.full.identity.events = ev.publisher
    identity = IdentityModule(ev.full.identity)
    user_id = await create_user(identity, "member")
    async with ev.full.database.unit_of_work() as uow:
        user = await identity.accounts.get_for_update(uow.session, user_id)
        await identity.accounts.transition(
            uow.session, user, AccountState.SUSPENDED, admin_actor(Principal(user_id=user_id)), reason="abuse"
        )
    async with ev.full.database.session() as session:
        event = (await session.execute(select(Event).where(Event.type == "user.suspended"))).scalar_one()
        audit = (
            await session.execute(select(AuditEntry).where(AuditEntry.action == "user.suspended"))
        ).scalar_one()
    assert audit.event_id == event.event_id and audit.correlation_id == event.correlation_id
