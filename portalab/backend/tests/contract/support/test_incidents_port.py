"""016 T004/T015 — the real ``support.incidents`` port and the in-memory reference used by 006/025 tests
pass the same conformance kit."""

from typing import Any
from uuid import UUID

import pytest

from portalab.capabilities.health import Incidents
from portalab.capabilities.support.testkit import IncidentsPortContractKit, InMemoryIncidents
from portalab.core.authz_port import Principal
from tests.integration.support.conftest import SupportHarness


class TestInMemoryIncidents(IncidentsPortContractKit):
    async def make_port(self) -> Incidents:
        return InMemoryIncidents()

    async def resolve(self, port: Any, incident_id: str) -> None:
        port.resolve(incident_id)


@pytest.mark.integration
class TestSupportPort(IncidentsPortContractKit):
    @pytest.fixture(autouse=True)
    def _harness(self, support: SupportHarness) -> None:
        self.harness = support

    async def make_port(self) -> Incidents:
        return self.harness.module.port

    async def resolve(self, port: Any, incident_id: str) -> None:
        await self.harness.module.incidents.resolve(
            Principal(channel="system"), UUID(incident_id), message="done"
        )
