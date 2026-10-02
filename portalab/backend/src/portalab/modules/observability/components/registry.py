"""Component registry (T012): the contribution model lives in :mod:`portalab.capabilities.observability`
(``declare_observable``) so core modules, plugins and connectors declare components without importing this
module; this module only reads it."""

from portalab.capabilities.observability import (
    Check,
    CheckResult,
    DiagnosticAction,
    ObservableRegistry,
    ObservedComponent,
    declare_observable,
    default_observables,
)

__all__ = [
    "Check",
    "CheckResult",
    "DiagnosticAction",
    "ObservableRegistry",
    "ObservedComponent",
    "declare_observable",
    "default_observables",
]
