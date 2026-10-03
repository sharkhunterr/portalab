---
description: "Task list — Automation / Rules Engine (spec 019)"
---

# Tasks: Automation / Rules Engine

**Input**: `specs/019-automations/` · **Branch**: `019-automations` · **Roadmap**: Phase 6 step 21 · **Tests**: included.
Abbrev: **`AU/`** = `backend/src/portalab/modules/automations`, **`CAP/`** = `backend/src/portalab/capabilities/automations`, **`FA/`** = `frontend/src/features/automations`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel/jobs/outbox · `D-003` principal (`channel=automation`), `authorize`, `ConfirmationService`, `AuditSink` · `D-007` events (consumers, `automatable` flags, `provenance`) · `D-020` settings · `D-021` retention · `D-022` UI · `D-026` time helpers · `D-010` (`communication.produce` registration contract). Owner actions/conditions plug in as their specs land: 013 (award, `grant_via_automation`), 016 (ticket/incident), 011 (publish), 005 (sync/connector), 018 (`ai.invoke`), 014/006 (condition sources). Follow-ups in 007/013/016/018/011 are listed in `docs/automations.md` (T035).

## Phase 1: Setup
- [X] T001 Create `CAP/__init__.py`, `AU/{definitions,registries,triggers,scheduler,gate,evaluator,runner,identity,approvals,suspender,history,dryrun,templates,api,models}/__init__.py`, `backend/migrations/automations/versions/`, `backend/automations/templates/`, `FA/{builder,history,approvals,templates}/`, `backend/tests/{unit,integration,contract,security}/automations/`, `frontend/tests/{unit,e2e}/automations/`
- [X] T002 [P] Declare settings (`automations.enabled`, `.allowUserAuthoring`, `.maxSteps`, `.maxChainDepth`, `.executionTimeoutSeconds`, `.actionTimeoutSeconds`, `.defaultRatePerMinute`, `.globalConcurrency`, `.suspendAfterFailures`, `.suspendFailureRate`, `.approvalTtlHours`, `.executionRetentionDays`, `.minScheduleIntervalMinutes`) in `AU/settings.py`; permissions `automation.read|manage|approve` (Admin; manage/approve sensitive, audited) in `AU/permissions.py`
- [X] T003 [P] Register retention targets (executions, dedup windows), notification categories `automations.suspended` and `automations.approval` (010), event types `automation.*` with 007

## Phase 2: Foundational — contracts, schema, registries, definition model
### Tests first
- [X] T004 [P] Write `backend/tests/unit/automations/test_definition_schema.py`: closed schema; max steps; unknown trigger/condition/action rejected; params validated against action `params_schema`; substitution limited to declared event attributes; condition depth ≤ 3; secrets-looking params rejected
- [X] T005 [P] Write `backend/tests/integration/automations/test_schema.py`: tables/constraints, unique execution key `(automation_id, version, trigger_event_id)`, append-only `versions`, FKs only intra-module/`identity.users(id)`
### Implementation
- [X] T006 Implement `CAP/` contracts (`ActionType`, `ActionContext`, `ActionResult`, condition leaf types, `ApprovalProvider`) and `AU/models` + Alembic revision for schema `automations`
- [X] T007 Implement `AU/registries/{actions,conditions,triggers}.py` (owner registration, `automatable` event discovery via 007 registry, schedule kinds) and `AU/definitions/service.py` (validate, version, publish with `ConfirmationService`, standing approvals attestation)

## Phase 3: US1 — Define and run a WHEN → IF → THEN automation (P1) 🎯 MVP
**Independent test**: an event-triggered automation with a condition and one action runs once and is recorded.
- [X] T008 [P] [US1] Write `backend/tests/integration/automations/test_run_basic.py` (fake owner action): event fires ⇒ conditions evaluated ⇒ action executed ⇒ execution `success` with trace/steps; conditions false ⇒ `no_op` recorded; duplicate event delivery ⇒ one execution (unique key); paused/archived automations ignore events; replayed events do not re-run
- [X] T009 [US1] Implement `AU/triggers/consumer.py` (dynamic 007 consumers for active trigger types, `replay_safe=False`, filter matching) and `AU/gate/gate.py` (idempotency, state checks)
- [X] T010 [US1] Implement `AU/runner/runner.py` (job `automations_run`, step orchestration, `on_error`, provenance propagation into `ActionContext`) and `AU/history/service.py`
- [X] T011 [US1] Implement admin routers `GET/POST/PUT /admin/automations`, `POST …/publish|pause|resume|archive`, `GET …/executions[/{id}]`, `GET /admin/automations/catalog`; register the 010 `communication.produce` action through `register_action_type` (contract test with the real registry)

