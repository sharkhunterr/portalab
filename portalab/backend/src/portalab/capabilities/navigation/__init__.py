"""``core.navigation`` (spec 004): navigation contributions declared by modules and plugins."""

from portalab.capabilities.navigation.contribution import NavigationContribution, VisibleWhen
from portalab.capabilities.navigation.registry import (
    NavigationRegistry,
    Rejection,
    default_navigation,
    register_contribution,
)

__all__ = [
    "NavigationContribution",
    "NavigationRegistry",
    "Rejection",
    "VisibleWhen",
    "default_navigation",
    "register_contribution",
]
