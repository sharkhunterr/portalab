# Implementation Plan: Notifications & Communication

**Branch**: `010-notifications` | **Date**: 2026-10-01 | **Spec**: `specs/010-notifications/spec.md`
**Roadmap**: Phase 4 step 15 *Notifications*. Builds on 007 (events/jobs), 006 (maintenance, service state), 022 (toast/sound primitives), 026 (recipient locale/templates), 004 (SSE, bell slot), 020 (preferences/policy), 003 (authorize).

## Summary
Module `notifications` owns the **production/delivery mechanism** for communications: the producer API `send`, the strict separation of Notification vs Alert (News stays in its module, Email is a channel), the per-user notification center, preferences by category × channel within admin policy, anti-flood coalescing, multi-channel delivery (portal, sound, email; push-ready), per-recipient localized rendering, and the **system-generated** sources (maintenance J-1/H-1/start/corrective, critical service alerts, account security). It contains **no rule engine**: configurable communications are an Automations (019) action that calls `send`.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: `aiosmtplib` (email) · **Storage**: schema `notify` · **Testing**: pytest real PG + SMTP test server (`aiosmtpd`), Vitest, Playwright + axe · **Constraints**: idempotent production, permission re-check at delivery, preference/policy precedence, channel independence, critical alerts never throttled, accessibility preferences win · **Scale**: personal/community (≤ thousands of recipients per communication).

## Constitution Check — PASS
I Product integrity (four distinct concepts) · II/XX no second rule engine (CD-010) · IV event-driven/idempotent · VI/VII permission at delivery, privacy of content in logs/events · IX channel isolation/retries · XI/XII presentation independent of urgency, reduced motion, sound off · XVIII preferences within policy hierarchy. No violations.

