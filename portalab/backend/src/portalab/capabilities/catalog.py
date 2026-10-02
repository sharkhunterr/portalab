"""Capability contracts known to the kernel, declared once into a fresh registry at start-up."""

from portalab.capabilities import (
    admin_authority,
    aggregation,
    confirmations,
    identity_directory,
    privacy_participants,
    service_data,
    user_grants,
    visibility,
)
from portalab.capabilities.registry import CapabilityRegistry, CapabilitySpec

KERNEL_SPECS: tuple[CapabilitySpec, ...] = (
    admin_authority.SPEC,
    identity_directory.SPEC,
    privacy_participants.ERASURE_SPEC,
    privacy_participants.EXPORT_SPEC,
    user_grants.SPEC,
    confirmations.SPEC,
    service_data.SPEC,
    visibility.PREFERENCE_SPEC,
    aggregation.SPEC,
)


def new_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    for spec in KERNEL_SPECS:
        registry.declare(spec)
    return registry
