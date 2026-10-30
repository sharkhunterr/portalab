# Impact — sources

What draws the `booster-impact` pack (not part of the pack: the format takes no scripts of this kind).

- `effectcraft/impact.jsx` (+ `lib.jsx`): the four animations — the opening and the rare, epic and legendary
  reveals — as anime impact frames at 24 fps: inked flat shapes redrawn every twelfth of a second, moving on every frame (rays round the
  pack or the card, crackling lightning, speed lines, brush slashes, a comic explosion and its halftone
  dissolve, halftone shockwaves, glints, cel-shaded flames, goo drops). Built with
  [EffectCraft](https://github.com/storytold/effectcraft) (0.18, After Effects-style scripting), rendered as
  PNG frames with alpha.
- `sheets.py`: the frames assembled into the WebP sprite sheets (`frames.webp`) each part's stylesheet plays
  frame by frame (`steps()` on two axes).
- `gen_svgs.py`: the pack's comic shapes (slash, goo, emblem, doodles, binary digits, glint).
- `gen_faces.py`: the four card faces' stylesheets.

Rebuild everything: `EFFECTCRAFT=~/.local/opt/effectcraft/bin/effectcraft-cli ./build.sh` (Python 3 with
Pillow), then `uv run portalab visuals analyse ../booster-impact` from `backend/`.
