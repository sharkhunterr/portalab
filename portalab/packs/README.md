# Portalab's own visual packs (spec 028)

`builtin/` holds Portalab's own catalog as visual packs — the same format as any pack
(`examples/visual-packs/README.md`, `specs/028-visual-packs/contracts/pack-format.md`). The image ships them
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

**Slice B1**: every element is drawn by the portal's own code (`render.renderer = "builtin"`). Slice B2
moves the optional looks' CSS and GLSL into their elements' files, family by family. The **fallbacks never
move**: the default interfaces and each family's base look stay in the code, so whatever fails or is off falls
back to them.

Regenerate (from `backend/`, after a change to the catalog): `uv run python scripts/build_builtin_packs.py`.
`tests/unit/visuals/test_builtin_packs.py` checks every key of `tests/fixtures/builtin-looks-before.json` is
held by exactly one element and every pack passes the analysis.
