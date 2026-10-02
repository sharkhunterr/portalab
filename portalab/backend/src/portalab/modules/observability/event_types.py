"""Event types owned by Observability (FR-036): only *important* observations go to the business event
store (007); raw metrics stay in the observability store."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, default_event_types

OWNER = "module:observability"


class HealthChanged(BaseModel):
    component: str
    axis: str
    from_state: str | None = None
    to_state: str
    seq: int
    status: str


class ErrorRecorded(BaseModel):
    error_id: str
    component: str
    category: str
    change: str


class AnomalyDetected(BaseModel):
    anomaly_id: str
    detector: str
    component: str
    severity: str


class AlertRaised(BaseModel):
    alert: str
    severity: str
    component: str
    title: str


class DiagnosticPerformed(BaseModel):
    action: str
    component: str
    result: str


for _name, _schema, _dedup in (
    ("observability.health_changed", HealthChanged, ("component", "axis", "to_state", "seq")),
    ("observability.error_recorded", ErrorRecorded, ()),
    ("observability.anomaly_detected", AnomalyDetected, ("anomaly_id",)),
    ("observability.alert_raised", AlertRaised, ()),
    ("observability.diagnostic_action_performed", DiagnosticPerformed, ()),
):
    default_event_types.register(
        EventType(
            name=_name,
            owner=OWNER,
            schema=_schema,
            open_payload=False,
            dedup_fields=_dedup,
            retention_class="technical",
            visibility_class="restricted",
            automatable=True,
            live_permission="observability.read",
        )
    )
