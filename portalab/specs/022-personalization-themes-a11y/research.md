# Research — Design System, Personalization, Themes & Accessibility (spec 022, roadmap step 8)

| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| R1 | **Design System = React component library** in `frontend/src/design-system` on **Radix UI primitives** (accessible behaviour: dialog, tabs, menu, popover, tooltip) styled with Tailwind mapped to **CSS custom-property tokens** | Accessible-by-construction behaviours, token-driven theming (CD-022) | Hand-rolled widgets; heavy styled UI kits (opinionated, theming limits) |
| R2 | **Themes are declarative data** (`ThemeDefinition` JSON validated by a schema): colors, typography, icon set mapping, backgrounds, borders, shadows, density, motion, sounds, notification appearance. **No executable code**, no custom CSS injection | OQ-108 default; safe for Marketplace themes | Themes as CSS/JS bundles |
| R3 | **Standardized functional states are a closed enum** (`loading, available, partial, stale, error, unavailable, maintenance, unauthorized, no-data, syncing`); a theme maps each to representation (color + icon + label), never changes the set or meaning; **a non-color cue is mandatory** | CD-022, FR-001..004 | Per-theme state vocabularies |
| R4 | **Accessibility floor enforced at theme registration**: automated WCAG 2.2 AA contrast checks on declared foreground/background pairs (text 4.5:1, large text/UI 3:1, state colors) — a theme failing the floor is rejected | CD-027, FR-013/014 | Trusting theme authors |
| R5 | **User accessibility preferences override theme effects**: high contrast, reduced motion (OS `prefers-reduced-motion` + explicit pref), text scale, sound off, density; applied via root attributes/tokens after the theme | FR-011/012 | Theme-level overrides |
| R6 | **Preferences are user-tier settings in Administration config** (`ui.*` keys) mirrored to localStorage for instant first paint; account-level persistence across devices/updates | CD-011, FR-020..022 | A separate preference store |
| R7 | **WCAG 2.2 AA component checklist** baked into components and tests: target size ≥ 24×24 CSS px, visible focus appearance, no drag-only interaction (alternative provided), consistent help, accessible authentication (paste allowed, autocomplete tokens), reflow at 320 px, text spacing support | CD-027 (2.2 criteria incl. new ones) | AA 2.1 only |
| R8 | **RTL via CSS logical properties and a `dir` provider** fed by i18n's `LocaleContext`; directional icons flagged for mirroring | FR-031 (spec 026) | Separate RTL stylesheets |
| R9 | **Testing a11y in CI**: eslint-plugin-jsx-a11y, `axe-core` in component tests, Playwright + axe on key routes, keyboard-only journeys | Plan 001 §9 | Manual audits only |
| R10 | **Sound handled by one `SoundService`** honoring `ui.soundEnabled`; sounds come from theme definitions; no audio autoplay before user gesture | FR-012/018/019 | Per-component audio |

Dashboard widget framework/layout rules stay in 009; notification delivery stays in 010 — 022 supplies appearance/preference primitives they consume.
No `NEEDS CLARIFICATION` remains.
