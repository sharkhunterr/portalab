"""CapabilityRegistry — declare / provide / resolve (contracts/capability-contract.md).

Modules depend on capability *contracts*, never on concrete services. Providers (connectors or modules)
register per service instance; consumers resolve the providers the acting principal may use, in a
deterministic order (admin-configured priority, then instance reference). The registry is in-memory and
rebuilt at start-up; every registration is owner-tagged so a disabled plugin/connector can be removed
cleanly (spec 023 conformance sweep).
"""

from dataclasses import dataclass, field
from typing import Any

from portalab.capabilities.results import NoProvider
from portalab.core.authz_port import Authorizer, Principal, ResourceRef


class CapabilityError(ValueError):
    """Programming/configuration error in capability declaration or provision."""


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    name: str
    version: str
    protocol: type[Any]
    required_permission: str | None = None
    multi_provider: bool = True
    description: str = ""


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
    capability: str
    provider: Any
    instance_ref: str
    priority: int = 100
    owner: str = "core"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def sort_key(self) -> tuple[int, str]:
        return (self.priority, self.instance_ref)


class CapabilityRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, CapabilitySpec] = {}
        self._providers: dict[str, dict[str, ProviderRegistration]] = {}

    # --- declaration -------------------------------------------------------------------------------
    def declare(self, spec: CapabilitySpec) -> None:
        if spec.name in self._specs:
            raise CapabilityError(f"capability {spec.name!r} is already declared")
        self._specs[spec.name] = spec
        self._providers[spec.name] = {}

    def spec(self, name: str) -> CapabilitySpec:
        try:
            return self._specs[name]
        except KeyError as exc:
            raise CapabilityError(f"capability {name!r} is not declared") from exc

    def specs(self) -> list[CapabilitySpec]:
        return [self._specs[name] for name in sorted(self._specs)]

    # --- provision ---------------------------------------------------------------------------------
    def provide(
        self,
        name: str,
        provider: Any,
        *,
        instance_ref: str,
        priority: int = 100,
        owner: str = "core",
        metadata: dict[str, Any] | None = None,
    ) -> ProviderRegistration:
        spec = self.spec(name)
        if _is_runtime_protocol(spec.protocol) and not isinstance(provider, spec.protocol):
            raise CapabilityError(f"provider for {name!r} does not implement {spec.protocol.__name__}")
        existing = self._providers[name]
        if instance_ref in existing:
            raise CapabilityError(f"{name!r} already has a provider for instance {instance_ref!r}")
        if existing and not spec.multi_provider:
            raise CapabilityError(f"capability {name!r} accepts a single provider")
        registration = ProviderRegistration(
            capability=name,
            provider=provider,
            instance_ref=instance_ref,
            priority=priority,
            owner=owner,
            metadata=dict(metadata or {}),
        )
        existing[instance_ref] = registration
        return registration

    def withdraw(self, name: str, instance_ref: str) -> None:
        self.spec(name)
        self._providers[name].pop(instance_ref, None)

    def unregister(self, owner: str) -> int:
        """Remove every provider registered by ``owner``; returns how many were removed."""
        removed = 0
        for providers in self._providers.values():
            for ref in [ref for ref, reg in providers.items() if reg.owner == owner]:
                del providers[ref]
                removed += 1
        return removed

    # --- resolution --------------------------------------------------------------------------------
    def system_providers(self, name: str) -> list[ProviderRegistration]:
        """All providers ordered by (priority, instance_ref), for *system* use (sagas, kernel wiring).

        Never use this on behalf of a user: user-initiated access goes through :meth:`resolve`.
        """
        self.spec(name)
        return sorted(self._providers[name].values(), key=lambda reg: reg.sort_key)

    async def resolve(
        self,
        name: str,
        *,
        principal: Principal,
        authorizer: Authorizer | None = None,
    ) -> list[ProviderRegistration]:
        """Providers the principal may use, ordered by (priority, instance_ref)."""
        spec = self.spec(name)
        candidates = sorted(self._providers[name].values(), key=lambda reg: reg.sort_key)
        if spec.required_permission is None:
            return candidates
        if authorizer is None:
            return []  # deny by default when a permission is required but no authorizer is supplied
        allowed: list[ProviderRegistration] = []
        for registration in candidates:
            resource = ResourceRef(kind="service", id=registration.instance_ref)
            if await authorizer.is_allowed(principal, spec.required_permission, resource):
                allowed.append(registration)
        return allowed

    async def resolve_first(
        self,
        name: str,
        *,
        principal: Principal,
        authorizer: Authorizer | None = None,
    ) -> ProviderRegistration | NoProvider[Any]:
        providers = await self.resolve(name, principal=principal, authorizer=authorizer)
        if not providers:
            return NoProvider(capability=name, detail=f"no usable provider for {name}")
        return providers[0]


def _is_runtime_protocol(protocol: type[Any]) -> bool:
    return bool(getattr(protocol, "_is_runtime_protocol", False))
