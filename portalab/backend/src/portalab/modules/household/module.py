"""Household module facade (spec 032): a member account's profiles — « Who's there? », PINs, the master's
policy for each profile, the access requests, the household page. Switched on or off from the module manager
like every module; the accounts behind the profiles stay identity's (``identity.profile_accounts``)."""

from portalab.capabilities.administration import EXTENSION_STATE_CAPABILITY
from portalab.capabilities.household import CAPABILITY as HOUSEHOLD
from portalab.capabilities.navigation.attention import ATTENTION
from portalab.capabilities.notifications import declare_category, default_categories
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditSink
from portalab.core.db import Database
from portalab.core.time import Clock
from portalab.modules.household import settings as _settings  # noqa: F401 — declares its settings
from portalab.modules.household.service import CATEGORY, HouseholdAttention, HouseholdService

KEY = "household"
OWNER = "module:household"


class HouseholdModule:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        audit: AuditSink,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.service = HouseholdService(database, capabilities, audit, clock=clock)

    def register(self) -> None:
        if not self.capabilities.system_providers(HOUSEHOLD):
            self.capabilities.provide(HOUSEHOLD, self.service, instance_ref=KEY, owner=OWNER)
        if not any(p.instance_ref == KEY for p in self.capabilities.system_providers(ATTENTION)):
            self.capabilities.provide(
                ATTENTION, HouseholdAttention(self.service), instance_ref=KEY, owner=OWNER
            )
        if default_categories.get(CATEGORY) is None:
            declare_category(CATEGORY, OWNER, "household:category", default_channels=("portal", "email"))

    async def enabled(self) -> bool:
        """Switched on in the module manager (every module is, without its toggles)."""
        providers = self.capabilities.system_providers(EXTENSION_STATE_CAPABILITY)
        if not providers:
            return True
        try:
            return bool(await providers[0].provider.enabled("module", KEY))
        except Exception:
            return True
