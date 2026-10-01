# Implementation Plan: Roles, Permissions & Authorization

**Branch**: `003-roles-permissions` | **Date**: 2026-10-01 | **Spec**: `specs/003-roles-permissions/spec.md`
**Roadmap**: Phase 1 step 2 *Auth / Users / Permissions* — **introduces the `AuditSink` and the minimal append-only audit model**; step 3 *Audit / Security* completes it (same model).

## Summary
Module `authz` implements the single authorization model of the portal: permission catalog declared in code, roles and groups with allow/deny grants and structural scopes, the `authorize()` engine, the Admin-authority capability (single-Admin invariant and atomic transfer), the confirmation primitive for sensitive actions, and the `AuditSink` with a minimal append-only `audit.audit_entries` table. It replaces the deny-everything `Authorizer` port stub of spec 001. It does **not** own privacy/visibility (021), the AI/automation confirmation *flows* (018/019), or the audit query/retention/tamper-verification features (step 3).

## Technical Context
**Language**: Python 3.12 · **Dependencies**: none new (001 baseline) · **Storage**: PostgreSQL schemas `authz`, `audit` · **Testing**: pytest (real PG), property-style unit tests for the engine, concurrency tests · **Constraints**: server-side only, default-deny, fail closed on audit failure for sensitive actions, no cross-request permission cache · **Scale**: dozens of roles, hundreds of permissions, evaluation per request in sub-millisecond-to-few-ms DB lookups.

## Constitution Check — PASS
VI default-deny/server-side · II/XX one authorization model, no module-local checks · III plugin permissions integrate, cannot be Admin-equivalent · XIII audit of sensitive actions, append-only · XIV deterministic evaluation (order-independent) · XVI AI never exceeds user · VII privacy kept separate (021) · VIII tests below · XIX expand/contract migrations. No violations.

