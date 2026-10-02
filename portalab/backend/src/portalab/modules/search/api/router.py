"""Search API (T014, T019, T026, T029, T033): ``/search``, ``/search/suggest``, ``/search/assist`` (SSE),
``/me/search-history``, ``/palette/resolve`` and ``/admin/search/*``. ``require()`` comes first so an
unavailable module never answers before authentication/authorization."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.search import SearchItem
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.search.coordinator.coordinator import Group
from portalab.modules.search.module import SearchModule, SearchRequest
from portalab.modules.search.permissions import SEARCH_MANAGE, SEARCH_USE, SELF

router = APIRouter(prefix="/api/v1", tags=["search"])


def search_module(request: Request) -> SearchModule:
    module = getattr(request.app.state, "search_module", None)
    if not isinstance(module, SearchModule):
        raise Unavailable("Search is not available.", code="search.unavailable")
    return module


Module = Annotated[SearchModule, Depends(search_module)]
Searcher = Annotated[Principal, require(SEARCH_USE)]
Self = Annotated[Principal, require(SELF)]
Manager = Annotated[Principal, require(SEARCH_MANAGE)]


class SearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(default="", max_length=4096)  # the configured cap (search.maxQueryLength) is checked after
    mode: Literal["exact", "semantic", "mixed"] = "mixed"
    filters: dict[str, list[str]] = Field(default_factory=dict, max_length=10)
    kinds: list[str] | None = Field(default=None, max_length=20)
    cursor: str | None = Field(default=None, max_length=256)


class SearchSegmentOut(BaseModel):
    text: str
    hit: bool


class SearchItemOut(BaseModel):
    kind: str
    id: str
    title: str
    url_ref: str
    snippet: list[SearchSegmentOut]
    language: str | None
    matched_by: Literal["exact", "semantic"]
    score: float
    facets: dict[str, str]


class SearchFacetOut(BaseModel):
    key: str
    label_key: str
    kind: str
    values: list[str]
    counts: dict[str, int]


class SearchGroupOut(BaseModel):
    kind: str
    label_key: str
    state: Literal["ok", "partial", "unavailable"]
    items: list[SearchItemOut]
    next_cursor: str | None
    facets: list[SearchFacetOut]


class SearchOut(BaseModel):
    request_id: str
    groups: list[SearchGroupOut]
    took_ms: int
    total: int
    semantic: Literal["ok", "unavailable", "off"]


class AssistRefIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(max_length=96)
    id: str = Field(max_length=128)


class AssistIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(min_length=1, max_length=1024)
    refs: list[AssistRefIn] = Field(default_factory=list, max_length=50)


class SearchHistoryOut(BaseModel):
    id: UUID
    query: str
    mode: str
    filters: dict[str, Any]
    count: int
    performed_at: str


class ReindexIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kinds: list[str] | None = Field(default=None, max_length=50)


def _item(item: SearchItem) -> SearchItemOut:
    return SearchItemOut(
        kind=item.kind,
        id=item.id,
        title=item.title,
        url_ref=item.url_ref,
        snippet=[SearchSegmentOut(text=s.text, hit=s.hit) for s in item.snippet],
        language=item.language,
        matched_by=item.matched_by,
        score=round(item.score, 4),
        facets=dict(item.facets),
    )


def _group(group: Group) -> SearchGroupOut:
    return SearchGroupOut(
        kind=group.kind,
        label_key=group.label_key,
        state=group.state,
        items=[_item(item) for item in group.items],
        next_cursor=group.next_cursor,
        facets=[
            SearchFacetOut(
                key=facet.key,
                label_key=facet.label_key,
                kind=facet.kind,
                values=list(facet.values),
                counts=dict(group.facets.get(facet.key, {})),
            )
            for facet in group.facet_defs
        ],
    )


@router.post("/search", response_model=SearchOut)
async def search(principal: Searcher, body: SearchIn, module: Module) -> SearchOut:
    outcome, request_id = await module.search(
        principal,
        SearchRequest(q=body.q, mode=body.mode, filters=body.filters, kinds=body.kinds, cursor=body.cursor),
    )
    return SearchOut(
        request_id=request_id,
        groups=[_group(group) for group in outcome.groups],
        took_ms=outcome.took_ms,
        total=outcome.total,
        semantic=outcome.semantic,
    )


@router.get("/search/suggest")
async def suggest(
    principal: Searcher, module: Module, q: Annotated[str, Query(max_length=4096)] = ""
) -> dict[str, Any]:
    return {"items": await module.suggest(principal, q) if q.strip() else []}


@router.post("/search/assist", response_class=StreamingResponse)
async def assist(principal: Searcher, body: AssistIn, module: Module) -> StreamingResponse:
    module.limit(principal)
    stream = module.assist.stream(body.q, principal, [(ref.kind, ref.id) for ref in body.refs])
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/me/search-history", response_model=list[SearchHistoryOut])
async def history(principal: Self, module: Module) -> list[SearchHistoryOut]:
    assert principal.user_id is not None
    return [
        SearchHistoryOut(
            id=row.id,
            query=row.query_text,
            mode=row.mode,
            filters=row.filters,
            count=row.count,
            performed_at=row.performed_at.isoformat(),
        )
        for row in await module.history.list(principal.user_id)
    ]


@router.delete("/me/search-history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(principal: Self, module: Module) -> Response:
    assert principal.user_id is not None
    await module.history.clear(principal.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me/search-history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(principal: Self, entry_id: UUID, module: Module) -> Response:
    assert principal.user_id is not None
    await module.history.delete(principal.user_id, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/palette/resolve")
async def palette(
    principal: Self,
    module: Module,
    q: Annotated[str, Query(max_length=512)] = "",
    route: Annotated[str | None, Query(max_length=256, pattern=r"^/[A-Za-z0-9/_:.\-]*$")] = None,
) -> dict[str, Any]:
    return (await module.resolve_palette(principal, q, route)).as_dict()


@router.post("/admin/search/reindex")
async def reindex(principal: Manager, body: ReindexIn, module: Module) -> dict[str, Any]:
    return {"queued": await module.reindex(principal, body.kinds)}


@router.get("/admin/search/status")
async def admin_status(_: Manager, module: Module) -> dict[str, Any]:
    return await module.status()
