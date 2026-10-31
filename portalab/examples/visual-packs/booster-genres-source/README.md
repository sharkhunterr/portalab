# Genre scenes — sources

The five genre scene packs Mediacards' genre boosters wear — [Blockbuster](../booster-blockbuster) (Action),
[Ténèbres](../booster-tenebres) (Sombre), [Rideau](../booster-rideau) (Drame), [Arcanes](../booster-arcanes)
(Fantastique), [Hyperespace](../booster-hyperespace) (Science-fiction) — built from one source: `./build.sh [key
[comp…]]` (Python 3, Node with the frontend's dependencies, ffmpeg, and
[EffectCraft](https://github.com/storytold/effectcraft) 0.18's `effectcraft-cli` given by `EFFECTCRAFT`;
`GENRES_WORK=<folder>` keeps the renders, `JOBS` slices side by side).

- `effectcraft/genres.jsx`: on the manga toolkit (`../booster-manga-source/effectcraft/core.jsx`), each genre's
  opening and its reveals over the whole screen (`place: screen`), timed on Portalab's takeover — the rarity's
  screen behind the name until the card comes (0.9 s), a wipe, the card's stage, its turn (frame 42) — behind the
  card and over it. Few, big, flat shapes: fire, steel and debris; claw marks, crows and cracks; velvet, a
  spotlight, roses; runes, a portal, wings of light; hyperspace and a ringed planet.
- `stages/*.glsl`: each scene's stage, written as a shader and played as a looping video
  (`../tools/stage_video.mjs`).
- `gen_genres.py`: everything else — emblems, the sealed pack's look, the back, the four faces, the opening's
  stylesheet (each pack its own way of going: blown up, clawed and torn, hidden by the curtain, dissolved, beamed
  away), the look of the rarity's name, every manifest; fonts from `fonts/` (SIL OFL).
