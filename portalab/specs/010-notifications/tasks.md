---
description: "Task list — Notifications & Communication (spec 010)"
---

# Tasks: Notifications & Communication

**Input**: `specs/010-notifications/` · **Branch**: `010-notifications` · **Roadmap**: Phase 4 step 15 · **Tests**: included.
Abbrev: **`NT/`** = `backend/src/portalab/modules/notifications`, **`CAP/`** = `backend/src/portalab/capabilities/notifications`, **`FN/`** = `frontend/src/features/notifications`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` jobs/outbox/secrets · `D-002` principal + `VerificationChannel` port · `D-003` `authorize` · `D-004` SSE stream/bell slot · `D-006` maintenance + service events · `D-007` events · `D-020` settings/policies · `D-022` `Notification`, `SoundService`, `Announce` · `D-026` `RecipientLocale`/templates · `D-025` health. The generic rule engine is `D-019` (later): only the action contract is built here against a fake engine.

## Phase 1: Setup
- [ ] T001 Create `CAP/__init__.py`, `NT/{categories,producer,fanout,preferences,coalesce,channels/portal,channels/email,maintenance,sources,api,models}/__init__.py`, `backend/migrations/notify/versions/`, `FN/{center,toasts,preferences,bell}/`, `backend/tests/{unit,integration,contract,security}/notifications/`, `frontend/tests/{unit,e2e}/notifications/`
- [ ] T002 [P] Add `aiosmtplib` (+ dev `aiosmtpd`) dependencies; declare settings (`notifications.coalesceWindowSeconds`, `.retentionDays`, `.email.*` with secret password, `.email.maxAttempts`, `.digest.defaultMode`, user `notifications.preferences.<category>.<channel>`, `.email.digest`) in `NT/settings.py`; permissions `notifications.manage` (audited), `notifications.broadcast` (audited), `notifications.send_to_audience` in `NT/permissions.py`
- [ ] T003 [P] Register retention targets (inbox/deliveries/outbox) with 021, classify inbox/deliveries as `activity` personal data, and implement the 020/021 export+erasure participant in `NT/privacy.py`

## Phase 2: Foundational — contracts, schema, categories, producer
### Tests first
- [ ] T004 [P] Write `backend/tests/unit/notifications/test_categories.py`: declare/validate; mandatory channels; plugin categories namespaced and never mandatory; unknown category rejected at `send`
- [ ] T005 [P] Write `backend/tests/integration/notifications/test_producer.py`: duplicate `(source, dedup_key)` ⇒ one communication; audience resolved under caller authority (automation author cannot target unseen audience); alert requires priority ≥ high; secrets in params rejected by schema
### Implementation
- [ ] T006 Implement `CAP/` contracts (`CommunicationRequest`, `AudienceSpec`, `Channel`, `EmailTransport`, `ActionType` registration types, `send`, `send_alert`, `declare_category`)
- [ ] T007 Implement `NT/models` + Alembic revision for schema `notify` (categories, communications, notifications, deliveries, email_outbox, maintenance_reminders, digest_state)
- [ ] T008 Implement `NT/categories/registry.py` and `NT/producer/service.py` per T004/T005

## Phase 3: US1 + US2 — Notification center; four distinct concepts (P1) 🎯 MVP
**Independent test**: produce notifications and alerts; center lists them important-first with read/archive; News and Email are not conflated.
- [ ] T009 [P] [US1] Write `backend/tests/integration/notifications/test_center.py`: priority-then-time ordering; unread count; read/read-all/archive/delete; owner-only access (403/404 for others); category/kind filters; retention purge
- [ ] T010 [P] [US2] Write `backend/tests/unit/notifications/test_concepts.py`: `kind=alert` UI/data distinct; News has no inbox representation unless a notification is explicitly produced; Email exists only as `channel=email` deliveries with separate preferences; model forbids priority < high for alerts
- [ ] T011 [US1] Implement `NT/fanout/worker.py` (per-recipient job: permission re-check, preference resolution, render via 026, create inbox row, deliveries) and `NT/channels/portal.py` with SSE `notification.created` ping
- [ ] T012 [US1] Implement routers `GET /me/notifications`, `GET /me/notifications/unread-count`, `POST …/{id}/read|read-all|archive`, `DELETE …/{id}`, `GET /notifications/categories` in `NT/api/router.py`
- [ ] T013 [US1] Implement frontend `FN/center/NotificationCenter.tsx` (list, filters, priority/kind visual distinction with non-color cues, read/archive), `FN/bell/Bell.tsx` (004 slot, live unread count)
- [ ] T014 [US2] Implement rendering pipeline `NT/fanout/render.py` (ICU keys per recipient language, escaped params) and the Alert vs Notification presentation variants in `FN/toasts/`

## Phase 4: US3 — Preferences by category and channel (P1)
- [ ] T015 [P] [US3] Write `backend/tests/unit/notifications/test_preferences.py`: policy ∩ preference matrix; disabling a category on one channel leaves others; mandatory category/channel cannot be disabled (`notifications.mandatory_channel`); preference retained when policy later relaxes; effective on next communication
- [ ] T016 [US3] Implement `NT/preferences/resolver.py` and routers `GET/PUT /me/notification-preferences` (with lock info) plus `FN/preferences/NotificationPreferences.tsx` using `PolicyField`
- [ ] T017 [US3] Implement coalescing/anti-flood `NT/coalesce/coalescer.py` (window per `(user, category, subject)`, count merge, critical exempt) and the email digest job `NT/coalesce/digest.py`; tests `backend/tests/unit/notifications/test_coalesce.py`

## Phase 5: US7 — Presentation, accessibility, reduced motion, sound off (P1)
- [ ] T018 [P] [US7] Write `frontend/tests/a11y/toasts.spec.tsx`: position/duration/style from `ui.*` prefs; reduced motion removes animation; sound-off silences cue (critical bypass never overrides sound-off); alerts assertive vs notifications polite; critical alert persists until acknowledged; theme change alters appearance only (meaning/urgency unchanged); keyboard dismissal
- [ ] T019 [US7] Implement `FN/toasts/ToastRegion.tsx` using 022 `Notification`, `Announce`, `SoundService`; wire to SSE + fetch; ensure critical content never hidden by presentation settings

## Phase 6: US5 — Scheduled maintenance notifications (P1)
- [ ] T020 [P] [US5] Write `backend/tests/integration/notifications/test_maintenance_reminders.py` (fake clock): J-1 and H-1 produced for permitted audience; start alert on `maintenance.started`; reschedule cancels pending and sends corrective to already-notified; cancel sends corrective; late evaluation past `valid_until` ⇒ suppressed `expired`; replayed/duplicate events ⇒ no duplicates; per-user preferences/permissions respected
- [ ] T021 [US5] Implement `NT/maintenance/reminders.py` (consumers for `maintenance.*`, jobs with `run_at`, dedup `(maintenance_id, schedule_version, kind)`, state in `notify.maintenance_reminders`) using `category=system.maintenance` and audience from 006 service permissions

## Phase 7: US6 — Automatic, admin-rule, event, automation sources (P2)
- [ ] T022 [P] [US6] Write `backend/tests/integration/notifications/test_sources.py`: critical `service.state_changed` ⇒ alert once per state change; account security events ⇒ mandatory notification; admin broadcast needs `notifications.broadcast` and is audited; event-sourced communications use `occurred_at` and are idempotent on replay
- [ ] T023 [P] [US6] Write `backend/tests/contract/notifications/test_automation_action.py`: `communication.produce` ActionType registered against a fake engine; author-bounded audience; duplicate trigger ⇒ one communication; unpermitted audience rejected
- [ ] T024 [US6] Implement `NT/sources/{services,security}.py`, admin broadcast endpoint `POST /admin/notifications/broadcast`, and `register_action_type("communication.produce")` in `NT/automation.py` (stub registry until 019)

## Phase 8: US8 — Email and multi-channel delivery (P2)
- [ ] T025 [P] [US8] Write `backend/tests/integration/notifications/test_email.py` (SMTP test server): enabled per category → outbox sends and clears body; SMTP down ⇒ retries with backoff then `failed`, portal delivery unaffected; recipient without address ⇒ `suppressed(no_address)`; recipient language/locale/tz in message; no clear address or content in logs/events
- [ ] T026 [US8] Implement `NT/channels/email.py` (SMTP adapter via `aiosmtplib`, outbox job, sanitized text/HTML templates from catalogs, credentials from `core.secrets`), `PUT /admin/notifications/email`, `POST …/email/test` (audited, secret masked) and the `VerificationChannel` email implementation for 002
- [ ] T027 [US8] Implement channel-independence guarantees (per-channel job isolation, unique `(communication_id, user_id, channel)`) and admin `GET /admin/notifications/deliveries|status` (metadata only)

## Phase 9: Polish & cross-cutting
- [ ] T028 [P] Write `backend/tests/security/notifications/test_privacy_authz.py`: permission lost before delivery ⇒ suppressed; no content in events/logs; recipient cannot read others' items; admin delivery view has no content; erasure/export participant covers inbox
- [ ] T029 [P] Register `notifications` with Observability (delivery success by channel, fan-out lag, SMTP errors, suppressed-by-reason, coalescing ratio) in `NT/observability.py`; wire `notifications.send_alert` port for 025
- [ ] T030 [P] Add `/me/notification*`, `/notifications/*`, `/admin/notifications/*` to the permission-matrix test, regenerate OpenAPI client, write `docs/notifications.md` (categories, sending guide, automation action contract, maintenance reminder semantics)
- [ ] T031 Run `specs/010-notifications/quickstart.md` end-to-end; record deviations and open product confirmations (OQ-45..49 defaults)

## Dependencies & Order
Setup → Foundational → US1/US2 (MVP) → US3 → US7 → US5 → US6 → US8 → Polish. US5 needs 006 events; US6 contract test uses a fake 019; US8 independent of US5/US6 after fan-out exists.
**Parallel examples**: T004/T005 · T009/T010 · T018 with T015 · T022/T023/T025 · T028/T029/T030.
**MVP**: Phases 1–3 (producer, fan-out, portal channel, notification center with alerts vs notifications).

## Format validation
31 tasks, all checkbox + ID + path; story labels only on story phases.
