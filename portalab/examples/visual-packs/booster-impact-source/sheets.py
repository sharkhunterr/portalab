"""Assembles each animation's rendered frames (PNG with alpha) into a WebP sprite sheet in the pack — the grid
its stylesheet plays frame by frame (columns × rows, row after row)."""

import sys
from pathlib import Path

from PIL import Image

SHEETS = {"opening": ("opening-impact", 8), "reveal-rare": ("reveal-rare", 6), "reveal-epic": ("reveal-epic", 6),
          "reveal-legendary": ("reveal-legendary", 6), "legendary-front": ("face-legendary", 6),
          "legendary-back": ("face-legendary", 6)}
# the legendary's vortex lives on its face (over and under the card): its own file names
FILES = {"legendary-front": "vortex-front.webp", "legendary-back": "vortex-back.webp"}

if __name__ == "__main__":
    frames, pack = Path(sys.argv[1]), Path(sys.argv[2])
    for name, (element, cols) in SHEETS.items():
        files = sorted((frames / name).glob("*.png"))
        w, h = Image.open(files[0]).size
        rows = (len(files) + cols - 1) // cols
        sheet = Image.new("RGBA", (w * cols, h * rows), (0, 0, 0, 0))
        for i, file in enumerate(files):
            sheet.paste(Image.open(file).convert("RGBA"), ((i % cols) * w, (i // cols) * h))
        out = pack / "elements" / element / FILES.get(name, "frames.webp")
        sheet.save(out, "WEBP", quality=82, method=6, alpha_quality=90)
        print(f"{name}: {len(files)} frames, {cols}x{rows}, {out.stat().st_size // 1024} KB")
