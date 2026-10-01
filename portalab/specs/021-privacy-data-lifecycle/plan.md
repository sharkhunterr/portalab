# Implementation Plan: Privacy, Data Lifecycle & Audit/Security completion

**Branch**: `021-privacy-data-lifecycle` | **Date**: 2026-10-01 | **Spec**: `specs/021-privacy-data-lifecycle/spec.md`
**Roadmap**: Phase 1 step 3 *Audit / Security* — completes the audit system introduced in 003 (same `audit.audit_entries`, no second model) and hosts the privacy/retention engine and security hardening baseline.

## Summary
Module `privacy` implements the visibility engine (policy ▸ preference ▸ default, composed after authorization), temporary admin overrides that never touch the preference, data classification enforcement, the retention engine over a target registry, generic registry-driven erasure/export participants, the aggregation guard, and the separately-authorized service-data purge. In this step it also **completes the audit system** (partitioning, hash-chain checkpoints, verification, query/export) and ships the **security hardening baseline** (headers, rate limits, dependency/secret scanning).
Not owned: audit rules (007+003, CD-013), user-facing export/deletion endpoints (002), connector disconnect semantics (005), statistics (017).

## Technical Context
**Language**: Python 3.12 · **Dependencies**: none new at runtime; CI adds `pip-audit`, `npm audit`, secret scanner · **Storage**: schemas `privacy`, `audit` (partitioned) · **Testing**: pytest real PG, security suite · **Constraints**: privacy independent of permission; append-only audit/events/ledger; no PII in append-only tables; admin-configurable thresholds · **Scale**: personal/community; audit volume handled by monthly partitions.

## Constitution Check — PASS
VII Privacy by design · XIII Observability & Auditability (completion, tamper evidence) · VI security baseline · XV/XIX integrity preserved through retention/erasure · II/XX no new audit/preference/config store · XI/XII n/a (no UI beyond admin screens, which meet WCAG 2.2 AA). No violations.

