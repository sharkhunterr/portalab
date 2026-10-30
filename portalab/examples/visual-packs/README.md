# Example visual packs

Every customizable look of Portalab can come from outside, its animations in its own files: Portalab only
provides the renderers, the sandbox and the contracts — all described in the authors' guide,
**[`docs/visual-packs.md`](../../docs/visual-packs.md)** (format, every element type, the sandbox protocol, the
data contracts of widgets, the analysis codes, the workflow). Complete examples:

- `nordlys/`: an interface (on a built-in navigation), a GPU level-up, GPU and CSS frames, a name style with its
  own font, a JavaScript celebration, a GPU ambience, a palette, a title, a badge, the theme pack and a booster;
- `abysses/`: the same, and **a navigation of its own** (`nav-sonar/`: a sonar bar that opens on the depths);
- `booster-scene/` (`maree`): **a whole booster scene** (spec 028, US5) — the deep as the stage's background, the
  booster as a cursed pirate's chest (its strip becomes the lid, its emblem a skull on the lock), an opening
  of its own that replaces Portalab's tear (the lid swings open, light, bubbles and coins, the cards escaping),
  card faces and backs shaped per rarity and GPU reveals for rare, epic and legendary cards;
- `booster-celeste/` (`celeste`), `booster-noel/` (`noel`), `booster-halloween/` (`graveyard`): **three more
  booster scenes**, each a whole opening — a GPU stage (deep space with nebulae and a ringed planet; a snowy
  night with an aurora and a garland; a graveyard under the moon with mist and bats), the sealed pack's own look
  (a starred foil and its moons; a gift box; a jack-o'-lantern and its candle), an opening of its own (a
  supernova; the ribbon undone in a spray of stars; ghosts and bats out of the pumpkin), a card back, a face
  per rarity with the holographic effect of issue 151 from rare up (a sheen sliding in ``screen``, glitter, the
  legendary art leaning) and GPU reveals for rare, epic and legendary cards;
  each scene carries a little tension — the sealed pack breathing with a double heartbeat, the dark closing in
  while it opens;
- `booster-horreur/` (`horreur`): **a scene made for dread** — a dying bulb at the end of a corridor and a
  figure standing in the doorway now and then, a chained box with a red eye at its keyhole, a long opening
  where the light dies, the heart races and claw marks appear before a red strobe, glitching faces (the
  photograph, the negative, rust and blood, the Eye) and reveals (static, crawling hands, the eye watching);
- `booster-odyssee/` (`odyssee`), `booster-retro/` (`retro8`), `booster-neon2077/` (`neon2077`): **a space
  battle** (asteroids, fighters weaving, a cargo container venting, a hyperspace jump), **an 8-bit game on a CRT**
  (a scrolling pixel world, a cartridge, a console powering on, pixel coins and fireworks) and **a cyberpunk
  megacity in the rain** (holograms, flying cars, a data shard hacked, its ICE shattering, neon arcs). Every
  scene's effects fade out inside an ellipse of their layer, so its box never shows.
