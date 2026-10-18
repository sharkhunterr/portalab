"""Portalab's confirmation of a committing plugin operation (spec 030, R6).

A route labelled ``committing`` (a post published, a purchase, a deletion) is called only once the member
confirmed **its exact content** in Portalab's own dialog: the first request answers 409
``plugin.confirmation_required`` with a single-use token and the summary the plugin's ``describe`` returned
(a title, a few lines, an amount), bounded and drawn by Portalab's components; the request sent again with
the token is checked — same member, plugin, route and body — before the plugin is called.
"""

import hashlib
import json
import secrets
from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import update

from portalab.core.db import Database
from portalab.core.errors import Conflict
from portalab.core.time import Clock, utc_now
from portalab.modules.plugins.models import Confirmation

LIFETIME = timedelta(minutes=5)
FIELD = "confirmation"


class ConfirmationRequired(Conflict):
    default_code = "plugin.confirmation_required"
    default_title = "Confirm this action"


def body_hash(body: Mapping[str, Any] | None) -> bytes:
    clean = {k: v for k, v in dict(body or {}).items() if k != FIELD}
    return hashlib.sha256(json.dumps(clean, sort_keys=True, default=str).encode()).digest()


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def summary_of(raw: Any) -> dict[str, Any]:
    """What Portalab's dialog shows, from what ``describe`` returned (bounded plain text only)."""
    value = raw if isinstance(raw, Mapping) else {}
    raw_lines = value.get("lines")
    lines: list[Any] = list(raw_lines) if isinstance(raw_lines, (list, tuple)) else []
    out: dict[str, Any] = {
        "title": _text(value.get("title"), 120) or "Confirm",
        "lines": [_text(line, 200) for line in lines[:8] if _text(line, 200)],
    }
    amount = value.get("amount")
    if isinstance(amount, (int, float)) and not isinstance(amount, bool):
        out["amount"] = amount
        out["currency"] = _text(value.get("currency") or "coins", 16)
    return out


class Confirmations:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def require(
        self,
        *,
        user_id: UUID,
        plugin: str,
        route: str,
        body: Mapping[str, Any] | None,
        token: str | None,
        describe: Callable[[], Awaitable[Any]],
    ) -> None:
        """Returns when ``token`` confirms exactly this request; otherwise raises 409 with a new token."""
        digest = body_hash(body)
        now = utc_now(self.clock)
        if token:
            async with self.database.unit_of_work() as uow:
                used = await uow.session.execute(
                    update(Confirmation)
                    .where(
                        Confirmation.token_hash == hashlib.sha256(token.encode()).digest(),
                        Confirmation.user_id == user_id,
                        Confirmation.plugin_key == plugin,
                        Confirmation.route == route,
                        Confirmation.body_hash == digest,
                        Confirmation.expires_at > now,
                        Confirmation.used_at.is_(None),
                    )
                    .values(used_at=now)
                )
                if used.rowcount == 1:  # type: ignore[attr-defined]
                    return
        summary = summary_of(await describe())
        fresh = secrets.token_urlsafe(24)
        async with self.database.unit_of_work() as uow:
            uow.session.add(
                Confirmation(
                    token_hash=hashlib.sha256(fresh.encode()).digest(),
                    user_id=user_id,
                    plugin_key=plugin,
                    route=route[:140],
                    body_hash=digest,
                    summary=summary,
                    expires_at=now + LIFETIME,
                )
            )
        raise ConfirmationRequired(
            "Confirm what this action does before it is done.",
            extensions={FIELD: fresh, "summary": summary, "plugin": plugin},
        )
