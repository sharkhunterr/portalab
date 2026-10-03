---
description: "Task list — Support: tickets, incidents, feedback (spec 016)"
---

# Tasks: Support — Tickets, Incidents, Feedback

**Input**: `specs/016-support/` · **Branch**: `016-support` · **Roadmap**: **Slice A** (Phases 1–4: incidents) = step 13; **Slice B** (Phases 5–12) = step 17 · **Tests**: included.
Abbrev: **`SP/`** = `backend/src/portalab/modules/support`, **`CAP/`** = `backend/src/portalab/capabilities/support`, **`FS/`** = `frontend/src/features/support`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel/blobstore/jobs · `D-002/003` principal/authz (roles `support`, `moderator`) + `AuditSink`/`ConfirmationService` · `D-006` health (port consumer) · `D-025` observability (port consumer) · `D-007` events · `D-010` notification categories · `D-020` settings · `D-021` retention/erasure · `D-022/004` UI. Later/stubbed: `support.knowledge` (011), AI executor (018), `gamification.grant_contribution` (013), `community.proposals.create` (012; kinds `feature|project`, the funding lifecycle is registered by 012 in 015).

## Phase 1: Setup (Slice A)
- [X] T001 Create `CAP/__init__.py`, `SP/{incidents,tickets,workflow,attachments,precheck,diagnosis,feedback,conversion,admin,providers,api,models}/__init__.py`, `backend/migrations/support/versions/`, `FS/{incidents,tickets,staff,diagnosis,feedback,admin}/`, `backend/tests/{unit,integration,contract,security}/support/`, `frontend/tests/{unit,e2e}/support/`
- [X] T002 [P] Declare settings (`support.attachments.maxBytes|maxPerPost|allowedTypes`, `support.ticketRetentionMonths`, `support.reopenWindowDays`, `support.draftTtlMinutes`, `support.incident.precheckMatchMode`) in `SP/settings.py`; declare permissions `tickets.create|comment|manage`, `incidents.read|manage`, `feedback.submit|read|convert|convert.contribution`, `support.configure` with default role grants (user/support/moderator/admin) in `SP/permissions.py`
- [X] T003 [P] Declare notification categories `support.assignment|ticket_status|incident|feedback` (010), register retention targets and the 020/021 export+erasure participant `SP/privacy.py` (classify ticket text/comments/attachments, private fields)

## Phase 2: Foundational — schema & port contracts (Slice A)
### Tests first
- [X] T004 [P] Write `backend/tests/contract/support/test_incidents_port.py`: `support.incidents` conformance kit used by 006/025 fakes — `create` idempotent per `(source, dedup_key)`, `attach`, `link`, `open_for_service`, `get` permission-bounded
- [X] T005 [P] Write `backend/tests/integration/support/test_schema_incidents.py`: incident tables, append-only `incident_updates` (trigger), unique `(source, dedup_key)`, FKs only intra-module/`identity.users(id)`
### Implementation
- [X] T006 Implement `CAP/` port Protocols (`support.incidents`, `support.tickets`, `support.knowledge`, conversion target ports, `AttachmentScanner`, `DiagnosisFlow` tool contracts) with in-memory fakes
- [X] T007 Implement `SP/models` + Alembic revision for schema `support` (incident tables first; ticket/feedback tables in a second revision for Slice B)

## Phase 3: US3 — Incidents distinct from tickets, surfaced to reduce duplicates (P1) 🎯 MVP (Slice A)
**Independent test**: open an incident, see it surfaced when starting a related ticket, confirm lifecycles are independent.
- [X] T008 [P] [US3] Write `backend/tests/integration/support/test_incident_lifecycle.py`: `investigating → identified → monitoring → resolved` with append-only timeline; resolve independent of any ticket; severity change audited; duplicate create returns existing; critical resolve/severity sensitive + audited
- [X] T009 [P] [US3] Write `backend/tests/integration/support/test_incident_surfacing.py`: users see only permitted affected services; open incident surfaced by precheck for matching service/text; Observability escalation through the port after validation creates one incident; 006 `open_for_service` returns it
- [X] T010 [US3] Implement `SP/incidents/service.py` (lifecycle, updates, services, evidence, dedup) and the `support.incidents` port implementation registered in the capability registry
- [X] T011 [US3] Implement routers `GET /incidents[/{id}]`, admin `POST /admin/incidents`, `POST …/{id}/updates`, `PATCH …/{id}`, `POST …/{id}/resolve` (`incidents.manage`, audited) and emit `incident.created|updated|resolved` events (dedup `(incident_id, update_seq)`)
- [X] T012 [US3] Implement notification fan-out through the `notifications.send` port (stub until 010 lands at roadmap step 15) (`support.incident`, audience = users permitted on affected services, critical ⇒ alert) in `SP/incidents/notify.py` and dashboard widget `support.open_incidents` (009) + search provider `incidents` (008)
- [X] T013 [US3] Implement frontend `FS/incidents/IncidentBanner.tsx`, `IncidentsPage.tsx`, admin `IncidentConsole.tsx` (timeline editor, severity/state/services); wire 006 service-page incidents section to the port

