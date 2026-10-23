"""Issue 229: a card's character cut out of its image — its background removed on the processor (IS-Net,
« general use », run by OpenCV), kept as a WebP with its transparency in the blob store. A card then shows
it over a scene of its own (the genre's light, the work's backdrop on the borderless version) rather than
the photograph's background. The model is fetched once from rembg's releases into the cards' folder and
checked against its known fingerprint. The image a card shows first (its character's, else the person's
portrait), the cards members own first; an administrator's setting turns it off (``cards.cutouts``)."""

import asyncio
import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import case, cast, exists, func, select
from sqlalchemy.dialects.postgresql import JSONB

from portalab.capabilities.media import unwrap
from portalab.capabilities.media_core import CARD_SOURCES
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core import egress
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.modules.cards.models import Card, Copy

MODEL = (
    "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx",
    "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a",
)
SIZE = 1024  # the model's input
LONGEST = 900  # a cut-out kept at this size at most
# the model's answer made a little firmer: what is surely the character opaque, its hair and soft edges kept
FLOOR, SPAN = 0.02, 0.4
BATCH = 60  # cards cut out a run (about a second each)
# a cut-out kept only when the character stands on the image's foot (its shoulders, its body there): a head
# the model kept alone, its body taken for background, would float — the card keeps its photograph
GROUNDED = 0.2
NAMESPACE = "cards"
log = get_logger("portalab.cards")


class Cutter:
    """The background removal model (CPU: ``cut`` runs in a thread, one image at a time)."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._net: Any = None
        self._cv: Any = None
        self._broken = False

    async def ready(self) -> bool:
        if self._net is not None:
            return True
        if self._broken:
            return False
        try:
            import cv2  # optional, like the faces
        except ImportError:
            self._broken = True
            return False
        url, digest = MODEL
        path = self.root / "models" / url.rsplit("/", 1)[-1]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            async with httpx.AsyncClient(
                timeout=600.0, follow_redirects=True, event_hooks=egress.hooks()
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
            if hashlib.sha256(response.content).hexdigest() != digest:
                log.warning("cut-out model fingerprint mismatch")
                self._broken = True
                return False
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
        self._cv = cv2
        self._net = cv2.dnn.readNetFromONNX(str(path))
        return True

    def cut(self, data: bytes) -> bytes | None:
        """The image with its background removed, as a WebP with transparency (``None``: unreadable, or the
        character not standing on the image's foot)."""
        import numpy as np  # with OpenCV

        cv = self._cv
        image = cv.imdecode(np.frombuffer(data, np.uint8), cv.IMREAD_COLOR)
        if image is None:
            return None
        height, width = image.shape[:2]
        scale = min(1.0, LONGEST / max(height, width))
        if scale < 1:
            image = cv.resize(image, (int(width * scale), int(height * scale)), interpolation=cv.INTER_AREA)
            height, width = image.shape[:2]
        blob = cv.dnn.blobFromImage(image, 1 / 255.0, (SIZE, SIZE), (0, 0, 0), swapRB=True) - 0.5
        self._net.setInput(blob)
        found = self._net.forward()[0, 0]
        found = (found - found.min()) / (found.max() - found.min() + 1e-8)
        alpha = np.clip((cv.resize(found, (width, height)) - FLOOR) / SPAN, 0, 1)
        alpha = cv.GaussianBlur(alpha, (3, 3), 0)  # an edge a little soft, never cut sharp
        if float(alpha[int(height * 0.94) :].mean()) < GROUNDED:
            return None
        rgba = cv.cvtColor(image, cv.COLOR_BGR2BGRA)
        rgba[:, :, 3] = (alpha * 255).astype(np.uint8)
        done, encoded = cv.imencode(".webp", rgba, [cv.IMWRITE_WEBP_QUALITY, 88])
        return encoded.tobytes() if done else None


def _uncut(column: Any) -> Any:
    return column.is_not(None) & ~func.coalesce(Card.cutout, cast("{}", JSONB)).op("?")(column)


class ArtCutouts:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        cutter: Cutter,
        blobs: BlobStore | None,
        *,
        enabled: Callable[[], bool] = lambda: True,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.cutter = cutter
        self.blobs = blobs
        self.enabled = enabled

    async def run(self, count: int = BATCH) -> int:
        """Cut out the next cards' characters: how many cards were looked at."""
        sources = self.capabilities.system_providers(CARD_SOURCES)
        if not self.enabled() or self.blobs is None or not sources or not await self.cutter.ready():
            return 0
        owned = exists().where(Copy.card_id == Card.id)
        rank = case(
            (Card.rarity == "legendary", 0), (Card.rarity == "epic", 1), (Card.rarity == "rare", 2), else_=3
        )
        shown = func.coalesce(Card.role_art, Card.art)  # the image the card shows
        async with self.database.session() as session:
            cards = (
                await session.execute(
                    select(Card.id, shown, Card.cutout)
                    .where(Card.retired.is_(False), Card.kind != "title", _uncut(shown))
                    .order_by(owned.desc(), rank, Card.score.desc())
                    .limit(count)
                )
            ).all()
        done: dict[Any, dict[str, Any]] = {}
        for card_id, ref, cutout in cards:
            known = dict(cutout or {})
            known[ref] = await self._cut(sources[0].provider, ref)
            done[card_id] = known
        async with self.database.unit_of_work() as uow:
            for card_id, known in done.items():
                card = await uow.session.get(Card, card_id)
                if card is not None:
                    card.cutout = known
        if done:
            log.info("cards' characters cut out", extra={"fields": {"cards": len(done)}})
        return len(done)

    async def _cut(self, sources: Any, ref: str) -> str | None:
        try:
            if ref.startswith("blob:"):
                assert self.blobs is not None
                data = await self.blobs.get(ref.removeprefix("blob:"))
            else:
                data = unwrap(await sources.image(ref, "h632"))
            webp = await asyncio.to_thread(self.cutter.cut, data)
            if webp is None or self.blobs is None:
                return None
            return f"blob:{(await self.blobs.put(NAMESPACE, webp, content_type='image/webp')).key}"
        except Exception:  # an image that cannot be read or cut: the card keeps its photograph
            log.debug("card's character not cut out", exc_info=True)
            return None
