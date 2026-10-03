"""Wiki events (ids and versions only, never page text): ``wiki.page_created|revised|published|archived|
restored|deleted`` deduplicated by ``(page, version)``."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:wiki"
TYPES = ("created", "revised", "published", "archived", "restored", "deleted")


class PageEvent(BaseModel):
    page: str
    version: int


def register_event_types(registry: EventTypeRegistry) -> None:
    for action in TYPES:
        name = f"wiki.page_{action}"
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=PageEvent,
                    open_payload=False,
                    dedup_fields=("page", "version"),
                    retention_class="business",
                    visibility_class="community",
                    automatable=action in ("published", "revised"),
                )
            )
