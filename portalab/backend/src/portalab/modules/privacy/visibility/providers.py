"""Resolution of the owner-held preference for a datum class (``privacy.visibility_preference`` providers).

A provider declares the classes it serves in its registration metadata (``{"datum_classes": [...]}``). A
missing provider or a provider failure falls back to the class default — never to public (plan §9).
"""

from uuid import UUID

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.visibility import (
    LEVELS,
    PREFERENCE_CAPABILITY,
    Level,
    VisibilityPreferenceProvider,
)
from portalab.modules.privacy.observability import log, metrics


class PreferenceProviders:
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    def provider_for(self, datum_class: str) -> VisibilityPreferenceProvider | None:
        for registration in self.capabilities.system_providers(PREFERENCE_CAPABILITY):
            if datum_class in registration.metadata.get("datum_classes", ()):
                provider: VisibilityPreferenceProvider = registration.provider
                return provider
        return None

    async def preference(self, subject: UUID, datum_class: str, datum_ref: str | None) -> Level | None:
        provider = self.provider_for(datum_class)
        if provider is None:
            return None
        try:
            level = await provider.get_preference(subject, datum_class, datum_ref)
        except Exception:
            metrics.increment("privacy.provider_failures")
            log.warning("visibility provider failed", extra={"fields": {"datum_class": datum_class}})
            return None
        return level if level in LEVELS else None
