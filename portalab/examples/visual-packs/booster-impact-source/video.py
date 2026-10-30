"""Makes ``booster-impact-video`` — Impact again, its animations played as videos rather than sprite sheets
(issue 287), to compare the two: the same pack, the same EffectCraft renders (``build.sh`` with IMPACT_WORK
keeps them), at their full size. Its looks are ``impact-video…`` (a look belongs to one pack); the legendary's
vortex, a face's sprite sheets in Impact, becomes its reveal's two videos (behind the card, then over it).

    video.py <IMPACT_WORK>/frames
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "booster-impact"
PACK = HERE.parent / "booster-impact-video"
TOOL = HERE.parent / "tools" / "alpha_video.py"
FRAMES_BLOCK = re.compile(r"/\* frames: begin.*?/\* frames: end \*/\n", re.S)
# name: (element, video, its frame folders from the bottom up)
VIDEOS = {
    "opening": ("opening-impact", "opening.mp4", ["opening"]),
    "reveal-rare": ("reveal-rare", "reveal.mp4", ["reveal-rare"]),
    "reveal-epic": ("reveal-epic", "reveal.mp4", ["reveal-epic"]),
    "reveal-legendary": ("reveal-legendary", "reveal.mp4", ["reveal-legendary", "legendary-back"]),
    "legendary-over": ("reveal-legendary", "over.mp4", ["legendary-front"]),
}


def renamed(text: str) -> str:
    """Impact's looks as this pack's: ``impact`` → ``impact-video``, ``impact-rare`` → ``impact-video-rare``."""
    return re.sub(r'(data-[a-z-]+=\\?")impact(-|\\?")', r"\1impact-video\2", text).replace('"look": "impact', '"look": "impact-video')


def main(frames: Path) -> None:
    shutil.rmtree(PACK, ignore_errors=True)
    shutil.copytree(SOURCE, PACK, ignore=shutil.ignore_patterns("*.webp", "still.glsl"))
    for path in PACK.rglob("*"):
        if path.suffix in (".css", ".json"):
            path.write_text(renamed(path.read_text()))
    pack = json.loads((PACK / "pack.json").read_text())
    pack["id"] = "impact-video"
    pack["names"] = {"fr": "Impact vidéo — scène de booster manga", "en": "Impact video — an anime booster scene"}
    for lang, note in (("fr", " Ses animations sont jouées en vidéo (même rendu qu'Impact, pour comparer)."),
                       ("en", " Its animations play as videos (the same renders as Impact's, to compare).")):  # fmt: skip
        pack["descriptions"][lang] += note
    (PACK / "pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n")
    # the parts drawn from frames: videos now, their stylesheets keeping only the room they take
    for element, video, _ in VIDEOS.values():
        manifest = PACK / "elements" / element / "element.json"
        data = json.loads(manifest.read_text())
        data["render"].update(kind="video", alpha="side")
        data["render"]["over" if video == "over.mp4" else "file"] = video
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        for css in data["render"].get("css", []):
            sheet = PACK / "elements" / element / css
            sheet.write_text(FRAMES_BLOCK.sub("", sheet.read_text()).replace("frames.webp, ", "a video, "))
    # the legendary's face: no vortex of its own any more (its reveal plays it)
    face = PACK / "elements" / "face-legendary" / "face.css"
    text = FRAMES_BLOCK.sub("", face.read_text())
    text = re.sub(r"/\* as it turns: the power vortex.*?@media \(max-width: 40rem\) \{.*?\n  \}\n\}\n", "", text, flags=re.S)
    text = text.replace('  [data-card-face="impact-video-legendary"]::before,\n  [data-card-face="impact-video-legendary"]::after,\n', "")
    face.write_text(text)
    for _, (element, video, folders) in VIDEOS.items():
        subprocess.run([sys.executable, str(TOOL), str(PACK / "elements" / element / video), *(str(frames / f) for f in folders)], check=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
