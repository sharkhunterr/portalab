"""Issue 229: the media cards — my collection, a set, a person's cards, my packs (opened one by one); making
the cards again (administrators)."""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound, Unavailable
from portalab.modules.cards.module import CardsModule
from portalab.modules.cards.permissions import MANAGE, READ
from portalab.modules.cards.search import image_type

router = APIRouter(prefix="/api/v1", tags=["cards"])


def cards_module(request: Request) -> CardsModule:
    module = getattr(request.app.state, "cards_module", None)
    if not isinstance(module, CardsModule):
        raise Unavailable("The cards are not available.", code="cards.unavailable")
    return module


Module = Annotated[CardsModule, Depends(cards_module)]
Reader = Annotated[Principal, require(READ)]
Manager = Annotated[Principal, require(MANAGE)]


class CardNotFound(NotFound):
    default_code = "cards.not_found"
    default_title = "No such cards"


def _me(principal: Principal) -> UUID:
    user = principal.acting_for or principal.user_id
    if user is None:
        raise CardNotFound("No member.")
    return user


@router.get("/me/cards")
async def my_cards(principal: Reader, module: Module) -> dict[str, Any]:
    """My collection in numbers: cards and sets owned, packs waiting to be opened."""
    return await module.service.summary(_me(principal))


@router.get("/cards/sets")
async def card_sets(
    principal: Reader,
    module: Module,
    q: Annotated[str, Query(max_length=80)] = "",
    started: bool = False,
    page: Annotated[int, Query(ge=0, le=500)] = 0,
) -> dict[str, Any]:
    """The sets (a work each), those I started first."""
    return await module.service.sets(_me(principal), q=q, started=started, page=page)


@router.get("/cards/pool")
async def card_pool(
    principal: Reader,
    module: Module,
    q: Annotated[str, Query(max_length=80)] = "",
    rarity: Annotated[str | None, Query(pattern=r"^(common|rare|epic|legendary)$")] = None,
    kind: Annotated[str | None, Query(pattern=r"^(title|cast|director|creator|writer|composer)$")] = None,
    country: Annotated[str | None, Query(pattern=r"^[A-Z]{2}$")] = None,
    owned: bool = False,
    page: Annotated[int, Query(ge=0, le=2000)] = 0,
) -> dict[str, Any]:
    """Every card there is (the pool), the rarest first — by name, rarity, kind, country, or mine only."""
    return await module.service.pool(
        _me(principal), q=q, rarity=rarity, kind=kind, country=country, owned=owned, page=page
    )


@router.get("/cards/sets/{key}")
async def card_set(
    principal: Reader, module: Module, key: Annotated[str, Path(pattern=r"^[0-9a-f-]{36}$")]
) -> dict[str, Any]:
    """A set's cards, each with the versions I own."""
    found = await module.service.set_detail(_me(principal), key)
    if found is None:
        raise CardNotFound("No such set.")
    return found


@router.get("/cards/people")
async def card_person(
    principal: Reader, module: Module, ref: Annotated[str, Query(min_length=3, max_length=160)]
) -> dict[str, Any]:
    """A person's cards across the sets (a card per work they are credited on)."""
    return await module.service.person(_me(principal), ref)


@router.get("/me/cards/packs")
async def my_packs(principal: Reader, module: Module, unopened: bool = True) -> list[dict[str, Any]]:
    """My packs (those to open first): their cards shown once opened."""
    return await module.service.packs(_me(principal), unopened=unopened)


@router.post("/me/cards/packs/{pack_id}/open")
async def open_pack(principal: Reader, module: Module, pack_id: UUID) -> dict[str, Any]:
    """Open one of my packs: its cards (drawn when it was given) revealed."""
    user = _me(principal)
    if await module.packs.open(user, pack_id) is None:
        raise CardNotFound("No such pack.")
    found = await module.service.pack(user, pack_id)
    if found is None:
        raise CardNotFound("No such pack.")
    return found


@router.post("/admin/cards/sync")
async def sync_cards(principal: Manager, module: Module) -> dict[str, Any]:
    """Make the cards again from the works present now (those that changed), then rank them again; and look
    for the next actors' characters at once."""
    return {
        **asdict(await module.forge.sync()),
        "characters": await module.roles.run(),
        "fan_art": await module.fan_art.run(),
        "searched": await module.search.run(),
    }


@router.post("/admin/cards/sets/{key}/characters")
async def look_for_characters(
    principal: Manager, module: Module, key: Annotated[str, Path(pattern=r"^[0-9a-f-]{36}$")]
) -> dict[str, Any]:
    """Look for this set's actors' characters on the web now (again for those found there before)."""
    return {"found": await module.search.run(20, set_key=key)}


@router.get("/cards/images/{namespace}/{digest}")
async def card_image(
    _: Reader,
    module: Module,
    namespace: Annotated[str, Path(pattern=r"^cards$")],
    digest: Annotated[str, Path(pattern=r"^[0-9a-f]{64}$")],
) -> Response:
    """An image the cards found and kept (an actor's character): only one a card shows."""
    key = f"{namespace}/{digest}"
    if module.blobs is None or not await module.service.shows(f"blob:{key}"):
        raise CardNotFound("No such image.")
    data = await module.blobs.get(key)
    return Response(
        content=data,
        media_type=image_type(data),
        headers={"Cache-Control": "private, max-age=2592000, immutable", "X-Content-Type-Options": "nosniff"},
    )
