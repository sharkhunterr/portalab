# Sumi — sources

The drawn parts of the [Sumi](../booster-sumi) booster scene, and how to rebuild them: `./build.sh` (Python 3 with
Pillow, and [EffectCraft](https://github.com/storytold/effectcraft) 0.18's `effectcraft-cli`, given by
`EFFECTCRAFT`; ffmpeg; `SUMI_WORK=<folder>` keeps the renders).

- `effectcraft/sumi.jsx` (+ `lib.jsx`): the six animations — the opening, the rare, epic and legendary reveals,
  and the legendary's ink dragon in two halves (over and under the card) — drawn frame by frame at 24 fps in
  ink and gold: a brush made of bristles (a heavy round press where it lands, its weight swelling and easing,
  the outer bristles running dry into streaks), gilded ink splashes, ensō drawn in one breath, gold leaf turning
  over, cherry petals and blossoms, gold cracks (kintsugi), ripples, rays and the dragon (scaled and gilded
  body, fins, vermillion mane, horns, whiskers). The reveals play behind the card; the dragon's front half over
  it.
- The frames become the videos the parts play (`../tools/alpha_video.py`: H.264 MP4, the transparency stacked
  under the picture — `kind: video`, `alpha: stacked`): the legendary's reveal plays its dragon's back half and,
  from when the dragon soars away, its reveal, behind the card, and the dragon's front half over it.
- `gen_svgs.py`: the still shapes — washi paper, the name's ink band (the same brush, in Python), mizuhiki cords,
  ensō, seigaiha and asanoha patterns, kintsugi seams, cherry blossoms, cut gold leaf, a glint, a seal.
- `gen_faces.py`: the four card faces' stylesheets.

The font (Yuji Syuku, OFL) is copied as is into the pack; the stage (`lacquer.glsl`), the pack's look, the back
and the opening's stylesheet are written by hand in the pack itself.
