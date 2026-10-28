"""HTTP API of each member's taste (issue 190): the recommendations made for me, each with its reason; the
cards to judge one by one; what I said of a title (like, not for me, seen, later), the lists it makes, and my
taste as I may see it — and forget."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from portalab.modules.media.api.router import Module, Reader, _me
from portalab.modules.media.providers.taste_widgets import cards
from portalab.modules.media.taste.features import KINDS
from portalab.modules.media.taste.service import Pick

router = APIRouter(prefix="/api/v1", tags=["media"])
Verdict = Literal["like", "dislike", "seen", "later"]


class TasteReason(BaseModel):
    """Why a title is offered: a trait it shares with my taste (``kind``: saga, franchise, director, cast,
    author, genre, keyword… and its ``name``) and the titles of mine that have it; ``rated`` when it is only
    well rated."""

    kind: str
    name: str | None = None
    titles: list[str] = []


class TasteCard(BaseModel):
    id: UUID
    kind: str
    title: str
    year: int | None = None
    available: bool = True
    image_id: UUID | None = None
    genres: list[str] = []
    overview: str | None = None
    rating: float | None = None
    author: str | None = None
    reason: TasteReason | None = None
    seen: bool = False  # a title of mine, not judged yet: « did you like it? »
    verdict: Verdict | None = None


class TasteCards(BaseModel):
    items: list[TasteCard]


class TasteVerdictIn(BaseModel):
    verdict: Verdict


class TasteVerdictOut(BaseModel):
    object_id: UUID | None  # the work the verdict went to (an episode's: its series)
    verdict: Verdict | None


async def _cards(module: Module, picks: list[Pick]) -> list[TasteCard]:
    return [TasteCard.model_validate(card) for card in await cards(module.database, picks)]


@router.get("/me/media/recommendations", response_model=TasteCards)
async def my_recommendations(
    principal: Reader,
    module: Module,
    kind: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> TasteCards:
    """What my taste recommends among the library's titles not seen yet — a film, a series, a book… or only
    one ``kind`` — each with its reason, never ten of one saga or director in a row."""
    kinds = [kind] if kind in KINDS else None
    picks = await module.taste.recommend(_me(principal), limit=limit, kinds=kinds)
    return TasteCards(items=await _cards(module, picks))


@router.get("/me/media/taste/deck", response_model=TasteCards)
async def my_deck(
    principal: Reader, module: Module, limit: Annotated[int, Query(ge=1, le=30)] = 12
) -> TasteCards:
    """Titles to judge one by one (« I like it », « not for me », « seen », « later »): mostly what my taste
    recommends, now and then one of mine not judged yet, and a well-rated one out of my habits."""
    return TasteCards(items=await _cards(module, await module.taste.deck(_me(principal), limit=limit)))


@router.get("/me/media/taste")
async def my_taste(principal: Reader, module: Module) -> dict[str, Any]:
    """My taste as it is drawn: the genres, people, sagas and themes that weigh most, those that weigh
    against, how many works it comes from and my verdicts' counts."""
    return await module.taste.profile(_me(principal))


@router.delete("/me/media/taste", status_code=status.HTTP_204_NO_CONTENT)
async def forget_my_taste(principal: Reader, module: Module) -> None:
    """Forget everything I said of the titles (my history is untouched: its use is a preference)."""
    await module.taste.clear(_me(principal))


@router.get("/me/media/taste/lists/{verdict}", response_model=TasteCards)
async def my_list(
    principal: Reader, verdict: Verdict, module: Module, limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> TasteCards:
    """The titles I said I like, are not for me, saw, or keep for later — the last said first."""
    index = await module.taste.index()
    rows = await module.taste.listed(_me(principal), verdict, limit=limit)
    picks = [Pick(index.works[i], 0.0, None) for i, _ in rows if i in index.works]
    cards = await _cards(module, picks)
    return TasteCards(items=[card.model_copy(update={"verdict": verdict}) for card in cards])


@router.get("/me/media/taste/titles/{object_id}", response_model=TasteVerdictOut)
async def my_verdict(principal: Reader, object_id: UUID, module: Module) -> TasteVerdictOut:
    await module.catalog.get(principal, object_id)  # a title I may see
    verdict = await module.taste.verdict(_me(principal), object_id)
    return TasteVerdictOut(object_id=object_id, verdict=verdict)


@router.put("/me/media/taste/titles/{object_id}", response_model=TasteVerdictOut)
async def judge(principal: Reader, object_id: UUID, body: TasteVerdictIn, module: Module) -> TasteVerdictOut:
    """Say what I think of a title: an episode's or a season's verdict goes to its series."""
    await module.catalog.get(principal, object_id)
    work = await module.taste.judge(_me(principal), object_id, body.verdict)
    return TasteVerdictOut(object_id=work, verdict=body.verdict if work else None)


@router.delete("/me/media/taste/titles/{object_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unjudge(principal: Reader, object_id: UUID, module: Module) -> None:
    await module.catalog.get(principal, object_id)
    await module.taste.unjudge(_me(principal), object_id)
