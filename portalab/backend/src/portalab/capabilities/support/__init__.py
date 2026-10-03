"""Support ports (spec 016 T006; contracts/support-contracts.md).

* ``support.incidents`` — the incident lifecycle, consumed by Health (006) and Observability (025). Its
  contract is declared once, next to its first consumers, in :mod:`portalab.capabilities.health`
  (``INCIDENTS``, ``Incidents``, ``IncidentRef``) and re-exported here;
* ``notifications.send`` — the notification fan-out port implemented by Notifications (010); until then
  incident notifications are skipped (never an error);
* ticket/knowledge/conversion/diagnosis ports arrive with Slice B.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from portalab.capabilities.health import INCIDENTS, IncidentRef, Incidents
from portalab.capabilities.registry import CapabilitySpec

NOTIFY = "notifications.send"

Severity = Literal["minor", "major", "critical"]
IncidentState = Literal["investigating", "identified", "monitoring", "resolved"]
SEVERITIES: tuple[str, ...] = ("minor", "major", "critical")
STATES: tuple[str, ...] = ("investigating", "identified", "monitoring", "resolved")
SEVERITY_ALIASES: Mapping[str, str] = {"info": "minor", "warning": "major", "critical": "critical"}


def normalize_severity(value: str) -> str:
    severity = SEVERITY_ALIASES.get(value, value)
    if severity not in SEVERITIES:
        raise ValueError(f"unknown severity {value!r}")
    return severity


@dataclass(frozen=True, slots=True)
class Audience:
    """Who may receive a notification: holders of ``permission`` (optionally on each listed service)."""

    permission: str
    service_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Notification:
    category: str  # e.g. ``support.incident``
    title_key: str
    args: Mapping[str, Any] = field(default_factory=dict)
    ref: str | None = None  # SPA route
    urgent: bool = False  # critical ⇒ alert channel


@runtime_checkable
class NotificationSender(Protocol):
    async def send(self, notification: Notification, audience: Audience, *, dedup_key: str) -> None: ...


NOTIFY_SPEC = CapabilitySpec(
    name=NOTIFY,
    version="1.0",
    protocol=NotificationSender,
    multi_provider=False,
    description="Notification fan-out by category and audience (Notifications 010).",
)
SPECS: tuple[CapabilitySpec, ...] = (NOTIFY_SPEC,)

__all__ = [
    "INCIDENTS",
    "NOTIFY",
    "SEVERITIES",
    "STATES",
    "Audience",
    "IncidentRef",
    "IncidentState",
    "Incidents",
    "Notification",
    "NotificationSender",
    "Severity",
    "normalize_severity",
]
