# Example visual packs

Every customizable look of Portalab can come from outside, its animations in its own files: Portalab only
provides the renderers, the sandbox and the contracts — all described in the authors' guide,
**[`docs/visual-packs.md`](../../docs/visual-packs.md)** (format, every element type, the sandbox protocol, the
data contracts of widgets, the analysis codes, the workflow). Four complete examples:

- `nordlys/`: an interface (on a built-in navigation), a GPU level-up, GPU and CSS frames, a name style with its
  own font, a JavaScript celebration, a GPU ambience, a palette, a title, a badge, the theme pack and a booster;
- `abysses/`: the same, and **a navigation of its own** (`nav-sonar/`: a sonar bar that opens on the depths);
- `booster-scene/` (`maree`): **a whole booster scene** (spec 028, US5) — the deep as the stage's background, the
  booster as a cursed pirate's chest (its strip becomes the lid, its emblem a skull on the lock), an opening
  of its own that replaces Portalab's tear (the lid swings open, light, bubbles and coins, the cards escaping),
  card faces and backs shaped per rarity and GPU reveals for rare, epic and legendary cards;
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
