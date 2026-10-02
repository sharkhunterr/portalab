"""Event types owned by the Connectors module (spec 005 "Connector-Related Domain Events")."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, default_event_types
from portalab.capabilities.service_events import ServiceStatus, register_status_changed

OWNER = "module:connectors"


class SyncPayload(BaseModel):
    service_id: str
    run_id: str
    kind: str
    status: str | None = None
    added: int = 0
    modified: int = 0
    removed: int = 0
    ignored: int = 0
    errored: int = 0


class ConnectorPayload(BaseModel):
    connector: str
    candidate_id: str | None = None
    service_id: str | None = None
    result: str | None = None
    mode: str | None = None
    purged: int | None = None


_STATUS = ("service.connected", "service.disconnected")
_SYNC = ("sync.started", "sync.completed", "sync.failed")
_CONNECTOR = (
    "connector.discovered",
    "connector.compatibility_checked",
    "connector.resync_requested",
    "connector.data_purged",
)


def register_event_types() -> None:
    register_status_changed()
    for name in _STATUS:
        default_event_types.register(
            EventType(
                name=name,
                owner=OWNER,
                schema=ServiceStatus,
                open_payload=False,
                dedup_fields=("service_id", "dimension", "to_state", "state_seq"),
                retention_class="technical",
                visibility_class="restricted",
                automatable=True,
                live_permission="services.read",
            )
        )
    for name in _SYNC:
        default_event_types.register(
            EventType(
                name=name,
                owner=OWNER,
                schema=SyncPayload,
                open_payload=False,
                dedup_fields=("service_id", "run_id"),
                retention_class="technical",
                visibility_class="restricted",
                automatable=name != "sync.started",
                live_permission="services.read",
            )
        )
    for name in _CONNECTOR:
        default_event_types.register(
            EventType(
                name=name,
                owner=OWNER,
                schema=ConnectorPayload,
                open_payload=False,
                retention_class="technical",
                visibility_class="restricted",
            )
        )


register_event_types()
