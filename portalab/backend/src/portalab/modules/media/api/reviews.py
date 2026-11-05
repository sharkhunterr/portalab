"""HTTP API of members' reviews (#355): a title's reviews — its average, how many, mine, the others' (signed,
or « Anonymous ») — and mine to give, change or take back once I watched, read, listened to or played it."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from portalab.modules.media.api.router import Module, Reader
from portalab.modules.media.reviews.service import MAX_COMMENT, ReviewLine, Reviews

router = APIRouter(prefix="/api/v1", tags=["media"])


class ReviewOut(BaseModel):
    author_id: UUID | None  # None: an anonymous member
    author: str | None
    mine: bool
    rating: int
    comment: str | None
    at: datetime


class ReviewsOut(BaseModel):
    object_id: UUID  # the work the reviews are of (an episode's: its series)
    reviewable: bool
    can_review: bool
    count: int
    average: float | None
    mine: ReviewOut | None
    items: list[ReviewOut]


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=MAX_COMMENT)


def _line(line: ReviewLine) -> ReviewOut:
    return ReviewOut(
        author_id=line.author_id,
        author=line.author,
        mine=line.mine,
        rating=line.rating,
        comment=line.comment,
        at=line.at,
    )


def _out(reviews: Reviews) -> ReviewsOut:
    return ReviewsOut(
        object_id=reviews.object_id,
        reviewable=reviews.reviewable,
        can_review=reviews.can_review,
        count=reviews.count,
        average=reviews.average,
        mine=_line(reviews.mine) if reviews.mine else None,
        items=[_line(line) for line in reviews.items],
    )


@router.get("/media/{object_id}/reviews", response_model=ReviewsOut)
async def reviews(principal: Reader, object_id: UUID, module: Module) -> ReviewsOut:
    await module.catalog.get(principal, object_id)  # a title I may see
    return _out(await module.reviews.view(principal, object_id))


@router.put("/media/{object_id}/reviews/mine", response_model=ReviewsOut)
async def review(principal: Reader, object_id: UUID, body: ReviewIn, module: Module) -> ReviewsOut:
    """Give or change my review: a rating from 1 to 5, a few words if I want."""
    await module.catalog.get(principal, object_id)
    await module.reviews.save(principal, object_id, body.rating, body.comment)
    return _out(await module.reviews.view(principal, object_id))


@router.delete("/media/{object_id}/reviews/mine", status_code=status.HTTP_204_NO_CONTENT)
async def unreview(principal: Reader, object_id: UUID, module: Module) -> None:
    await module.catalog.get(principal, object_id)
    await module.reviews.remove(principal, object_id)
