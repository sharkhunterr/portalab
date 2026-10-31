# Edition scenes — sources

The fourteen edition scene packs Mediacards' edition boosters wear — `booster-ed-<edition>` for nitrate, noir,
drivein, super8, film, laserdisc, vhs, zine, bubble, disc, leather, tiles, stream and glass — each staged in its
card frame's era (`portalab-editions`), built from one source: `./build.sh [edition [comp…]]` (Python 3, Node with
the frontend's dependencies, ffmpeg, and [EffectCraft](https://github.com/storytold/effectcraft) 0.18's
`effectcraft-cli` given by `EFFECTCRAFT`; `EDITIONS_WORK=<folder>` keeps the renders, `JOBS` slices side by side).

- `effectcraft/editions.jsx`: on the manga toolkit (`../booster-manga-source/effectcraft/core.jsx`), each
  edition's opening and its reveals over the whole screen (`place: screen`), timed on Portalab's takeover — the
  edition's screen until the card comes (0.9 s), a wipe, the card's stage, its turn (frame 42) — behind the card
  and over it. A background layer under each frame's light, so haze and glow show over it.
- `stages/*.glsl`: each scene's stage, written as a shader and played as a looping video
  (`../tools/stage_video.mjs`).
- `gen_editions.py`: everything else — emblems, the sealed pack's look, the back, the opening's stylesheet (each
  pack its own way of going), every manifest, and each edition's reveal (`CONCEPTS`): the card's way in (thrown
  on a desk, projected, spiralling out, rising like the sun, popping, a TV switching on, slapped like a sticker,
  floating up, coming down in the light, swinging, flipping like a tile, scanned as a hologram, sharpening out of
  a drop) and Portalab's word for the rarity — slammed on a slant (super8, film, laserdisc, zine), set otherwise
  (an intertitle, a neon sign, an arcade's blinking text, a panorama's title, a HUD's caption) or left out (noir,
  bubble, disc, leather, glass); fonts from `fonts/` (SIL OFL; Special
  Elite and Permanent Marker under Apache 2.0). No card faces: a card keeps its edition's frame.
