"""029: the exposure catalog put together — every module's labels declared into one registry — and served to
members (``GET /api/v1/exposure``): what Portalab opens to an extension, in plain words (spec 030 scopes an
extension's code with it).
"""

import hashlib
import json
from typing import Annotated, Any

from fastapi import APIRouter, Request, Response

from portalab.capabilities.exposure import ExposureRegistry, default_exposure
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.calendar import exposure as calendar
from portalab.modules.cards import exposure as cards
from portalab.modules.community import exposure as community
from portalab.modules.dashboard import exposure as dashboard
from portalab.modules.games import exposure as games
from portalab.modules.gamification import exposure as gamification
from portalab.modules.marketplace import exposure as marketplace
from portalab.modules.media import exposure as media
from portalab.modules.news import exposure as news
from portalab.modules.notifications import exposure as notifications
from portalab.modules.search import exposure as search
from portalab.modules.statistics import exposure as statistics
from portalab.modules.wiki import exposure as wiki

TABLES = (
    calendar, cards, community, dashboard, games, gamification, marketplace, media,
    news, notifications, search, statistics, wiki,
)  # fmt: skip


def declare_all(registry: ExposureRegistry = default_exposure) -> ExposureRegistry:
    """Every module's labels, declared once (idempotent)."""
    for table in TABLES:
        registry.declare(*table.LABELS)
    return registry


declare_all()

router = APIRouter(prefix="/api/v1", tags=["exposure"])
Member = Annotated[Principal, require("users.self.manage")]


def catalog(registry: ExposureRegistry = default_exposure) -> dict[str, Any]:
    return {"operations": [label.out() for label in registry.exposable()]}


_TAG = '"' + hashlib.sha256(json.dumps(catalog(), sort_keys=True).encode()).hexdigest()[:16] + '"'


@router.get("/exposure")
async def exposure(_: Member, request: Request, response: Response) -> Any:
    """What Portalab opens to an extension (forbidden operations are never listed)."""
    if request.headers.get("if-none-match") == _TAG:
        return Response(status_code=304, headers={"ETag": _TAG})
    response.headers["ETag"] = _TAG
    response.headers["Cache-Control"] = "private, no-cache"
    return catalog()
