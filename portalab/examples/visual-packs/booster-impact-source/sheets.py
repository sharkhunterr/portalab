"""Assembles each animation's rendered frames (PNG with alpha, 24 a second) into a WebP sprite sheet in the pack
— a grid, row after row, scaled down to keep the pack light — and writes, between its stylesheet's
``frames: begin`` / ``frames: end`` marks, the rule that plays it frame by frame (steps() on two axes)."""

import re
import sys
from pathlib import Path

from PIL import Image

FPS = 24
COLS = 8
# scaled to keep each sheet under the format's 5 MB and the pack under 20 MB: the opening, the largest, most
SCALE = {"opening": 0.66}
DEFAULT_SCALE = 0.75
# name: (element, file, stylesheet, the selector the frames are played on, the keyframes' prefix)
SPRITES = {
    "opening": ("opening-impact", "frames.webp", "spin.css", '[data-opening="impact"] .booster-stage__opening', "opening"),
    "reveal-rare": ("reveal-rare", "frames.webp", "reveal.css", '[data-reveal="impact-rare"] .booster-fx__scene', "reveal-rare"),
    "reveal-epic": ("reveal-epic", "frames.webp", "reveal.css", '[data-reveal="impact-epic"] .booster-fx__scene', "reveal-epic"),
    "reveal-legendary": ("reveal-legendary", "frames.webp", "reveal.css", '[data-reveal="impact-legendary"] .booster-fx__scene', "reveal-legendary"),
    "legendary-back": ("face-legendary", "vortex-back.webp", "face.css", '[data-card-face="impact-legendary"]::before,\n[data-card-face="impact-legendary"]::after', "vortex"),
    # the vortex's front half: the same grid, played by the same rule (face.css sets its own image on ::after)
    "legendary-front": ("face-legendary", "vortex-front.webp", None, None, None),
}


def rule(selector: str, file: str, prefix: str, cols: int, rows: int) -> str:
    return f"""{selector} {{
  background: url("{file}") 0 0 / {cols * 100}% {rows * 100}% no-repeat;
  animation: impact-{prefix}-x {cols / FPS:.4g}s steps({cols}) {rows} both, impact-{prefix}-y {cols * rows / FPS:.4g}s steps({rows}) both;
}}
@keyframes impact-{prefix}-x {{
  from {{ background-position-x: 0%; }}
  to {{ background-position-x: {cols / (cols - 1) * 100:.4f}%; }}
}}
@keyframes impact-{prefix}-y {{
  from {{ background-position-y: 0%; }}
  to {{ background-position-y: {rows / (rows - 1) * 100:.4f}%; }}
}}
"""


if __name__ == "__main__":
    frames, pack = Path(sys.argv[1]), Path(sys.argv[2])
    for name, (element, file, css, selector, prefix) in SPRITES.items():
        files = sorted((frames / name).glob("*.png"))
        w0, h0 = Image.open(files[0]).size
        scale = SCALE.get(name, DEFAULT_SCALE)
        w, h = round(w0 * scale), round(h0 * scale)
        rows = (len(files) + COLS - 1) // COLS
        sheet = Image.new("RGBA", (w * COLS, h * rows), (0, 0, 0, 0))
        for i, path in enumerate(files):
            frame = Image.open(path).convert("RGBA").resize((w, h), Image.LANCZOS)
            sheet.paste(frame, ((i % COLS) * w, (i // COLS) * h))
        folder = pack / "elements" / element
        sheet.save(folder / file, "WEBP", quality=78, method=6, alpha_quality=85)
        print(f"{name}: {len(files)} frames, {COLS}x{rows}, {(folder / file).stat().st_size // 1024} KB")
        if css:
            sheet_css = folder / css
            text = sheet_css.read_text()
            block = "/* frames: begin (written by booster-impact-source/sheets.py) */\n" + rule(selector, file, prefix, COLS, rows) + "/* frames: end */"
            text, n = re.subn(r"/\* frames: begin.*?/\* frames: end \*/", lambda _: block, text, flags=re.S)
            if n != 1:
                raise SystemExit(f"{sheet_css}: no frames marks")
            sheet_css.write_text(text)
