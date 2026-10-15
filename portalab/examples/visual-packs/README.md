# Visual packs (issue 1, POC)

Every customizable look of Portalab can come from outside, its animations in its own files: Portalab only
provides the renderers and the contracts below. Two complete examples:

- `nordlys/`: an interface (on a built-in navigation), a GPU level-up, GPU and CSS frames, a name style with its
  own font, a JavaScript celebration, a GPU ambience, a palette, a title, a badge, the theme pack and a booster;
- `abysses/`: the same, and **a navigation of its own** (`nav-sonar/`: a sonar bar that opens on the depths).

## Where packs come from

- **Inbox**: drop a folder or a `.zip` into `DATA_DIR/visuals/inbox/`, then *Read the inbox* in
  Administration → Shop → Visual packs.
- **Upload**: send a `.zip` from the same page.
- **GitHub**: `https://github.com/<owner>/<repo>[/tree/<ref>/<folder>]`. The latest release (or the default
  branch) is offered. *Check for updates* compares its `pack.json` version with the installed ones and never
  installs on its own.

Each version is stored apart (`DATA_DIR/visuals/store/<pack>/<fingerprint>/`), analysed, shown in a sandbox,
then validated, with the price, rarity, level and copies changeable. A published version is never changed in
place: new content needs a new version number. A pack can be switched off at once (its products leave the
shop, their owners keep them, its files are no longer served) and rolled back.

## Layout

```
pack.json                 {format: 1, id, version, names{fr,en}, descriptions, author, license, homepage}
elements/<name>/element.json
elements/<name>/…         its files (css, glsl, js, json, images, fonts, sounds)
```

`element.json`:

| field | |
|---|---|
| `type` | `level_up`, `effect` (celebration), `ambient`, `profile_background`, `avatar_frame`, `profile_banner`, `name_style`, `level_badge`, `notification_style`, `notification_animation`, `palette`, `badge`, `title`, `theme` (an **interface**), `navigation` (an interface's own navigation, never sold alone), `bundle` (a pack, a theme pack), `booster` |
| `look` | the look's key: what preferences and profiles store, what the interface's `data-*` attributes carry |
| `product` | the shop product's key (default `<prefix>_<look>`) |
| `names`, `descriptions` | `{fr, en}` |
| `render` | `{kind: css\|glsl\|js\|theme\|none, file, css[], stage, shape, radius, reveal, duration, nav}` — `nav`: a navigation's place, `{position: top\|bottom\|left\|right\|floating, size (px), expands}` |
| `economy` | proposed `{price, rarity, level, supply, collection, icon, repeatable}`. No price: reward only |
| `payload` | `bundle`: `products[]`; `booster`: `pool, packs, cards, odds, guarantee…`; `badge`/`title`: `label, icon, style` |
| `palette` | palettes: `{dark: {accent, accentAlt, contrast}, light: {…}}` |
| `replaces` | takes over a built-in look of the same key (a warning, decided by the administrator) |

## Rendering contracts

- **CSS**: a look styles **its own element only**: every selector starts on its hook
  (`.avatar-frame[data-frame="<look>"]`, `.name-style[data-name="<look>"]`, `.levelup[data-look="<look>"]`,
  `[data-effect="<look>"]`…) and goes no further than inside it (no `~`, `+`, `:has()`, `:root`, `html`,
  `body`). An interface's selectors all start with `[data-theme="<key>"]`; Portalab makes each of them skip the
  protected surfaces (administration, purchases, confirmations). Fonts are declared with `@font-face`, addresses
  relative to the sheet (or `data:`); `@import` and outside addresses are refused. The analysis blocks what
  breaks these rules, and the interface enforces them again on the browser's own reading of the sheet.
- **GLSL, a shape** (frames, level badges, notifications, titles, badges): a fragment of `main()`. It receives
  `p` (position in half heights), `d` (distance to the shape's edge, < 0 inside), `ax` (width / height), `t`
  (time), `u_age`, and `hash()`, `noise()`, `fbm()`, `over()`. It writes its colour into `vec4 o`.
- **GLSL, a stage** (`"stage": true`: level-ups, celebrations): the same frame over the whole screen
  (`gl_FragCoord`, `u_res`, `u_age` = seconds since it started). A level-up's card shows at `reveal` seconds.
- **GLSL, an ambience**: a complete shader after Portalab's common helpers (`u_res`, `u_time`, `hash`, `noise`,
  `fbm`, `over`). It defines `main()` and writes premultiplied colour into `gl_FragColor`.
- **JS** (level-ups, celebrations, navigations): one ES module (no `import` of other files) whose default export
  is `mount(root, api)`; it returns what stops it. It **always runs in a sandbox**: an iframe of an opaque origin
  (`sandbox="allow-scripts"`), with its own content security policy. It has no cookie, no session, no storage of
  Portalab's, no network, no form, no popup and cannot move the page around it. `api` holds what it may know
  (`reducedMotion`, `level`/`text` for a moment; for a navigation, see below), `api.asset(path)` (a file of its
  own element, as a `blob:` URL) and `api.onContext(listener)` (what it knows changed).
- **Navigation** (`navigation`, JS): `api.sections` (each `{key, label, icon (SVG), active, entries[{key, label,
  icon, active}]}`, only what this member may open), `api.current`, `api.colors`, `api.fonts`, `api.strings`,
  `api.counts.unread`, `api.me` (level, coins), `api.device`, `api.layout`. It never knows an address:
  `api.navigate(key)` asks Portalab to open one of the keys it was given (checked, a few per second at most), and
  `api.expand(true|false)` lets it cover the screen while open. Portalab keeps its room (`render.nav`), the
  landmark and the skip link; if the script does not answer within 4 s or fails, a built-in navigation takes
  over; the administration always keeps its own.
- **Interface** (`theme`): `file` is a theme definition (colours, fonts, layout and navigation — a built-in one or
  the pack's own `navigation` look —, vocabulary, and the looks it wears, including the pack's own). Its
  vocabulary renames the navigation, page titles and value names only (`nav:…`, `…title`,
  `gamification:value.…`): what a member confirms stays in Portalab's words. Its `css` add its own touches
  under `[data-theme="<key>"]`.

## The analysis

Blocking, warning and info findings, among them:

- the manifests, the files they name and their kinds and sizes;
- the look keys, which must be neither a built-in look nor another pack's look;
- CSS scope, imports and outside addresses;
- the GLSL contracts and the names GLSL reserves;
- what a script does (network, Portalab's API, browser storage, `eval`);
- the economy against Portalab's own rules;
- an interface's validity and accessibility floor.

The sandbox then compiles each GPU look in the administrator's browser and measures the frames per second.

## Security model

- **Packs**: the administrator's sources are trusted, yet a pack can never act as a member: its scripts run
  sandboxed, its stylesheets are confined, its files are served as sandboxed documents
  (`Content-Security-Policy: sandbox`), never readable by another site. Every action on a pack (import,
  validation with its economy, refusal, switching off or on, rollback) is in the audit log.
- **Intrusion guard**: every API answer is weighed (a refusal, a refusal on the administration, an unknown
  administration address, an attack-shaped address). Past a limit within ten minutes, the member's sessions
  are signed out and their account is blocked for fifteen minutes (signing in again changes nothing); an
  address is blocked for requests without a session. The holders of `security.manage` are alerted, see and
  lift the blocks (Administration → Security blocks).
