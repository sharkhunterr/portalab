# Design system, themes & accessibility (spec 022)

The presentation layer lives in `frontend/src/design-system/` and is the only UI surface plugins build on
(`index.ts`). Functional meaning never depends on presentation: themes and preferences change CSS custom
properties on `<html>`, never data, permissions or the set of functional states.

## Tokens
- `tokens/tokens.css`: color roles (`--color-*`), functional-state pairs (`--state-<state>-fg|bg`), type scale,
  spacing (scaled by `--space-unit` for density), radii, motion, focus ring, `--target-min` (24 px).
- Components and features use tokens only: `npm run lint` runs `scripts/check-tokens.mjs`, which rejects raw
  colors (`#hex`, `rgb()`, `hsl()`) outside `design-system/tokens/` and the built-in theme data.

## Themes
- A theme is an inert `ThemeDefinition` document (`themes/schema.ts`, JSON Schema shared with the backend in
  `backend/src/portalab/modules/ui/themes/theme.schema.json`; regenerate with
  `UPDATE_THEME_SCHEMA=1 npx vitest run tests/unit/theme-schema.test.ts`): colors, the ten functional states
  (color + icon + label key; optional opacity/display), typography, radii, motion, icon set, background
  (bundled asset or raster data URI + mandatory solid fallback), bundled sounds, notification defaults.
  No CSS, scripts, external URLs or unknown keys.
- **Accessibility floor** (`themes/floor.ts`, mirrored by `modules/ui/themes/definition.py`): WCAG 2.2 AA on
  text/surface, text/raised surface, muted text, accent text, every state fg/bg (4.5:1), focus ring and
  critical states against the surface (3:1); critical states (error, unauthorized, maintenance, unavailable)
  can never be hidden or faded below 0.9 opacity. A failing theme is refused (`theme.floor_violation`).
- Built-ins: `light`, `dark`, `high-contrast` (`themes/builtin/*.json`, seeded by the `ui` migration; a test
  keeps frontend and backend copies identical).
- Registry: `POST /api/v1/admin/ui/themes` (`appearance.manage`), `PATCH …/{key}` (definition/enabled),
  `GET …/{key}/floor-report`, `POST …/check` (dry run). Marketplace/plugin themes register disabled and are
  enabled explicitly (audited). Themes are never deleted; withdrawing an owner disables its themes.

## Preferences
User-tier settings in Administration (`/me/preferences`): `ui.theme`, `ui.density`, `ui.textScale`,
`ui.contrast`, `ui.reducedMotion`, `ui.soundEnabled`, `ui.notificationPosition|DurationSeconds|Style`,
`ui.layoutPresets`, `ui.campaignThemes`. Admin policy: `ui.allowedThemes`, `ui.defaultTheme`,
`ui.textScale.min|max`, `ui.forceReducedMotion`. Order of application: theme → campaign overlay (if allowed
and passing the floor) → accessibility overrides (high contrast, reduced motion, text scale, density), which
always win. A policy narrowing a value keeps the user's own choice. Preferences are mirrored to
localStorage for first paint. Changes emit `theme.changed`, `theme.policy_changed`,
`accessibility.preference_changed` (setting names only, never values).

## Components & WCAG 2.2 AA checklist
Buttons/links/fields/dialog/drawer/tabs/menu/popover/tooltip/table/list/layout/card/panel/badge/progress/
timeline/avatar/entity cards/notifications/policy fields. Every component: visible focus (token ring),
targets ≥ 24×24 px, keyboard operable (Radix primitives: Escape, focus return, arrow keys), no drag-only
interaction, labels and descriptions wired, paste never blocked and `autocomplete` passed through
(accessible authentication), logical CSS properties (RTL), reflow at 320 px and text-spacing tolerant,
state = icon + text + color. Calendar and chart wrappers arrive with their first consumers (011, 017).

## Testing
- `npm test`: unit + axe component tests (contrast, schema, token lint, states across themes, preferences,
  RTL, critical information, policy fields, sound/notifications, campaign overlay, gallery under each theme).
- `npm run test:a11y`: Playwright against the dev server with a stubbed API — keyboard-only journey
  (sign-in → settings), no focus trap, target sizes, dialog focus return, 320 px reflow with WCAG text
  spacing and 200 % text, axe (WCAG 2.2 AA tags) on `/dev/gallery` for every built-in theme.

## Visual experience (spec 027)

**Theme schema v2.** Besides colors, states, typography, radii, icons, backgrounds and sounds, a theme may
choose — never define — an arrangement from a closed vocabulary that the portal implements once:

| Block | Choices |
|-------|---------|
| `layout.nav.desktop / tablet / phone` | `sidebar`, `topbar`, `rail`, `orbit` / `rail`, `topbar`, `drawer`, `orbit` / `bottom-bar`, `drawer`, `orbit` |
| `layout.header`, `layout.headerPosition` | `full`, `compact`, `centered`; `top` or `bottom` (the header becomes a footer bar) |
| `layout.cards`, `layout.widgetFrame` | `elevated`, `flat`, `outlined`, `glass`; `card`, `plain`, `glass` |
| `layout.content`, `layout.corners` | `narrow`, `wide`, `full`; `square`, `soft`, `round` |
| `motion.profile`, `motion.celebration` | `none`, `subtle`, `lively`, `playful`; `none`, `sparkle`, `confetti`, `glow` |
| `sounds` | `notification`, `alert`, `success`, `reward`, `levelUp`, `ui` (bundled `asset:` only) |
| `colors.accentAlt`, `colors.rarity` | gamification accent and badge rarities (floor-checked, 3:1 on raised surfaces) |
| `family` | groups light/dark members; the user's `ui.colorMode` (`dark`, `light`, `system`) picks the member |

v1 documents remain valid (missing blocks take defaults). The choices land as `data-*` attributes on `<html>`
(`data-nav-desktop|tablet|phone`, `data-header`, `data-header-position`, `data-cards`, `data-content`,
`data-corners`, `data-widget-frame`, `data-motion`, `data-celebration`); accessibility overrides are applied last
and always win (reduced motion ⇒ `data-motion="none"`; high contrast or reduced transparency ⇒ glass becomes solid).
Built-ins: `portalab-dark` (default) and `portalab-light` (family `portalab`), `orbit` (orbit navigation, header at
the bottom), `studio` (top bar, flat, narrow), `light`, `dark`, `high-contrast`.

**Page kit** (exported to plugins): `PageHeader` (required on every routed page — `npm run lint` checks it), `Card`
(variants), `Tile`/`TileGrid`, `ListItem`, `StatFigure`, `Avatar` (initials on a hue derived from the user id),
`LevelBadge`, `ProgressBar`, `CoinBadge`, `Skeleton`, `EmptyState` (an action is mandatory), `Icon` (stable names
mapped to lucide icons), `AuthLayout`, and `useCelebrate()` (rewards and level-ups, coalesced, reduced-motion
aware, sounds through `SoundService`). Fonts (Inter, Plus Jakarta Sans) and sounds are self-hosted.

**Shell.** The personal header (avatar, level + XP, Coins, notifications, search, assistant, personal menu) reads
its parts independently and updates live from `progression.changed`; navigation comes in sections
(`docs/navigation-contributions.md`); the frame picks the theme's arrangement per device class (phone < 640 px,
tablet < 1024 px, desktop) without remounting the page. All live updates share one SSE connection.