## 1. Architecture
```
router/job/AI/automation/plugin ─▶ require(permission, resource)
                                       │
        PermissionCatalog ◀── declare_permission() (core/modules/plugins, startup upsert)
                                       ▼
   AuthorizationEngine ── GrantStore (roles+groups, allow/deny, scopes) ──▶ Decision
        │ sensitive? ─▶ AuditSink ─▶ audit.audit_entries (append-only)
        └ requires_confirmation? ─▶ ConfirmationService
   AdminAuthority (capability) ── locks authz.admin_singleton ── identity orchestrates transfer
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `PermissionCatalog` | declare/upsert/enable-disable permissions; reserved & sensitive metadata | `core.db` | `declare_permission()` | idempotent; plugin disable ⇒ inactive | declare idempotence, plugin withdrawal |
| `GrantStore` | roles, groups, grants, user assignments | `core.db` | CRUD services | reserved perms only on `admin`; base roles undeletable | reserved-assignment test, aggregation-escalation test |
| `AuthorizationEngine` | deny-by-default evaluation, scope matching, Admin = all enabled | GrantStore, Catalog | `authorize()`, `require()` | explicit deny wins; deterministic; no AI superset | engine unit/property tests |
| `AdminAuthority` | first-admin grant, atomic transfer, protect sole Admin | singleton row lock | `authz.admin_authority` | exactly one Admin, never zero | concurrency test |
| `AuditSink` + store | append audit entries, fail-closed for sensitive | `core.db` | `record()` | append-only trigger; no secrets in context | append-only + redaction tests |
| `ConfirmationService` | single-use bound confirmation tokens | `core.db`, `core.secrets` | `issue()`/`consume()` | TTL, bound to payload hash | replay/expiry tests |
| `authz.api` | roles/groups/grants/assignments/catalog/`me/permissions` | all | OpenAPI | each route self-protected | permission matrix |
| Route dependency + route-table checker | wires `require()` into FastAPI, replaces 001 stub, CI test asserting every route is protected or allow-listed | app factory | `Depends(require(...))` | default-deny | generated route test |

## 3. Data Model / 4. Contracts
See `data-model.md` and `contracts/authz-contracts.md`.

## 5. Events
Produced: `permission.*` (role/group/grant changes, `policy_changed`, `admin_transfer_attempted`, sensitive `denied`) via the kernel `EventPublisher`; consumed here: plugin lifecycle events (`plugin.enabled|disabled`) to toggle permission availability (until 023 exists the toggle is a direct service call). Dedup `(holder, key, change_seq)`; order per holder. Failure: outbox retry.

## 6. Permissions & Security
| Operation | Actor | Permission | Audit |
|---|---|---|---|
| manage roles/groups/grants/assignments | Admin (default) | `users.roles.manage` | yes (sensitive) |
| view catalog | Admin | `users.roles.manage` | no |
| transfer Admin | Admin | `users.admin.transfer` + step-up (spec 002) | yes |
| read own effective permissions | user | self | no |
Fail closed: audit write failure ⇒ sensitive action refused. Audit context redacted via kernel redaction. No permission derived from the frontend.

## 7. Configuration
Declared: `authz.confirmationTtlSeconds`, `authz.auditContextMaxBytes`. Base-role default grants are declared **in code** per module (`default_roles`) and seeded idempotently; admins adjust grants through the API.

## 8. External Integrations
None.

## 9. Error Handling & Resilience
DB down ⇒ authorization fails closed (503); unknown permission key ⇒ programmer error caught at startup (declared-vs-used test); plugin crash does not affect engine; reserved-assignment attempts ⇒ 422 `authz.reserved_permission`; concurrent admin transfer ⇒ one wins, others 409.

## 10. Observability
Counters: decisions allow/deny by permission, sensitive denials, audit-write failures, confirmation issued/consumed; structured logs with correlation id; feeds Observability (025) later.

## 11. Testing Strategy
Unit/property: union, deny-wins, scope matching, order independence, Admin=all-enabled, AI/automation never superset. Integration: assignment→effect on next request; revoke; plugin disable withdraws; reserved set; single-Admin under concurrency; audit written for sensitive allow+deny, append-only enforced. Security: generated permission matrix over **all** routes (replaces 001 default-deny stub test), confirmation replay/expiry. Migration: upgrade from empty + from 002.

## 12. Migration / Versioning
Revisions for `authz` and `audit` (expand/contract); audit table never altered destructively; `permissions` catalog changes additive; API `/api/v1`.

## 13. Cross-Spec Dependencies
Prerequisites: 001 kernel; 002 (`identity.users`, `identity.principal`) — implemented together in step 2 (identity tables first). Exposes: `authorize/require`, `declare_permission`, `authz.admin_authority`, `AuditSink`, `ConfirmationService` to every later spec. Completed later: step 3 (audit completion, security hardening), 007 (adopts audit table/event envelope), 018/019 (confirmation flows), 021 (visibility composes after authz), 023 (plugin permission lifecycle).

## 14. Implementation Phases
1 Data & migrations → 2 Catalog & declaration → 3 Engine → 4 Admin authority → 5 AuditSink + store → 6 Route dependency + API → 7 Confirmation → 8 Matrix/hardening tests.

## 15. Technical Decisions & Trade-offs
`research.md` R1–R11. In-process engine with DB reads (no cache) trades a little latency for always-correct revocation; policy-language engines rejected as disproportionate.

## 16. Risks / Open Technical Questions
- **R1** Per-request DB lookups on hot paths: mitigated by one query per request (memoized); a cache only if measured necessary, invalidated by `permission.*` events.
- **R2** Audit hash-chain/tamper-evidence deferred to step 3 (this plan provides append-only + `seq`).
- **R3** Scope `owned` needs the caller to supply `owner_id`; wrong supply = authorization bug ⇒ review checklist + tests per router.
- **R4** Plugin permission lifecycle depends on 023; temporary direct toggle.

## Project Structure
```text
backend/src/portalab/modules/authz/{catalog,grants,engine,admin_authority,audit,confirmation,api,models}/
backend/migrations/authz/versions/ · backend/migrations/audit/versions/
backend/src/portalab/core/authorization.py   # port + FastAPI dependency (replaces 001 stub)
```
