# Implementation Plan: Marketplace

**Branch**: `015-marketplace` | **Date**: 2026-10-01 | **Spec**: `specs/015-marketplace/spec.md`
**Roadmap**: **Slice A** = Phase 7 step 25 *Community Projects / Funding* (funding lifecycle, reservations, validation gate); **Slice B** = Phase 8 step 26 *Marketplace* (catalog, products, conditions, purchase, ownership, activation, refunds, grants, revocation, quota, audit). Builds on 013 (ledger), 012 (proposals/votes), 014 (campaign conditions), 003, 007, 010, 009/017/022/024 (entitlement consumers), 023 (activation, later).

## Summary
Module `marketplace` is the convergence point: **(A)** the community-funding lifecycle (Idea → Proposal → open for free votes + reserved Coin funding → Admin validation → Development → Beta → Release, with Rejected/Abandoned off-ramps) in which Community owns proposals/votes, Gamification/Economy owns Coins and reservations, and Marketplace owns state and published refund/consume rules; and **(B)** the product marketplace — extensible product types, versioned price/conditions/refund policy, strict-AND server-side eligibility, atomic acquisition, ownership with no double purchase, activation through type handlers, history, refunds as new transactions, grants/revocations, extra request quota with **no paid priority**, and full audit.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: none · **Storage**: schema `marketplace` · **Testing**: pytest real PG (concurrency on acquisition/funding, atomicity with fault injection, state machine), contract tests with real 013/012/024 stubs, Vitest, Playwright · **Constraints**: no real-money, balances never negative, ledger transactions only, versions never reinterpret history, activation failure isolated · **Scale**: community scale (≤ 10³ products, ≤ 10⁵ ownerships).

## Constitution Check — PASS
I Product integrity (locked marketplace/economy rules, no paid priority) · II/XX Coins only via 013, activation via 023, votes via 012, conditions via 013/014/003 · III extensible ProductTypes · IV events + idempotency · V provenance/versioning · VI/VII server-side eligibility, audit, privacy · IX activation isolation · XIII audit of sensitive actions. No violations.

## 1. Architecture
```
Slice A: Community proposal ─register─▶ ProjectService(state machine, rules freeze at open, history, events)
   Funding ─▶ FundingService(state=open, min/max, acknowledgement) ─▶ EconomyService.reserve (013)  ─▶ project_fundings(reserved)
   Admin transitions ─▶ validation gate ─▶ development ─▶ beta ─▶ released ⇒ ResolutionService.consume (per rules/milestones)
   reject/abandon ⇒ ResolutionService.release (refund tx) ; deletion saga ⇒ R6 handling ; notifications(010)
Slice B: Catalog (products + versions + categories) ─▶ Eligibility(AND of closed conditions: 013/014/003)
   acquire(user, product, idem) ─ UoW ─▶ ownership check ─▶ EconomyService.spend(uow) ─▶ ownership(snapshot) ─▶ outbox ─▶ after commit: ActivationHandler(type) ⇒ active | needs_configuration | failed
   Refund/Grant/Revoke ─▶ RefundService (new tx) / GrantService / RevocationService (ground+reason) ─▶ audit+events+notifications
   QuotaService (units) ─▶ RequestQuotaProvider(024) ; EntitlementReader ─▶ 009/022/017/Community
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `ProjectService` | lifecycle state machine, rules freeze, history, events | `core.db`, audit | API + `ProjectLifecycle` | permissioned/audited transitions; append-only history | transition table tests |
| `FundingService` | validate funding, acknowledgement, reserve | `EconomyService`, state | `/projects/{id}/fund` | only in `open`; independent of votes; atomic with reservation | concurrency/overspend tests |
| `ResolutionService` | consume/release per frozen rules, milestones, deletion handling | `EconomyService` | internal/job | never silent; idempotent | refund/consume tests |
| `ProductService` + `ProductTypeRegistry` | catalog, versions, availability states | `core.db`, 026 | API | versioned; archived keeps access | version tests |
| `EligibilityService` | closed conditions strict AND | 013/014/003 ports | `evaluate()` | server-side; names unmet conditions | matrix tests |
| `PurchaseService` | atomic acquisition, idempotency | `EconomyService`, UoW | `acquire()` | no double purchase; atomic | race/fault tests |
| `ActivationService` + handlers | per-type activation, retries, needs-configuration | 009/022/017/023/003 ports | internal/job | failure isolated; allow-listed access grants | handler tests |
| `RefundService` | policy-based refunds as new tx, revoke ownership | `EconomyService` | API | window/percent; non-refundable labelled | refund tests |
| `GrantService` / `RevocationService` | grants (marked), revocation grounds | audit, notifications | admin API | reason mandatory; history intact | audit tests |
| `QuotaService` | extra units, provider impl | `quota_units` | `RequestQuotaProvider` | no priority input | quota tests |
| `EntitlementReader` | ownership reads for consumers | `ownerships` | capability | cached per epoch | contract tests |
| Frontend | catalog, purchase, owned, projects, admin | 022/004 | components | accessible; conditions named | a11y/e2e |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/marketplace-contracts.md`

