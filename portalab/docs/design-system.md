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