## 1. Architecture
```
viewer ─▶ require() (003) ─▶ domain data ─▶ VisibilityFilter ─▶ response
                                      ▲  effective_level = policy ▸ owner preference (VisibilityPreferenceProvider) ▸ class default (config)
Worker: retention_job ─▶ RetentionTarget registry ─▶ delete/anonymize/aggregate/drop_partition ─▶ retention_runs
        audit_checkpoint_job ─▶ audit_checkpoints ; `portalab audit verify`
Participants: RegistryErasureParticipant / ExportContributor (used by identity's DeletionSaga/ExportBuilder)
Middleware: security headers · size limits · rate limiter
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `VisibilityService` + `VisibilityFilter` | effective level, redaction after authz | policies, providers, config | `filter()`, `effective_level()` | never reads permissions; never mutates preferences | level matrix tests, permission≠privacy test |
| `PolicyService` | apply/remove temporary override, one active per (subject, class) | `core.db`, `AuditSink` | `apply()`, `remove()` | preference untouched; audited; sensitive | preserve/restore tests |
| `RetentionEngine` | run policies per target, batch, record runs | registry, config | job `retention_run` | skips `integrity_necessary`; partition drop for append-only | retention tests |
| `ClassificationGuard` | CI tests: PII classification, no PII in append-only | kernel registry | tests | blocks merge | boundary tests |
| `RegistryErasureParticipant` / export helper | generic scrub/export of classified columns | kernel registry | participant contracts | idempotent; no secrets | erasure/export tests |
| `AggregationGuard` | suppress small cells | config | `guard()` | default min 5 (config) | guard tests |
| `ServicePurge` | purge historized data of a disconnected service | connectors capability, jobs | job `purge_service_data` | only via `services.purge`, confirmation, audited | purge tests |
| `AuditPartitioner` | monthly partitions, retention by drop | `core.db` | maintenance job | no row-level DML | partition tests |
| `AuditCheckpointer` + `audit verify` | hash-chained batch checkpoints, verification | `core.db` | job, CLI | detects altered/missing rows | tamper test |
| `AuditQuery` API | filter/export, redacted by viewer level, audit-reads audited | authz | `GET /audit` | `audit.read` | permission/redaction tests |
| `SecurityMiddleware` | headers, size limit, rate limit | app factory | middleware | configurable via Administration | header/limit tests |

## 3. Data Model / 4. Contracts
See `data-model.md`, `contracts/privacy-contracts.md`.

## 5. Events
Produced: `privacy.override_applied|removed`, `privacy.retention_applied`, `service.data_purged`, `audit.checkpoint_created`, `audit.verification_failed` (via `EventPublisher`; dedup `(policy_id, change_seq)` / `(checkpoint range)`). Consumed: `user.deletion_*` only through identity's saga (participant calls), `service.disconnected` (informational — never triggers purge). Failure: retried jobs, idempotent.

## 6. Permissions & Security
| Operation | Permission | Audit |
|---|---|---|
| apply/remove visibility policy; change retention config | `privacy.manage` | yes (sensitive) |
| read/export audit | `audit.read` (Support level sees redacted context, Admin full — registry default) | audit-reads audited |
| purge service data | `services.purge` + confirmation | yes |
Hardening: CSP/HSTS/`X-Content-Type-Options`/frame-ancestors none, body-size caps, rate limiting (per IP + per user), dependency audit + secret scan in CI, no secrets in audit context (redaction).

## 7. Configuration (declared into Administration)
`privacy.minAggregateSize`, `privacy.retention.<class>.days`, `privacy.retention.auditMonths`, `privacy.exportTtlDays`, `privacy.defaultLevel.<class>`, `security.rateLimit.*`, `security.maxBodyBytes`.

## 8. External Integrations
None (CI tooling only).

## 9. Error Handling & Resilience
Retention/purge failures retry per target and never block requests · provider missing ⇒ class default level, never public · checkpoint job lag does not affect writes · verification failure ⇒ `audit.verification_failed` + alert (025 later) · rate limiter fails open only for health endpoints.

## 10. Observability
Counters: visibility decisions by level, overrides active, retention rows by target, checkpoint lag, verification result, rate-limit hits; structured logs without PII.

## 11. Testing Strategy
Unit: level resolution matrix, preserve/restore, aggregation. Integration (real PG): override then remove ⇒ preference intact; retention skips integrity targets; partition drop; checkpoint + verify + tamper detection. Security: permission≠privacy, audit redaction by role, headers/limits, no secrets in audit. CI: classification/no-PII-in-append-only tests, `pip-audit`/`npm audit`. Migration: audit table → partitioned (expand/contract) with data.

## 12. Migration / Versioning
Convert `audit.audit_entries` to monthly partitions via create-new/copy/swap migration (low volume at this stage); new revisions for `privacy` schema; checkpoints append-only; API `/api/v1`.

## 13. Cross-Spec Dependencies
Prerequisites: 001 kernel (registry, tombstone), 002 (participants contract, deletion saga), 003 (AuditSink, `VisibilityFilter` port, `require`). Exposes: `VisibilityFilter`, `RetentionTarget`, `AggregationGuard`, `AuditQuery`. Used later by: 007 (adopts audit/event retention), 009/012/017/024 (visibility, aggregation), 020 (surfaces audit/security), 005 (purge).

## 14. Implementation Phases
1 Visibility engine & policies → 2 Classification guards & retention engine → 3 Erasure/export participants & aggregation guard → 4 Audit partitioning → 5 Checkpoints, verify, query/export → 6 Service purge → 7 Security middleware & CI scanners → 8 hardening tests.

## 15. Technical Decisions & Trade-offs
`research.md` R1–R10. Checkpoint chaining over per-row chain (no write contention), partition-drop retention (keeps append-only), preferences not centralized (no second store).

## 16. Risks / Open Technical Questions
- **R1** Privacy is not an explicit roadmap line; planned here under "Audit / Security" — confirm.
- **R2** Converting the audit table to partitions touches 003's migration; scheduled before volume exists.
- **R3** Default thresholds (min aggregate 5, retention windows) are registry defaults pending product confirmation.
- **R4** Rate limiting is in-process (single node); distributed limiting is out of scope.

## Project Structure
```text
backend/src/portalab/modules/privacy/{visibility,policies,retention,participants,aggregation,purge,api,models}/
backend/src/portalab/modules/authz/audit/{partitions.py,checkpoints.py,query.py,verify.py}   # completion of 003's audit store
backend/src/portalab/app/security.py   # headers, limits, rate limiting
backend/migrations/privacy/versions/ · .gitlab-ci.yml (pip-audit, npm audit, secret scan)
```
