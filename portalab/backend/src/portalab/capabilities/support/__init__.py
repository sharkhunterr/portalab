"""Support ports (spec 016 T006; contracts/support-contracts.md).

* ``support.incidents`` — the incident lifecycle, consumed by Health (006) and Observability (025). Its
  contract is declared once, next to its first consumers, in :mod:`portalab.capabilities.health`
  (``INCIDENTS``, ``Incidents``, ``IncidentRef``) and re-exported here;
* incident notifications go through ``notifications.send`` (:mod:`portalab.capabilities.notifications`);
* ticket/knowledge/conversion/diagnosis ports arrive with Slice B.
"""

from collections.abc import Mapping
from typing import Literal

from portalab.capabilities.health import INCIDENTS, IncidentRef, Incidents
from portalab.capabilities.registry import CapabilitySpec

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


SPECS: tuple[CapabilitySpec, ...] = ()

__all__ = [
    "INCIDENTS",
    "SEVERITIES",
    "STATES",
    "IncidentRef",
    "IncidentState",
    "Incidents",
    "Severity",
    "normalize_severity",
]
