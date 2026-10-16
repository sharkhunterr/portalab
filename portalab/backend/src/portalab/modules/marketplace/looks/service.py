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

from portalab.capabilities.themes import PROFILE_SLOTS
from portalab.capabilities.visuals import external_looks, live_looks
from portalab.core.db import Database
from portalab.core.errors import ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.activation.service import LIVE, USABLE
from portalab.modules.marketplace.entitlements.reader import CosmeticsReader, waits_for
from portalab.modules.marketplace.models import Equipped, Ownership, Product, ProductVersion

BACKDROP_REF = re.compile(r"^/[A-Za-z0-9_-]{1,64}\.(jpg|jpeg|png)$")
# the slots a look is chosen in: a banner, an avatar frame, an animated background behind the profile (027),
# the name's font and effect, the level badge's look (``classic`` changes with the level) — their looks come
# from the packs (``live_looks``), none is written here
CHOICES = ("banner", "frame", "background", "name", "level")


def choices(slot: str, *, held: bool = False) -> tuple[str, ...]:
    """issue 1 / 028: a slot's designs — Portalab's own packs', then those of the published visual packs (an
    ambience is also a profile background); ``held`` (028): with those whose pack is off, for the owners'
    lists."""
    kind = PROFILE_SLOTS[slot][0]
    known = external_looks.listed(kind) if held else external_looks.known(kind)
    if slot == "background":
        known = (*known, *(k for k in external_looks.of("ambient") if k not in known))
        if held:
            known = (*known, *sorted(k for k in external_looks.held("ambient") if k not in known))
    return known


SLOTS = (*CHOICES, "backdrop", "title", "badges")


def _badge_styles() -> frozenset[str]:
    """The styles a badge or a title may wear (one vocabulary for both)."""
    return frozenset((*live_looks.known("badge"), *live_looks.known("title")))


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
        sold = await self.cosmetics.sold(kind, field)
        owned = await self.cosmetics.owned(user, kind, field)
        if slot == "background":
            # #79: an ambience sold in the shop is also a profile background — worn by its owners only (owning
            # the ambience unlocks its background); before, those sold only as ambiences were free here
            sold |= await self.cosmetics.sold("ambient", "ambient")
            owned |= await self.cosmetics.owned(user, "ambient", "ambient")
        return frozenset(sold - owned)

    async def waiting(self, user: UUID, slot: str) -> dict[str, dict[str, int]]:
        """#99: the designs of ``slot`` the member won but may not wear yet, and what each waits for."""
        reader = getattr(self.cosmetics, "waiting", None)
        if reader is None:
            return {}
        kind, field = PROFILE_SLOTS[slot]
        result: dict[str, dict[str, int]] = await reader(user, kind, field)
        if slot == "background":
            result = {**await reader(user, "ambient", "ambient"), **result}
        return result

    async def backdrop_unlocked(self, user: UUID) -> bool:
        sold = await self.cosmetics.sold("profile_backdrop", "feature")
        if not sold:
            return True  # nobody sells it: a free feature
        return bool(await self.cosmetics.owned(user, "profile_backdrop", "feature"))

    async def owned_items(self, user: UUID, product_type: str) -> list[dict[str, Any]]:
        """The titles or badges a member owns, as worn: key, label, icon, animated style."""
        async with self.database.session() as session:
            rows = await session.execute(
                select(
                    Product.key,
                    ProductVersion.payload,
                    Product.rarity,
                    Ownership.state,
                    Ownership.conditions_snapshot,
                )
                .join(ProductVersion, ProductVersion.product_id == Product.id)
                .join(Ownership, Ownership.product_id == Product.id)
                .where(
                    ProductVersion.version == Product.current_version,
                    Product.type == product_type,
                    Ownership.user_id == user,
                    Ownership.state.in_((*USABLE, "locked")),
                )
            )
            found: dict[str, Any] = {}
            for key, payload, rarity, state, conditions in rows.all():
                # #99: one won but waiting for a level shows locked, with what it waits for
                if key not in found or state != "locked":
                    found[key] = (payload, rarity, waits_for(conditions) if state == "locked" else None)
            items = []
            for key, (payload, rarity, waiting) in found.items():
                style = str((payload or {}).get("style") or "none")
                items.append(
                    {
                        "key": key,
                        "label": str((payload or {}).get("label") or key)[:60],
                        "icon": (payload or {}).get("icon"),
                        "style": style if style in _badge_styles() else "none",
                        "rarity": rarity,  # #79
                        **({"waiting": waiting} if waiting else {}),
                    }
                )
        return sorted(items, key=lambda item: item["label"])

    async def _sold(self, slot: str) -> dict[str, dict[str, Any]]:
        """#72: the product selling each design of ``slot`` (its key, rarity and price)."""
        details = getattr(self.cosmetics, "details", None)
        if details is None:
            return {}
        result: dict[str, dict[str, Any]] = await details(*PROFILE_SLOTS[slot])
        if slot == "background":  # #79: the ambience's own rarity when it is not sold as a background
            result = {**await details("ambient", "ambient"), **result}
        return result

    async def unowned(self, user: UUID, product_type: str) -> int:
        """#79: products of this type on sale that the member does not own."""
        async with self.database.session() as session:
            owned = (
                select(Ownership.product_id)
                .where(Ownership.user_id == user, Ownership.state.in_(LIVE))
                .scalar_subquery()
            )
            rows = await session.scalars(
                select(Product.key).where(
                    Product.type == product_type, Product.state == "available", Product.id.not_in(owned)
                )
            )
            return len(list(rows))

    async def catalog(self, user: UUID) -> dict[str, Any]:
        locked = {slot: await self.locked(user, slot) for slot in CHOICES}
        sold = {slot: await self._sold(slot) for slot in CHOICES}
        waiting = {slot: await self.waiting(user, slot) for slot in CHOICES}

        def listed(slot: str, keys: tuple[str, ...]) -> list[dict[str, Any]]:
            held = live_looks.held(PROFILE_SLOTS[slot][0]) | (
                live_looks.held("ambient") if slot == "background" else frozenset()
            )
            return [
                {
                    "key": k,
                    "locked": k in locked[slot],
                    **sold[slot].get(k, {}),
                    **({"waiting": waiting[slot][k]} if k in waiting[slot] else {}),
                }
                for k in keys
                # 028: a look whose pack is off shows to its owners only (« currently unavailable »)
                if k not in held or k in waiting[slot]
            ]

        return {
            "banners": listed("banner", choices("banner", held=True)),
            "frames": listed("frame", choices("frame", held=True)),
            "backgrounds": listed("background", choices("background", held=True)),
            "names": listed("name", choices("name", held=True)),
            "levels": listed("level", choices("level", held=True)),
            "titles": await self.owned_items(user, "title"),
            "badges": await self.owned_items(user, "badge"),
            # #79: how many more the shop sells (shown in one line, never listed)
            "in_shop": {
                "title": await self.unowned(user, "title"),
                "badge": await self.unowned(user, "badge"),
            },
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
                if value not in choices(slot):
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
