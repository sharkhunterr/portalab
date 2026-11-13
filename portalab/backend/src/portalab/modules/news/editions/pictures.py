"""Issue 411 — an edition's pictures for its e-mail: what the public picture route answers (« <token>/<id> »,
only the pictures the edition shows), read here so they travel in the e-mail."""

import re
from uuid import UUID

from portalab.modules.news.editions.service import Editions

TOKEN = re.compile(r"[A-Za-z0-9_-]{20,64}")
PICTURE = re.compile(r"[0-9a-fA-F-]{36}|t-[A-Za-z0-9_.-]{1,120}|b-[A-Za-z0-9_-]{1,380}")


class EditionPictures:
    prefix = "/api/v1/newsletters/pictures/"

    def __init__(self, editions: Editions) -> None:
        self.editions = editions

    async def image(self, path: str, reader: UUID | None) -> bytes | None:
        token, _, image_id = path.partition("/")
        if not TOKEN.fullmatch(token) or not PICTURE.fullmatch(image_id):
            return None
        return await self.editions.picture(token, image_id if image_id[1:2] == "-" else image_id.lower())
