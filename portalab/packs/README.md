# Portalab's own visual packs (spec 028)

`builtin/` holds Portalab's own catalog as visual packs — the same format as any pack
(`docs/visual-packs.md`, `specs/028-visual-packs/contracts/pack-format.md`). The image ships them
at `/app/packs/builtin` (`PORTALAB_BUILTIN_PACKS_DIR` elsewhere); `portalab migrate`, every start of `serve`
and `portalab visuals builtin sync [--dry-run]` synchronise them.

| pack | what it holds | on by default |
|---|---|---|
| `portalab-socle` | the default interfaces (Portalab dark and light, light, dark, high contrast), the looks no product sells, the built-in navigations | always (never off) |
| `portalab-<universe>` | a universe: its interface and everything its « ultimate » pack holds | adopted on, new off |
| `portalab-hd-<collection>` | an HD collection and what it holds (when no universe does) | adopted on, new off |
| `portalab-season-<season>` | the looks of a season | adopted on, new off |
| `portalab-base` | every other look — the « base collection » | adopted on, new off |

« Adopted on »: the first synchronisation of a portal switches on every pack whose products the catalog
already has, touching nothing of them (prices, texts, availability, owners, equipped looks, preferences). A
pack new in a later release arrives switched off. The demo seed switches them all on; Administration →
Visual packs → « Portalab's » does it too.

**The packs are the source** (028, B2): every look Portalab offers is drawn by its element's own files — its
stylesheet (`look.css`), its GPU fragment (`<effect>.glsl`), an ambience's shader and layers (`render.params`:
flows, particles, landscape, CSS stand-in), a palette's colours (`palette`), an interface's definition and
stylesheet (`theme.json`, `theme.css`) — with its product, price, rarity, level and texts. Nothing of them is
written in the code, server or interface: the server lists what the packs hold, the interface reads it. What
stays in the code are the **fallbacks** drawn before any pack is read (first paint, sign-in): the socle's
looks and interfaces, each family's base rules. « Live weather » stays Portalab's renderer (drawn from the
weather report); the demo shop keeps only what no pack holds (`backend/src/portalab/app/demo_catalog.json`).

**Editing a pack**: change its files like any pack's, then stamp its version (from `backend/`):
`uv run python scripts/stamp_builtin_packs.py` — a release synchronises an edited pack only under a new
version. `tests/unit/visuals/test_builtin_packs.py` checks every pack's version follows its content, every key
of `tests/fixtures/builtin-looks-before.json` is held by exactly one element and every pack passes the
analysis; the one-off scripts that moved the looks out of the code are kept in `frontend/scripts/extract-*.mjs`.
