"""Profile looks (027, Steam-like): a member equips a banner, an avatar frame or a film backdrop banner on
their profile. Designs are drawn by the interface; the ones a product sells are worn by their owners only
(directly or through a pack), the others by everyone. The film backdrop banner is a feature: owning the
« profile_backdrop » product (when one is sold) unlocks every film or series with a TMDB backdrop."""

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.themes import AVATAR_FRAMES, PROFILE_BANNERS, PROFILE_SLOTS
from portalab.core.db import Database
from portalab.core.errors import ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.entitlements.reader import CosmeticsReader
from portalab.modules.marketplace.models import Equipped

BACKDROP_REF = re.compile(r"^/[A-Za-z0-9_-]{1,64}\.(jpg|jpeg|png)$")
CHOICES = {"banner": PROFILE_BANNERS, "frame": AVATAR_FRAMES}


class LookLocked(ValidationFailed):
    default_code = "marketplace.look_locked"
    default_title = "Sold in the shop"


class ProfileLooks:
    def __init__(self, database: Database, cosmetics: CosmeticsReader, *, clock: Clock | None = None) -> None:
        self.database = database
        self.cosmetics = cosmetics
        self.clock = clock

    async def locked(self, user: UUID, slot: str) -> frozenset[str]:
        kind, field = PROFILE_SLOTS[slot]
        return frozenset(
            await self.cosmetics.sold(kind, field) - await self.cosmetics.owned(user, kind, field)
        )

    async def backdrop_unlocked(self, user: UUID) -> bool:
        sold = await self.cosmetics.sold("profile_backdrop", "feature")
        if not sold:
            return True  # nobody sells it: a free feature
        return bool(await self.cosmetics.owned(user, "profile_backdrop", "feature"))

    async def catalog(self, user: UUID) -> dict[str, Any]:
        banners, frames = await self.locked(user, "banner"), await self.locked(user, "frame")
        return {
            "banners": [{"key": k, "locked": k in banners} for k in PROFILE_BANNERS],
            "frames": [{"key": k, "locked": k in frames} for k in AVATAR_FRAMES],
            "backdrop": {"unlocked": await self.backdrop_unlocked(user)},
            "equipped": await self.cosmetics.equipped(user),
        }

    async def equip(self, user: UUID, slot: str, value: Any) -> dict[str, Any]:
        """Wear ``value`` in ``slot`` (``None`` takes it off); refused when sold and not owned."""
        if slot not in ("banner", "frame", "backdrop"):
            raise ValidationFailed("Unknown profile slot.", code="marketplace.invalid_look")
        stored: dict[str, Any] | None = None
        if value is not None:
            if slot == "backdrop":
                if not await self.backdrop_unlocked(user):
                    raise LookLocked("The film backdrop banner is sold in the shop: buy it to use it.")
                try:
                    object_id = str(UUID(str(value.get("object_id"))))
                except (AttributeError, ValueError) as exc:
                    raise ValidationFailed(
                        "Pick a film or a series.", code="marketplace.invalid_look"
                    ) from exc
                ref = str(value.get("ref") or "")
                if not BACKDROP_REF.fullmatch(ref):
                    raise ValidationFailed("This title has no backdrop.", code="marketplace.invalid_look")
                stored = {"object_id": object_id, "ref": ref, "title": str(value.get("title") or "")[:200]}
            else:
                if value not in CHOICES[slot]:
                    raise ValidationFailed("Unknown design.", code="marketplace.invalid_look")
                if value in await self.locked(user, slot):
                    raise LookLocked("This design is sold in the shop: buy it to use it.")
                stored = {"key": value}
        now: datetime = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            if stored is None:
                await uow.session.execute(
                    delete(Equipped).where(Equipped.user_id == user, Equipped.slot == slot)
                )
            else:
                statement = insert(Equipped).values(user_id=user, slot=slot, value=stored, updated_at=now)
                await uow.session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[Equipped.user_id, Equipped.slot],
                        set_={"value": stored, "updated_at": now},
                    )
                )
        return await self.cosmetics.equipped(user)


async def equipped_of(database: Database, user: UUID) -> dict[str, Any]:
    async with database.session() as session:
        rows = (await session.execute(select(Equipped).where(Equipped.user_id == user))).scalars()
        out: dict[str, Any] = {}
        for row in rows:
            out[row.slot] = row.value.get("key") if row.slot in CHOICES else row.value
        return out
