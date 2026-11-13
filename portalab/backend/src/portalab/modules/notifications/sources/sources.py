"""System sources (T024; R6): account security (``user.suspended|reactivated|deletion_requested`` ⇒ a
mandatory notification to that user). Event time is the event's ``occurred_at``; replays produce nothing;
dedup keys make redelivery harmless. Service outages are announced by Health itself (027), following each
service's alerting rule (delay, audiences, e-mail)."""

from collections.abc import Awaitable, Callable

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.capabilities.notifications import CommunicationRef, CommunicationRequest, Users

CONSUMER = "notifications.sources"
OWNER = "module:notifications"
SECURITY_EVENTS = ("user.suspended", "user.reactivated", "user.deletion_requested")

Send = Callable[[CommunicationRequest], Awaitable[CommunicationRef]]


def sources_consumer(send: Send) -> Consumer:
    async def handle(envelope: Envelope, ctx: ConsumerContext) -> None:
        if ctx.replay:
            return
        if envelope.type in SECURITY_EVENTS and envelope.subject_type == "user" and envelope.subject_id:
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
                    # issue 398: when the account goes for good (deletion), and when it all happened
                    params={
                        "due_at": str(envelope.payload.get("due_at") or "none"),
                        "occurred_at": envelope.occurred_at.isoformat(),
                    },
                )
            )

    return Consumer(CONSUMER, frozenset(SECURITY_EVENTS), handle, OWNER, replay_safe=False)
