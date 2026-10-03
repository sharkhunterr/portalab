"""Identity guard (T013; R5, R6): an automation acts as ``Principal(channel="automation", acting_for=author)``
— never with more rights than its author **today** (re-evaluated at every action). A *system* identity is
the author's rights further restricted to the scopes declared at publish. A refusal flags the automation
``needs_review``."""

from portalab.capabilities.automation_actions import ActionType
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Authorizer, Principal
from portalab.modules.automations.models import Automation


def principal_of(automation: Automation) -> Principal:
    return Principal(channel="automation", acting_for=automation.owner_user_id)


class IdentityGuard:
    def __init__(self, authorizer: Authorizer, capabilities: CapabilityRegistry | None = None) -> None:
        self.authorizer = authorizer
        self.capabilities = capabilities

    async def author_active(self, automation: Automation) -> bool:
        """A suspended, deactivated or deleted author's automations act for nobody (fail closed)."""
        if self.capabilities is None:
            return True
        providers = self.capabilities.system_providers(DIRECTORY)
        if not providers:
            return True
        try:
            return bool(await providers[0].provider.is_active_account(automation.owner_user_id))
        except Exception:
            return False

    async def allowed(self, automation: Automation, action: ActionType) -> bool:
        if automation.identity_kind == "system" and action.permission not in (automation.system_scopes or []):
            return False
        if not await self.author_active(automation):
            return False
        try:
            return await self.authorizer.is_allowed(principal_of(automation), action.permission)
        except Exception:
            return False

    async def may_publish(self, publisher: Principal, scopes: list[str]) -> list[str]:
        """Scopes the publisher does not hold themselves (a system identity never exceeds its publisher)."""
        return [s for s in scopes if not await self.authorizer.is_allowed(publisher, s)]
