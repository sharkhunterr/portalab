"""``ConnectorHttpClient`` factory (T008): builds the shared client from the connectors settings."""

from collections.abc import Mapping
from typing import Any

from portalab.capabilities.connector_http import (
    ConnectorHttpClient,
    ConnectorHttpError,
    RedirectRefused,
    ResponseTooLarge,
)
from portalab.modules.connectors.settings import ConnectorsConfig

__all__ = ["ConnectorHttpClient", "ConnectorHttpError", "RedirectRefused", "ResponseTooLarge", "client_for"]


def client_for(
    config: Mapping[str, Any], secrets: Mapping[str, str], settings: ConnectorsConfig, **kwargs: Any
) -> ConnectorHttpClient | None:
    base_url = config.get("base_url")
    if not isinstance(base_url, str) or not base_url:
        return None
    return ConnectorHttpClient(
        base_url,
        timeout_seconds=settings.http_timeout_seconds,
        max_response_bytes=settings.http_max_response_bytes,
        retries=settings.http_retries,
        verify_tls=bool(config.get("verify_tls", True)),
        secrets=secrets,
        **kwargs,
    )
