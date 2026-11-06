"""Issue 363: the requests' events, for the reward rules and the achievements the administrators set — a
request made, a « me too » said, a request fulfilled (told to each member who wanted it: whether they asked
first). Ids and kinds only, never titles."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:requests"
CREATED = "requests.created"
SUPPORTED = "requests.supported"
FULFILLED = "requests.fulfilled"


class Created(BaseModel):
    request: str
    kind: str


class Supported(BaseModel):
    request: str
    kind: str


class Fulfilled(BaseModel):
    request: str
    kind: str
    asked: bool  # the member asked for it (else said « me too »)
    supporters: int  # how many wanted it


def register_event_types(registry: EventTypeRegistry) -> None:
    for name, schema, dedup, fields in (
        (CREATED, Created, ("request",), frozenset({"kind"})),
        (SUPPORTED, Supported, ("request",), frozenset({"kind"})),
        (FULFILLED, Fulfilled, ("request",), frozenset({"kind", "asked", "supporters"})),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    dedup_fields=dedup,
                    retention_class="business",
                    visibility_class="private",
                    rewardable=fields,
                    aggregatable=fields,
                    automatable=True,
                )
            )
