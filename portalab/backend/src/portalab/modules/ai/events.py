"""AI events (via 007; ids and counts only, never prompts or answers): ``ai.conversation_started``,
``ai.action_confirmed|declined|expired`` (dedup per pending action), ``ai.provider_failed`` (diagnostic,
at most one per minute and code). Domain actions performed by the AI are emitted by their owning domain
with the AI actor."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:ai"


class ConversationStarted(BaseModel):
    conversation: str


class ActionOutcome(BaseModel):
    tool: str
    action: str


class ProviderFailed(BaseModel):
    code: str
    minute: str


def register_event_types(registry: EventTypeRegistry) -> None:
    schemas: tuple[tuple[str, type[BaseModel]], ...] = (
        ("ai.conversation_started", ConversationStarted),
        ("ai.action_confirmed", ActionOutcome),
        ("ai.action_declined", ActionOutcome),
        ("ai.action_expired", ActionOutcome),
        ("ai.provider_failed", ProviderFailed),
    )
    for name, schema in schemas:
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    retention_class="technical",
                    visibility_class="private" if name != "ai.provider_failed" else "restricted",
                )
            )
