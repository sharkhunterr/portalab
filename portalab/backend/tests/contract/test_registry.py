"""T024 — CapabilityRegistry: provide/resolve, deterministic priority ordering, NoProvider,
permission-filtered resolution."""

from typing import Protocol, runtime_checkable
from uuid import uuid4

import pytest

from portalab.capabilities.registry import CapabilityError, CapabilityRegistry, CapabilitySpec
from portalab.capabilities.results import NoProvider
from portalab.core.authz_port import DenyAllAuthorizer, Principal, ResourceRef

pytestmark = pytest.mark.contract


@runtime_checkable
class Greeter(Protocol):
    async def greet(self, name: str) -> str: ...


class EnglishGreeter:
    async def greet(self, name: str) -> str:
        return f"Hello {name}"


class FrenchGreeter:
    async def greet(self, name: str) -> str:
        return f"Bonjour {name}"


class NotAGreeter:
    async def wave(self) -> None: ...


class AllowInstances:
    def __init__(self, allowed: set[str]) -> None:
        self.allowed = allowed
        self.calls: list[tuple[str, str | None]] = []

    async def is_allowed(
        self, principal: Principal, permission: str, resource: ResourceRef | None = None
    ) -> bool:
        self.calls.append((permission, resource.id if resource else None))
        return resource is not None and resource.id in self.allowed


USER = Principal(user_id=uuid4())


def _registry(*, multi: bool = True, permission: str | None = None) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.declare(
        CapabilitySpec(
            name="demo.greeter",
            version="1.0",
            protocol=Greeter,
            multi_provider=multi,
            required_permission=permission,
        )
    )
    return registry


async def test_provide_then_resolve() -> None:
    registry = _registry()
    registry.provide("demo.greeter", EnglishGreeter(), instance_ref="svc-en")
    providers = await registry.resolve("demo.greeter", principal=USER)
    assert [p.instance_ref for p in providers] == ["svc-en"]
    assert await providers[0].provider.greet("Ada") == "Hello Ada"


async def test_two_providers_are_ordered_deterministically_by_priority_then_ref() -> None:
    registry = _registry()
    registry.provide("demo.greeter", FrenchGreeter(), instance_ref="svc-fr", priority=20)
    registry.provide("demo.greeter", EnglishGreeter(), instance_ref="svc-en-b", priority=10)
    registry.provide("demo.greeter", EnglishGreeter(), instance_ref="svc-en-a", priority=10)
    for _ in range(3):
        refs = [p.instance_ref for p in await registry.resolve("demo.greeter", principal=USER)]
        assert refs == ["svc-en-a", "svc-en-b", "svc-fr"]


async def test_consumer_works_with_either_provider() -> None:
    for provider, expected in ((EnglishGreeter(), "Hello Ada"), (FrenchGreeter(), "Bonjour Ada")):
        registry = _registry()
        registry.provide("demo.greeter", provider, instance_ref="svc")
        chosen = await registry.resolve_first("demo.greeter", principal=USER)
        assert not isinstance(chosen, NoProvider)
        assert await chosen.provider.greet("Ada") == expected


async def test_no_provider_is_a_typed_result_not_an_exception() -> None:
    registry = _registry()
    result = await registry.resolve_first("demo.greeter", principal=USER)
    assert isinstance(result, NoProvider)
    assert result.state == "no_provider"
    assert result.capability == "demo.greeter"


async def test_permission_filtered_resolution_uses_authorizer_port() -> None:
    registry = _registry(permission="services.read")
    registry.provide("demo.greeter", EnglishGreeter(), instance_ref="svc-a")
    registry.provide("demo.greeter", FrenchGreeter(), instance_ref="svc-b")
    authorizer = AllowInstances({"svc-b"})
    providers = await registry.resolve("demo.greeter", principal=USER, authorizer=authorizer)
    assert [p.instance_ref for p in providers] == ["svc-b"]
    assert ("services.read", "svc-a") in authorizer.calls
    denied = await registry.resolve_first("demo.greeter", principal=USER, authorizer=DenyAllAuthorizer())
    assert isinstance(denied, NoProvider)


async def test_permission_required_without_authorizer_denies() -> None:
    registry = _registry(permission="services.read")
    registry.provide("demo.greeter", EnglishGreeter(), instance_ref="svc-a")
    assert await registry.resolve("demo.greeter", principal=USER) == []


def test_single_provider_capability_rejects_a_second_provider() -> None:
    registry = _registry(multi=False)
    registry.provide("demo.greeter", EnglishGreeter(), instance_ref="svc-a")
    with pytest.raises(CapabilityError):
        registry.provide("demo.greeter", FrenchGreeter(), instance_ref="svc-b")


def test_unknown_capability_and_duplicates_are_rejected() -> None:
    registry = _registry()
    with pytest.raises(CapabilityError):
        registry.provide("demo.unknown", EnglishGreeter(), instance_ref="svc")
    with pytest.raises(CapabilityError):
        registry.declare(CapabilitySpec(name="demo.greeter", version="1.0", protocol=Greeter))
    registry.provide("demo.greeter", EnglishGreeter(), instance_ref="svc")
    with pytest.raises(CapabilityError):
        registry.provide("demo.greeter", EnglishGreeter(), instance_ref="svc")


def test_provider_must_implement_the_protocol() -> None:
    registry = _registry()
    with pytest.raises(CapabilityError):
        registry.provide("demo.greeter", NotAGreeter(), instance_ref="svc")


async def test_withdraw_and_unregister_owner() -> None:
    registry = _registry()
    registry.provide("demo.greeter", EnglishGreeter(), instance_ref="svc-a", owner="connector:demo")
    registry.provide("demo.greeter", FrenchGreeter(), instance_ref="svc-b", owner="plugin:fr")
    registry.withdraw("demo.greeter", "svc-a")
    assert [p.instance_ref for p in await registry.resolve("demo.greeter", principal=USER)] == ["svc-b"]
    registry.unregister("plugin:fr")
    assert await registry.resolve("demo.greeter", principal=USER) == []


def test_spec_metadata_is_queryable() -> None:
    registry = _registry(permission="services.read")
    spec = registry.spec("demo.greeter")
    assert spec.version == "1.0"
    assert spec.required_permission == "services.read"
    assert [s.name for s in registry.specs()] == ["demo.greeter"]
