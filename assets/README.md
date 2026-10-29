# Portalab brand assets

| File | Use |
| --- | --- |
| `icon.svg` → `icon.jpg`, `icon.png` | the app icon (README, Docker Hub, social preview) |
| `favicon.svg` → `favicon.ico` | the browser tab |
| `banner.svg` → `banner.jpg` | the README banner (1280×400) |

The SVG files are the sources; everything else is rendered by `npm run assets` (headless Chromium + Pillow),
which also installs `favicon.svg`, `favicon.ico`, `icon-192.png`, `icon-512.png` and `apple-touch-icon.png`
into `portalab/frontend/public/`. Never edit a render by hand.

## Palette

The brand uses **Portalab's own default theme** (`portalab-dark` / `portalab-light`,
`portalab/frontend/src/design-system/themes/builtin/`) — when those change, the brand follows.

| Role | Dark | Light |
| --- | --- | --- |
| Surface | `#0b0e17` | `#f5f6fb` |
| Raised surface | `#161b2b` | `#ffffff` |
| Border | `#2b3349` | `#d5d9e4` |
| Text | `#eef1f8` | `#141824` |
| Muted text | `#a9b2c7` | `#4a5368` |
| Accent | `#7f9cff` | `#3a55d0` |
| Focus / highlight | `#a3b8ff` | `#3a55d0` |
| Second accent | `#ffb547` | `#a35f00` |
| Rarity — rare / epic / legendary | `#5cb4ff` / `#c48dff` / `#ffb547` | `#1767bd` / `#8436cc` / `#a35f00` |

Typeface: **Plus Jakarta Sans** (titles), **Inter** (text) — both bundled with the frontend.
