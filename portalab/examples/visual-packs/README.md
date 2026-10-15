# Visual packs (issue 1, POC)

Every customizable look of Portalab can come from outside, its animations in its own files: Portalab only
provides the renderers and the contracts below. `nordlys/` is a complete example (an interface, a GPU level-up,
GPU and CSS frames, a name style with its own font, a JavaScript celebration, a GPU ambience, a palette, a
title, a badge, the theme pack and a booster).

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
| `type` | `level_up`, `effect` (celebration), `ambient`, `profile_background`, `avatar_frame`, `profile_banner`, `name_style`, `level_badge`, `notification_style`, `notification_animation`, `palette`, `badge`, `title`, `theme` (an **interface**), `bundle` (a pack, a theme pack), `booster` |
| `look` | the look's key: what preferences and profiles store, what the interface's `data-*` attributes carry |
| `product` | the shop product's key (default `<prefix>_<look>`) |
| `names`, `descriptions` | `{fr, en}` |
| `render` | `{kind: css\|glsl\|js\|theme\|none, file, css[], stage, shape, radius, reveal, duration}` |
| `economy` | proposed `{price, rarity, level, supply, collection, icon, repeatable}`. No price: reward only |
| `payload` | `bundle`: `products[]`; `booster`: `pool, packs, cards, odds, guarantee…`; `badge`/`title`: `label, icon, style` |
| `palette` | palettes: `{dark: {accent, accentAlt, contrast}, light: {…}}` |
| `replaces` | takes over a built-in look of the same key (a warning, decided by the administrator) |

## Rendering contracts

- **CSS**: style the interface's hooks for your look only: `.avatar-frame[data-frame="<look>"]`,
  `.name-style[data-name="<look>"]`, `.levelup[data-look="<look>"]`, `[data-effect="<look>"]`,
  `[data-theme="<interface>"]`… Fonts are declared with `@font-face` and addresses relative to the sheet.
  Outside addresses are blocked by the content security policy.
- **GLSL, a shape** (frames, level badges, notifications, titles, badges): a fragment of `main()`. It receives
  `p` (position in half heights), `d` (distance to the shape's edge, < 0 inside), `ax` (width / height), `t`
  (time), `u_age`, and `hash()`, `noise()`, `fbm()`, `over()`. It writes its colour into `vec4 o`.
- **GLSL, a stage** (`"stage": true`: level-ups, celebrations): the same frame over the whole screen
  (`gl_FragCoord`, `u_res`, `u_age` = seconds since it started). A level-up's card shows at `reveal` seconds.
- **GLSL, an ambience**: a complete shader after Portalab's common helpers (`u_res`, `u_time`, `hash`, `noise`,
  `fbm`, `over`). It defines `main()` and writes premultiplied colour into `gl_FragColor`.
- **JS** (level-ups, celebrations): an ES module whose default export is
  `mount(host, {type, look, level?, text?, reducedMotion, asset(path)})`. It returns a function that stops it.
  It runs in every member's page: the administrator confirms it at validation. Network calls are limited to
  Portalab by the content security policy.
- **Interface** (`theme`): `file` is a theme definition (colours, fonts, layout and navigation, vocabulary, and
  the looks it wears, including the pack's own). Its `css` add its own touches under `[data-theme="<key>"]`.

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
