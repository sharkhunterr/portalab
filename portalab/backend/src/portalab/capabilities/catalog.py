"""Capability contracts known to the kernel, declared once into a fresh registry at start-up."""

from portalab.capabilities import (
    activity,
    admin_authority,
    administration,
    aggregation,
    ai,
    config,
    confirmations,
    content,
    dashboard,
    economy,
    events,
    health,
    i18n,
    identity_directory,
    media,
    media_core,
    notifications,
    observability,
    privacy_participants,
    search,
    service_data,
    statistics,
    support,
    user_grants,
    visibility,
)
from portalab.capabilities.registry import CapabilityRegistry, CapabilitySpec

KERNEL_SPECS: tuple[CapabilitySpec, ...] = (
    admin_authority.SPEC,
    identity_directory.SPEC,
    identity_directory.CONTACT_SPEC,
    identity_directory.VERIFICATION_SPEC,
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
    *notifications.SPECS,
    *statistics.SPECS,
    *media.SPECS,
    *media_core.SPECS,
    activity.SPEC,
    *content.SPECS,
    *ai.SPECS,
    *economy.SPECS,
)


def new_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    for spec in KERNEL_SPECS:
        registry.declare(spec)
    return registry
