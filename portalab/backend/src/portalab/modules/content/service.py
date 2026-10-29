"""Assets and links (T007; R4, R5): uploads are sniffed by magic bytes, size-limited, images re-encoded
(metadata stripped) through the shared ``core.uploads`` helper, stored in the blob store and bound to an
owning object; an asset is readable only by viewers who may read that owner (resolved through the owner's
``LinkResolver``) — or by its uploader. Link resolution is batched per viewer and never leaks a title for
a forbidden target."""

import asyncio
import hashlib
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import update

from portalab.capabilities.content import ContentError, ContentRef, LinkResolverRegistry, ResolvedLink
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.errors import Forbidden, NotFound, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.core.uploads import IMAGE_TYPES, UnsafeUpload, clean_upload
from portalab.modules.content.models import Asset
from portalab.modules.content.permissions import EDIT_PERMISSION

MAX_BYTES = 10 * 1024 * 1024
MAX_REFS = 200


class AssetNotFound(NotFound):
    default_code = "content.asset_not_found"
    default_title = "Asset not found"


class UnsafeAsset(ValidationFailed):
    default_code = "content.unsafe_upload"
    default_title = "This file cannot be uploaded"


@dataclass(frozen=True, slots=True)
class AssetView:
    id: UUID
    owner_ref: str
    content_type: str
    filename: str
    size: int
    markdown: str


class ContentService:
    def __init__(
        self,
        database: Database,
        authorizer: Authorizer,
        blobs: BlobStore | None,
        resolvers: LinkResolverRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.authorizer = authorizer
        self.blobs = blobs
        self.resolvers = resolvers
        self.clock = clock

    async def resolve(self, refs: Sequence[str], viewer: Principal) -> list[ResolvedLink]:
        wanted = list(dict.fromkeys(refs))[:MAX_REFS]
        by_kind: dict[str, list[ContentRef]] = defaultdict(list)
        out: dict[str, ResolvedLink] = {}
        for value in wanted:
            try:
                ref = ContentRef.parse(value)
            except ContentError:
                out[value] = ResolvedLink(value, "unavailable")
                continue
            by_kind[ref.kind].append(ref)
        for kind, items in by_kind.items():
            resolver = self.resolvers.get(kind)
            answers: dict[str, ResolvedLink] = {}
            if resolver is not None:
                try:
                    answers = await resolver.resolve(items, viewer)
                except Exception:
                    answers = {}
            for ref in items:
                key = ref.format()
                found = answers.get(key) or ResolvedLink(key, "unavailable")
                out[key] = found if found.state in ("ok", "archived") else ResolvedLink(key, found.state)
        return [out[value] if value in out else ResolvedLink(value, "unavailable") for value in wanted]

    async def upload(self, data: bytes, filename: str, owner_ref: str, actor: Principal) -> AssetView:
        if self.blobs is None:
            raise UnsafeAsset("Uploads are not available.")
        try:
            owner = ContentRef.parse(owner_ref)
        except ContentError as exc:
            raise ValidationFailed("Upload to a page or an article.", code="content.invalid_owner") from exc
        permission = EDIT_PERMISSION.get(owner.kind)
        if permission is None or not await self.authorizer.is_allowed(actor, permission):
            raise Forbidden("You cannot add files to this content.")
        [state] = await self.resolve([owner.format()], actor)
        if state.state not in ("ok", "archived"):
            raise Forbidden("You cannot add files to this content.")
        try:
            clean = await asyncio.to_thread(  # #274: decoded off the event loop
                clean_upload, data, filename, allowed=IMAGE_TYPES, max_bytes=MAX_BYTES
            )
        except UnsafeUpload as exc:
            raise UnsafeAsset(
                "This file is not an accepted image.", extensions={"reason": exc.reason}
            ) from exc
        stored = await self.blobs.put("content", clean.data, content_type=clean.content_type)
        async with self.database.unit_of_work() as uow:
            row = Asset(
                owner_ref=owner.format(),
                blob_key=stored.key,
                content_type=clean.content_type,
                filename=clean.filename,
                sha256=hashlib.sha256(clean.data).hexdigest(),
                size=len(clean.data),
                uploaded_by=actor.acting_for or actor.user_id,
                created_at=utc_now(self.clock),
            )
            uow.session.add(row)
            await uow.session.flush()
            return AssetView(
                row.id,
                row.owner_ref,
                row.content_type,
                row.filename,
                row.size,
                f"![{row.filename}](portalab-asset:{row.id})",
            )

    async def read(self, asset_id: UUID, viewer: Principal) -> tuple[bytes, str]:
        async with self.database.session() as session:
            row = await session.get(Asset, asset_id)
        if row is None or self.blobs is None:
            raise AssetNotFound("This file does not exist.")
        mine = row.uploaded_by is not None and row.uploaded_by == (viewer.acting_for or viewer.user_id)
        if not mine:
            [state] = await self.resolve([row.owner_ref], viewer)
            if state.state not in ("ok", "archived"):
                raise AssetNotFound("This file does not exist.")  # never reveal a forbidden owner's file
        return await self.blobs.get(row.blob_key), row.content_type

    async def erase_uploader(self, user: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(update(Asset).where(Asset.uploaded_by == user).values(uploaded_by=None))
