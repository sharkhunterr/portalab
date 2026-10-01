# Implementation Plan: Dashboard & Widget System

**Branch**: `009-dashboard-widgets` | **Date**: 2026-10-01 | **Spec**: `specs/009-dashboard-widgets/spec.md`
**Roadmap**: Phase 4 step 12 *Dashboard / Home*. Builds on 004 (shell/SSE), 022 (states, `PolicyField`, density), 020 (policies), 002 (onboarding step), 003.

## Summary
Module `dashboard` owns **composition only**: widget registry, per-user instances (add/hide/remove/reorder/resize/configure), admin policy overlay computed on read (preserve/restore), starter dashboard at onboarding, responsive grid, the "Since Last Login" aggregator, and declarative Marketplace/plugin widgets. Every widget loads independently through its own provider endpoint and renders standardized functional states; domain logic stays with the owning modules.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: none required (CSS grid; no layout library; `@dnd-kit` optional for drag enhancement) · **Storage**: schema `dashboard` (2 tables) · **Testing**: pytest real PG, Vitest, Playwright · **Constraints**: one widget's failure never affects another; policy beats stored preference but never destroys it; WCAG 2.2 AA (no drag-only); no raw other-user private data in the summary · **Scale**: tens of widgets, ≤ ~25 instances per user.

## Constitution Check — PASS
I/XI states standardized & theme-independent · IX isolation · X consistency · XII keyboard/touch alternatives · XVIII/CD-011 policies in Administration · XX no second rules engine (closed-set conditions) · III Marketplace widgets inside the same framework · VII privacy in summary. No violations.

## 1. Architecture
```
Modules/Plugins ─register_widget(defn, provider)─▶ widget registry (in-memory)
GET /dashboard ─▶ DashboardService.effective(user) = overlay( 020 policy , dashboard.widget_instances ) ∩ permissions ∩ conditions
Browser: per instance <WidgetFrame> ─GET /widgets/{key}/data─▶ provider (authorize, timeout 5s) ─▶ WidgetPayload{state,as_of,data}
SSE (004): widget.invalidate{key} ◀ event consumer(invalidate_on) ; refetch re-authorizes
Since Last Login: ChangeSummaryProvider[*] (parallel, per-provider timeout) ─▶ rank/cap ─▶ card
Onboarding(002) step "dashboard" ─▶ StarterService.apply (idempotent)
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| Widget registry | register/unregister definitions + providers, schema validation | capability registry | `register_widget` | duplicate/invalid rejected, isolated | registry tests |
| `PolicyOverlay` | compute effective dashboard (disabled/mandatory/locked/default/conditional) | 020 settings, `ConditionEvaluator` | `effective()` | pure; never mutates rows | property tests (preserve/restore) |
| `ConditionEvaluator` | closed-set conditions | authz, 006, 014 (later), config | `evaluate()` | unknown ⇒ hidden + diagnostic | unit |
| `DashboardService` | CRUD instances, ordering/resizing batch, optimistic concurrency, config validation/upgrade | `core.db`, registry | API | policy-validated server-side | API + concurrency tests |
| `WidgetGateway` | `/widgets/{key}/data` with permission, timeout, state mapping, stale computation | providers | router | failure ⇒ state, not 5xx | isolation/timeout tests |
| `StarterService` | apply starter once | 002 onboarding, policy | `apply()` | idempotent; permission-filtered | idempotency tests |
| `SinceLastLogin` | aggregate providers, rank, cap, boundary | providers | API | permission/privacy at source; boundary robust to concurrent sessions | privacy/boundary tests |
| `InvalidationBridge` | event → SSE `widget.invalidate` | 007 consumers, 004 stream | internal | payload = key only | unit |
| Frontend grid/edit mode | responsive grid, keyboard move/resize, catalog drawer | 022 | components | no drag-only; DOM order = layout order | a11y/e2e |
| `WidgetFrame` + templates | boundary, states, declarative templates | 022 | components | states via `FunctionalState` only | component tests |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/dashboard-contracts.md`

