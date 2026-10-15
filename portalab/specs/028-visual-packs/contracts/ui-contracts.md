# UI Contracts (028)

## Administration → Appearance → Packs (`/admin/visuals`, `visuals.manage`)

- **Pack list**: one card per pack (built-in and imported together) — name, source badge (built-in / inbox /
  upload / GitHub), state chip (enabled / disabled / archived), current version, « update available »,
  owners count, element health (failures reported); filters by source/state; actions: *Read the inbox*,
  *Upload*, *From GitHub*, *Check for updates*. The socle shows no disable/remove action.
- **Version workflow** (`/admin/visuals/:pack/:version`): a horizontal stepper (vertical on phone) —
  Import · Analysis · Security · Test · Review · Validation — each step with its state icon (done / warning /
  blocking / to do), a summary line and the next action button; steps are links (revisit until published).
  - *Import*: source, fingerprint, size, files tree.
  - *Analysis*: element grid (type icon, name, look, kind), findings table filtered by level, conflicts.
  - *Security*: per element, what it would try and what the portal refuses (plain words); the « scripts may /
    may not » panel; confirmation checkboxes (scripts, each replaced look).
  - *Test*: stage tabs (shop card, profile, moment, navigation in phone/tablet/desktop frames, booster scene,
    widget); « Try on myself » toggle (session-only); measures table (compiled, fps, ready ms, errors),
    re-run button; results saved automatically.
  - *Review*: economy table (proposed vs decided, editable price/rarity/level/copies/collection), scene
    bindings, widget contracts with plain-words descriptions and accept checkboxes.
  - *Validation*: summary of decisions, *Publish* (confirmation dialog) or *Refuse* (reason).
- **Built-in « what changed »** panel on a built-in pack updated by a release.
- **Pack actions**: switch off/on, roll back (version picker), remove (dialog shows owners; explains archive
  vs removal), purge a never-published version.

## Administration → Security blocks (`/admin/security-blocks`, `security.manage`)

POC page kept: list (kind, who, reason, points, last paths, time left), *Lift* per row and *Lift all*.

## Protected surfaces

`data-protected` on: administration frame, `Dialog`/`ConfirmDialog`, purchase sheet and booster purchase,
booster opening confirmation, security pages, sign-in/registration/recovery pages. Interface vocabulary and
interface CSS never apply inside.

## Members

- Looks from packs appear in the shop, profile customizer, appearance page exactly like built-in ones;
  a look whose pack is off shows the default with a « currently unavailable » note in the owner's lists.
- Pack navigation (`PackNav`): keeps landmark, accessible name, skip link; falls back to the interface's
  built-in variant within 4 s; administration pages always use the built-in navigation.
- Booster opening: the portal draws the cards; pack parts draw the sealed look, opening, reveal effects,
  faces and backs; reduced motion reveals without animation.
- Dashboard: pack widgets in the gallery (with their data needs listed), widget styles in widget settings.
