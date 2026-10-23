"""Issue 229: a character cut out — the model's answer made firmer, kept as a WebP with its transparency."""

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from portalab.modules.cards.cutouts import SIZE, Cutter


class HeadOnly:
    """A model keeping a head alone, its body taken for background."""

    def setInput(self, blob: Any) -> None:
        pass

    def forward(self) -> Any:
        found = np.zeros((1, 1, SIZE, SIZE), np.float32)
        found[..., : SIZE // 2, SIZE // 3 : 2 * SIZE // 3] = 1.0
        return found


class Halves:
    """A model seeing the character in the left half only."""

    def setInput(self, blob: Any) -> None:
        assert blob.shape == (1, 3, SIZE, SIZE)

    def forward(self) -> Any:
        found = np.zeros((1, 1, SIZE, SIZE), np.float32)
        found[..., : SIZE // 2] = 1.0
        return found


def test_the_background_goes_the_character_stays(tmp_path: Path) -> None:
    cutter = Cutter(tmp_path)
    cutter._cv, cutter._net = cv2, Halves()
    _, jpeg = cv2.imencode(".jpg", np.full((400, 300, 3), 200, np.uint8))
    webp = cutter.cut(jpeg.tobytes())
    assert webp is not None and webp[:4] == b"RIFF" and webp[8:12] == b"WEBP"
    image = cv2.imdecode(np.frombuffer(webp, np.uint8), cv2.IMREAD_UNCHANGED)
    assert image.shape == (400, 300, 4)
    assert image[200, 40, 3] == 255 and image[200, 260, 3] == 0
    assert cutter.cut(b"not an image") is None


def test_a_head_kept_alone_is_no_cut_out(tmp_path: Path) -> None:
    cutter = Cutter(tmp_path)
    cutter._cv, cutter._net = cv2, HeadOnly()
    _, jpeg = cv2.imencode(".jpg", np.full((400, 300, 3), 200, np.uint8))
    assert cutter.cut(jpeg.tobytes()) is None