## Phase 4: Slice A closure
- [X] T014 [P] Write `backend/tests/security/support/test_incident_security.py`: only `incidents.manage` can mutate; public summary never leaks internal evidence/service names the viewer cannot see; XSS-safe rendering
- [X] T015 Wire cross-spec contract tests: 006 `IncidentLinkService` and 025 escalation against the real port implementation; record Slice A completion in `docs/support.md` (incident section)

## Phase 5: Foundational — tickets (Slice B)
### Tests first
- [X] T016 [P] Write `backend/tests/unit/support/test_workflow_engine.py`: baseline workflow transition table (allowed/forbidden), guards on role/permission/assignee, reopen window, custom workflow validation (closed schema, unreachable/dead-end states rejected), versioned definitions pinned per ticket
- [X] T017 [P] Write `backend/tests/unit/support/test_ticket_types.py`: custom field schema types, required fields enforced at creation naming missing fields, private-field flags, enum/select validation
### Implementation
- [X] T018 Implement `SP/workflow/engine.py` + seeded baseline workflow/types (`bug`, `access_request`, `service_issue`, `question`, `other`) via migration; `SP/admin/definitions.py` (validate/version/audit)

## Phase 6: US1 + US2 + US7 — Tickets, types/fields/tags, roles/assignment/attachments (P1/P2)
**Independent test**: create a ticket of a type, move it through its workflow with assignment, with privacy and attachment rules enforced.
- [X] T019 [P] [US1] Write `backend/tests/integration/support/test_ticket_lifecycle.py`: create → assign → transition → resolve → close/reopen; history append-only with `seq`; events `ticket.*` with dedup; optimistic concurrency (`If-Match`, 409); state change + history + event atomic (fault injection)
- [X] T020 [P] [US7] Write `backend/tests/security/support/test_ticket_privacy_roles.py`: matrix (requester / other user / support / moderator / admin): own-ticket access, internal notes hidden from requester, private fields staff-only, cross-user reassignment and close-any need `tickets.manage` and are audited, IDOR on ids/attachments denied
- [X] T021 [P] [US7] Write `backend/tests/security/support/test_attachments.py`: magic-byte allowlist (disguised `.exe` as `.png` rejected), size/count limits, image re-encode strips EXIF, non-images download-only with `nosniff`, filename sanitization, scanner port hook, retention deletion
- [X] T022 [US1] Implement `SP/tickets/service.py` (create with type schema, comments incl. internal, tags, assignment, incident link, history, events) and routers `POST /tickets`, `GET /me/tickets`, `GET /tickets/{id}`, `POST …/comments`, `GET /tickets/types`
- [X] T023 [US7] Implement `SP/attachments/service.py` + routers `POST /tickets/{id}/attachments`, `GET /tickets/attachments/{id}` per R5
- [X] T024 [US7] Implement staff routers `GET /support/tickets` (filters, cursor), `POST /tickets/{id}/transition|assign|tags|link-incident|internal-notes` with permission/guard enforcement and sensitive-action audit/confirmation
- [X] T025 [US1] Implement frontend `FS/tickets/{NewTicketWizard,MyTickets,TicketDetail}.tsx` (timeline, comments, attachments, workflow-driven actions) and staff `FS/staff/{Queue,TicketConsole}.tsx` with accessible states
- [X] T026 [US2] Implement admin editors `FS/admin/{TypeEditor,WorkflowEditor}.tsx` and `GET/PUT /admin/support/types|workflows` (`support.configure`, versioned, audited)

## Phase 7: Precheck, incident linking, bulk (P1)
- [X] T027 [P] [US3] Write `backend/tests/integration/support/test_precheck_bulk.py`: precheck returns matching open incidents + knowledge suggestions with partial/unavailable sections when Wiki or health down, AI-free; ticket links ≤ 1 incident; no ticket merge endpoint exists; incident resolve does not auto-resolve tickets; bulk comment/transition on linked tickets audited with per-ticket results
- [X] T028 [US3] Implement `SP/precheck/service.py`, `POST /tickets/precheck`, `POST /admin/incidents/{id}/tickets/bulk` and frontend `FS/tickets/PrecheckStep.tsx`

