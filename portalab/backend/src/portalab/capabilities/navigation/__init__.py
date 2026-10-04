"""``core.navigation`` (spec 004): navigation contributions declared by modules and plugins."""

from portalab.capabilities.navigation.contribution import NavigationContribution, VisibleWhen
from portalab.capabilities.navigation.registry import (
    NavigationRegistry,
    Rejection,
    default_navigation,
    register_contribution,
    register_section,
)
from portalab.capabilities.navigation.sections import (
    FALLBACK_SECTION,
    LEGACY_GROUP,
    NavigationSection,
    SectionTopic,
)

__all__ = [
    "FALLBACK_SECTION",
    "LEGACY_GROUP",
    "NavigationContribution",
    "NavigationRegistry",
    "NavigationSection",
    "Rejection",
    "SectionTopic",
    "VisibleWhen",
    "default_navigation",
    "register_contribution",
    "register_section",
]
