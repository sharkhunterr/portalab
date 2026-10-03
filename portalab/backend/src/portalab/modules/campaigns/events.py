"""Campaign lifecycle events (T002; via 007, no PII): ``campaign.created|version_published|started|
ending_soon|ended|paused|resumed|cancelled|archived`` — automatable (019 announcements react to them)."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:campaigns"
TYPES = (
    "campaign.created",
    "campaign.version_published",
    "campaign.started",
    "campaign.ending_soon",
    "campaign.ended",
    "campaign.paused",
    "campaign.resumed",
    "campaign.cancelled",
    "campaign.archived",
)


class CampaignLifecycle(BaseModel):
    campaign: str
    version: int
    occurrence: str | None = None
    cause: str | None = None


def register_event_types(registry: EventTypeRegistry) -> None:
    for name in TYPES:
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=CampaignLifecycle,
                    open_payload=False,
                    aggregatable=frozenset({"campaign"}),
                    automatable=True,
                    visibility_class="community",
                )
            )