## 1. Architecture
```
Sources: system(006 maintenance, 006/025 service alerts, 002 account security) · modules · admin rules · 019 action "communication.produce"
      └─▶ notifications.send(CommunicationRequest, caller) ─▶ validate category/priority · authorize audience under caller authority
              └▶ notify.communications (dedup (source,dedup_key)) ─▶ fan-out job per recipient
                    ├ authorize(recipient, subject_ref)  ✗ ⇒ suppressed(permission_lost)
                    ├ preferences ∩ policy (mandatory channels, critical bypass rules)  ✗ ⇒ suppressed(preference)
                    ├ coalescing window / digest decision (never for critical)
                    ├ render ICU in recipient language (026)  ⇒ notify.notifications (portal)
                    └ channels: portal(+SSE ping) · sound(client) · email(outbox→SMTP job) · push(future)
MaintenanceReminders (system source): 006 maintenance.* events ─▶ jobs(run_at) J-1/H-1 · start alert · corrective on change/cancel
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `CategoryRegistry` | declare/validate categories, mirror to table, policy overlay | 020 | `declare_category` | mandatory channels enforced | registry tests |
| `ProducerService` | validate request, audience authority, dedup, persist communication, enqueue fan-out | authz, jobs | `send`, `send_alert` | idempotent; caller-bounded audience | idempotency/authority tests |
| `FanoutWorker` | per recipient: permission re-check, preferences, coalescing, render, channel dispatch | 026, prefs | job | one recipient's failure isolated | failure-injection tests |
| `PreferenceResolver` | effective channels per category (policy ∩ preference ∩ bypass) | 020 | `resolve()` | critical bypass portal only | matrix tests |
| `Coalescer` / `DigestJob` | merge repeats, email digests | jobs | internal | never critical | window tests |
| `PortalChannel` + inbox API + SSE ping | center, unread, read/archive | 004 stream | `Channel` | owner-only | API tests |
| `EmailChannel` + `EmailTransport` (SMTP) + outbox job | send, retry, sanitize, secret handling | `core.secrets` | `Channel` | portal unaffected by email failure | SMTP tests |
| `MaintenanceReminders` | J-1/H-1/start/corrective jobs from 006 events | 006 events, jobs | consumers | cancel on change; valid_until relevance; dedup per schedule version | schedule tests |
| `SystemSources` | service critical → alert, account security notices | 006/025/002 events | consumers | dedup per state change | event tests |
| Automations action registration | `communication.produce` ActionType | 019 contract | `register_action_type` | author-bounded | contract test with fake engine |
| Frontend center/toasts/preferences/bell | present, a11y, preferences | 022, 004 | components | alert vs notification distinct; reduced motion/sound off | a11y/e2e |
| Admin | deliveries, SMTP config/test, categories | 020, 025 | `/admin/notifications/*` | audited; secrets masked | API tests |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/notifications-contracts.md`

## 5. Events
Consumed: `maintenance.*`, `service.state_changed`, `user.suspended|reactivated|deletion_requested`, `admin.config_changed`; idempotent through `ctx.idempotent_effect` and dedup keys (`maintenance_id:schedule_version:kind`, `service_id:state_seq`). Produced: `notification.sent` (counts), `notification.read`, `notification.delivery_failed` (diagnostic, rate-limited). Ordering: per-maintenance order by `schedule_version`; stale versions ignored. Late events use `occurred_at`; relevance via `valid_until`.

## 6. Permissions & Security
Sending: internal capability; automations act on behalf of the author and may only target audiences within the author's visibility (`notifications.send_to_audience`); admin broadcast requires `notifications.broadcast` (audited). Recipients read only their own items. Admin screens expose delivery metadata, never content. Templates escape params; email HTML sanitized from catalog templates; links are internal routes (no open redirects); SMTP password only in `core.secrets`; email addresses never logged (hash).

## 7. Configuration — `data-model.md` settings (declared into 020).

## 8. External Integrations
SMTP server (operator-provided) via `EmailTransport` port; push channel reserved. Portal works fully without email configured.

## 9. Error Handling & Resilience
Email failure ⇒ retry with backoff, then `failed`; other channels unaffected (FR-027) · recipient render failure ⇒ that recipient only, logged · SSE unavailable ⇒ inbox still correct on next fetch · category unknown ⇒ rejected at `send` · late reminder past `valid_until` ⇒ suppressed `expired` · jobs crash ⇒ re-claimed, deliveries unique constraint prevents duplicates · 006 events duplicated/replayed ⇒ no duplicate reminders · preferences read failure ⇒ conservative defaults (mandatory channels only plus category defaults).

## 10. Observability
Delivery success/failure by channel, fan-out lag, SMTP errors, suppressed-by-reason counts, coalescing ratio, reminder lateness; registers `notifications` with 025 (functional: recent fan-out within threshold; email functional state separate).

## 11. Testing Strategy
Unit: preference/policy/bypass matrix; coalescing; dedup; template rendering per language/plurals; audience authority. Integration (real PG + SMTP test server): end-to-end send → inbox/email; permission lost before delivery; mandatory category not disable-able; channel independence; maintenance J-1/H-1/start/reschedule/cancel with fake clock and replay; late evaluation expiry; SMTP outage; privacy (no content in events/logs, erasure removes inbox). Frontend: center filters, priority ordering, alert vs notification styling, reduced motion/sound-off, persistent critical toast, keyboard operation, `aria-live` politeness. E2E: SSE ping updates bell and toast.

## 12. Migration / Versioning
Alembic revision for `notify`; category declarations versioned by owner; template keys live in catalogs (026) with `catalog_version`; contract semver'd.

## 13. Cross-Spec Dependencies
Prerequisites: 001 (jobs, secrets), 002 (principal, `VerificationChannel` — email implementation delivered here), 003, 004 (SSE, bell), 006 (maintenance/service events), 007, 020, 022 (`Notification`, `SoundService`, `Announce`), 026. Exposes `send`/`declare_category`/`send_alert` to every module, 025 (alert port), 017 (Wrapped delivery), 011 (News → notification), 013/014/015/016 categories; registers `communication.produce` with 019 when it exists (stub registry until then). Admin-configurable reminders/rules remain 019's.

## 14. Implementation Phases
1 Categories + producer + persistence → 2 Fan-out, preferences, coalescing, rendering → 3 Portal channel + center API + SSE → 4 Frontend center/toasts/preferences → 5 Email channel + outbox + admin transport → 6 Maintenance reminders → 7 System sources (service alerts, account security) → 8 Automations action contract + digests → 9 Observability/hardening.

## 15. Technical Decisions — `research.md` R1–R13.

## 16. Risks / Open Technical Questions
- **R1** OQ-45..49 use plan defaults (research); **product confirmation requested** (taxonomy, late evaluation, corrective messages, throttling, mute bypass).
- **R2** The generic engine (019) is planned later: until then rules are code-defined system sources only; the action contract is tested with a fake engine so 019 can plug in without changes here.
- **R3** Email deliverability (SPF/DKIM) is operator responsibility; documented.
- **R4** Push is out of scope (interface reserved).
- **R5** Large broadcast audiences: fan-out in batches with bounded concurrency; acceptable at community scale.

## Project Structure
```text
backend/src/portalab/{capabilities/notifications, modules/notifications/{categories,producer,fanout,preferences,coalesce,channels/{portal,email},maintenance,sources,api,models}} · backend/migrations/notify/versions/
frontend/src/features/notifications/{center,toasts,preferences,bell}
```
