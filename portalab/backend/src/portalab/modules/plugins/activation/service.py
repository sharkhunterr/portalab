"""ExtensionActivation (T029; R13, consumed by 015): a Marketplace plugin product is per user — acquiring it
grants ``plugin:<key>.use`` through 003 (the permission every contribution of a ``scope=user`` plugin is
gated by); the plugin itself was installed and enabled by the Admin. Revocation removes the grant."""

from uuid import UUID

from portalab.capabilities.plugins import ActivationStatus
from portalab.capabilities.user_grants import CAPABILITY as USER_GRANTS
from portalab.modules.plugins.lifecycle.service import Lifecycle, PluginNotFound


class Activations:
    def __init__(self, lifecycle: Lifecycle) -> None:
        self.lifecycle = lifecycle

    def _grants(self) -> object | None:
        providers = self.lifecycle.capabilities.system_providers(USER_GRANTS)
        return providers[0].provider if providers else None

    async def status(self, product_ref: str, user: UUID) -> ActivationStatus:
        try:
            plugin = await self.lifecycle.get(product_ref)
        except PluginNotFound:
            return "incompatible"
        if plugin.state == "incompatible":
            return "incompatible"
        if plugin.state != "enabled" or plugin.scope != "user":
            return "failed"
        if plugin.needs_restart:
            return "needs_configuration"
        return "active"

    async def activate_for_user(self, product_ref: str, user: UUID) -> ActivationStatus:
        status = await self.status(product_ref, user)
        if status in ("failed", "incompatible"):
            return status
        grants = self._grants()
        if grants is None:
            return "failed"
        try:
            await grants.grant(user, f"plugin:{product_ref}.use", source=f"marketplace:plugin:{product_ref}")  # type: ignore[attr-defined]
        except Exception:
            return "failed"
        return status

    async def deactivate_for_user(self, product_ref: str, user: UUID) -> None:
        grants = self._grants()
        if grants is not None:
            await grants.revoke(user, f"plugin:{product_ref}.use")  # type: ignore[attr-defined]
