"""Issue 363: a member's requests — what may be asked for, my requests and the open ones I may want too;
asking for a title (refused when the library has it; another member's request: « me too » instead), saying
« me too » and taking it back."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from portalab.modules.requests.api.deps import Member, Module, me

router = APIRouter(prefix="/api/v1", tags=["requests"])
Short = Annotated[str, Field(max_length=120)]


class RequestIn(BaseModel):
    kind: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=300)
    creators: list[Short] = Field(default_factory=list, max_length=10)  # its authors, a game's studio…
    year: int | None = Field(default=None, ge=0, le=3000)
    # what edition: its language, its format, a game's platform…
    details: dict[Annotated[str, Field(max_length=32)], Short] = Field(default_factory=dict, max_length=12)
    # every identifier known of it, by scheme (whatever the scheme: the library reads those it holds)
    ids: dict[Annotated[str, Field(max_length=32)], list[Annotated[str, Field(max_length=200)]]] = Field(
        default_factory=dict, max_length=20
    )
    note: str | None = Field(default=None, max_length=1000)


@router.get("/requests/options")
async def options(principal: Member, module: Module) -> dict[str, Any]:
    """The kinds of titles open to requests, what a request costs, how many I have left of each."""
    return await module.requests.options(me(principal))


@router.get("/requests")
async def requests(
    principal: Member,
    module: Module,
    kind: Annotated[str | None, Query(max_length=40)] = None,
) -> dict[str, Any]:
    """My requests (asked for or « me too »), and every open request, the most wanted first."""
    user = me(principal)
    return {"mine": await module.requests.mine(user), "open": await module.requests.wanted(user, kind)}


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def ask(principal: Member, module: Module, body: RequestIn) -> dict[str, Any]:
    return await module.requests.create(
        me(principal),
        kind=body.kind,
        title=body.title,
        creators=body.creators,
        year=body.year,
        details=body.details,
        ids=body.ids,
        note=body.note,
    )


@router.post("/requests/{request_id}/support")
async def support(principal: Member, module: Module, request_id: UUID) -> dict[str, Any]:
    """« Me too »."""
    return await module.requests.support(me(principal), request_id)


@router.delete("/requests/{request_id}/support")
async def withdraw(principal: Member, module: Module, request_id: UUID) -> dict[str, Any] | None:
    """I no longer want it (the last one cancels it)."""
    return await module.requests.withdraw(me(principal), request_id)
