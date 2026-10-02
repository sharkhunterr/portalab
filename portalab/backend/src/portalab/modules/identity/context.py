"""Dependencies of the identity services, wired once by the composition root (tests wire fakes)."""

from dataclasses import dataclass, field
from datetime import datetime

from portalab.capabilities.admin_authority import CAPABILITY as ADMIN_AUTHORITY
from portalab.capabilities.admin_authority import AdminAuthority
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.errors import Unavailable
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, SystemClock, utc_now
from portalab.modules.identity.settings import IdentityConfig

OWNER = "module:identity"


@dataclass
class IdentityContext:
    database: Database
    events: EventPublisher
    audit: AuditSink
    capabilities: CapabilityRegistry
    blobs: BlobStore
    authorizer: Authorizer
    config: IdentityConfig = field(default_factory=IdentityConfig)
    clock: Clock = field(default_factory=SystemClock)

    def now(self) -> datetime:
        return utc_now(self.clock)

    def admin_authority(self) -> AdminAuthority:
        """The single-Admin authority (spec 003); unavailable ⇒ fail closed."""
        providers = self.capabilities.system_providers(ADMIN_AUTHORITY)
        if not providers:
            raise Unavailable(
                "The authorization module is not available.", code="authz.admin_authority_unavailable"
            )
        provider: AdminAuthority = providers[0].provider
        return provider
