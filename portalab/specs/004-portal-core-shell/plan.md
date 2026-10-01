# Implementation Plan: Portal Core — Global Shell & Navigation

**Branch**: `004-portal-core-shell` | **Date**: 2026-10-01 | **Spec**: `specs/004-portal-core-shell/spec.md`
**Roadmap**: Phase 3 step 9 *Navigation* (builds on 022 Design System).

## Summary
The permanent SPA frame: a persistent `AppShell`, a server-assembled and permission-filtered **navigation manifest** (modules and, later, plugins contribute declaratively), breadcrumbs and contextual links from route handles, always-present Search/AI/Notification/Identity slots, a Command Palette with keyboard shortcuts, responsive/mobile navigation and standardized global states (loading, error, degraded, unauthorized, unavailable). It owns no business data and no search/AI engine; it consumes authz, config, module/plugin state and the design system.

## Technical Context
**Language**: Python 3.12 (assembler, small `shell` module) + TypeScript/React 19 (shell) · **Deps (new)**: `react-router` (data router); no palette library (own accessible implementation) · **Storage**: schema `shell` (diagnostics only); settings in 020 · **Testing**: pytest (assembler/permission matrix), Vitest + Testing Library, Playwright (keyboard/mobile) · **Constraints**: server is the authority for filtering; shell never blocks on one failing area; WCAG 2.2 AA · **Scale**: ~30–60 entries.

## Constitution Check — PASS
I One environment, not links · II/XX no new engine (uses authz, config, registries) · III extensible via manifest contributions · VI default-deny, no permission leak via nav · IX isolation & degraded mode · X UX consistency · XII accessibility · XVIII config hierarchy for layout/shortcuts. No violations.

