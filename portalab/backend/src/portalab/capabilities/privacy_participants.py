"""Privacy participant capability contracts (spec 002 T042, research R11; semantics owned by spec 021).

Every module storing personal data registers:

* a **``privacy.erasure_participant``** — ``erase(user_id, mode)`` deletes or anonymizes what the module
  holds about the user. It MUST be idempotent (the deletion saga retries a failed participant until it
  succeeds) and MUST keep integrity-necessary rows (ledgers, history) referencing the same pseudonymous id;
* a **``privacy.export_contributor``** — ``export(user_id)`` returns the records attributable to the user,
  never secrets (credentials, tokens) and never other users' private data.

The deletion saga and the export builder (identity) discover participants through the capability registry,
so plugins can contribute without any hard-coded table list. ``instance_ref`` identifies a participant in
the saga state; keep it stable (e.g. ``"identity"``, ``"gamification.coins"``).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

ERASURE_CAPABILITY = "privacy.erasure_participant"
EXPORT_CAPABILITY = "privacy.export_contributor"

ErasureMode = Literal["final"]
"""``final``: account final deletion (tombstone). Retention-driven purges are added by spec 021."""


@dataclass(frozen=True, slots=True)
class ExportRecord:
    category: str
    data: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class ErasureParticipant(Protocol):
    async def erase(self, user_id: UUID, mode: ErasureMode) -> None: ...


@runtime_checkable
class ExportContributor(Protocol):
    async def export(self, user_id: UUID) -> Sequence[ExportRecord]: ...


ERASURE_SPEC = CapabilitySpec(
    name=ERASURE_CAPABILITY,
    version="1.0",
    protocol=ErasureParticipant,
    multi_provider=True,
    description="Deletes/anonymizes a user's data at final deletion; idempotent.",
)

EXPORT_SPEC = CapabilitySpec(
    name=EXPORT_CAPABILITY,
    version="1.0",
    protocol=ExportContributor,
    multi_provider=True,
    description="Contributes a user's own records to the personal-data export.",
)
