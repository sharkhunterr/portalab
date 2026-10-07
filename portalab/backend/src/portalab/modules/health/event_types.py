"""Event types owned by the Health module (spec 006 FR-032/033). ``service.status_changed`` is the shared
type of :mod:`portalab.capabilities.service_events` (``dimension="health"``)."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, default_event_types
from portalab.capabilities.service_events import register_status_changed

OWNER = "module:health"


class HealthRecorded(BaseModel):
    service_id: str
    ok: bool
    error_code: str | None = None


class MaintenancePayload(BaseModel):
    maintenance_id: str
    service_id: str | None = None
    starts_at: str
    ends_at: str
    schedule_version: int
    transition: str
    reference_time_zone: str | None = None


class OutageLasting(BaseModel):
    """027: a service still unavailable after a while (5, 10, 15, 30, 60, 120 minutes)."""

    service_id: str
    service_label: str | None = None  # the service as named in the portal
    state_seq: int
    minutes: int
    failures: int  # failed probes in a row so far
    since: str


class OperationPayload(BaseModel):
    service_id: str
    operation: str
    result: str


def register_event_types() -> None:
    register_status_changed()
    default_event_types.register(
        EventType(
            name="service.health_recorded",
            owner=OWNER,
            schema=HealthRecorded,
            open_payload=False,
            retention_class="technical",
            visibility_class="restricted",
        )
    )
    for name in ("scheduled", "rescheduled", "started", "ended", "cancelled"):
        default_event_types.register(
            EventType(
                name=f"maintenance.{name}",
                owner=OWNER,
                schema=MaintenancePayload,
                open_payload=False,
                dedup_fields=("maintenance_id", "transition", "schedule_version"),
                retention_class="business",
                visibility_class="community",
                automatable=True,
                live_permission="services.read",
            )
        )
    default_event_types.register(
        EventType(
            name="service.outage_lasting",
            owner=OWNER,
            schema=OutageLasting,
            open_payload=False,
            dedup_fields=("service_id", "state_seq", "minutes"),
            retention_class="technical",
            visibility_class="restricted",
            automatable=True,
            live_permission="services.read",
            description="A service has been unavailable for a while (minutes, failed probes).",
        )
    )
    default_event_types.register(
        EventType(
            name="service.operation_performed",
            owner=OWNER,
            schema=OperationPayload,
            open_payload=False,
            retention_class="business",
            visibility_class="restricted",
            automatable=True,
        )
    )


register_event_types()
