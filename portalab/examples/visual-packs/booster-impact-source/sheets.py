"""Assembles each animation's rendered frames (PNG with alpha, 24 a second) into a WebP sprite sheet in the pack
— a grid, row after row, scaled down to keep the pack light — and writes, between its stylesheet's
``frames: begin`` / ``frames: end`` marks, the rule that plays it frame by frame (steps() on two axes).

Each animation also gets a lighter sheet for phones (``-phone``), played below 40rem: no side longer than
4096 px — beyond it many phones' graphics can't hold the image and the browser decodes it again for nearly
every frame, a few frames a second — and no more than PHONE_PIXELS pixels, so a legendary's three sheets fit
in a phone's memory together. A phone downloads only its own sheets."""

import re
import sys
from pathlib import Path

from PIL import Image

FPS = 24
COLS = 8
# scaled to keep each sheet under the format's 5 MB and the pack under 40 MB: the opening, the largest, most
SCALE = {"opening": 0.66}
DEFAULT_SCALE = 0.75
PHONE_SIDE = 4096
PHONE_PIXELS = 12_000_000
# name: (element, file, stylesheet, the selector the frames are played on, the keyframes' prefix)
# (the vortex's front half shares its back half's grid and rule; vortex() sets its own image on ::after)
SPRITES = {
    "opening": ("opening-impact", "frames.webp", "spin.css", '[data-opening="impact"] .booster-stage__opening', "opening"),
    "reveal-rare": ("reveal-rare", "frames.webp", "reveal.css", '[data-reveal="impact-rare"] .booster-fx__scene', "reveal-rare"),
    "reveal-epic": ("reveal-epic", "frames.webp", "reveal.css", '[data-reveal="impact-epic"] .booster-fx__scene', "reveal-epic"),
    "reveal-legendary": ("reveal-legendary", "frames.webp", "reveal.css", '[data-reveal="impact-legendary"] .booster-fx__scene', "reveal-legendary"),
    "legendary-back": ("face-legendary", "vortex-back.webp", "face.css", '[data-card-face="impact-legendary"]::before,\n[data-card-face="impact-legendary"]::after', "vortex"),
    "legendary-front": ("face-legendary", "vortex-front.webp", None, None, None),
}


FRONT = '[data-card-face="impact-legendary"]::after'


def phone(file: str) -> str:
    return file.replace(".webp", "-phone.webp")


def phone_grid(count: int, w: int, h: int) -> tuple[int, float]:
    """The columns and scale giving the sharpest phone sheet within PHONE_SIDE and PHONE_PIXELS."""
    best = (COLS, 0.0)
    for cols in range(4, 13):
        rows = (count + cols - 1) // cols
        scale = min(PHONE_SIDE / (cols * w), PHONE_SIDE / (rows * h), (PHONE_PIXELS / (count * w * h)) ** 0.5, 1.0)
        if scale > best[1]:
            best = (cols, scale)
    return best


def keyframes(prefix: str, cols: int, rows: int) -> str:
    return f"""@keyframes impact-{prefix}-x {{
  from {{ background-position-x: 0%; }}
  to {{ background-position-x: {cols / (cols - 1) * 100:.4f}%; }}
}}
@keyframes impact-{prefix}-y {{
  from {{ background-position-y: 0%; }}
  to {{ background-position-y: {rows / (rows - 1) * 100:.4f}%; }}
}}
"""


def rule(selector: str, file: str, prefix: str, grid: tuple[int, int], phone_grid: tuple[int, int]) -> str:
    def play(file: str, prefix: str, cols: int, rows: int, pad: str) -> str:
        return f"""{pad}background: url("{file}") 0 0 / {cols * 100}% {rows * 100}% no-repeat;
{pad}animation: impact-{prefix}-x {cols / FPS:.4g}s steps({cols}) {rows} both, impact-{prefix}-y {cols * rows / FPS:.4g}s steps({rows}) both;
"""

    front = f"{FRONT} {{\n  background-image: url(\"vortex-front.webp\");\n}}\n" if prefix == "vortex" else ""
    phone_front = f"  {FRONT} {{\n    background-image: url(\"vortex-front-phone.webp\");\n  }}\n" if prefix == "vortex" else ""
    phone_selector = selector.replace("\n", "\n  ")
    return (
        f"{selector} {{\n{play(file, prefix, *grid, '  ')}}}\n{front}"
        f"@media (max-width: 40rem) {{\n  {phone_selector} {{\n{play(phone(file), prefix + '-phone', *phone_grid, '    ')}  }}\n{phone_front}}}\n"
        + keyframes(prefix, *grid)
        + keyframes(prefix + "-phone", *phone_grid)
    )


def sheet(files: list[Path], w: int, h: int, cols: int, out: Path) -> int:
    rows = (len(files) + cols - 1) // cols
    image = Image.new("RGBA", (w * cols, h * rows), (0, 0, 0, 0))
    for i, path in enumerate(files):
        frame = Image.open(path).convert("RGBA").resize((w, h), Image.LANCZOS)
        image.paste(frame, ((i % cols) * w, (i // cols) * h))
    image.save(out, "WEBP", quality=78, method=6, alpha_quality=85)
    return rows


if __name__ == "__main__":
    frames, pack = Path(sys.argv[1]), Path(sys.argv[2])
    for name, (element, file, css, selector, prefix) in SPRITES.items():
        files = sorted((frames / name).glob("*.png"))
        w0, h0 = Image.open(files[0]).size
        scale = SCALE.get(name, DEFAULT_SCALE)
        folder = pack / "elements" / element
        rows = sheet(files, round(w0 * scale), round(h0 * scale), COLS, folder / file)
        cols_p, scale_p = phone_grid(len(files), w0, h0)
        wp, hp = int(w0 * scale_p), int(h0 * scale_p)
        rows_p = sheet(files, wp, hp, cols_p, folder / phone(file))
        print(
            f"{name}: {len(files)} frames, {COLS}x{rows}, {(folder / file).stat().st_size // 1024} KB;"
            f" phone {cols_p}x{rows_p} of {wp}x{hp} ({cols_p * wp}x{rows_p * hp}), {(folder / phone(file)).stat().st_size // 1024} KB"
        )
        if css:
            sheet_css = folder / css
            text = sheet_css.read_text()
            block = "/* frames: begin (written by booster-impact-source/sheets.py) */\n" + rule(selector, file, prefix, (COLS, rows), (cols_p, rows_p)) + "/* frames: end */"
            text, n = re.subn(r"/\* frames: begin.*?/\* frames: end \*/", lambda _: block, text, flags=re.S)
            if n != 1:
                raise SystemExit(f"{sheet_css}: no frames marks")
            sheet_css.write_text(text)
