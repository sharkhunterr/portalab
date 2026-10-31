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
- `booster-impact/` (`impact`, the source `booster-impact-video/` is made from — import that one: this one,
  26 MB of sprite sheets, would double it): **an animated trading-card game's opening, drawn as a comic** — inked
  outlines, flat cel colours, halftone and hard edges everywhere; its opening and reveals are anime impact
  frames made in [EffectCraft](https://github.com/storytold/effectcraft) and played from WebP sprite sheets
  at 24 fps (sources and `build.sh` in `booster-impact-source/`): speed lines and halftone corners on black; a pack in flat violet with graffiti
  doodles, its art in an inked panel, spinning in crackling pink lightning and inked manga rays, cut by two
  huge white brush slashes, bursting in a white comic explosion that dissolves into halftone; media cards with
  a yellow comic title rimmed in red and ink, sticker badges and a holographic film in hard bands — a halftone
  shockwave for a rare, inked rays, lightning and a brush slash for an epic, and for a legendary a power vortex —
  energy ribbons whirling round the card, in front and behind — that blasts away into the biggest burst;
- `booster-impact-video/` (`impact-video`): **Impact again, its animations played as transparent videos**
  rather than sprite sheets, from the same EffectCraft renders (`booster-impact-source/video.py`), to compare
  the two: at their full size, 7.5 MB against 27 MB; the legendary's vortex is its reveal's two videos (behind
  the card, then over it);
- `booster-geode/` (`geode`): **an opening inside a geode, made for video** — every animation drawn frame by
  frame in EffectCraft, with real glows (blurred, added light), and played as transparent videos (sources and
  `build.sh` in `booster-geode-source/`): a cavern whose walls are lined with faceted amethyst points flashing
  now and then (GLSL); a pack of rough stone chipped where amethyst breaks through, cracked with pulsing violet
  light, that trembles and bursts — a flash, a shockwave, its shell flying in pieces — into a crown of
  amethysts, citrine and quartz that glints then shatters into shards; cards set like stones (polished stone,
  blue quartz, amethyst, rainbow opal set in gold) with engraved titles — druses of quartz for a rare, a fan of
  amethysts and orbiting shards for an epic, and for a legendary prismatic rays, a crown of giant crystals of
  every gem and a belt of shards passing behind then over the card;
- `booster-shonen/`, `booster-magical/`, `booster-ninja/`, `booster-mecha/`: **a manga universe in four
  scenes**, built together from `booster-manga-source/` (one EffectCraft toolkit, one stylesheet generator) and
  played as high-quality videos (1.5× the earlier scenes; their stages too, as looping videos): a **fighting
  aura** — flames licking up round the pack, rocks lifting, ki lightning, a pillar of light, a golden aura for a
  legendary; a **magical girl's transformation** — magic circles, ribbons, hearts, stars, bubbles; **ninja
  techniques** — a smoke bomb, shuriken, kunai and blue lightning, a fire dragon summoned; **giant robots** — a
  HUD locking on, steam, armour flying off, a missile salvo, wings of energy. Each pack goes its own way:
  exploding, imploding, vanishing in smoke, shutting off like a screen;
- `booster-apotheose/` (`apotheose`): **every rarity staged over the whole screen** (`place: screen`, sources in
  `booster-apotheose-source/`, on the manga toolkit): the card brought to the middle, big, between two square
  videos cropped to cover any screen — behind it the screen exploding in cyan, pink or orange and gold spikes
  (orange bands cracked with lightning first, for a legendary); over it slashes of light, lightning and sparks —
  and the rarity's name, written by Portalab, slammed across the screen first in big comic letters; a neon
  violet pack sliced by a beam of light; neon-framed cards; a neon stage as a looping video;
- `booster-blockbuster/`, `booster-tenebres/`, `booster-rideau/`, `booster-arcanes/`, `booster-hyperespace/`,
  `booster-tresor/`, `booster-reportage/`, `booster-insomnie/`, `booster-fourire/`, `booster-crayon/`,
  `booster-scelles/`, `booster-idylle/`, `booster-brume/`, `booster-concert/`, `booster-chronique/`, `booster-front/`,
  `booster-saloon/`: **a scene per Mediacards genre booster** (Action, Horreur, Drame, Fantastique, Science-fiction, Aventure, Documentaire, Thriller, Comédie,
  Animation, Crime, Romance, Mystère, Musique, Histoire, Guerre, Western), built together from
  `booster-genres-source/`, each rarity its own moment over the whole screen in the genre's world — a chase, an
  explosion, the finale; a bulb, claws, a blood moon; a spotlight, the curtain, the ovation; runes, a portal, a
  dragon; a scope, the jump, a fleet; a treasure map, a sunken chest, an island; a viewfinder, a clapperboard,
  the archive; a tail in the rain, a countdown, a manhunt ending in bullet holes in the card; a party popper, a
  cream pie, the big show; a sketch, a flip book, the grand finale; a clue, the board, the crime scene; a love
  letter, the ball, love at first sight; a lantern, a keyhole, the riddle; a note, a record, the stadium; a sealed parchment, a mosaic, the triumph; flares over a trench, the bombing,
  victory; a wanted poster, the duel, a rider in the sunset — each pack going
  its own way as it opens, its stage a looping video;
- `booster-ed-nitrate/` … `booster-ed-glass/`: **a scene per media card edition** (the fourteen editions'
  boosters), built together from `booster-editions-source/`, each in its frame's era — a silent film's iris and
  Art Deco sun; a detective's board of clues under the blinds; an atomic drive-in; op-art rings; a 1970s sunset
  and the countdown leader; Memphis confetti and a rainbow disc; an arcade's pixel dusk; a photocopied collage;
  Y2K bubbles and code rain; a stained-glass rose window; balloons in a leather-framed sky; flat tiles turning
  over; a holographic grid; an aurora under liquid glass — no card faces, so the cards keep their edition's
  frame; each pack going its own way as it opens (burnt, shredded, popped, melted, torn, pixelated, lifted away…),
  each card its own way in, and the rarity's name slammed, set as the era would (an intertitle, a neon sign…) or left out;
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
