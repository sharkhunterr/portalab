# Pack Format Contract (028)

The POC format (`examples/visual-packs/README.md`) generalised. `format: 1` packs of the POC stay valid.

## Layout

```text
pack.json                       {format: 1, id, version, names{fr,en}, descriptions{fr,en}, author, license, homepage?}
elements/<folder>/element.json  one element
elements/<folder>/…             its files: .css .glsl .js .json .svg .png .webp .jpg .woff2 .ogg .wav .txt
```

Limits (refused before anything is stored): archive ≤ 20 MB, ≤ 400 files, file ≤ 5 MB, path ≤ 200 chars,
no `..`, no absolute path, no link, no NUL, no other extension, folder names `^[a-z0-9][a-z0-9-]{0,47}$`.

## element.json

| field | rule |
|---|---|
| `type` | data-model `elements.type` vocabulary |
| `look` | the look key (required for every type that has one) |
| `product` | shop product key (default `<pack-prefix>_<look>`); absent for never-sold types |
| `names`, `descriptions` | `{fr, en}`; missing language → warning; both missing → blocking |
| `render` | `{kind: css\|glsl\|js\|theme\|data\|renderer, file?, css[]?, stage?, shape?, radius?, reveal?, duration?, nav?, renderer?, params?, rarity?}` |
| `economy` | proposed `{price, rarity, level, supply, collection, icon, repeatable, season}`; no price ⇒ reward only |
| `payload` | per type (below) |
| `palette` | palettes: `{dark: {accent, accentAlt, contrast}, light: {…}}` |
| `contracts` | widgets: data contract keys |
| `replaces` | `true`: takes over a look of the same key held elsewhere (explicit decision at Review) |

## Contracts per kind

- **css** — a look styles its own element only (selector starts on its hook, no `~ + :has() :root html
  body`); an interface's selectors start with `[data-theme="<key>"]` and never reach `[data-protected]`;
  `url()` only to the element's own files or `data:image|font`; no `@import`; keyframes and font families are
  namespaced by the portal (R15).
- **glsl** — POC contracts: *shape* (`p`, `d`, `ax`, `t`, `u_age`, helpers; writes `vec4 o`), *stage*
  (`gl_FragCoord`, `u_res`, `u_age`), *ambient* (full shader after helpers, premultiplied `gl_FragColor`).
  Reserved names refused, and so is declaring again, at the body's own level, a name the portal gives it
  (`p`, `ax`, `d`, `t`, `o` — a loop or a block of its own may shadow them); compile measured at Test.
- **js** — one ES module, no `import`, default export `mount(root, api)` returning a stop function; runs in
  the sandbox (see `sandbox-protocol.md`). Any `js` element requires the `scripts` confirmation.
- **theme** — an interface definition (theme schema v2 of 022/027): colours, fonts, layout, navigation (a
  built-in variant or the pack's `navigation` look), vocabulary (only `nav:…`, `…title`,
  `gamification:value.…`), the looks it wears; must pass the contrast floor.
- **renderer** — `{renderer, params}` for a portal renderer: `particles`, `flow`, `mesh`, `weather`,
  `nav:<variant>`; `params` validated against the renderer's schema.
- **data** — no file; `payload` only.

## Payload per type

| type | payload |
|---|---|
| `badge`, `title` | `{label{fr,en}, icon, style}` |
| `bundle`, `theme_pack` | `{products: [key…]}` — products of this pack, of the socle or of the « base collection » |
| `booster` | `{pool: {collections[], seasons[], packs[]}, packs, cards, odds{rarity: %}, guarantee?}` |
| `booster_scene` | `{parts: {booster_look?, backdrop?, opening?, reveal{common?,rare?,epic?,legendary?}, face{…}, back{…}}}` — element folders of this pack |
| `booster_backdrop` | the stage's animated background (css under its hook, a GLSL stage or ambience, or a script); replaces Portalab's mist, beams and glow |
| `booster_look`, `card_face`, `card_back` | none; `render.rarity` for faces and backs. Their CSS may change the **shape** too (outline, `clip-path`, `border-radius`, proportions), not only the dressing — a hexagonal legendary card, a rounded booster — set on `.booster-card__face` / `.booster-card__back` themselves, never on the part that turns in 3D (`.booster-card__inner`: a clip or `overflow` there flattens the turn). Face down, a card always wears the `common` back (a back never tells the rarity) |
| `booster_opening` with `duration` | **replaces** Portalab's tear (a booster inflating then bursting, a chest's lid swinging open…): its `duration` (≤ 4 s) is the time before the cards come. Portalab stills its own strip, glow and rising cards meanwhile; the opening's CSS may bring them back with its own movement (a lid swinging, cards escaping) |
| `booster_opening` | render `stage`, `duration` ≤ 4 s |
| `card_reveal` | render `stage`, `rarity`, `duration` ≤ 3 s |
| `widget` | `{sizes: [{w,h}], refresh_s, empty{fr,en}}` + `contracts` |
| `widget_style` | none (css hook `[data-widget-style="<look>"]`) |
| `navigation` | render `nav: {position: top\|bottom\|left\|right\|floating, size, expands}` |

## Analysis findings (codes)

`format.*` (manifest, files, kinds, sizes), `look.*` (invalid, builtin conflict, pack conflict, replaces),
`text.*` (missing language), `css.*` (scope, import, address, at-rule), `glsl.*` (contract, reserved),
`js.*` (network, storage, eval, portal API, import), `economy.*` (outside the portal's rules), `theme.*`
(invalid, contrast floor, unknown reference), `scene.*` (unknown part, duration), `widget.*` (unknown
contract, size), `bundle.*` (unknown product). Level: `blocking` \| `warning` \| `info`; category:
`analysis` \| `security` (shown at the Security step).
