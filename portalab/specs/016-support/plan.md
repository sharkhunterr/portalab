# Implementation Plan: Support — Tickets, Incidents, Feedback

**Branch**: `016-support` | **Date**: 2026-10-01 | **Spec**: `specs/016-support/spec.md`
**Roadmap**: **Slice A** = Phase 4 step 13 *Health / Maintenance / Incidents* (incidents + `support.incidents` port); **Slice B** = Phase 5 step 17 *Support / Wiki / Feedback* (tickets, feedback, conversions, AI diagnosis flow). Builds on 003 (roles), 006/025 (ports), 007, 010, 011 (knowledge port), 018 (diagnosis executor, later).

## Summary
Module `support` owns three **distinct** aggregates: **Incidents** (systemic problems with their own lifecycle and public surfacing — the single incident system of the portal), **Tickets** (individual issues with admin-defined types, custom fields, tags, declarative workflows, assignment and sanitized attachments), and **Feedback** (structured forms with explicit, provenance-preserving conversion into targets owned by other domains). It provides the AI-assisted diagnosis **flow contract** (executed by 018 as the requesting user; result is only a prefilled draft) plus a deterministic AI-free precheck. It owns neither the AI engine, the Wiki, the health model nor Community/Gamification.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: none beyond Pillow (image re-encode) · **Storage**: schema `support`; attachments via `core.blobstore` · **Testing**: pytest real PG (workflow/transition, concurrency, privacy), Vitest, Playwright + axe · **Constraints**: AI never auto-submits and never exceeds the user's rights; internal notes/private fields staff-only; attachments never executed; incident ≠ ticket ≠ feedback · **Scale**: community scale (≤ 10⁵ tickets).

## Constitution Check — PASS
I Product integrity (distinctions) · II/XX one incident system, no second rules engine (workflows are declarative; automation via 019 events), conversions to owners (no clones) · III extensible via types/forms/workflow definitions · VI/VII permission + privacy + sanitized attachments · IX graceful degradation (no AI/Wiki/health dependency for core flows) · XIII audit of sensitive actions · XVI AI bounded by user rights (CD-003). No violations.

## 1. Architecture
```
006/025/Admin ─support.incidents.create/attach/link─▶ IncidentService ─▶ incidents + updates ─▶ events(007) ─▶ notifications(010), widgets(009), 006 section
User ─POST /tickets/precheck─▶ PrecheckService(open incidents for service/text · KnowledgeProvider(011) · service state(006)) ─▶ [optional DiagnosisFlow via 018 ⇒ ticket_draft]
User ─POST /tickets─▶ TicketService(type schema, required fields, attachments) ─▶ WorkflowEngine(state, transition guards) ─▶ history+event(+audit if sensitive) in one TX
Staff console ─▶ queue/filters/assign/transition/bulk-on-incident ; Feedback ─▶ review ─▶ ConversionService ─ports─▶ ticket | 013 contribution | 012/015 proposals/projects (provenance kept)
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `IncidentService` | lifecycle, updates timeline, services, dedup, severity | `core.db`, events | port + admin API | independent of tickets; append-only timeline | lifecycle tests |
| `support.incidents` port impl | `create/attach/link/open_for_service/get` | IncidentService | capability | idempotent by `(source, dedup_key)` | port conformance |
| `IncidentSurfacing` | public list, precheck matching, notifications audience | 003/006/010 | API | permitted affected services only | surfacing tests |
| `WorkflowEngine` | validate/apply transitions from versioned definitions | definitions | `apply()` | closed schema; guards on role/permission/assignee | transition table tests |
| `TicketService` | create (types, required fields), comment, tags, assign, link incident | engine, blobstore | API | `If-Match`; one TX per mutation | concurrency tests |
| `AttachmentService` | sniff, allowlist, size, re-encode, safe download | blobstore | API | never inline/exec; optional scanner | hostile-file tests |
| `PrecheckService` | incidents + knowledge + service state, AI-free | 006, 011 port | `/tickets/precheck` | works without AI | unit |
| `DiagnosisOrchestrator` | contract for 018, draft + transcript (real vs AI) | 018 port | `/diagnosis/runs` | principal-bounded; never submits | contract tests with fake AI |
| `FeedbackService` | forms, submissions, review | schemas | API | not auto-ticketed | tests |
| `ConversionService` | explicit conversion via owner ports, provenance, audit | ports | API | idempotent per `(feedback, target)`; originals kept | conversion tests |
| `SupportAdmin` | types/workflows/forms editors, versioning | 020 audit | admin API | audited; closed schemas | schema tests |
| Integrations | search providers, widgets, notification categories, palette, stats pack | 008/009/010/017 | registrations | thin | contract tests |
| Frontend | wizard, ticket UI, staff console, incident UI, feedback | 022/004 | components | accessible, states | a11y/e2e |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/support-contracts.md`

