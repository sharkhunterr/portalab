"""Content helper module facade (spec 011): assets, link resolution, render preview."""

from dataclasses import replace
from typing import Any
from uuid import UUID

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.content import LinkResolverRegistry, default_link_resolvers
from portalab.capabilities.notifications import EMAIL_IMAGES
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.core.time import Clock
from portalab.modules.content import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.content.service import ContentService
from portalab.modules.content.settings import SETTINGS, ContentConfig

OWNER = "module:content"
log = get_logger("portalab.content")


class _Participant:
    def __init__(self, service: ContentService) -> None:
        self.service = service

    async def erase(self, user_id, mode) -> None:  # type: ignore[no-untyped-def]
        await self.service.erase_uploader(user_id)


class ContentModule:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        blobs: BlobStore | None = None,
        resolvers: LinkResolverRegistry = default_link_resolvers,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.config = ContentConfig()
        self.service = ContentService(database, authorizer, blobs, resolvers, clock=clock)

    def register(self) -> None:
        if not any(
            p.instance_ref == "content" for p in self.capabilities.system_providers(ERASURE_CAPABILITY)
        ):
            self.capabilities.provide(
                ERASURE_CAPABILITY, _Participant(self.service), instance_ref="content", owner=OWNER
            )
        if not any(p.instance_ref == "content" for p in self.capabilities.system_providers(EMAIL_IMAGES)):
            # issue 411: an article's pictures travel in the e-mail that carries it — read as its recipient
            self.capabilities.provide(
                EMAIL_IMAGES, _EmailPictures(self.service), instance_ref="content", owner=OWNER
            )

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                values = {
                    name: (await providers[0].provider.get(key)).value for name, key in SETTINGS.items()
                }
                self.config = replace(self.config, **values)
        except Exception:
            log.warning("content configuration not refreshed")


class _EmailPictures:
    """Issue 411: « /api/v1/content/assets/<id> » for an e-mail's recipient — only what they may see."""

    prefix = "/api/v1/content/assets/"

    def __init__(self, service: Any) -> None:
        self.service = service

    async def image(self, path: str, reader: UUID | None) -> bytes | None:
        if reader is None:
            return None
        try:
            asset = UUID(path)
        except ValueError:
            return None
        try:
            data, content_type = await self.service.read(asset, Principal(user_id=reader))
        except Exception:
            return None
        return bytes(data) if str(content_type).startswith("image/") else None
