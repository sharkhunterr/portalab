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
BLACK = 20  # a row darker than this on average is a black bar


@dataclass(frozen=True, slots=True)
class Face:
    signature: Any  # SFace's feature vector
    share: float  # the part of the image it takes
    box: tuple[int, int, int, int] = (0, 0, 0, 0)  # where it is: x, y, width, height (the image's pixels)
    sharpness: float = 0.0  # the variance of its Laplacian: low, it is blurred


@dataclass(frozen=True, slots=True)
class Looked:
    faces: Sequence[Face]
    width: int
    height: int
    top: int = 0  # the picture between black bars (a film in a wider format): its first row…
    bottom: int = 0  # …and the row after its last (0: the image's height)


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
        back = 1 / scale if scale < 1 else 1.0
        gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
        faces = []
        for row in found if found is not None else []:
            x, y, fw, fh = (max(0, int(v)) for v in row[:4])
            patch = gray[y : y + fh, x : x + fw]
            faces.append(
                Face(
                    self._recognizer.feature(self._recognizer.alignCrop(image, row)),
                    float(row[2] * row[3]) / (w * h),
                    (int(x * back), int(y * back), int(fw * back), int(fh * back)),
                    float(cv.Laplacian(patch, cv.CV_64F).var()) if patch.size else 0.0,
                )
            )
        lit = np.flatnonzero(gray.mean(axis=1) > BLACK)
        top = int(lit[0] * back) if lit.size and lit[0] > h * 0.02 else 0
        bottom = int((lit[-1] + 1) * back) if lit.size and lit[-1] + 1 < h * 0.98 else height
        return Looked(tuple(faces), width, height, top, bottom)

    def crop(self, data: bytes, box: tuple[int, int, int, int]) -> bytes | None:
        """That part of an image, as a JPEG (CPU: run it in a thread)."""
        import numpy as np  # with OpenCV

        cv = self._cv
        image = cv.imdecode(np.frombuffer(data, np.uint8), cv.IMREAD_COLOR)
        if image is None:
            return None
        x, y, w, h = box
        done, encoded = cv.imencode(".jpg", image[y : y + h, x : x + w], [cv.IMWRITE_JPEG_QUALITY, 90])
        return bytes(encoded) if done else None

    def similarity(self, a: Face, b: Face) -> float:
        return float(self._recognizer.match(a.signature, b.signature, self._cv.FaceRecognizerSF_FR_COSINE))


# what an image's page says when it is a premiere, a festival, an interview, a « then and now » — the actor,
# not their character
EVENT = re.compile(
    r"premi[eè]re|festival|red carpet|tapis rouge|cannes|gala|arrives|attends|award|oscars?|c[ée]sar|"
    r"interview|photocall|press|conf[ée]rence|getty|wireimage|"
    r"then and now|now and then|today|aujourd|years later|ans apr[eè]s|avant.apr[eè]s|before and after",
    re.IGNORECASE,
)
# stock photographs carry their site's watermark
STOCK = re.compile(
    r"alamy|shutterstock|dreamstime|depositphotos|istockphoto|123rf|agefotostock|bigstock", re.IGNORECASE
)
SKIPPED_ENGINES = {"wikicommons.images"}  # public photographs of people: events, almost never a film's


# what a character's credit says besides their name
NOT_A_NAME = {"voice", "voix", "uncredited", "self", "himself", "herself", "archive", "footage", "young"}


def words(text: str | None) -> list[str]:
    """The words worth finding in a page's title (a character's or a film's name)."""
    found = re.findall(r"[\w'\u2019]+", (text or "").lower())
    return [w for w in found if len(w) >= 4 and w not in NOT_A_NAME]


@dataclass(frozen=True, slots=True)
class Candidate:
    url: str
    title: str
    engine: str
    similarity: float
    width: int
    height: int


def score(
    candidate: Candidate, character: str | None, film: str, *, faces: bool = True, actor: str | None = None
) -> float | None:
    """How good an image is for the card (``None``: not kept) — the actor's face first, then the page naming
    the character or the film, then its size. Without faces (an animated work, the check switched off): the
    page must name the character — and the actor, for a work played by people (a character may share the
    work's name)."""
    if candidate.engine in SKIPPED_ENGINES or (faces and candidate.similarity < SAME_PERSON):
        return None
    if STOCK.search(candidate.url):  # a stock photograph: watermarked
        return None
    if EVENT.search(candidate.title) or min(candidate.width, candidate.height) < 360:
        return None
    title = candidate.title.lower()
    named = any(w in title for w in words(character))
    in_film = any(w in title for w in words(film))
    if not (named or in_film) or (not faces and not named):
        return None  # nothing says it is from this work (or, unchecked, this character)
    if not faces and actor and not any(w in title for w in words(actor)):
        return None  # unchecked: the page must name the actor too
    return (
        (candidate.similarity if faces else 0.5)
        + (0.25 if named else 0.0)
        + (0.15 if in_film else 0.0)
        + (0.1 if min(candidate.width, candidate.height) >= 700 else 0.0)
    )