## Phase 4: US2 — Permission-bounded actions (no bypass) (P1)
- [X] T012 [P] [US2] Write `backend/tests/security/automations/test_permission_bounds.py`: action the author cannot perform manually is `refused`; permissions re-evaluated at run time (author demoted/deactivated ⇒ `refused` + `needs_review`); system identity limited to declared scopes and ≤ Admin rights at publish; permission-based condition reflects current permissions and never grants; no private data of other users exposed by permission alone; secrets never in params/history
- [X] T013 [US2] Implement `AU/identity/guard.py` (author/system identity resolution, per-action `authorize`, `needs_review` flagging, scopes validation at publish)

## Phase 5: US3 — Sensitive actions, approval, deterministic critical rules (P1)
- [X] T014 [P] [US3] Write `backend/tests/integration/automations/test_approvals.py`: destructive action ⇒ `awaiting_approval` per run; approve ⇒ runs once (params-hash bound); reject/expire ⇒ not executed; non-destructive sensitive with standing approval attested at publish runs without per-run approval; approver must hold `automation.approve`; all decisions audited
- [X] T015 [P] [US3] Write `backend/tests/unit/automations/test_ai_boundary.py`: `ai.*` outputs cannot appear in conditions or in sensitive action params (rejected at publish); `ai.invoke` allowed only for text-field drafting in non-critical steps; AI never auto-approves; critical outcome paths are fully deterministic
- [X] T016 [US3] Implement `AU/approvals/service.py` + routers `GET /admin/automations/approvals`, `POST …/approve|reject`, expiry job, and the sensitive-action catalog validation (`docs/automations.md` references the 018 catalog)

## Phase 6: US5 — Rich structured conditions (P2)
- [X] T017 [P] [US5] Write `backend/tests/unit/automations/test_conditions.py`: every leaf (`user_is`, `role_in`, `level_at_least`, `service_state_in`, `media_kind/genre/title_contains`, `campaign_active`, `time_window`, `permission_held`, `event_field`) with true/false/unknown (provider unavailable ⇒ false + trace); `all_of/any_of/not` order-independence (shuffle property test); depth limit
- [X] T018 [US5] Implement `AU/evaluator/evaluator.py` (closed leaves via ports/stubs, trace output) and register leaves for 013/014/006/003/026 sources

## Phase 7: US4 — Broad triggers across the portal (P2)
- [X] T019 [P] [US4] Write `backend/tests/integration/automations/test_triggers.py`: triggers from service state, new media, request changed, achievement, level, campaign start/end, maintenance, ticket, project, news, marketplace, plugin and system events work through the same model (fake event types registered as `automatable`); filter on event fields; plugin-provided trigger isolated
- [X] T020 [P] [US4] Write `backend/tests/unit/automations/test_schedule.py`: `at`, `relative` (offset from reference event time), `recurring` daily/weekly/monthly in tz with DST rules; minimum interval enforced; no cron strings accepted; next-fire computation deterministic
- [X] T021 [US4] Implement `AU/scheduler/scheduler.py` (schedule state, jobs with `run_at`, reconciler) and relative-trigger handling for source events carrying reference times

## Phase 8: US6 — Broad authorized actions (P2)
- [X] T022 [P] [US6] Write `backend/tests/contract/automations/test_action_conformance.py`: reusable kit for owner actions (params schema, idempotency key, provenance propagation, permission enforcement, timeout behavior) run against `communication.produce` and fakes for award/ticket/incident/publish/sync/connector/status/approval/trigger
- [X] T023 [US6] Implement baseline actions owned by the engine only where no domain owns them: `approval.request` (internal) and `automation.trigger` (internal event with chain info); provide registration docs/stubs for owner actions (013 `award.*`/`reward.unlock` via `grant_via_automation`, 016 `ticket.create`/`incident.create`, 011 `content.publish`, 005 `connector.sync|action`, 018 `ai.invoke`, `status.update`) so owners register them in their own tasks

