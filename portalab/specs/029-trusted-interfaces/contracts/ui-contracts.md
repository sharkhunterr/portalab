# Contract: Trust layer and member UI

## `<portalab-trust>` (host document, shadow root, own stylesheet)

- `confirmTrusted({operation, words, content: [{label, value}], text?, amount?, danger?}) → Promise<boolean>`:
  a `<dialog>` opened with `showModal()`; shows the words, every content line, the full free text, the amount
  and the member's seal (symbol + colour + word); buttons « Confirm » / « Cancel »; Escape cancels; focus
  trapped; announced to assistive technologies. Used by Portalab's own committing flows and by the broker.
- Exit control: a `popover="manual"` button « Back to Portalab » (with the seal's colour edge), bottom-start,
  shown while an interface app or a full-screen pack navigation is active; re-shown on top after any dialog.
- Notices: « This interface was stopped (too heavy / not answering) — Portalab's interface is back ».
- Safe-mode banner: « Safe mode — no pack is shown · Leave safe mode ».

## Account page

« Your seal »: 48 symbols × 12 colours grid and a word field; a preview of a confirmation; explains that a
confirmation without this seal is not Portalab's.

## Appearance page

« Complete interfaces »: cards (preview, name, forms, « reads: … », price/owned/offered, rarity), « Use on
this kind of device » per form, « Portalab's interface » always first; safe-mode switch.

## Admin (028 workflow)

Review step: per `interface_app`, operations grouped Reads / Actions / Committing with their words and a
check each; components the same. Test step: the two profiles' measures and probe results.
