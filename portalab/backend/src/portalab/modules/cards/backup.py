"""Issue 247 — the cards' images left out of a restored backup (to keep it small: they come from the services
and the models): every reference to one of them forgotten, with the marks saying it was looked for, so the
roles' images, the frames and the cut-outs are looked for and made again in the background."""

from typing import Any

from sqlalchemy import null, update

from portalab.modules.cards.models import Card

FOLDER = "blobs/cards"


class CardsLeftOut:
    async def left_out(self, session: Any, folders: frozenset[str]) -> None:
        if FOLDER not in folders:
            return
        await session.execute(
            update(Card)
            .where(Card.role_art.like("blob:%"))
            .values(role_art=None, focus=null())
            .execution_options(synchronize_session=False)
        )
        await session.execute(
            update(Card)
            .values(
                cutout=null(),
                role_checked_at=None,
                search_checked_at=None,
                frame_checked_at=None,
                character_checked_at=None,
            )
            .execution_options(synchronize_session=False)
        )
