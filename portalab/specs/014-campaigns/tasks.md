---
description: "Task list — Events / Campaigns (spec 014)"
---

# Tasks: Events / Campaigns

**Input**: `specs/014-campaigns/` · **Branch**: `014-campaigns` · **Roadmap**: Phase 6 step 20 · **Tests**: included.
Abbrev: **`CM/`** = `backend/src/portalab/modules/campaigns`, **`CAP/`** = `backend/src/portalab/capabilities/campaigns`, **`FC/`** = `frontend/src/features/campaigns`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel/jobs/outbox · `D-003` authz/`ConfirmationService`/`AuditSink` · `D-007` events · `D-013` gamification (`ModifierProvider` consumer, ledger, `economy.maxTotalBoost`; follow-up `DefinitionSource`) · `D-020` settings · `D-021` retention · `D-022` theme registry (+ follow-up pref `ui.campaignThemes`) · `D-026` `resolve_wall_clock`/normalization · `D-011` calendar sources · `D-009` widgets · `D-017` unlock reader · `D-024` media (follow-up `ActivityAttributeProvider`) · `D-019` announcements (later).

## Phase 1: Setup
- [ ] T001 Create `CAP/__init__.py`, `CM/{definitions,planner,intervals,scheduler,overrides,resolver,matching,modifiers,content,presentation,simulate,api,models}/__init__.py`, `backend/migrations/campaigns/versions/`, `FC/{console,banner,history,presentation}/`, `backend/tests/{unit,integration,contract,security}/campaigns/`, `frontend/tests/{unit,e2e}/campaigns/`
- [ ] T002 [P] Declare settings (`campaigns.endingSoonHours`, `.maxActiveCampaigns`, `.reconcileSeconds`) in `CM/settings.py`; permissions `campaigns.read` (default grant), `campaigns.manage` (Admin, sensitive, audited) in `CM/permissions.py`; register retention targets and event types `campaign.*` with 007
- [ ] T003 [P] Add `btree_gist` extension migration helper and capability contracts in `CAP/` (`ModifierProvider` impl signature, `ActivityAttributeProvider`, `CampaignReader`, `CampaignContentProvider`, presentation types) with in-memory fakes

## Phase 2: Foundational — schema & definition model
### Tests first
- [ ] T004 [P] Write `backend/tests/unit/campaigns/test_definition_schema.py`: closed schema; unknown fields/operators rejected; bounded sizes; modifier factor range; recurrence parameters; theme key must exist; no expressions accepted
- [ ] T005 [P] Write `backend/tests/integration/campaigns/test_schema.py`: tables, append-only `versions`, `activation_log` exclusion constraint rejects overlapping intervals, single `open_intervals` row per campaign, FKs only intra-module/`identity.users(id)`
### Implementation
- [ ] T006 Implement `CM/models` + Alembic revision for schema `campaigns` (campaigns, versions, occurrences, activation_log, open_intervals, overrides, attribute_failures)
- [ ] T007 Implement `CM/definitions/service.py` (validate, publish new versions with `effective_from`, state machine Draft→Scheduled→Active⇄Paused→Ended→Archived) and the admin create/update routers `GET/POST /admin/campaigns`, `GET/PUT /admin/campaigns/{id}`

## Phase 3: US1 — Define a campaign with schedule, duration, recurrence (P1) 🎯 MVP
**Independent test**: a campaign activates at its start, deactivates at its end, and reactivates per recurrence.
- [ ] T008 [P] [US1] Write `backend/tests/unit/campaigns/test_planner.py`: none/yearly/custom recurrence expansion in campaign tz; DST gap/overlap boundaries per 026 policy; leap-year and month-end anchors; start+duration vs start/end; deterministic output
- [ ] T009 [P] [US1] Write `backend/tests/integration/campaigns/test_lifecycle.py` (fake clock): `campaign.started` / `campaign.ending_soon` / `campaign.ended` emitted once at boundaries; interval opened/closed atomically with outbox; scheduler downtime ⇒ reconciler repairs and logs actual times; duplicate boundary jobs idempotent
- [ ] T010 [US1] Implement `CM/planner/planner.py` (occurrence expansion using 026) and `CM/intervals/manager.py` (open/close, move to `activation_log`, events through `EventPublisher`)
- [ ] T011 [US1] Implement `CM/scheduler/jobs.py` (boundary jobs with `run_at`, per-minute reconciler) and state transitions to `scheduled|active|ended`

## Phase 4: US2 — Manual activation/deactivation (P2)
- [ ] T012 [P] [US2] Write `backend/tests/integration/campaigns/test_overrides.py`: manual activate/deactivate recorded with actor/reason/confirmation and audit; precedence over schedule until occurrence end / next start / explicit `until`; schedule resumes automatically; conflicting overrides rejected; paused state within window; permission matrix
- [ ] T013 [US2] Implement `CM/overrides/service.py` and routers `POST /admin/campaigns/{id}/activate|deactivate|cancel|archive` (`campaigns.manage`, `ConfirmationService`)

## Phase 5: US4 — Conditions across genres, media, users, activities (P1)
- [ ] T014 [P] [US4] Write `backend/tests/unit/campaigns/test_matching.py`: `media_kind`, `genre` (canonical tags, localized names), `title_contains` (NFKC/casefold/diacritics-insensitive, original + effective title), `activity`, `audience` (all/roles/groups/level range/users) incl. AND semantics inside a modifier; unknown attribute ⇒ not applied; users outside audience unaffected
- [ ] T015 [P] [US4] Write `backend/tests/integration/campaigns/test_attribute_providers.py`: provider registry per event type; provider unavailable ⇒ conditions unknown, no boost, no crash, diagnostics counter increments; unrelated functions unaffected
- [ ] T016 [US4] Implement `CM/matching/{conditions,audience,attributes}.py` and the `ActivityAttributeProvider` registry; provide a media provider stub/contract for 024 in `CAP/attributes.py`

