"""Shared provider helpers: localized labels through the i18n renderer (026) when installed."""

from typing import Any

from portalab.capabilities.i18n import RENDERER, LocaleContext
from portalab.capabilities.registry import CapabilityRegistry


class Labels:
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    def __call__(self, key: str, ctx: LocaleContext, *, namespace: str = "nav") -> str:
        try:
            providers = self.capabilities.system_providers(RENDERER)
            if not providers:
                return key
            renderer: Any = providers[0].provider
            return str(renderer.t(key, ctx, namespace=namespace))
        except Exception:
            return key  # i18n not installed: the key is still a usable label