## Phase 8: US4 — Feedback: forms, bug reports, feature requests (P2)
- [X] T029 [P] [US4] Write `backend/tests/integration/support/test_feedback.py`: seeded forms (general, bug_report, feature_request) validate required structured fields; submissions never become tickets automatically; staff review/dismiss; form versions pinned; permission matrix
- [X] T030 [US4] Implement `SP/feedback/service.py`, routers `GET /feedback/forms`, `POST /feedback`, staff `GET /support/feedback`, `POST …/review|dismiss`, admin `GET/PUT /admin/support/forms`, and frontend `FS/feedback/{FeedbackForm,ReviewQueue}.tsx`

## Phase 9: US5 — Feedback conversion (P2)
- [X] T031 [P] [US5] Write `backend/tests/integration/support/test_conversion.py`: conversion to ticket (Support), contribution (013 stub, once per feedback, no reward on submission), feature proposal and community project (012 `community.proposals.create` stub, kind `feature|project`) — each created in the owning domain via port, provenance preserved, original feedback kept, audited; unavailable target ⇒ option disabled with reason; double-convert idempotent
- [X] T032 [US5] Implement `SP/conversion/service.py` and `POST /support/feedback/{id}/convert` with `feedback.convert[.contribution]`, `feedback_conversions` provenance, `ConfirmationService` for contribution/project

## Phase 10: US6 — AI-assisted diagnosis before ticket creation (P1)
- [X] T033 [P] [US6] Write `backend/tests/contract/support/test_diagnosis_flow.py` (fake AI executor): steps identify user → service state → permitted Wiki → analyze → propose → prefill draft; runs under the requesting principal (no data beyond their rights); transcript separates real data vs AI interpretation; result is a `ticket_draft`, never a ticket; AI failure ⇒ 503 on diagnosis only and manual creation works; accepted solution creates nothing
- [X] T034 [US6] Implement `SP/diagnosis/orchestrator.py` (`POST /diagnosis/runs` SSE, `GET …/{id}`, `GET /tickets/drafts/{id}`, tools bound to principal), draft TTL job, and frontend `FS/diagnosis/DiagnosisPanel.tsx` (real vs AI labelling, confirm/modify before submit)

## Phase 11: Integrations & hardening
- [X] T035 [P] Implement search providers `tickets` (own for users, all for staff) and `feedback` (staff), widgets `support.my_tickets|queue` (009), palette actions `new-ticket`/`report-bug` (008), statistics pack `backend/definitions/packs/support.json` (017), notification wiring for assignment/status/feedback (010)
- [X] T036 [P] Register `support` with Observability (open incidents, queue age, transition errors, attachment rejections, diagnosis outcomes) in `SP/observability.py`; retention/erasure tests `backend/tests/integration/support/test_retention_erasure.py` (tombstoned requester, attachments and private fields purged, history retained anonymized)
- [X] T037 [P] Add all `/incidents*`, `/tickets*`, `/support/*`, `/feedback*`, `/diagnosis/*`, `/admin/incidents*`, `/admin/support/*` routes to the permission-matrix test, regenerate OpenAPI client, write `docs/support.md` (workflows, types, attachment policy, conversion ports, diagnosis contract)

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [X] T038 Reuse the shared upload sniff/re-encode helper extracted to `core` by 011 (T007) in `SP/attachments/service.py` instead of a local copy; regression test `backend/tests/security/support/test_attachments_shared_helper.py` (F10)
- [X] T039 Make `support.tickets.create` and `support.incidents.create` callable by non-interactive principals (automation channel) with the same rules and audit, and register the 019 action types `ticket.create|incident.create`; test `backend/tests/contract/support/test_automation_actions.py` (F11)

- [X] T040 Run `specs/016-support/quickstart.md` end-to-end; record deviations and open product confirmations (OQ-75..79 defaults)

## Dependencies & Order
**Slice A**: Setup → Foundational → US3 incidents → closure (can ship right after 006/025). **Slice B**: tickets foundation → US1/US2/US7 → precheck/bulk → US4 → US5 → US6 → integrations. US6 needs US1 (draft → ticket) and the precheck; US5 needs US4 and ticket service; conversions to 013/012/015 stay stubbed until those specs land.
**Parallel examples**: T004/T005 · T008/T009 · T016/T017 · T019/T020/T021 · T035/T036/T037.
**MVP (Slice A)**: Phases 1–4; **MVP (Slice B)**: Phases 5–6.

## Format validation
40 tasks, all checkbox + ID + path; story labels only on story phases.