## 5. Events
Produced: `incident.created|updated|resolved`, `ticket.created|assigned|state_changed|reopened|resolved|closed`, `feedback.submitted|converted` (ids/state only). Dedup per data-model; per-ticket/incident ordering by `seq`. Consumers: 010 (notifications), 013/014 (quests/rewards), 017 stats, 019 automations (reactions to transitions), 009 widgets. Consumed here: none required (ports are synchronous); optionally `service.status_changed` for suggestions.

## 6. Permissions & Security
Per research R9: `tickets.create|read|comment|assign|transition|internal_note|close_any`, `incidents.read|manage`, `feedback.submit|review|convert[.contribution]`, `support.configure`. Own-ticket access is implicit and enforced in queries; staff scopes via 003. Sensitive actions (cross-user reassign, close-any, private data/attachment access, conversion to contribution/project, incident critical/resolve, bulk updates) audited via `AuditSink` with `ConfirmationService` where irreversible. AI acts only as the principal; Support exposes tools that call the same authorization. Attachments per R5; all user text escaped/sanitized on render; downloads from non-inline route.

## 7. Configuration — `data-model.md` settings (declared into 020).

## 8. External Integrations — none directly (Wiki/AI/health via ports).

## 9. Error Handling & Resilience
AI down ⇒ manual creation unaffected (503 on diagnosis only) · Wiki/health unavailable ⇒ precheck shows partial/unavailable sections, creation proceeds · conversion target unavailable ⇒ conversion disabled with reason, feedback untouched · illegal transition ⇒ 409 problem · concurrent edit ⇒ 409 `version_conflict` · attachment rejected ⇒ 422 with reason · incident port duplicate ⇒ returns existing · bulk action partial failure ⇒ per-ticket result report.

## 10. Observability
Open incidents by severity/age, ticket queue age/backlog, transition errors, attachment rejections, diagnosis run outcomes; registers `support` with 025 (functional: incident port responding, queue worker health).

## 11. Testing Strategy
Unit: workflow transition table (baseline + custom), required-field validation, attachment sniffing/allowlist, precheck matching, conversion idempotency. Integration (real PG): ticket lifecycle with history/events/audit; concurrency (`If-Match`); privacy matrix (requester, other user, support, moderator, admin) for fields/notes/attachments; incident lifecycle independent of tickets; bulk-on-incident; feedback → conversion with provenance; erasure/retention. Contract: `support.incidents` port conformance (consumed by 006/025 fakes), diagnosis flow with a fake AI (never submits, principal-bounded, failure ⇒ manual path). Security: hostile files, XSS in titles/comments, IDOR on tickets/attachments. Frontend: wizard flows, staff console states, accessibility. E2E: incident surfaced during ticket creation.

## 12. Migration / Versioning
Alembic revision for `support`; workflow/type/form definitions versioned (tickets/feedback pin versions); baseline types/workflows/forms seeded by migration; port contracts semver'd.

## 13. Cross-Spec Dependencies
Prerequisites: 001, 002/003 (roles `support`, `moderator`; permission defaults), 007, 010 (categories), 020, 021, 022/004. Used by: 006 (incident links via port), 025 (escalation via port), 009 (widgets), 008 (providers), 018 (diagnosis tools), 012/013/015 (conversion targets), 019 (events). Consumes later: 011 (`support.knowledge`), 018 (executor), 013/012/015 (conversion ports, stubs until then).

## 14. Implementation Phases
**Slice A (roadmap step 13)**: 1 schema + incident service + port → 2 surfacing, public API/UI, notifications, widgets, 006/025 integration tests.
**Slice B (step 17)**: 3 workflow engine + ticket types/custom fields → 4 tickets CRUD/comments/tags/assignment/attachments → 5 staff console + permissions/audit → 6 precheck + incident link + bulk → 7 feedback forms/review → 8 conversions → 9 diagnosis flow contract + draft → 10 observability/hardening.

## 15. Technical Decisions — `research.md` R1–R14.

## 16. Risks / Open Technical Questions
- **R1** OQ-75..79 use plan defaults (research); **product confirmation requested** (workflows, permission split, attachment policy, feedback→contribution rule, incident/ticket linking).
- **R2** Retention vs erasure of free-text content (tickets may contain others' data): default anonymize authorship and purge by retention; stricter erasure is a 021 policy choice.
- **R3** Conversion targets (012/013/015) don't exist yet: ports stubbed; conversion options appear only when their provider is registered.
- **R4** Diagnosis quality depends on 018/011; the AI-free precheck guarantees baseline value.
- **R5** SLA/escalation timers are out of scope (display-only settings) — would be 019 automations.

## Project Structure
```text
backend/src/portalab/{capabilities/support, modules/support/{incidents,tickets,workflow,attachments,precheck,diagnosis,feedback,conversion,admin,providers,api,models}} · backend/migrations/support/versions/
frontend/src/features/support/{incidents,tickets,staff,diagnosis,feedback,admin}
```
