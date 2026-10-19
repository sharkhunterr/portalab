# Visual packs — the authors' guide (spec 028)

Every look of Portalab can come from a **visual pack**: an interface, a navigation of its own, profile designs,
level-ups and celebrations, ambiences, notification looks, palettes, badges and titles, a whole booster scene,
widgets with their looks and options. Portalab ships its own catalog as packs (`packs/builtin/`); the
administrator imports others, checks them step by step and decides what is sold. A pack carries **all** its
logic (its stylesheets, its GPU shaders, its scripts): Portalab only provides the renderers, the sandbox and
the contracts below.

Four complete examples live in [`examples/visual-packs/`](../examples/visual-packs/README.md): `nordlys` (an
interface and its looks), `abysses` (the same with a navigation of its own), `booster-scene` (a whole booster
scene) and `widgets` (self-contained widgets, their looks and options).

How to make each element **good** — composition, light, motion, phone first, the rarity staircase and the
pitfalls met so far — is in [**crafting looks that work**](visual-craft.md).

## Contents

1. [The workflow](#the-workflow)
2. [The format](#the-format)
3. [Element types](#element-types)
4. [Rendering contracts](#rendering-contracts)
5. [Booster scenes](#booster-scenes)
6. [Widgets](#widgets)
7. [Navigations](#navigations)
8. [The sandbox protocol](#the-sandbox-protocol)
9. [The analysis](#the-analysis)
10. [Tooling](#tooling)
11. [Security](#security)

## The workflow

Administration → Shop → **Visual packs** (permission `visuals.manage`, reserved to the Admin). A version goes
through six steps; each one shows what it found, and the next opens only when nothing blocks.

| step | what happens |
|---|---|
| **Import** | from the inbox (`DATA_DIR/visuals/inbox/`, a folder or a `.zip`), an upload (`.zip`, 20 MB at most) or a GitHub address (`https://github.com/<owner>/<repo>[/tree/<ref>/<folder>]`: the latest release or the default branch; *Check for updates* compares versions and never installs on its own). Each version is stored apart, under its fingerprint |
| **Analysis** | the format, the files, the look keys, the economy, the texts — see [the analysis](#the-analysis) |
| **Security** | what the stylesheets and scripts would try, and what Portalab refuses anyway |
| **Test** | the elements drawn in a sandbox in the administrator's browser: GPU looks compiled, frames per second, scripts started; « try on myself » for this session only |
| **Review** | each element's economy — the pack proposes, the administrator keeps or changes it: price (or reward only), rarity, minimum level, copies, and for widgets « sold » or « offered to everyone »; the confirmations (scripts, a look taken over, each data contract a widget asks for); booster scenes bound to every booster, one or none |
| **Validation** | publication: the elements become shop products (or are offered), the looks go live for every member within moments |

A published version never changes in place: new content needs a new version number. A pack can be **switched
off** (its products leave the shop, owners keep them and see them « currently unavailable », wearers see the
default), **rolled back** to an earlier validated version (with the economy decided then), **archived** (while
someone owns one of its products) or **removed** for good (once nobody does). Versions never published can be
purged. Every action is in the audit log.

## The format

```text
pack.json                       {format: 1, id, version, names{fr,en}, descriptions{fr,en}, author, license, homepage?}
elements/<folder>/element.json  one element
elements/<folder>/…             its files: .css .glsl .js .json .svg .png .webp .jpg .woff2 .ogg .wav .txt
```

Limits (refused before anything is stored): archive ≤ 20 MB, ≤ 400 files, file ≤ 5 MB, path ≤ 200 characters,
no `..`, no absolute path, no link, no NUL, no other extension, folder names `^[a-z0-9][a-z0-9-]{0,47}$`. The
pack's `id` and look keys: lowercase letters, digits, `-` and `_` (48 at most); `portalab-…` is reserved.

`element.json`:

| field | rule |
|---|---|
| `type` | one of the [element types](#element-types) |
| `look` | the look's key — what preferences and profiles store, what the interface's `data-*` attributes carry; required for every type that has one; never a built-in look's or another pack's (unless `replaces`) |
| `product` | the shop product's key (default `<prefix>_<look>`) |
| `names`, `descriptions` | `{fr, en}` (one missing: a warning; both: blocking) |
| `render` | `{kind: css\|glsl\|js\|theme\|data\|renderer, file?, css[]?, stage?, shape?, radius?, reveal?, duration?, nav?, rarity?, place?}` |
| `economy` | proposed `{price, rarity, level, supply, collection, icon, repeatable, season, sold}` — no price: reward only; `sold: false`: offered to everyone (widgets, their looks and options) |
| `payload` | per type (below) |
| `palette` | palettes: `{dark: {accent, accentAlt, contrast}, light: {…}}` |
| `contracts` | widgets and script options: the data they ask for |
| `replaces` | `true`: takes over a look of the same key held elsewhere (the administrator decides at Review) |
| `preview` | an image of the element (optional) |

## Element types

| type | drawn with | its hook / contract | payload |
|---|---|---|---|
| `theme` (an interface) | `theme` | a theme definition (colours, fonts, layout, navigation, vocabulary, the looks it wears); its `css` under `[data-theme="<key>"]` | — |
| `navigation` | `js`, `renderer` | see [navigations](#navigations); never sold alone | — |
| `palette` | `data` | `palette` | — |
| `ambient`, `profile_background` | `css`, `glsl` | `[data-ambient="<look>"]`, or a GLSL ambience | — |
| `avatar_frame` | `css`, `glsl` | `.avatar-frame[data-frame="<look>"]`, or a GLSL shape | — |
| `profile_banner` | `css` | `.profile-banner[data-banner="<look>"]` | — |
| `name_style` | `css` | `.name-style[data-name="<look>"]` | — |
| `level_badge` | `css`, `glsl` | `.ds-level[data-look="<look>"]`, or a GLSL shape | — |
| `level_up` | `css`, `glsl`, `js` | `.levelup[data-look="<look>"]`, a GLSL stage, or a script | — |
| `effect` (celebration) | `css`, `glsl`, `js` | `[data-effect="<look>"]`, a GLSL stage, or a script | — |
| `notification_style`, `notification_animation` | `css` | `[data-style="<look>"]`, `[data-animation="<look>"]` on the notification | — |
| `badge`, `title` | `css`, `glsl`, `data` | `[data-style="<look>"]` | `{label{fr,en}, icon, style}` |
| `bundle`, `theme_pack` | `data` | — | `{products: [key…]}` (this pack's, the socle's or the base collection's) |
| `booster` | `data` | — | `{pool: {collections[], seasons[], packs[]}, packs, cards, odds{rarity: %}, guarantee?}` |
| `booster_scene` and its parts | see [booster scenes](#booster-scenes) | | |
| `widget`, `widget_style`, `widget_option` | see [widgets](#widgets) | | |

## Rendering contracts

- **CSS**: a look styles **its own element only** — every selector starts on its hook (the table above; `~=`
  where an element wears several looks, a widget's options) and goes no further than inside it: no sibling
  (`~`, `+`), no `:has()`, never `:root`, `html` or `body`. An interface's selectors all start with
  `[data-theme="<key>"]`, and Portalab makes each of them skip the protected surfaces (administration,
  purchases, confirmations, security pages, sign-in). `url()` only to the element's own files or
  `data:image|font`; no `@import`; fonts by `@font-face` (a font usurping Portalab's own families is refused);
  keyframes and font families are renamed per pack by the portal (no clash between packs). The analysis blocks
  what breaks these rules, and the browser enforces them again on its own reading of each sheet.
- **GLSL, a shape** (frames, level badges, badges, titles, notifications): a fragment of `main()` receiving `p`
  (position in half heights), `d` (distance to the shape's edge, < 0 inside), `ax` (width / height), `t`
  (time), `u_age`, and `hash()`, `noise()`, `fbm()`, `over()`; it writes its colour into `vec4 o`. `shape`
  picks the outline (0 rounded box, 1 hexagon, 2 diamond, 3 shield…), `radius` its rounding.
- **GLSL, a stage** (`"stage": true`: level-ups, celebrations, booster scene parts): the same over its whole
  box (`gl_FragCoord`, `u_res`, `u_age` = seconds since it started). Fade its edges: never the outline of its box.
- **GLSL, an ambience**: a complete shader after the common helpers (`u_res`, `u_time`, `hash`, `noise`, `fbm`,
  `over`), defining `main()` and writing premultiplied colour into `gl_FragColor`.
- Names GLSL reserves are refused, and so is declaring again, at the body's own level, a name the portal gives
  it (`p`, `ax`, `d`, `t`, `o` — a loop or a block of its own may shadow them).
- **JS**: one ES module, no `import`, default export `mount(root, api)` returning what stops it; it **always**
  runs in the [sandbox](#the-sandbox-protocol). Any script asks for the administrator's explicit confirmation.

## Booster scenes

A `booster_scene` element (`data`, never sold) names the parts of a whole booster opening — each one an element
folder of the same pack — and is bound at Review to every booster, one or none. Whatever it does not bring
stays Portalab's; the cards and their rarities are always the ones the server drew.

```json
{ "type": "booster_scene", "look": "maree", "render": { "kind": "data" },
  "payload": { "parts": { "booster_look": "look-maree", "backdrop": "backdrop-maree", "opening": "opening-coffre",
    "back": { "common": "back-maree" }, "face": { "common": "face-common", "legendary": "face-legendary" },
    "reveal": { "legendary": "reveal-legendary" } } } }
```

| part | hook | rules |
|---|---|---|
| `booster_backdrop` | `[data-booster-backdrop="<look>"]`; a GLSL stage, an ambience or a script | the stage's animated background, in place of Portalab's mist, beams and glow |
| `booster_look` | `[data-booster-look="<look>"]` on the sealed pack | its dress **and its shape** (the strip is `.booster-pack__flap`, the emblem `.booster-pack__emblem`); a GLSL stage around it |
| `booster_opening` | `[data-opening="<look>"]` while it opens | `duration` ≤ 4 s: **replaces** Portalab's tear (inflating then bursting, a lid swinging open…), and its duration is when the cards come; Portalab stills its strip, glow and rising cards meanwhile, the opening may bring them back with its own movement |
| `card_face`, `card_back` | `[data-card-face]`, `[data-card-back]` | per rarity (`render.rarity`); the shape goes on `.booster-card__face` / `.booster-card__back`, never on `.booster-card__inner` (the part turning in 3D); face down, a card always wears the `common` back. A face or a back may also be **drawn by the GPU** (`kind: glsl`, a stage, with its `css`): drawn in `.booster-card__gpu`, over the card's panel and under its art and words, cut by its shape — the pack places it on its own hook (`[data-card-face="<look>"] .booster-card__gpu { inset: 13px; }`, inside a thick frame) |
| `card_reveal` | `[data-reveal="<look>"]` | per rarity, a GLSL stage or a script, `duration` ≤ 3 s |

A script part is told `{phase, rarity?, index?, count, reducedMotion}` — never a product's data.

## Widgets

A widget pack carries **everything** its widgets, looks and options do: the portal only provides the sandbox,
the data contracts and their place on the dashboard. Each element carries its rarity and its price — or
`economy.sold: false`, offered to everyone (no shop product) — and the administrator keeps or changes them.

### A new widget (`widget`, `js`)

```json
{ "type": "widget", "look": "vigie-cap", "render": { "kind": "js", "file": "cap.js" },
  "contracts": ["me.progression", "me.statistics", "widget:media.recently_added"],
  "payload": { "sizes": [{ "w": 4, "h": 2 }, { "w": 4, "h": 1 }, { "w": 2, "h": 3 }], "refresh_s": 60,
    "empty": { "fr": "…", "en": "…" },
    "options": [{ "key": "dial", "names": { "en": "Dial" }, "default": "brass",
      "values": [{ "value": "brass" }, { "value": "silver" }, { "value": "night" }] }] },
  "economy": { "price": 800, "rarity": "epic", "icon": "compass" } }
```

- `sizes` (≤ 6, `w` 1–12 columns, `h` 1–6 rows): the first is its default, the others bound how the member
  may resize it — a `h: 1` size lets it sit on a line.
- It is told its **form** — `line` (one row), `column` (narrow), `block`, `tall` (three rows or more) — and
  draws itself for each; its `config` (its own settings as the member chose them); its contracts' data.
- `options`: its own settings (≤ 6, 2–12 values each, a default); a value may be sold on its own (below).
- Nothing it may read (every contract forbidden), or a script that fails: it shows its `empty` words.
- The widget catalog lists what it reads of the member's data before it is added.

### Data contracts

A widget never asks the portal anything: the member's page reads each contract it declared through the
portal's usual routes, with the member's own session and permissions, keeps only the contract's fields and
hands them over. The analysis refuses any other contract; the administrator accepts each one at Review.

| contract | holds | permission |
|---|---|---|
| `me.progression` | `level, xp, level_floor, next_level_at, coins, contribution` | the member's own |
| `me.watching` | `items[] {title, kind, percent}` (12 at most) | the member's own |
| `media.recently_added` | `items[] {title, kind, year}` (12 at most) | `media.read` |
| `me.statistics` | `streak_days, streak_multiplier, achievements` | the member's own |
| `widget:<key>` | any dashboard widget's own data, as that widget shows it to the member (`{state, as_of, data}`, 256 KB at most) — so any information of the configured services | that widget's permission, and its purchase when it is sold |

A contract the member may not read arrives as `{state: "forbidden"}`; while loading `{state: "loading"}`; a
failure `{state: "error"}`.

### Widget looks (`widget_style`, `css`)

`payload.widget` names the widget it is for — a key (`media.recently_added`), this pack's widget, or none:
every widget. Its stylesheet dresses the widget's frame under `.widget-frame[data-widget-style="<look>"]`. The
member picks it in the widget's settings (« Pack look »).

### Widget options (`widget_option`)

- **An add-on** a widget wears — Portalab's or a pack's (`payload.widget`: its key, this pack's widget, or `*`
  for every widget): a stylesheet under `[data-widget-option~="<look>"]` (animations, another look) and/or a
  script with `render.place`: `replace` (shown instead of the widget's content — another way to show it, with
  more data) or `overlay` (drawn over it, never taking a click). A script add-on is handed `widget {key, state,
  data}` — that widget's own data — its `config`, its form and the contracts it declares. The member ticks it
  in the widget's settings; several may be worn together.
- **A value** of this pack's widget's own setting: `payload {widget, setting, value}`, `data` only (the widget's
  script draws it; its default is everyone's, never sold).

## Navigations

A `navigation` element (`js`; never sold alone — an interface names it) draws the interface's navigation in the
sandbox. It is told `sections` (each `{key, label, icon (SVG), active, entries[{key, label, icon, active}]}`,
only what this member may open), `current`, `colors`, `fonts`, `strings`, `counts.unread`, `me {level, coins}`,
`device`, `layout`, `reducedMotion`. It never knows an address: `api.navigate(key)` asks Portalab to open one of
the keys it was given (checked, a few per second at most); `api.expand(true|false)` lets it cover the screen
while open, within `render.nav.expands`. `render.nav {position: top|bottom|left|right|floating, size, expands}`
is its place, kept by Portalab with the landmark and the skip link. If it does not answer within 4 s, stops
answering, or fails, a built-in navigation takes over; the administration always keeps its own.

## The sandbox protocol

The frame: `<iframe sandbox="allow-scripts" referrerpolicy="no-referrer" src="/api/v1/visuals/sandbox">` — an
opaque origin (no cookie, no session, no storage of Portalab's), its own content security policy (no network,
no form, no popup, no navigation of the page around it; images, fonts and sounds only as `blob:`/`data:`). The
module is handed as text and imported from a `blob:` URL. `api`:

| member | what it is |
|---|---|
| `api.context` | what it knows now (per type, above) — also spread on `api` itself |
| `api.onContext(listener)` | called when what it knows changes; returns what unsubscribes |
| `api.asset(path)` | a file of its own element (relative path), as a `blob:` URL |
| `api.navigate(key)`, `api.expand(open)` | navigations only |

It must say `ready` within 4 s; it is then asked every 2 s whether it still answers, and stopped after three
silences — its default takes over and the administrators see the failure counted on the pack.

## The analysis

The same analysis runs at import and from the console (`portalab visuals analyse`). Blocking findings stop the
version; warnings are published knowingly; infos inform.

| code | level | what it says |
|---|---|---|
| `bundle.empty` | blocking | The shop pack holds no product. |
| `bundle.outside` | info | Holds products from elsewhere: {products}. |
| `css.external_url` | blocking | {file} loads an outside address ({url}): forbidden. |
| `css.fixed` | info | {file} uses position: fixed. |
| `css.import` | blocking | {file} imports another stylesheet (an import rule): forbidden. |
| `css.interface_scope` | blocking | {file}: every rule of an interface must start with [data-theme="{look}"] ({selectors}). |
| `css.unscoped` | blocking | {file} has rules reaching outside the look « {look} » ({selectors}): they will be left out. |
| `economy.given` | info | Offered to everyone: no shop product, every member may use it. |
| `economy.legendary_tier` | info | A legendary usually unlocks on a great tier (10, 20, 30, 40, 50), not at level {level}. |
| `economy.level_high` | warning | Level {level} is beyond the curve (50). |
| `economy.not_giveable` | blocking | Only a widget, its looks and its options may be given to everyone. |
| `economy.price_unusual` | info | A price of {price} is unusual for this rarity ({low}–{high} usually). |
| `economy.rarity` | blocking | Unknown rarity: {rarity}. |
| `economy.reward_only` | info | No price: kept for rewards (achievements, levels, boosters). |
| `element.duplicate` | blocking | Two elements have the same product key. |
| `element.invalid` | blocking | Invalid element.json in {folder}: {detail} |
| `element.missing` | blocking | No element.json in {folder}. |
| `element.no_look` | blocking | The look's key (look) is missing. |
| `element.no_preview` | info | No preview picture. |
| `element.type` | blocking | Unknown element type: {type}. |
| `file.kind` | blocking | A file of a kind not accepted ({suffix}): {file}. |
| `file.missing` | blocking | File not found: {file}. |
| `file.unsafe` | blocking | Forbidden path: {file}. |
| `glsl.ambient_contract` | blocking | A GLSL ambience must define main() and write gl_FragColor. |
| `glsl.large` | warning | A large fragment ({size} characters). |
| `glsl.no_timeline` | info | The scene does not use u_age (its timeline). |
| `glsl.not_stage` | warning | A GLSL level-up or celebration should fill the whole stage (stage). |
| `glsl.reserved` | blocking | « {name} » is reserved: a word of GLSL, or a name the portal already declares for its body. |
| `glsl.shape_contract` | blocking | The fragment must write its colour into o. |
| `js.dynamic_code` | warning | Makes code on the fly (eval, Function). |
| `js.large` | warning | A large script ({size} characters). |
| `js.network` | info | Tries network calls ({calls}): they will be refused in its sandbox. |
| `js.no_export` | blocking | The module has no default export. |
| `js.portal_api` | info | Mentions Portalab's API: it cannot reach it. |
| `js.sandboxed` | info | Its script runs isolated: no account, no network, no access to Portalab's pages. |
| `js.static_import` | blocking | The module imports other files: a pack's module must hold in one file. |
| `js.storage` | info | Tries to use the browser's data ({uses}): it has none in its sandbox. |
| `look.builtin` | blocking | The look « {look} » already exists in Portalab: rename it, or declare it replaces it (replaces). |
| `look.replaces` | warning | Takes over the look « {look} » held by « {pack} » (to confirm at the Review step). |
| `look.replaces_builtin` | warning | Replaces the built-in look « {look} ». |
| `look.taken` | blocking | The look « {look} » already belongs to the pack « {pack} ». |
| `nav.default_layout` | info | The navigation does not say where it sits: at the bottom, 72 pixels. |
| `pack.empty` | blocking | The pack holds no element. |
| `pack.invalid` | blocking | Invalid pack.json: {detail} |
| `pack.missing` | blocking | No pack.json at the root. |
| `pack.no_license` | info | No licence given. |
| `pack.version_format` | warning | Unusual version number: {version}. |
| `palette.colours` | blocking | Invalid palette colours in {scheme} (accent and accentAlt as #rrggbb). |
| `payload.fields` | blocking | Settings the shop refuses: {fields}. |
| `product.taken` | blocking | This product already belongs to the pack « {pack} ». |
| `render.builtin_reserved` | blocking | Only Portalab's own packs may use its built-in renderer. |
| `render.kind` | blocking | A {type} cannot be drawn in {kind} (possible: {allowed}). |
| `render.no_file` | blocking | The {kind} rendering names no file. |
| `render.no_renderer` | blocking | The renderer is not named (render.renderer). |
| `scene.duration` | blocking | Too long ({seconds} s): an opening lasts 4 s at most, a reveal 3 s. |
| `scene.empty` | blocking | The scene names no part. |
| `scene.part` | blocking | The part {slot} ({part}) is not an element of the right type in this pack. |
| `scene.rarity` | blocking | Unknown rarity for {slot}: {rarity}. |
| `scene.slot` | blocking | Unknown scene part: {slot}. |
| `text.missing` | warning | Text missing in {language}. |
| `theme.floor` | blocking | The interface does not reach the accessibility floor: {violations}. |
| `theme.invalid` | blocking | Invalid interface: {detail} |
| `theme.key` | blocking | The interface's key ({theme}) must be the look's ({look}). |
| `theme.nav` | info | Navigation used: {nav}. |
| `theme.unchecked` | blocking | The interface could not be checked. |
| `theme.vocabulary` | blocking | An interface may rename only the navigation, page titles and value names ({keys}). |
| `widget.contract_twice` | warning | A data contract is asked for twice. |
| `widget.contracts_elsewhere` | blocking | Only a widget may ask for data contracts. |
| `widget.empty` | blocking | What it says when empty: short texts (200 characters at most). |
| `widget.no_contract` | info | This widget reads none of the member's data. |
| `widget.option_default` | warning | This value is the widget's default: everyone has it already. |
| `widget.option_empty` | blocking | An add-on brings a stylesheet or a script. |
| `widget.option_place` | blocking | Its script says where it shows: instead of the widget (replace) or over it (overlay). |
| `widget.option_target` | blocking | « {widget} » is neither a widget's key, this pack's widget, nor « * » (every widget). |
| `widget.option_unknown` | blocking | This value is not one of the settings the pack's widget « {widget} » declares. |
| `widget.option_value_drawn` | blocking | A setting's value is data only: the widget's own script draws it. |
| `widget.options` | blocking | Its settings: 6 at most, each with a key, 2 to 12 values and a default among them. |
| `widget.refresh` | blocking | Its pace: between 30 s and an hour. |
| `widget.size` | blocking | Its sizes: from 1 to 6 sizes, each 1 to 12 columns wide and 1 to 6 rows high. |
| `widget.unknown_contract` | blocking | « {contract} » is not one of the data contracts the portal offers widgets. |

## Tooling

- `portalab visuals analyse <folder|zip> [--json]` — the analysis above, offline (no database), exiting
  non-zero on a blocking finding: run it before sending a pack.
- `portalab visuals builtin sync [--dry-run]` — Portalab's own packs (administrators).
- `examples/visual-packs/` — four complete packs to start from; `backend/tests/unit/visuals/test_examples.py`
  keeps every one of them free of any blocking or warning finding.

## Security

- A pack can never act as a member: its scripts run in the sandbox, its stylesheets are confined (and checked
  again by the browser), its files are served as sandboxed documents (`Content-Security-Policy: sandbox`,
  never readable by another site), the protected surfaces are out of an interface's reach, and an interface's
  vocabulary renames the navigation, page titles and value names only (what a member confirms stays in
  Portalab's words).
- Every action on a pack is in the audit log; the permission to manage packs is reserved to the Admin.
- The **fallbacks never move into packs**: the default interfaces (Portalab dark and light, light, dark, high
  contrast) and each family's base look stay in the code, so whatever fails or is switched off falls back to
  them.
- Without a session only signing in (and the single sign-on return) answers; a member whose requests look like
  an attack is blocked (sessions signed out, administrators alerted, lifted from Administration → Security
  blocks or the server's console: `portalab security blocks list|lift`).