## Phase 6: US3 + US6 + US7 — Modifiers supplied to Gamification; deterministic overlap; anti-farming integrity (P1)
- [ ] T017 [P] [US3] Write `backend/tests/integration/campaigns/test_modifier_provider.py`: horror movie ⇒ XP x2 + Coins x1.5; title contains "Halloween" ⇒ additional XP x2; each modifier contributes at most once per occurrence; eligibility by `occurred_at` (late and duplicate events resolve identically; ended campaign still applies to earlier occurrences); modifiers carry `campaign:key:version:id`
- [ ] T018 [P] [US6] Write `backend/tests/integration/campaigns/test_overlap_with_gamification.py` (real 013 consumer): two overlapping campaigns + rule multiplier combine multiplicatively and are capped by `economy.maxTotalBoost`; reproducible result; single grant per occurrence (no duplicate on redelivery)
- [ ] T019 [P] [US7] Write `backend/tests/integration/campaigns/test_anti_farming.py` (real 013): boosted grants still subject to cooldown/caps/diminishing; anomaly handling recorded; transaction records campaign version
- [ ] T020 [US3] Implement `CM/resolver/active.py` (`ActiveResolver.at(instant)` from log + open interval + version in force) and `CM/modifiers/provider.py` (`ModifierProvider.modifiers_for`) registered with the capability registry for 013
- [ ] T021 [US6] Document the single combination rule (delegated to 013 CD-024) in `docs/campaigns.md` and add a contract test asserting Campaigns never computes final amounts (only factors with refs)

## Phase 7: US5 — Campaign achievements, quests, theme/UI, notifications (P2)
- [ ] T022 [P] [US5] Write `backend/tests/integration/campaigns/test_content_provider.py`: campaign-scoped achievements/quests available only while the campaign is active at the instant; granting happens in 013 (no parallel reward path); version-in-force definitions
- [ ] T023 [P] [US5] Write `backend/tests/integration/campaigns/test_presentation.py`: theme overlay returned per user (audience-filtered, priority-ordered); only themes allowed by 022 policy; user `ui.campaignThemes=ignore` respected; accessibility preferences still win; presentation never changes permissions/state
- [ ] T024 [US5] Implement `CM/content/provider.py` (`CampaignContentProvider`), `CM/presentation/service.py` + `GET /campaigns/active`, `GET /campaigns/active/presentation`, and frontend `FC/presentation/CampaignPresentationProvider.tsx` + `FC/banner/ActiveCampaignBanner.tsx`
- [ ] T025 [US5] Implement manual announcement `POST /admin/campaigns/{id}/announce` via 010 broadcast (audited) and ship announcement automation preset descriptors for 019 (`docs/campaigns.md`); events `campaign.started|ending_soon|ended` documented as the automation triggers

## Phase 8: US8 — Campaign history and rule versioning (P2)
- [ ] T026 [P] [US8] Write `backend/tests/integration/campaigns/test_history_versions.py`: editing an active campaign publishes a new version effective now; earlier grants keep the old version; ending/changing never rewrites history; history endpoint lists versions, occurrences, activation intervals, overrides; schema upgraders
- [ ] T027 [US8] Implement `GET /admin/campaigns/{id}/history`, `POST /admin/campaigns/{id}/simulate` (`CM/simulate/service.py`, no writes), and frontend `FC/history/Timeline.tsx` + `FC/console/{DefinitionStepper,SimulationPanel}.tsx` (closed condition catalog, recurrence preview in tz)

## Phase 9: Integrations, polish & cross-cutting
- [ ] T028 [P] Implement `CalendarSource(kind="campaign")` (011) and `CampaignReader` (009 `campaign_active` condition, 017 unlock) with contract tests `backend/tests/contract/campaigns/test_readers.py`; widget `campaigns.active` (009)
- [ ] T029 [P] Write `backend/tests/security/campaigns/test_permissions_audit.py`: only `campaigns.manage` mutates; sensitive actions audited with actor/action/timestamp/context/result and confirmed; no secrets in definitions/events; hostile definitions (oversized, deep nesting) rejected
- [ ] T030 [P] Register `campaigns` with Observability (active campaigns, boundary lateness, unknown-vs-matched rate, provider failures, override usage) in `CM/observability.py`
- [ ] T031 [P] Add `/campaigns*`, `/admin/campaigns*` to the permission-matrix test, regenerate OpenAPI client, finalize `docs/campaigns.md` (schedule semantics, overrides, matching catalog, cross-spec follow-ups for 013/019/022/024)
- [ ] T032 Run `specs/014-campaigns/quickstart.md` end-to-end; record deviations, open product confirmations (OQ-65..69 defaults) and the cross-plan follow-ups to apply

## Dependencies & Order
Setup → Foundational → US1 (MVP) → US2 → US4 → US3/US6/US7 (modifiers + 013 integration) → US5 → US8 → Polish. US3 needs resolver + matching; US6/US7 integration tests require the 013 consumer; US5 needs 022/011 contracts (stubs acceptable).
**Parallel examples**: T004/T005 · T008/T009 · T014/T015 · T017/T018/T019 · T028–T031.
**MVP**: Phases 1–3 (definitions, schedule/recurrence, activation log and lifecycle events).

## Format validation
32 tasks, all checkbox + ID + path; story labels only on story phases.
