"""Connector SDK (T007). The contract lives in :mod:`portalab.capabilities.connector_sdk` so connector
packages (``portalab.connectors.*``, plugins) implement it without importing this module."""

from portalab.capabilities.connector_sdk import (
    Candidate,
    CapabilityBinding,
    Connector,
    Manifest,
    ServiceHandle,
    SourceRecord,
    SyncContext,
    SyncProgress,
    TestResult,
)

__all__ = [
    "Candidate",
    "CapabilityBinding",
    "Connector",
    "Manifest",
    "ServiceHandle",
    "SourceRecord",
    "SyncContext",
    "SyncProgress",
    "TestResult",
]
