"""005 T032 — the connector ConformanceKit, run against the ``fake`` connector."""

from uuid import uuid4

from portalab.capabilities.connector_sdk import Connector, ServiceHandle
from portalab.connectors.conformance import ConformanceKit, Scenario
from portalab.connectors.fake import BACKENDS, FakeBackend, FakeConnector

TOKEN = "fake-credential"


class TestFakeConnector(ConformanceKit):
    limit_seconds = 0.2

    def make_connector(self) -> Connector:
        return FakeConnector()

    def make_handle(self, scenario: Scenario) -> ServiceHandle:
        url = f"http://conformance-{uuid4().hex[:8]}.lan"
        remote = FakeBackend()
        remote.put("a", at=1, title="A")
        remote.put("b", at=2, title="B")
        remote.mode = {
            "ok": "ok",
            "slow": "hang",
            "garbage": "garbage",
            "auth_error": "auth_error",
            "down": "error",
        }[scenario]
        BACKENDS[url] = remote
        return ServiceHandle(
            service_id=uuid4(), name="kit", config={"base_url": url}, secrets={"api_token": TOKEN}
        )
