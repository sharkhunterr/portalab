# Implementation Plan: Design System, Personalization, Themes & Accessibility

**Branch**: `022-personalization-themes-a11y` | **Date**: 2026-10-01 | **Spec**: `specs/022-personalization-themes-a11y/spec.md`
**Roadmap**: Phase 3 step 8 *Design System / UI*.

## Summary
The presentation layer: a token-driven React component library on accessible primitives, declarative themes validated against a WCAG 2.2 AA floor, the standardized functional-state mapping (never color-only), user accessibility/personalization preferences stored as user-tier configuration, RTL and responsive foundations, notification appearance/sound primitives, and the CI accessibility gates. Dashboard widget layout (009), notification delivery (010) and language resolution (026) consume these primitives; no business rule is touched.

## Technical Context
**Language**: TypeScript 5.9 / React 19 (frontend), small Python module for the theme registry · **Deps (new)**: `@radix-ui/*` primitives, `class-variance-authority`, `eslint-plugin-jsx-a11y`, `axe-core`/`@axe-core/playwright`, a contrast-calculation lib · **Storage**: schema `ui` (themes); preferences in 020 config · **Testing**: Vitest + Testing Library + axe; Playwright keyboard/a11y journeys · **Constraints**: WCAG 2.2 AA floor over any theme; no executable theme code; reduced-motion/contrast/text-size always win · **Scale**: ~25 components.

## Constitution Check — PASS
XI functional state vs presentation · XII accessibility (core) · X UX consistency · XVIII configuration hierarchy (prefs in config) · III themes via Marketplace safe by construction · VIII automated a11y tests. No violations.

## 1. Architecture
```
ThemeDefinition (data) ─▶ validator (schema + contrast floor) ─▶ ui.themes ─▶ GET /ui/themes
ThemeProvider: tokens(theme) ─▶ user overrides (contrast, textScale, reducedMotion, density) ─▶ CSS custom properties on <html>
Components (Radix + Tailwind→tokens) ─▶ FunctionalState/StateMap · Announce · KeyboardShortcuts · SoundService
Preferences: /me/preferences (020) ⇄ localStorage mirror (first paint)
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| Token system | color roles, type scale, density, motion, radii, shadows as CSS vars | Tailwind config | `tokens.css`, `tailwind.preset` | no hard-coded colors in components (lint rule) | token lint test |
| `ThemeProvider` | apply theme + user overrides, mirror prefs | 020 preferences | hook/provider | overrides win over theme | override tests |
| Theme validator (frontend+backend shared schema) | schema + contrast floor | schema | `validateTheme()` | rejects floor violations | contrast table tests |
| Theme registry module | persist/enable/disable themes, floor report, policy | `core.db`, 020 | API | `appearance.manage`; no deletion while referenced | registry tests |
| Component library | accessible components with states | Radix | exports | target size, focus, RTL, keyboard | per-component a11y tests |
| `FunctionalState` + `StateMap` | ten states, icon+text+color | theme | component | never color-only; critical states always visible | state tests |
| `Announce`, `SoundService`, `KeyboardShortcuts` | live regions, sound with pref, shortcut registry | prefs | hooks | no autoplay; shortcuts don't trap focus | unit tests |
| i18n bridge | `dir`/`lang` from LocaleContext; logical CSS | 026 contract | provider | mirrored icons list | RTL tests |
| A11y CI gates | jsx-a11y, axe, Playwright keyboard journeys | CI | scripts | fail build on violations | CI self-test |

## 3. Data Model / 4. Contracts
`data-model.md`, `contracts/ui-contracts.md`.

## 5. Events
UI-specific types `theme.changed`, `theme.policy_changed`, `accessibility.preference_changed` registered with 007 and emitted by the preference/theme services (dedup `(user, key, change_seq)`). No consumers required here.

## 6. Permissions & Security
`appearance.manage` (admin theme registration/enable/disable, sensitive audited); users change only their own `ui.*` preferences (`users.self.manage`, via 020). Themes are inert data (no scripts, URLs restricted to bundled assets/data URIs in schema) so Marketplace themes cannot execute code or exfiltrate data.

## 7. Configuration (declared)
`ui.allowedThemes`, `ui.defaultTheme`, `ui.textScale.min|max`, `ui.forceReducedMotion`, user keys listed in data model.

## 8. External Integrations
None.

## 9. Error Handling & Resilience
Theme load failure ⇒ built-in default theme; invalid stored preference ⇒ default; theme missing for user ⇒ fall back to `ui.defaultTheme` (preference retained); sound asset failure ⇒ silent; token missing ⇒ build-time lint error.

## 10. Observability
Client error reporting hook for render failures (component name only); counts of floor rejections; no user content.

## 11. Testing Strategy
Unit: contrast calculator and floor table; theme schema; token lint. Component: every component × states × 3 themes with axe; keyboard interaction; RTL snapshot-free assertions on `dir`; reduced-motion and text-scale behaviour. E2E (few): keyboard-only login → shell → settings; mobile viewport reflow at 320 px. Backend: registry/API/permission tests.

## 12. Migration / Versioning
`ui` schema revision seeding built-in themes; `schema_version` on theme definitions with registered upgraders; component library semver'd for plugins (023).

## 13. Cross-Spec Dependencies
Prerequisites: 001 frontend scaffold (FunctionalState/tokens seed), 020 (preferences), 003 (permissions). Exposes: design system to every UI spec (004, 008, 009, 010, 012, 015, 016, 024, …), theme registry to Marketplace (015), `Announce`/`SoundService` to 010. Consumes `LocaleContext` shape from 026 (contract only until step 10).

## 14. Implementation Phases
1 Tokens & provider → 2 Core components with states → 3 Functional-state mapping → 4 Theme schema/validator/floor → 5 Theme registry + API → 6 Preference integration & overrides → 7 Notification/sound/announce primitives → 8 RTL/responsive + a11y CI gates → 9 Remaining components & gallery.

## 15. Technical Decisions & Trade-offs
`research.md` R1–R10: Radix + tokens, declarative themes, floor at registration, prefs in config.

## 16. Risks / Open Technical Questions
- **R1** Contrast computation for gradients/backgrounds with imagery is approximate — rule: themes with imagery must declare a solid fallback pair.
- **R2** Component breadth is large; phase 9 can ship incrementally per consuming spec.
- **R3** Tailwind-to-token discipline needs lint rules to avoid raw colors.
- **R4** RTL language set (OQ-125) is a product input; capability built regardless.

## Project Structure
```text
frontend/src/design-system/{tokens,themes,components,state,a11y,sound,rtl}/ · frontend/tests/{unit,a11y,e2e}/
backend/src/portalab/modules/ui/{themes,api,models}/ · backend/migrations/ui/versions/
```
