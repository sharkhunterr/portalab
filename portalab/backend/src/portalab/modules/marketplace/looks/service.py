"""Profile looks (027, Steam-like): a member equips a banner, an avatar frame, a film backdrop banner, an
animated background, a name style, one of their titles and a showcase of their badges on their profile.
Designs are drawn by the interface; the ones a product sells are worn by their owners only (directly or
through a pack), the others by everyone. The film backdrop banner is a feature: owning the
« profile_backdrop » product (when one is sold) unlocks every film or series with a TMDB backdrop."""

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.themes import (
    AMBIENTS,
    AVATAR_FRAMES,
    BADGE_STYLES,
    LEVEL_BADGES,
    NAME_STYLES,
    PROFILE_BANNERS,
    PROFILE_SLOTS,
)
from portalab.core.db import Database
from portalab.core.errors import ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.activation.service import LIVE
from portalab.modules.marketplace.entitlements.reader import CosmeticsReader
from portalab.modules.marketplace.models import Equipped, Ownership, Product, ProductVersion

BACKDROP_REF = re.compile(r"^/[A-Za-z0-9_-]{1,64}\.(jpg|jpeg|png)$")
CHOICES = {
    "banner": PROFILE_BANNERS,
    "frame": AVATAR_FRAMES,
    "background": AMBIENTS,  # 027: an animated background behind the profile
    "name": NAME_STYLES,  # 027: the name's font and effect
    "level": LEVEL_BADGES,  # 027: the level badge's look (``classic`` changes with the level)
}
SLOTS = (*CHOICES, "backdrop", "title", "badges")
SHOWCASE = 3  # badges shown next to the name


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

    async def owned_items(self, user: UUID, product_type: str) -> list[dict[str, Any]]:
        """The titles or badges a member owns, as worn: key, label, icon, animated style."""
        async with self.database.session() as session:
            rows = await session.execute(
                select(Product.key, ProductVersion.payload)
                .join(ProductVersion, ProductVersion.product_id == Product.id)
                .join(Ownership, Ownership.product_id == Product.id)
                .where(
                    ProductVersion.version == Product.current_version,
                    Product.type == product_type,
                    Ownership.user_id == user,
                    Ownership.state.in_(LIVE),
                )
                .distinct()
            )
            items = []
            for key, payload in rows.all():
                style = str((payload or {}).get("style") or "none")
                items.append(
                    {
                        "key": key,
                        "label": str((payload or {}).get("label") or key)[:60],
                        "icon": (payload or {}).get("icon"),
                        "style": style if style in BADGE_STYLES else "none",
                    }
                )
        return sorted(items, key=lambda item: item["label"])

    async def _sold(self, slot: str) -> dict[str, dict[str, Any]]:
        """#72: the product selling each design of ``slot`` (its key, rarity and price)."""
        details = getattr(self.cosmetics, "details", None)
        if details is None:
            return {}
        result: dict[str, dict[str, Any]] = await details(*PROFILE_SLOTS[slot])
        return result

    async def catalog(self, user: UUID) -> dict[str, Any]:
        locked = {slot: await self.locked(user, slot) for slot in CHOICES}
        sold = {slot: await self._sold(slot) for slot in CHOICES}

        def listed(slot: str, keys: tuple[str, ...]) -> list[dict[str, Any]]:
            return [{"key": k, "locked": k in locked[slot], **sold[slot].get(k, {})} for k in keys]

        return {
            "banners": listed("banner", PROFILE_BANNERS),
            "frames": listed("frame", AVATAR_FRAMES),
            "backgrounds": listed("background", AMBIENTS),
            "names": listed("name", NAME_STYLES),
            "levels": listed("level", LEVEL_BADGES),
            "titles": await self.owned_items(user, "title"),
            "badges": await self.owned_items(user, "badge"),
            "backdrop": {"unlocked": await self.backdrop_unlocked(user)},
            "equipped": await self.cosmetics.equipped(user),
        }

    async def equip(self, user: UUID, slot: str, value: Any) -> dict[str, Any]:
        """Wear ``value`` in ``slot`` (``None`` takes it off); refused when sold and not owned."""
        if slot not in SLOTS:
            raise ValidationFailed("Unknown profile slot.", code="marketplace.invalid_look")
        stored: dict[str, Any] | None = None
        if value is not None:
            if slot in ("title", "badges"):
                owned = {
                    item["key"]: item
                    for item in await self.owned_items(user, "title" if slot == "title" else "badge")
                }
                keys = [value] if slot == "title" else value
                if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
                    raise ValidationFailed("Pick your own titles or badges.", code="marketplace.invalid_look")
                keys = list(dict.fromkeys(keys))[:SHOWCASE]
                if any(key not in owned for key in keys):
                    raise LookLocked("You can only show what you own.")
                stored = owned[keys[0]] if slot == "title" and keys else {"items": [owned[k] for k in keys]}
                if slot == "badges" and not keys:
                    stored = None
            elif slot == "backdrop":
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
