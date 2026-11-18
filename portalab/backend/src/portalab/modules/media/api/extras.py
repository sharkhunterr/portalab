"""Issue 465: a title's videos and extra pictures, on its page — told by the services that know them, every
picture served by the portal (``img-src 'self'``)."""

from collections.abc import Awaitable
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Path, Query, Response
from pydantic import BaseModel

from portalab.core.errors import NotFound, Unavailable
from portalab.modules.media.api.router import Module, Reader
from portalab.modules.media.extras import ExtraNotFound, TitleExtras

router = APIRouter(prefix="/api/v1", tags=["media"])
INDEX = Annotated[int, Path(ge=0, le=999)]
PICTURE_HEADERS = {
    "Cache-Control": "private, max-age=86400",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'",
}


class ExtraVideoOut(BaseModel):
    index: int
    site: Literal["youtube", "service"]
    youtube: str | None = None  # the YouTube video's id (played by YouTube's privacy-enhanced player)
    play: str | None = None  # a media server's extra: the portal's player route
    name: str
    kind: str
    language: str | None = None
    duration_s: float | None = None
    picture: str | None = None  # a ready URL, through the portal


class ExtraImageOut(BaseModel):
    index: int
    kind: str
    preview: str  # ready URLs, through the portal
    full: str


class MediaExtrasOut(BaseModel):
    videos: list[ExtraVideoOut] = []
    images: list[ExtraImageOut] = []


@router.get("/media/{object_id}/extras", response_model=MediaExtrasOut)
async def title_extras(principal: Reader, object_id: UUID, module: Module) -> MediaExtrasOut:
    """Issue 465: a title's videos (trailers first, the member's language first) and extra pictures."""
    await module.catalog.get(principal, object_id)  # a title the member may see
    await module.gate.check(principal, object_id)  # 032: and open (a household profile's age rating)
    extras = await module.extras.of(object_id, await module.member_language(principal))
    return _out(extras, f"/api/v1/media/{object_id}/extras", "", object_id)


GAME_REF = Annotated[str, Query(min_length=1, max_length=20, pattern=r"^[0-9]+$")]


@router.get("/media/game-extras", response_model=MediaExtrasOut)
async def game_extras(principal: Reader, module: Module, ref: GAME_REF) -> MediaExtrasOut:
    """Issue 501: a game the library lacks — its videos and pictures as on a library game's page, by its id
    in the game database (IGDB)."""
    extras = await module.extras.of_title("game", {"igdb": ref}, await module.member_language(principal))
    return _out(extras, "/api/v1/media/game-extras", f"ref={ref}", None)


@router.get("/media/game-extras/images/{index}")
async def game_extra_image(
    principal: Reader,
    index: INDEX,
    module: Module,
    ref: GAME_REF,
    preview: Annotated[bool, Query()] = False,
) -> Response:
    """Issue 501: one of a game's pictures (a game the library lacks), small (``preview``) or large."""
    extras = await module.extras.of_title("game", {"igdb": ref}, await module.member_language(principal))
    return await _picture(module.extras.image_of(extras, index, preview=preview))


@router.get("/media/game-extras/videos/{index}/picture")
async def game_extra_video_picture(
    principal: Reader, index: INDEX, module: Module, ref: GAME_REF
) -> Response:
    """Issue 501: a game's video's picture (a game the library lacks), fetched by the portal."""
    extras = await module.extras.of_title("game", {"igdb": ref}, await module.member_language(principal))
    return await _picture(module.extras.video_picture_of(extras, index))


async def _picture(fetch: Awaitable[bytes]) -> Response:
    try:
        data = await fetch
    except ExtraNotFound as exc:
        raise NotFound("No such picture.", code="media.extra_not_found") from exc
    except Exception as exc:
        raise Unavailable("The picture cannot be fetched right now.", code="media.image_unavailable") from exc
    return Response(content=data, media_type="image/jpeg", headers=PICTURE_HEADERS)


def _out(extras: TitleExtras, base: str, query: str, object_id: UUID | None) -> MediaExtrasOut:
    """The extras with their addresses through the portal (``query``: what each address carries)."""

    def at(path: str, *more: str) -> str:
        params = "&".join(p for p in (query, *more) if p)
        return f"{base}{path}?{params}" if params else f"{base}{path}"

    return MediaExtrasOut(
        videos=[
            ExtraVideoOut(
                index=i,
                site=v.video.site,
                youtube=v.video.key if v.video.site == "youtube" else None,
                play=f"/media/{object_id}/watch?item={v.video.key}"
                if v.video.site == "service" and object_id is not None
                else None,
                name=v.video.name,
                kind=v.video.kind,
                language=v.video.language,
                duration_s=v.video.duration_s,
                picture=at(f"/videos/{i}/picture") if v.video.site == "youtube" or v.video.picture else None,
            )
            for i, v in enumerate(extras.videos)
        ],
        images=[
            ExtraImageOut(
                index=i,
                kind=p.image.kind,
                preview=at(f"/images/{i}", "preview=true"),
                full=at(f"/images/{i}"),
            )
            for i, p in enumerate(extras.images)
        ],
    )


@router.get("/media/{object_id}/extras/images/{index}")
async def title_extra_image(
    principal: Reader,
    object_id: UUID,
    index: INDEX,
    module: Module,
    preview: Annotated[bool, Query()] = False,
) -> Response:
    """Issue 465: one of a title's extra pictures, small (``preview``) or large."""
    await module.gate.check(principal, object_id)
    try:
        data = await module.extras.image(
            object_id, index, await module.member_language(principal), preview=preview
        )
    except ExtraNotFound as exc:
        raise NotFound("No such picture.", code="media.extra_not_found") from exc
    except Exception as exc:
        raise Unavailable("The picture cannot be fetched right now.", code="media.image_unavailable") from exc
    return Response(content=data, media_type="image/jpeg", headers=PICTURE_HEADERS)


@router.get("/media/{object_id}/extras/videos/{index}/picture")
async def title_extra_video_picture(
    principal: Reader, object_id: UUID, index: INDEX, module: Module
) -> Response:
    """Issue 465: a video's picture (a YouTube video's, fetched by the portal: the browser never calls it)."""
    await module.gate.check(principal, object_id)
    try:
        data = await module.extras.video_picture(object_id, index, await module.member_language(principal))
    except ExtraNotFound as exc:
        raise NotFound("No such picture.", code="media.extra_not_found") from exc
    except Exception as exc:
        raise Unavailable("The picture cannot be fetched right now.", code="media.image_unavailable") from exc
    return Response(content=data, media_type="image/jpeg", headers=PICTURE_HEADERS)
