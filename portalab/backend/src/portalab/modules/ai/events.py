"""AI events (via 007; ids and counts only, never prompts or answers): ``ai.conversation_started``,
``ai.action_confirmed|declined|expired`` (dedup per pending action), ``ai.provider_failed`` (diagnostic,
at most one per minute and code); issue 181 — what the achievements count: ``ai.answered`` (one per answer),
``ai.answer_rated`` (a member's first verdict on an answer), ``ai.capacity_gained`` (one per shop grant).
Domain actions performed by the AI are emitted by their owning domain with the AI actor."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:ai"


class ConversationStarted(BaseModel):
    conversation: str


class ActionOutcome(BaseModel):
    tool: str
    action: str


class Answered(BaseModel):
    """Issue 181: an answer given — whether it drew on the portal's data, how many look-ups (no text)."""

    conversation: str
    sourced: bool
    tools: int


class AnswerRated(BaseModel):
    """Issue 181: a member's first verdict on an answer — and whether they said what they expected."""

    rating: str
    commented: bool


class CapacityGained(BaseModel):
    """Issue 181: a capacity of the assistant a member got (bought or given in the shop)."""

    perk: str


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
        ("ai.answered", Answered),
        ("ai.answer_rated", AnswerRated),
        ("ai.capacity_gained", CapacityGained),
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
