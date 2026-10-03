"""System sources (T024; R6): service outages (006 ``service.status_changed`` to ``unavailable`` on the
health dimension ⇒ one critical alert per state change, holders of ``services.read``) and account security
(``user.suspended|reactivated|deletion_requested`` ⇒ a mandatory notification to that user). Event time is
the event's ``occurred_at``; replays produce nothing; dedup keys make redelivery harmless."""

from collections.abc import Awaitable, Callable

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.capabilities.notifications import CommunicationRef, CommunicationRequest, Users, WithPermission

CONSUMER = "notifications.sources"
OWNER = "module:notifications"
SECURITY_EVENTS = ("user.suspended", "user.reactivated", "user.deletion_requested")

Send = Callable[[CommunicationRequest], Awaitable[CommunicationRef]]


def sources_consumer(send: Send) -> Consumer:
    async def handle(envelope: Envelope, ctx: ConsumerContext) -> None:
        if ctx.replay:
            return
        payload = envelope.payload
        if envelope.type == "service.status_changed":
            if payload.get("dimension") != "health" or payload.get("to_state") != "unavailable":
                return
            service = str(payload.get("service_id", ""))
            await send(
                CommunicationRequest(
                    category="system.health",
                    template_key="notifications:service.unavailable",
                    audience=WithPermission("services.read", (service,)),
                    dedup_key=f"service:{service}:{payload.get('state_seq')}:unavailable",
                    kind="alert",
                    priority="critical",
                    params={"service": service},
                    source="event",
                    source_ref=str(envelope.event_id),
                    subject_ref=f"service:{service}",
                    required_permission="services.read",
                    action_url=f"/services/{service}",
                )
            )
        elif envelope.type in SECURITY_EVENTS and envelope.subject_type == "user" and envelope.subject_id:
            from uuid import UUID

            user = UUID(envelope.subject_id)
            action = envelope.type.split(".", 1)[1]
            await send(
                CommunicationRequest(
                    category="account.security",
                    template_key=f"notifications:account.{action}",
                    audience=Users((user,)),
                    dedup_key=f"account:{envelope.event_id}",
                    priority="high",
                    source="event",
                    source_ref=str(envelope.event_id),
                    subject_ref=f"account:{user}",
                    action_url="/account",
                )
            )

    return Consumer(
        CONSUMER, frozenset({"service.status_changed", *SECURITY_EVENTS}), handle, OWNER, replay_safe=False
    )
