"""Capability contracts known to the kernel, declared once into a fresh registry at start-up."""

from portalab.capabilities import (
    admin_authority,
    administration,
    aggregation,
    config,
    confirmations,
    dashboard,
    events,
    health,
    i18n,
    identity_directory,
    observability,
    privacy_participants,
    search,
    service_data,
    support,
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
    user_grants.ROLES_SPEC,
    confirmations.SPEC,
    service_data.SPEC,
    visibility.PREFERENCE_SPEC,
    aggregation.SPEC,
    config.SPEC,
    config.LOCALE_SPEC,
    config.I18N_SPEC,
    *administration.SPECS,
    *health.SPECS,
    *observability.SPECS,
    events.STATS_SPEC,
    *i18n.SPECS,
    *search.SPECS,
    *dashboard.SPECS,
    *support.SPECS,
)


def new_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    for spec in KERNEL_SPECS:
        registry.declare(spec)
    return registry