- `booster-impact/` (`impact`): **an animated trading-card game's opening, drawn as a comic** — inked
  outlines, flat cel colours, halftone and hard edges everywhere; its opening and reveals are anime impact
  frames made in [EffectCraft](https://github.com/storytold/effectcraft) and played from WebP sprite sheets
  at 24 fps (sources and `build.sh` in `booster-impact-source/`): speed lines and halftone corners on black; a pack in flat violet with graffiti
  doodles, its art in an inked panel, spinning in crackling pink lightning and inked manga rays, cut by two
  huge white brush slashes, bursting in a white comic explosion that dissolves into halftone; media cards with
  a yellow comic title rimmed in red and ink, sticker badges and a holographic film in hard bands — a halftone
  shockwave for a rare, inked rays, lightning and a brush slash for an epic, and for a legendary a power vortex —
  energy ribbons whirling round the card, in front and behind — that blasts away into the biggest burst;
- `booster-sumi/` (`sumi`): **an opening in ink and gold, like Japanese lacquerware** — every animation drawn
  frame by frame in EffectCraft at 24 fps with a brush of bristles that lands heavy and runs dry, played as
  transparent videos (sources and `build.sh` in `booster-sumi-source/`), on a stage of black urushi lacquer where gold seigaiha waves rise and gold
  dust twinkles; a washi pack tied with mizuhiki cords, cut through by one huge dry-brush stroke after gold
  cracks run over it, bursting in a gilded ink splash and gold leaf, a great gold ensō drying away; cards of
  lacquer and washi with brushed titles and vermillion seals — an ensō and ripples for a rare, crossing
  vermillion strokes and a storm of cherry blossoms for an epic, and for a legendary an ink dragon, scaled and
  gilded, coiling round the card in front and behind before soaring away, leaving gold cracks across the stage;
- `rouages/`, `ruee-vers-l-or/`, `olympe/`: **three complete universes**, each one pack of every kind of look a
  member wears (no messenger bubble): an interface (colours, fonts, layout, sounds, its own words — « L'atelier »,
  « Le saloon », « Le temple »…; Olympe is a light one, on marble), a palette, a GPU ambience and profile
  background, a CSS frame and a GPU frame, a banner, a name style, a level badge, a GPU level-up, a GPU
  celebration, a notification style and animation, a title, a badge and the theme pack selling them all — and a
  whole booster scene any booster may wear (an engine room, a western train with the desert rolling by, the hall
  of the gods), with its card back, a face shaped per rarity and GPU reveals. They bring no booster of their own:
  a booster names the packs it draws from (Shop › Boosters).
- `briques/`: **a building-bricks universe, light and HD** — a bright plastic interface (studs along the header,
  cards set like bricks, the builders' words), and for several kinds both a light CSS look and an HD one drawn by
  the GPU: a brick rain (CSS) and bricks falling and stacking on a plate (HD), a town building itself brick by
  brick behind the profile, studded frames, banners, a name in plastic letters, level badges, a « Click! »
  level-up (CSS) and towers stacking up to a gold brick (HD), a burst of bricks, notifications on a plate that
  click in; and a booster scene all on the GPU — a playroom with a brick town, a crane and a window's light, a
  giant brick bursting into little ones, faces grey, clear blue, chrome and gold.
- `booster-cinema/` (`cinema`): **a movie palace** — the old film flickering on the screen, velvet curtains, the
  projector's beam through the dust, the audience in silhouette; a clapperboard as the sealed pack, an opening
  where it claps, the leader counts down and the film burns in the gate; film-frame backs and faces from the
  silent sepia card to the gala night's gold. The Cinema booster wears it and draws from every film universe.
- `widgets/` (`vigie`): **self-contained widgets** (spec 028, US6) — everything they do is in the pack: a new
  widget « Heading » (a compass of the member's progression, drawing itself on one line, in a column or as a
  block, with its own setting « dial » whose silver value is sold and night value offered, reading the
  portal's contracts and « Recently added »'s own data), a frame look for any widget, and options: « the
  swell » (a stylesheet animating any widget), « the sonar » (a script drawn over any widget) and « the
  logbook » (a script showing « Recently added » otherwise, with what the member is watching). Each element
  carries its rarity and its price, or is offered; the administrator decides at Review.

How to craft each kind of element well, with these examples as models:
**[`docs/visual-craft.md`](../../docs/visual-craft.md)**.

## Trying one

Drop a folder (or its `.zip`) into `DATA_DIR/visuals/inbox/` and read the inbox in Administration → Shop →
Visual packs, or upload the `.zip` there — then follow the six steps. Check a pack offline first:

```bash
cd backend && uv run portalab visuals analyse ../examples/visual-packs/widgets
```

Every example here passes the analysis with no blocking finding and no warning
(`backend/tests/unit/visuals/test_examples.py`).
