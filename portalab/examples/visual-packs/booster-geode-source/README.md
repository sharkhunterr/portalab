# Géode — sources

The drawn parts of the [Géode](../booster-geode) booster scene, and how to rebuild them: `./build.sh [comp…]`
(Python 3, ffmpeg, and [EffectCraft](https://github.com/storytold/effectcraft) 0.18's `effectcraft-cli`, given by
`EFFECTCRAFT`; `GEODE_WORK=<folder>` keeps the renders; `JOBS` slices built side by side, 4 by default).

- `effectcraft/geode.jsx` (+ `lib.jsx`): the animations, drawn frame by frame at 24 fps for video — faceted
  crystals (a hexagonal column ending in a point: three faces and a lit edge) growing in druses, crowns and fans,
  their glow (the same shapes blurred and added), shards turning as they fly, the geode's shell of stone in
  pieces, cracks of light, rays (prismatic for the legendary), rings and glints. Each comp is built in slices
  of 16 frames (`FROM`, `TO`: only their layers are made), side by side.
- The frames become the videos the parts play (`../tools/alpha_video.py`: H.264 MP4, the transparency beside the
  picture — `kind: video`, `alpha: side`): the opening; the rare and epic reveals; the legendary's reveal behind
  the card and its second video, over it (the near half of its belt of shards, glints).
- `gen_svgs.py`: the still shapes — rough stone lit in relief, veined pale stone, gem-cut facets, a geode cut in
  two, amethyst breaking through a chipped corner, cracks of light, a cut gem, a glint.
- `gen_faces.py`: the four card faces' stylesheets.

The font (Cinzel, OFL) is copied as is into the pack; the stage (`cavern.glsl`: inside a geode, its walls lined
with faceted amethyst points), the pack's look, the back and the opening's stylesheet are written by hand in the
pack itself.
