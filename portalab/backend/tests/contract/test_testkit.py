"""T029 — the conformance kit itself is exercised against a sample provider (and must catch a bad one)."""

from typing import Any, ClassVar, Protocol, runtime_checkable

import pytest
from pydantic import BaseModel, ValidationError

from portalab.capabilities.isolation import ProviderGuard
from portalab.capabilities.results import CapabilityResult
from portalab.capabilities.testkit import CapabilityConformanceKit, FakeExternalService

pytestmark = pytest.mark.contract


class Item(BaseModel):
    id: str
    title: str


@runtime_checkable
class ItemSource(Protocol):
    async def list_items(self) -> Any: ...


class SampleConnector:
    def __init__(self, service: FakeExternalService) -> None:
        self._service = service

    async def list_items(self) -> Any:
        return await self._service.fetch("/items")


def parse_items(payload: Any) -> list[Item]:
    if not isinstance(payload, list):
        raise ValueError("expected a list")
    return [Item.model_validate(entry) for entry in payload]


class TestSampleConnectorConformance(CapabilityConformanceKit):
    capability = "demo.items"
    valid_payload: ClassVar[list[dict[str, str]]] = [{"id": "1", "title": "Alpha"}]

    def make_provider(self, service: FakeExternalService) -> Any:
        return SampleConnector(service)

    async def invoke(self, guard: ProviderGuard, provider: Any) -> CapabilityResult[Any]:
        return await guard.call(provider.list_items, validate=parse_items, external_id="items")


class LeakyConnector(SampleConnector):
    """A badly written provider that swallows errors and returns raw garbage."""

    async def list_items(self) -> Any:
        try:
            return await super().list_items()
        except Exception:
            return None


async def test_kit_detects_a_non_conforming_provider() -> None:
    kit = TestSampleConnectorConformance()
    kit.make_provider = LeakyConnector  # type: ignore[method-assign]
    with pytest.raises(AssertionError):
        await kit.test_conformance_auth_error_is_typed()


def test_parse_items_rejects_bad_entries() -> None:
    with pytest.raises(ValidationError):
        parse_items([{"id": "1"}])
