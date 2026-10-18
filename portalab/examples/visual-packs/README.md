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
- `widgets/` (`vigie`): **self-contained widgets** (spec 028, US6) — everything they do is in the pack: a new
  widget « Heading » (a compass of the member's progression, drawing itself on one line, in a column or as a
  block, with its own setting « dial » whose silver value is sold and night value offered, reading the
  portal's contracts and « Recently added »'s own data), a frame look for any widget, and options: « the
  swell » (a stylesheet animating any widget), « the sonar » (a script drawn over any widget) and « the
  logbook » (a script showing « Recently added » otherwise, with what the member is watching). Each element
  carries its rarity and its price, or is offered; the administrator decides at Review.

## Trying one

Drop a folder (or its `.zip`) into `DATA_DIR/visuals/inbox/` and read the inbox in Administration → Shop →
Visual packs, or upload the `.zip` there — then follow the six steps. Check a pack offline first:

```bash
cd backend && uv run portalab visuals analyse ../examples/visual-packs/widgets
```

Every example here passes the analysis with no blocking finding and no warning
(`backend/tests/unit/visuals/test_examples.py`).
