# Genre scenes — sources

The genre scene packs Mediacards' genre boosters wear — [Blockbuster](../booster-blockbuster) (Action),
[Ténèbres](../booster-tenebres) (Horreur), [Rideau](../booster-rideau) (Drame), [Arcanes](../booster-arcanes)
(Fantastique), [Hyperespace](../booster-hyperespace) (Science-fiction), [Trésor](../booster-tresor) (Aventure),
[Reportage](../booster-reportage) (Documentaire), [Insomnie](../booster-insomnie) (Thriller), [Fou rire](../booster-fourire)
(Comédie), [Crayonné](../booster-crayon) (Animation), [Scellés](../booster-scelles) (Crime), [Idylle](../booster-idylle)
(Romance), [Brume](../booster-brume) (Mystère), [Concert](../booster-concert) (Musique), [Chronique](../booster-chronique)
(Histoire), [Front](../booster-front) (Guerre), [Saloon](../booster-saloon) (Western) — built from one source: `./build.sh [key
[comp…]]` (Python 3, Node with the frontend's dependencies, ffmpeg, and
[EffectCraft](https://github.com/storytold/effectcraft) 0.18's `effectcraft-cli` given by `EFFECTCRAFT`;
`GENRES_WORK=<folder>` keeps the renders, `JOBS` slices side by side).

- `effectcraft/genres.jsx`: on the manga toolkit (`../booster-manga-source/effectcraft/core.jsx`), each genre's
  opening and its reveals over the whole screen (`place: screen`), timed on Portalab's takeover — the rarity's
  screen behind the name until the card comes (0.9 s), a wipe, the card's stage, its turn (frame 42) — behind the
  card and over it — each rarity its own moment (a genre's `rarities`: a chase, an explosion, the finale…).
  Few, big, flat shapes: fire, steel and debris; claw marks, crows and cracks; velvet, a spotlight, roses;
  runes, a portal, a dragon; hyperspace, a ringed planet, a fleet; a treasure map, a sunken chest, an island; a
  viewfinder, a clapperboard, reels; rain, a clock's pulse, a reticle and bullet holes in the card; confetti, a
  cream pie, balloons; pencil lines, a bouncing ball, a rainbow; a fingerprint, red strings, a chalk outline;
  hearts, a waltz, Cupid's arrow; a lantern, gears, question marks; notes, a record, lasers.
- `stages/*.glsl`: each scene's stage, written as a shader and played as a looping video
  (`../tools/stage_video.mjs`).
- `gen_genres.py`: everything else — emblems, the sealed pack's look, the back, the four faces, the opening's
  stylesheet (each pack its own way of going: blown up, clawed and torn, hidden by the curtain, dissolved, beamed
  away), the look of the rarity's name, every manifest; fonts from `fonts/` (SIL OFL).