## Phase 9: US7 — Loop prevention, repeat prevention, timeout (P1)
- [X] T024 [P] [US7] Write `backend/tests/integration/automations/test_safety.py`: A→B→A cycle prevented; depth ≥ `maxChainDepth` prevented with recorded `prevented(loop)`; `automation.trigger` obeys the same limits; same logical occurrence fires once (`dedup_key`/`dedup_window`); cooldown honored; execution/action timeouts abort and record `timeout`; storm ⇒ batched (`batchable`) or `throttled` records, never silent; other automations unaffected
- [X] T025 [US7] Implement chain tracking (`chain_id` = 007 `correlation_id`, `depth`, `provenance.automation` in emitted events), `Gate` loop/dedup/cooldown/rate logic, per-action timeouts with cancellation, batching in `AU/gate/storm.py`

## Phase 10: US8 — Auto-suspension and execution history (P1)
- [X] T026 [P] [US8] Write `backend/tests/integration/automations/test_suspension_history.py`: ≥ N consecutive failures (or failure rate) ⇒ `suspended` with reason + `automations.suspended` notification; executions while suspended recorded; explicit re-enable resets counters; history keeps provenance (trigger ref, condition trace, step results) with no payload bodies/secrets; retention purge; failing/plugin automation isolated from the rest
- [X] T027 [US8] Implement `AU/suspender/suspender.py`, `POST /admin/automations/{id}/reenable`, retention job, and frontend `FA/history/{ExecutionList,ExecutionDetail}.tsx` (condition trace and step outcomes with text status, not color-only)

## Phase 11: Authoring UX, templates, dry-run
- [X] T028 [P] Write `backend/tests/integration/automations/test_dry_run_templates.py`: dry-run evaluates conditions and plans actions with zero side effects (no executions of owner handlers, no events); presets validate and instantiate; manual `run` requires confirmation and obeys all safety controls
- [X] T029 Implement `AU/dryrun/service.py`, `POST /admin/automations/{id}/dry-run|run`, templates loader + `GET/POST /admin/automations/templates[/{key}/instantiate]` (presets: `campaign-start-announcement`, `campaign-ending-soon`, `welcome-on-verification`, `critical-service-incident-draft`, `weekly-community-digest-news`, `new-ticket-notify-support`)
- [X] T030 Implement frontend builder `FA/builder/{TriggerPicker,ConditionBuilder,StepList,ValidationPanel,DryRunResult}.tsx` (schema-driven forms from the catalog, keyboard accessible), `FA/approvals/Inbox.tsx`, `FA/templates/Gallery.tsx`, suspended banner

## Phase 12: Polish & cross-cutting
- [X] T031 [P] Write `backend/tests/security/automations/test_secrets_privacy.py`: no secrets in definitions/executions/audit; trigger payload bodies never persisted; history exposes refs only; non-admin cannot read/author; hostile definitions (huge, deeply nested, injection in templates) rejected
- [X] T032 [P] Register `automations` with Observability (executions by status, durations, suspended, loop/storm preventions, approval latency, scheduler lag) in `AU/observability.py`; audit wiring for publish/approvals/sensitive executions
- [X] T033 [P] Wire existing contract points: validate 014 announcement presets against real `campaign.*` event types and verify `communication.produce` end-to-end with the real 010 `send` (integration test `backend/tests/integration/automations/test_with_notifications.py`)
- [X] T034 [P] Add `/admin/automations*` routes to the permission-matrix test, regenerate OpenAPI client
- [X] T035 [P] Write `docs/automations.md` (model, catalogs, safety controls, approvals, AI boundary, authoring guide, how owners register actions/conditions) including the **follow-up list** for 007 (`automatable`/`rewardable`/`aggregatable` flags, `provenance.automation`), 013 (`grant_via_automation`), 016, 018 (`ai.invoke`), 011 (`content.publish`)

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [X] T036 [P] Expose owner-tagged registration on the action/condition/trigger registries: `register(..., owner="module:<id>|plugin:<key>")` and `unregister(owner)`, with a test in `backend/tests/unit/automations/test_registry_owner.py` proving all contributions of an owner disappear (required by 023's conformance sweep, F20)

- [X] T037 Run `specs/019-automations/quickstart.md` end-to-end; record deviations and open product confirmations (OQ-90..94 defaults)

## Dependencies & Order
Setup → Foundational → US1 (MVP) → US2 → US3 → US5 → US4 → US6 → US7 → US8 → authoring UX → Polish. US2/US3 must land before any owner registers a sensitive action; US7 safety controls must be complete before schedule triggers (US4) go live in production configurations.
**Parallel examples**: T004/T005 · T008 with T012 · T014/T015 · T019/T020 · T031–T035.
**MVP**: Phases 1–3 (registries, versioned definitions, event-triggered run with history and the notification action).

## Format validation
37 tasks, all checkbox + ID + path; story labels only on story phases.
