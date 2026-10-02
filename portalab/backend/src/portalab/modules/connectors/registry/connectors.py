"""Connector registry (T007, T038): owner-tagged, duplicate keys rejected, manifests validated."""

from portalab.capabilities.connector_sdk import (
    Connector,
    ConnectorRegistry,
    ConnectorRegistryError,
    default_connectors,
    register_connector,
)

__all__ = [
    "Connector",
    "ConnectorRegistry",
    "ConnectorRegistryError",
    "default_connectors",
    "register_connector",
]
