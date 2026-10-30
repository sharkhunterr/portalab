# Manga universe — sources

The four manga scene packs — [Shōnen](../booster-shonen), [Magical girl](../booster-magical),
[Ninja](../booster-ninja), [Mecha](../booster-mecha) — built from one source: `./build.sh [style [comp…]]`
(Python 3, Node with the frontend's dependencies, ffmpeg, and [EffectCraft](https://github.com/storytold/effectcraft)
0.18's `effectcraft-cli` given by `EFFECTCRAFT`; `MANGA_WORK=<folder>` keeps the renders, `JOBS` slices side by
side, `SCALE` the animations' size — 1.5 by default).

- `effectcraft/core.jsx`: the toolkit the four share — comps built in slices of 16 frames side by side and at a
  scale, each frame four layers (haze and glow: blurred and added light; main; top), and the manga effects:
  impact stars, rays, concentration and speed lines, halftone, flame auras (pointed tongues licking upwards,
  changing every other frame), lightning, stars, hearts, ribbons turning over, helices and bands round a card,
  magic circles, shuriken, kunai, smoke, rocks, energy blades, missiles.
- `effectcraft/shonen.jsx`, `magical.jsx`, `ninja.jsx`, `mecha.jsx`: each scene's opening, rare and epic reveals,
  and legendary reveal in two videos (behind the card, then over it).
- `stages/*.glsl`: each scene's stage, written as a shader and played as a looping video
  (`../tools/stage_video.mjs`: lighter for a phone than a full-screen shader every frame).
- `gen_packs.py`: everything else — still shapes (SVG), the sealed pack's look, the back, the four faces, the
  opening's and reveals' stylesheets (each pack its own way of going: exploding, imploding, vanishing in smoke,
  shutting off like a screen), every manifest; fonts from `fonts/` (SIL OFL).
