"""« Since your last visit » for media (027): what arrived in the library (one line, a few titles) and my
requests that became available (one line each — the news a member waits for)."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from portalab.capabilities.dashboard import ChangeItem
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.modules.media.models import MediaObject, MediaRequest
from portalab.modules.media.permissions import MEDIA_READ

TOP_LEVEL = ("movie", "series", "book", "audiobook")


class MediaChanges:
    kind = "media"

    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self.database = database
        self.authorizer = authorizer

    async def changes_since(
        self, principal: Principal, since: datetime, limit: int, ctx: LocaleContext
    ) -> Sequence[ChangeItem]:
        if not await self.authorizer.is_allowed(principal, MEDIA_READ):
            return []
        user = principal.acting_for or principal.user_id
        items: list[ChangeItem] = []
        async with self.database.session() as session:
            fresh = (
                MediaObject.kind.in_(TOP_LEVEL),
                MediaObject.status == "active",
                MediaObject.available.is_(True),
                MediaObject.created_at > since,
            )
            count = int(
                await session.scalar(select(func.count()).select_from(MediaObject).where(*fresh)) or 0
            )
            if count:
                latest = (
                    await session.execute(
                        select(MediaObject.title, MediaObject.created_at)
                        .where(*fresh)
                        .order_by(MediaObject.created_at.desc())
                        .limit(4)
                    )
                ).all()
                items.append(
                    ChangeItem(
                        kind="media",
                        occurred_at=latest[0][1],
                        ref="/media",
                        title_key="dashboard:summary.mediaAdded",
                        title_args={"count": count},
                        detail=", ".join(title for title, _ in latest[:3]) + ("…" if count > 3 else ""),
                        priority=2,
                    )
                )
            if user is not None:
                ready = (
                    await session.execute(
                        select(MediaRequest)
                        .where(
                            MediaRequest.requester_user_id == user,
                            MediaRequest.state == "available",
                            MediaRequest.updated_at > since,
                        )
                        .order_by(MediaRequest.updated_at.desc())
                        .limit(limit)
                    )
                ).scalars()
                ready_rows = list(ready)
                if len(ready_rows) > 2:  # many at once: one line, the first titles as detail
                    titles = [str((r.external_ref or {}).get("title") or "") for r in ready_rows]
                    items.append(
                        ChangeItem(
                            kind="media_request",
                            occurred_at=ready_rows[0].updated_at,
                            ref="/media/requests",
                            title_key="dashboard:summary.requestsAvailable",
                            title_args={"count": len(ready_rows)},
                            detail=", ".join(titles[:4]) + ("…" if len(titles) > 4 else ""),
                            priority=5,
                        )
                    )
                for request in ready_rows if len(ready_rows) <= 2 else []:
                    title = str((request.external_ref or {}).get("title") or "")
                    items.append(
                        ChangeItem(
                            kind="media_request",
                            occurred_at=request.updated_at,
                            ref=f"/media/{request.object_id}" if request.object_id else "/media/requests",
                            title_key="dashboard:summary.requestAvailable",
                            title_args={"title": title},
                            priority=5,
                        )
                    )
        return items[:limit]