## 5. Events
Produced (ids/amounts only): `marketplace.purchase|unlock|refund|grant|revocation|product_published|product_archived`, `project.status_changed`, `project.funding_added|funding_released|funding_consumed`. Dedup per data-model; transactional outbox with the ledger writes. Consumers: 013 (rewards on purchase/funding events if rules exist), 017 stats, 010 notifications (category `marketplace.*`, `marketplace.project`), 012 feed. Consumed: `project.created`, deletion saga calls, `campaign.*`, activation results.

## 6. Permissions & Security
`marketplace.read|purchase` (default grants for active accounts), `marketplace.manage|grant|revoke|refund|audit`, `projects.manage` (Admin; sensitive + `ConfirmationService`; audited). Eligibility and ownership checks only server-side; `Idempotency-Key` required on acquire/fund; amounts validated as integers within configured limits; `access` products can grant only permissions on the Admin-approved allow-list and never Admin-reserved ones; prices/conditions edited only through versioned publishes. No paid priority: contract test asserts request queue ordering inputs exclude ownership/quota.

## 7. Configuration — `data-model.md` settings (declared into 020).

## 8. External Integrations — none (plugin packages come from 023).

## 9. Error Handling & Resilience
Insufficient Coins ⇒ 409/422 problem, no side effects · duplicate acquire ⇒ same result (idempotency) · activation failure ⇒ ownership kept, retry job, isolated · ledger/DB failure mid-acquire ⇒ single transaction rolls back (or compensating refund when the saga fallback is used) · state transition race ⇒ optimistic `version` · funding after state change ⇒ `project.funding_closed` · 013 unavailable ⇒ funding/purchase refused (fail closed) · consumer/handler outage (009/022/017) ⇒ ownership still recorded, activation retried.

## 10. Observability
Purchases/refunds/grants, activation failures, reserved vs consumed vs released totals (drift check against 013 `verify`), stuck lifecycle states; registers `marketplace` with 025 (functional: activation retry queue, reservation reconciliation = 0).

## 11. Testing Strategy
State-machine tables (project + product availability); property tests for funding totals vs reservations; concurrency (double acquire, double fund, overspend); atomicity fault injection (after spend before ownership); eligibility matrix incl. named unmet conditions and strict AND; refund policy matrix; revocation grounds; activation per type with fakes; quota with 024 (priority-independence test); deletion handling (R6) with 002 saga; privacy/permission matrix; frontend flows (conditions, non-guarantee notice, needs-configuration). E2E: propose → vote → fund → validate → release; publish → buy → refund.

## 12. Migration / Versioning
Alembic revision for `marketplace` (slice A tables first, B additive); product versions append-only; project funding rules frozen; ProductType registry additive; contracts semver'd.

## 13. Cross-Spec Dependencies
Prerequisites: 001, 002 (deletion saga), 003, 007, 010, 013 (+ **follow-ups: `reserve/release/consume`, `spend(uow)`**), 012 (proposals/votes; calls `ProjectLifecycle`), 014 (`CampaignReader`), 020, 021, 022, 026. Consumers: 009 (widget entitlements), 022 (theme availability), 017 (`product_owned`), 024 (quota), Community (cosmetics sections), 023 (`ExtensionActivation`, step 27). **Follow-ups to apply in earlier plans**: 013 reservation operations and ledger kinds; 009/022/017 read `EntitlementReader`; 024 consumes `RequestQuotaProvider`; 023 provides `ExtensionActivation`.

## 14. Implementation Phases
**Slice A (25)**: 1 schema + project state machine → 2 `ProjectLifecycle` port + Community integration → 3 funding (reserve, acknowledgement) → 4 validation/transitions/notifications → 5 resolution (release/consume/milestones, deletion handling) → 6 UI.
**Slice B (26)**: 7 catalog + versions + categories + admin publish → 8 eligibility + acquisition + ownership → 9 activation handlers + needs-configuration → 10 history/refunds → 11 grants/revocation/audit → 12 quota + entitlement reader + search/widgets/stats → 13 hardening.

## 15. Technical Decisions — `research.md` R1–R14.

## 16. Risks / Open Technical Questions
- **R1** OQ-70..74 use plan defaults (research); **product confirmation requested** (refund windows, funding formulas/milestones, quota semantics, revocation grounds, strict-AND conditions).
- **R2** 013 must gain reservation operations and a unit-of-work-aware `spend` (follow-ups); until then this plan's tests run against a compliant fake and the saga fallback is specified.
- **R3** Per-user ownership vs portal-level plugin installation needs product confirmation (R10).
- **R4** `access` products touching permissions are high risk: allow-list + Admin approval only.
- **R5** Funding deletion default (R6) is a policy choice to confirm.
- **R6** Real-money purchase is impossible by design (no payment code, tests assert no such path).

## Project Structure
```text
backend/src/portalab/{capabilities/marketplace, modules/marketplace/{projects,funding,resolution,products,types,eligibility,purchase,activation,refunds,grants,revocation,quota,entitlements,providers,api,models}} · backend/migrations/marketplace/versions/
frontend/src/features/marketplace/{catalog,product,owned,projects,admin}
```