## 5. Events
Produced `dashboard.layout_changed` (counts only), `dashboard.starter_applied`. Consumed: onboarding progress (002), `admin.config_changed` (policy epoch), plugin/marketplace state changes (registry), widgets' `invalidate_on` domain events (→ SSE only). All consumers idempotent (invalidations are naturally idempotent; starter via `starter_applied_at`). Ordering irrelevant.

## 6. Permissions & Security
Instances editable only by the owner (`users.self.manage`); policy edits `dashboard.manage` (audited via 020/`AuditSink`). Widget availability requires the widget permission **and** module/plugin enabled; data endpoints re-authorize on every call (hiding in UI is not security). Locked/mandatory rules enforced server-side. Declarative template config validated by JSON Schema (no HTML/script injection; text escaped). Summary providers must exclude other users' private data (conformance test).

## 7. Configuration — `data-model.md` (declared into 020).

## 8. External Integrations — none (widgets reach external services only through domain/connector providers).

## 9. Error Handling & Resilience
Provider timeout/exception ⇒ `unavailable`/`error` state in that frame only · invalid stored config ⇒ defaults + `config_invalid` indicator · widget unregistered (plugin disabled) ⇒ placeholder, config retained · version conflict ⇒ 409 with current layout · policy invalid reference ⇒ ignored + diagnostic · SSE drop ⇒ refetch on focus · starter partially filtered ⇒ still applies the permitted part.

## 10. Observability
Per-widget load latency/state counts/timeouts, frame crashes (client beacon, no content), starter applications, summary latency. Registers `dashboard` component with 025 (functional: probe principal gets an effective dashboard and at least the mandatory widgets).

## 11. Testing Strategy
Unit: overlay precedence matrix (disabled/mandatory/locked/default/conditional/free) incl. preserve/restore; condition catalog; config upgrade; ranking/cap. Integration (real PG): CRUD with policy enforcement, concurrency (`If-Match`), starter idempotency, widget gateway isolation and timeout, summary privacy per principal, boundary with concurrent sessions. Frontend: widget crash isolation, states mapping, keyboard move/resize, catalog filtering, responsive order. E2E: onboarding → starter, personalization persistence across a second browser context, mandatory widget not removable, one-service outage.

## 12. Migration / Versioning
Alembic revision for `dashboard`; `layout_version` and per-widget `config_schema_version` with upgraders; capability contract semver'd; removing a widget definition keeps rows (placeholder).

## 13. Cross-Spec Dependencies
Prerequisites: 001, 002 (principal, onboarding), 003, 004 (shell, SSE), 020 (policy/starter settings), 022 (states, `PolicyField`, tokens), 026 (formatting). Exposes registry/SDK to domain specs (006 service widgets, 010, 011, 013, 014, 015, 017, 024, …). Soft: 006 for `service_state` conditions, 014 for `campaign_active`. Marketplace (015)/Plugins (023) call `register_widget` later.

## 14. Implementation Phases
1 Registry & contracts → 2 Instances CRUD + effective overlay → 3 Widget gateway + frontend frame/states → 4 Responsive grid + edit mode (a11y) → 5 Policies/conditions + admin API → 6 Starter dashboard → 7 Since Last Login → 8 Invalidation (SSE) → 9 Declarative templates for Marketplace/plugin widgets → 10 Observability, hardening.

## 15. Technical Decisions — `research.md` R1–R12.

## 16. Risks / Open Technical Questions
- **R1** OQ-40..44 use plan defaults (research); **product confirmation requested** (hide semantics, layout model, summary scope, condition catalog, refresh thresholds).
- **R2** Declarative-only plugin widgets limit richness until 023 defines a sandbox; acceptable and safe.
- **R3** Summary requires each domain to implement `ChangeSummaryProvider`; coverage grows as domain specs land (starter set: services, announcements/news later).
- **R4** Drag-and-drop is optional; keyboard controls are the baseline (a11y).
- **R5** Event-driven invalidation fan-out cost: limited to connected users with that widget; fallback is on-view refetch.

## Project Structure
```text
backend/src/portalab/{capabilities/dashboard, modules/dashboard/{registry,overlay,conditions,service,gateway,starter,summary,invalidate,api,models}} · backend/migrations/dashboard/versions/
frontend/src/features/dashboard/{DashboardPage,grid,frame,templates,catalog,summary,edit}
```
