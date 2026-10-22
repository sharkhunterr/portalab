"""Issue 229: is this the actor? Faces compared on the processor (OpenCV: YuNet finds the faces, SFace turns
each into a signature; two signatures of one person are close). The models are fetched once from OpenCV's
model zoo into the cards' folder, checked against their known fingerprints — never used otherwise.

Nothing is named or recognised: a face is only compared with the actor's own portrait (TMDB) to keep an
image of them in their character, for their card."""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from portalab.core import egress
from portalab.core.logging import get_logger

log = get_logger("portalab.cards")
ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models"
MODELS = {
    "detector": (
        f"{ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    "recognizer": (
        f"{ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
}
SAME_PERSON = 0.42  # SFace's cosine similarity: 0.363 is its own threshold, a little stricter here
LONGEST = 1280  # images are looked at this size at most


@dataclass(frozen=True, slots=True)
class Face:
    signature: Any  # SFace's feature vector
    share: float  # the part of the image it takes


@dataclass(frozen=True, slots=True)
class Looked:
    faces: Sequence[Face]
    width: int
    height: int


class FaceMatcher:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._detector: Any = None
        self._recognizer: Any = None
        self._cv: Any = None
        self._broken = False

    async def ready(self) -> bool:
        """The models fetched (once) and checked; ``False`` when OpenCV or a model is missing."""
        if self._recognizer is not None:
            return True
        if self._broken:
            return False
        try:
            import cv2  # optional: the cards work without it (portraits only)
        except ImportError:
            self._broken = True
            return False
        paths = {}
        for name, (url, digest) in MODELS.items():
            path = self.root / "models" / url.rsplit("/", 1)[-1]
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                data = await self._download(url)
                if hashlib.sha256(data).hexdigest() != digest:
                    log.warning("face model fingerprint mismatch", extra={"fields": {"model": name}})
                    self._broken = True
                    return False
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            paths[name] = str(path)
        self._cv = cv2
        self._detector = cv2.FaceDetectorYN.create(paths["detector"], "", (320, 320), 0.8)
        self._recognizer = cv2.FaceRecognizerSF.create(paths["recognizer"], "")
        return True

    async def _download(self, url: str) -> bytes:
        async with httpx.AsyncClient(
            timeout=60.0, follow_redirects=True, event_hooks=egress.hooks()
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    def look(self, data: bytes) -> Looked:
        """The faces of an image (CPU: run it in a thread)."""
        import numpy as np  # with OpenCV

        cv = self._cv
        image = cv.imdecode(np.frombuffer(data, np.uint8), cv.IMREAD_COLOR)
        if image is None:
            return Looked((), 0, 0)
        height, width = image.shape[:2]
        scale = min(1.0, LONGEST / max(height, width))
        if scale < 1:
            image = cv.resize(image, (int(width * scale), int(height * scale)))
        h, w = image.shape[:2]
        self._detector.setInputSize((w, h))
        _, found = self._detector.detect(image)
        faces = [
            Face(
                self._recognizer.feature(self._recognizer.alignCrop(image, row)),
                float(row[2] * row[3]) / (w * h),
            )
            for row in (found if found is not None else [])
        ]
        return Looked(tuple(faces), width, height)

    def similarity(self, a: Face, b: Face) -> float:
        return float(self._recognizer.match(a.signature, b.signature, self._cv.FaceRecognizerSF_FR_COSINE))


# what an image's page says when it is a premiere, a festival, an interview — the actor, not their character
EVENT = re.compile(
    r"premi[eè]re|festival|red carpet|tapis rouge|cannes|gala|arrives|attends|award|oscars?|c[ée]sar|"
    r"interview|photocall|press|conf[ée]rence|getty|wireimage",
    re.IGNORECASE,
)
SKIPPED_ENGINES = {"wikicommons.images"}  # public photographs of people: events, almost never a film's


def words(text: str | None) -> list[str]:
    """The words worth finding in a page's title (a character's or a film's name)."""
    return [w for w in re.findall(r"[\w'\u2019]+", (text or "").lower()) if len(w) >= 4]


@dataclass(frozen=True, slots=True)
class Candidate:
    url: str
    title: str
    engine: str
    similarity: float
    width: int
    height: int


def score(candidate: Candidate, character: str | None, film: str) -> float | None:
    """How good an image is for the card (``None``: not kept) — the actor's face first, then the page naming
    the character or the film, then its size."""
    if candidate.similarity < SAME_PERSON or candidate.engine in SKIPPED_ENGINES:
        return None
    if EVENT.search(candidate.title) or min(candidate.width, candidate.height) < 360:
        return None
    title = candidate.title.lower()
    named = any(w in title for w in words(character))
    in_film = any(w in title for w in words(film))
    if not (named or in_film):
        return None  # nothing says it is from this work
    return (
        candidate.similarity
        + (0.25 if named else 0.0)
        + (0.15 if in_film else 0.0)
        + (0.1 if min(candidate.width, candidate.height) >= 700 else 0.0)
    )
