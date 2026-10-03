"""Support ports (spec 016 T006; contracts/support-contracts.md).

* ``support.incidents`` — the incident lifecycle, consumed by Health (006) and Observability (025). Its
  contract is declared once, next to its first consumers, in :mod:`portalab.capabilities.health`
  (``INCIDENTS``, ``Incidents``, ``IncidentRef``) and re-exported here;
* incident notifications go through ``notifications.send`` (:mod:`portalab.capabilities.notifications`);
* Slice B: ``support.tickets`` (create/read for AI drafts, automations and Community), the conversion
  target ports owned elsewhere (``gamification.grant_contribution`` by 013, ``community.proposals.create``
  by 012 — absent until those specs land, the conversion option is then disabled with a reason), the
  optional ``support.attachment_scanner`` and the ``support.diagnosis_executor`` the AI capability (018)
  provides to run the diagnosis analysis **as the requesting principal**.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.health import INCIDENTS, IncidentRef, Incidents
from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

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


TICKETS = "support.tickets"
CONTRIBUTIONS = "gamification.grant_contribution"
PROPOSALS = "community.proposals.create"
SCANNER = "support.attachment_scanner"
DIAGNOSIS = "support.diagnosis_executor"


@dataclass(frozen=True, slots=True)
class TicketRequest:
    type_key: str
    title: str
    description: str
    fields: Mapping[str, Any] = field(default_factory=dict)
    service_id: str | None = None
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    tags: Sequence[str] = ()
    source: Literal["manual", "ai_diagnosis", "feedback_conversion", "automation"] = "manual"


@dataclass(frozen=True, slots=True)
class TicketRef:
    id: UUID
    number: int
    state: str
    url: str


@runtime_checkable
class TicketsPort(Protocol):
    async def create(self, request: TicketRequest, principal: Principal) -> TicketRef:
        """Create as ``principal`` (a user, or an automation acting for its author) with the same rules."""
        ...

    async def get_for_viewer(self, ticket_id: UUID, viewer: Principal) -> TicketRef | None: ...


@runtime_checkable
class ContributionGrant(Protocol):
    """013: credit a contribution once per ``source_ref`` (anti-abuse owned by 013)."""

    async def grant_contribution(self, user: UUID, kind: str, source_ref: str, actor: Principal) -> str: ...


@runtime_checkable
class ProposalCreator(Protocol):
    """012: create a Community proposal (``feature`` or ``project``) keeping the provenance."""

    async def create(
        self,
        kind: Literal["feature", "project"],
        title: str,
        body: str,
        author: UUID | None,
        provenance: str,
        actor: Principal,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class ScanVerdict:
    clean: bool
    reason: str = ""


@runtime_checkable
class AttachmentScanner(Protocol):
    async def scan(self, data: bytes, content_type: str) -> ScanVerdict: ...


@dataclass(frozen=True, slots=True)
class DiagnosisFacts:
    """What the deterministic steps found, as the requesting user may see it (real data with ``as_of``)."""

    problem: str
    service: Mapping[str, Any] | None = None
    open_incidents: Sequence[Mapping[str, Any]] = ()
    wiki: Sequence[Mapping[str, Any]] = ()


@dataclass(frozen=True, slots=True)
class DiagnosisAnalysis:
    """AI interpretation — always labelled as such, never a ticket."""

    summary: str
    proposed_solution: str = ""
    suggested_title: str = ""
    suggested_type: str = "other"
    suggested_fields: Mapping[str, Any] = field(default_factory=dict)
    solved: bool = False


@runtime_checkable
class DiagnosisExecutor(Protocol):
    async def analyze(self, facts: DiagnosisFacts, principal: Principal) -> DiagnosisAnalysis: ...


def _spec(name: str, protocol: type[Any], multi: bool, description: str) -> CapabilitySpec:
    return CapabilitySpec(
        name=name, version="1.0", protocol=protocol, multi_provider=multi, description=description
    )


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(TICKETS, TicketsPort, False, "Support tickets (016)"),
    _spec(CONTRIBUTIONS, ContributionGrant, False, "Credit a contribution (Gamification 013)"),
    _spec(PROPOSALS, ProposalCreator, False, "Create a Community proposal (Community 012)"),
    _spec(SCANNER, AttachmentScanner, False, "Optional attachment scanner"),
    _spec(DIAGNOSIS, DiagnosisExecutor, False, "AI analysis step of the support diagnosis (AI 018)"),
)

__all__ = [
    "CONTRIBUTIONS",
    "DIAGNOSIS",
    "INCIDENTS",
    "PROPOSALS",
    "SCANNER",
    "SEVERITIES",
    "STATES",
    "TICKETS",
    "AttachmentScanner",
    "ContributionGrant",
    "DiagnosisAnalysis",
    "DiagnosisExecutor",
    "DiagnosisFacts",
    "IncidentRef",
    "IncidentState",
    "Incidents",
    "ProposalCreator",
    "ScanVerdict",
    "Severity",
    "TicketRef",
    "TicketRequest",
    "TicketsPort",
    "normalize_severity",
]