## 1. Architecture
```
Modules/Plugins ─register_contribution─▶ core.navigation registry
Browser ─GET /me/navigation─▶ NavigationAssembler ─▶ [enablement(020/023)] [authorize() batch] [layout policy + user order] ─▶ NavigationView(ETag)
Browser ◀─SSE /me/stream (navigation.changed)─ shell.invalidate ─▶ refetch
AppShell: Header(SearchEntry, AiEntry, Notifications, Identity) · PrimaryNav · Breadcrumbs · RouteBoundary(Outlet) · GlobalStatusBanner · CommandPalette
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `core.navigation` registry | collect/validate contributions, detect duplicates | capability registry (001) | `register_contribution()` | closed schema; deterministic conflict resolution | schema/conflict tests |
| `NavigationAssembler` | merge, filter by enablement and permission, apply layout | authz, 020 config, module/plugin state | `build(principal)` | batched `authorize()`, cached by epochs; fails closed (empty nav + banner) | permission-matrix & epoch tests |
| `shell` API module | `/me/navigation`, `/me/stream`, admin layout, diagnostics | assembler, 007 events | OpenAPI | `shell.manage` audited | API tests |
| Contribution validator/isolator | drop malformed/failing entries, record diagnostics | registry | internal | one bad contribution never breaks others | isolation tests |
| `AppShell` + slots | persistent frame | design system (022) | React components | no business logic; keyboard/landmark structure | a11y tests |
| Router + `RouteBoundary` | lazy routes, per-route states, guards | React Router | `registerRoutes` | existence-sensitive handling | routing tests |
| `Breadcrumbs` / `RelatedLinks` | orientation, contextual nav | route handles | components | labels via i18n keys; no dead-end empty states | unit |
| `CommandRegistry` + `CommandPalette` | destinations/actions, shortcuts | navigation view, shortcuts | hooks | only permitted commands; focus management | Playwright |
| `ShortcutManager` | baseline + user-customizable shortcuts | prefs (020) | hook | disabled in inputs; conflict detection | unit |
| `GlobalStatusBanner` | degraded mode summary | health summary API (006/025) | component | never hides nav/search | unit |
| Responsive layout | drawer/rail/top layout | 022 primitives | CSS + hooks | same destinations on mobile | reflow tests |

## 3. Domain / Data Model — `data-model.md` · 4. Contracts — `contracts/shell-contracts.md`

## 5. Events
Consumed: `permission.*` (003), `admin.module_toggled|plugin_toggled` (020), `plugin.state_changed`, `service.status_changed`, user preference changes → bump epochs, emit SSE `navigation.changed`. Emitted: `navigation.contribution_rejected` (diagnostic). Consumers idempotent (epoch increments are monotonic; duplicate events cause at most one extra refetch). Ordering irrelevant (last epoch wins).

## 6. Permissions & Security
Entries/commands carry `required_permission`; assembler evaluates server-side; route data endpoints re-authorize (nav hiding is convenience only). `/me/navigation` never reveals names of entries the user cannot access. `existence_sensitive` routes answer identically for missing and forbidden. Admin layout editing requires `shell.manage` (audited). SSE carries no sensitive payload.

## 7. Configuration (declared)
`shell.navigation.layout`, `shell.navigation.allowUserOrdering`, `shell.shortcuts.defaults`, user `shell.navigation.userOrder`, `shell.shortcuts`, `shell.sidebarCollapsed`; plugin conflict priority keys.

## 8. External Integrations — none.

## 9. Error Handling & Resilience
Assembler failure ⇒ cached last-known view if the principal's epoch unchanged else minimal safe nav (Home + identity menu) with banner (never more rights than allowed) · invalid contribution ⇒ dropped + diagnostic · SSE drop ⇒ reconnect with backoff + refetch on focus · lazy route chunk failure ⇒ route-level error with retry, shell intact · AI/search entry failure isolated.

## 10. Observability
Metrics: assembly latency, cache hit ratio, rejected contributions, SSE connections, route chunk failures (client beacon without PII). Registers `shell` component with 025 (functional check: assembler can build for a probe principal).

## 11. Testing Strategy
Unit: merge/conflict/ordering precedence, schema validation, shortcut conflicts, breadcrumb resolution. Integration: permission matrix per entry; epoch invalidation on role change/module toggle; malformed contribution isolation. Frontend: shell persistence across route changes (state preserved), palette filtering, focus management, degraded banner. E2E (few): keyboard-only palette + navigation, mobile drawer parity, unauthorized vs not-available, live nav update via SSE.

## 12. Migration / Versioning
Alembic revision for `shell.contribution_errors`; contribution `schema_version` with registered upgraders; `/me/navigation` versioned within `/api/v1`.

## 13. Cross-Spec Dependencies
Prerequisites: 001 (capability registry, SSE kernel), 002/003 (principal, authorize, `/me/permissions`), 020 (config, toggles, prefs), 022 (design system, `FunctionalState`, shortcut registry, `Announce`). Exposes: contribution API to every module/plugin (023), palette registry to 008, slots to 008/010/018, `RouteBoundary` to all features. Soft: 006/025 health summary (banner), 007 events (epochs).

## 14. Implementation Phases
1 Shell skeleton & router → 2 Contribution registry/validation → 3 Assembler + API + caching → 4 Live updates (SSE epochs) → 5 Breadcrumbs/related links → 6 Slots (search/AI/notifications/identity) → 7 Command Palette & shortcuts → 8 Responsive/mobile → 9 Global states & degraded banner → 10 Admin layout + diagnostics + tests.

## 15. Technical Decisions & Trade-offs — `research.md` R1–R15.

## 16. Risks / Open Technical Questions
- **R1** OQ-16/17/19 are product questions; plan defaults documented (R5, R10, R13) and kept in config so changing them is not a rewrite. **Product confirmation requested.**
- **R2** Per-request batched authorization could become costly with many entries: mitigated by epoch-keyed cache; measure in tests.
- **R3** Palette without global search (008 later) is limited to destinations/actions; designed so 008 plugs in as a provider.
- **R4** Plugin enrichment depends on 023 (extension slots); until then only first-party modules contribute.

## Project Structure
```text
backend/src/portalab/{capabilities/navigation, modules/shell/{assembler,api,models,validator}} · backend/migrations/shell/versions/
frontend/src/shell/{AppShell,router,nav,breadcrumbs,palette,shortcuts,status,slots}/
```
