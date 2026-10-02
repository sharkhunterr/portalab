"""Connection test (T016; FR-007..009, US3).

Runs the connector's ``test_connection`` under a timeout and turns any failure into actionable diagnostics
(reachable / authenticated / compatible + a redacted detail). A test never changes the service's state; it
can run on a saved service or on a draft configuration before saving.
"""

import asyncio
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from portalab.capabilities.connector_http import ConnectorHttpError
from portalab.capabilities.connector_sdk import Connector, ServiceHandle, TestResult
from portalab.capabilities.results import ProviderAuthError
from portalab.core.logging import redact_text
from portalab.modules.connectors.http.client import client_for
from portalab.modules.connectors.observability import metric_part, metrics


async def run_connection_test(
    connector: Connector, handle: ServiceHandle, *, limit_seconds: float
) -> TestResult:
    try:
        result = await asyncio.wait_for(connector.test_connection(handle), timeout=limit_seconds)
    except TimeoutError:
        result = TestResult(
            ok=False, reachable=False, authenticated=False, detail="The service did not answer in time."
        )
    except ProviderAuthError:
        result = TestResult(
            ok=False, reachable=True, authenticated=False, detail="The credentials were rejected."
        )
    except ConnectorHttpError as exc:
        result = TestResult(ok=False, reachable=False, authenticated=False, detail=redact_text(str(exc)))
    except Exception as exc:
        result = TestResult(
            ok=False, reachable=False, authenticated=False, detail=f"The test failed ({type(exc).__name__})."
        )
    metrics.increment(f"connectors.tests.{metric_part(connector.key)}.{'ok' if result.ok else 'failed'}")
    return TestResult(
        ok=result.ok,
        reachable=result.reachable,
        authenticated=result.authenticated,
        compatible=result.compatible,
        detail=redact_text(result.detail),
        diagnostics={key: redact_text(str(value)) for key, value in result.diagnostics.items()},
    )


def as_dict(result: TestResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "reachable": result.reachable,
        "authenticated": result.authenticated,
        "compatible": result.compatible,
        "detail": result.detail,
        "diagnostics": dict(result.diagnostics),
    }


class ConnectionTester:
    def __init__(self, manager: Any) -> None:
        self.manager = manager

    async def test_service(
        self,
        service_id: UUID,
        *,
        config: Mapping[str, Any] | None = None,
        secrets: Mapping[str, str] | None = None,
    ) -> TestResult:
        """Test a saved service, optionally with draft overrides (nothing is persisted)."""
        async with self.manager.database.session() as session:
            row = await self.manager._row(session, service_id)
            connector = self.manager.connector(row.connector_key)
            handle = self.manager.handle(row)
        if config or secrets:
            merged = self.manager._validate_config(connector, {**handle.config, **(config or {})})
            handle = self._draft_handle(connector, merged, {**handle.secrets, **(secrets or {})}, service_id)
        compatibility = self.manager.checker.check(connector)
        result = await run_connection_test(
            connector, handle, limit_seconds=self.manager.config.http_timeout_seconds * 3
        )
        if not compatibility.compatible:
            return TestResult(
                ok=False,
                reachable=result.reachable,
                authenticated=result.authenticated,
                compatible=False,
                detail="; ".join(compatibility.reasons),
                diagnostics=result.diagnostics,
            )
        return result

    async def test_draft(
        self, connector_key: str, config: Mapping[str, Any], secrets: Mapping[str, str]
    ) -> TestResult:
        connector = self.manager.connector(connector_key)
        merged = self.manager._validate_config(connector, config)
        handle = self._draft_handle(connector, merged, secrets, None)
        return await run_connection_test(
            connector, handle, limit_seconds=self.manager.config.http_timeout_seconds * 3
        )

    def _draft_handle(
        self,
        connector: Connector,
        config: Mapping[str, Any],
        secrets: Mapping[str, str],
        service_id: UUID | None,
    ) -> ServiceHandle:
        unknown = set(secrets) - set(connector.secret_fields)
        clean = {key: value for key, value in secrets.items() if key not in unknown and value}
        http = client_for(config, clean, self.manager.config, transport=self.manager.hooks.http_transport)
        return ServiceHandle(
            service_id=service_id or UUID(int=0), name="draft", config=dict(config), secrets=clean, http=http
        )
