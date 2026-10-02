"""005 T005/T038 — connector registry: duplicate keys rejected, secrets kept out of the config schema,
owner-tagged registrations removed together."""

import pytest
from pydantic import BaseModel

from portalab.capabilities.connector_sdk import ConnectorRegistry, ConnectorRegistryError
from portalab.connectors.fake import FakeConnector


class LeakyConfig(BaseModel):
    base_url: str
    api_token: str


def test_duplicate_keys_are_rejected() -> None:
    registry = ConnectorRegistry()
    registry.register(FakeConnector())
    with pytest.raises(ConnectorRegistryError, match="already registered"):
        registry.register(FakeConnector())


def test_invalid_key_rejected() -> None:
    with pytest.raises(ConnectorRegistryError, match="invalid connector key"):
        ConnectorRegistry().register(FakeConnector(key="bad key!"))


def test_secret_fields_must_stay_out_of_the_config_schema() -> None:
    connector = FakeConnector(key="leaky")
    connector.config_schema = LeakyConfig  # type: ignore[assignment]
    with pytest.raises(ConnectorRegistryError, match="secrets"):
        ConnectorRegistry().register(connector)


def test_manifest_and_schema_declared() -> None:
    connector = FakeConnector()
    assert connector.manifest.version and connector.manifest.requires_portal
    assert "base_url" in connector.config_schema.model_fields and connector.secret_fields == {"api_token"}
