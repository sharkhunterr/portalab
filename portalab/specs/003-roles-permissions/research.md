# Research — Roles, Permissions & Authorization (spec 003)

| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| R1 | **One in-process `AuthorizationEngine`** evaluating `authorize(principal, permission, resource) -> Decision`; every router, job, AI action, automation action and plugin handler goes through it | Single authorization model (CD-002/003/010) | Per-module checks; ABAC/policy-language engine (OPA/Casbin) — disproportionate for the model in the spec |
| R2 | **Role/group → permission grants with `allow`/`deny` effect; explicit deny wins; union otherwise; scope matched structurally** (`self`, `owned`, `module`, `service`, `plugin`, `global`) | FR-002/003/004, OQ-13 default | Allow-only (no explicit deny, rejected by spec edge case) |
| R3 | **Permissions are declared in code** (`declare_permission`) by core/modules/plugins and upserted idempotently into `authz.permissions`; disabled plugin ⇒ its permissions inactive | FR-021..023; keeps catalog and code consistent | Free-form permission rows entered by admins |
| R4 | **Reserved (Admin-only) set** enforced at assignment time and by a DB trigger; `Admin` role = "all enabled permissions" evaluated by the engine, not by copying rows | FR-009/010, no escalation by aggregation | Copying all permissions to the Admin role (drifts when new ones appear) |
| R5 | **Single-Admin invariant**: partial unique index (≤ 1 active Admin assignment) + transactional `transfer_admin` that locks a one-row `admin_singleton`; revoke-without-transfer is rejected | FR-009/011/012, CD-001; atomic, race-free | Application-only check (race) |
| R6 | **No permission cache across requests**; per-request memoization only; changes take effect on the next evaluation | FR-030/spec edge "orphaned grant", simplest correct | TTL caches (stale grants) |
| R7 | **AuditSink port + minimal append-only `audit.audit_entries`** introduced here (roadmap step 2); step 3 completes it (hash-chain checkpoints, query/retention/export) without a second model. 007 later adopts the same table | User roadmap decision; CD-013 | Separate audit tables per module |
| R8 | **Sensitive actions** = permissions flagged `sensitive`; allow *and* deny decisions are always audited; non-sensitive denials are not (OQ-14 default) | FR-034/035 | Auditing every decision (noise) |
| R9 | **Acting channel in the principal** (`channel = user|ai|automation|plugin`, `acting_for = user_id`); effective permissions are the user's, never a superset; channel recorded in audit | CD-003, FR-025 (AI) | Separate AI identity with its own role |
| R10 | **`ConfirmationService`**: short-lived single-use confirmation token bound to (principal, permission, resource, payload hash) for sensitive actions invoked via AI/automation or flagged `requires_confirmation` | FR-007 and CD-003 need a portal-wide primitive; AI/Automation specs consume it | Each caller inventing confirmation |
| R11 | **Privacy composes after authorization** (021): the engine returns allow; callers apply visibility filtering; the engine never reads or alters visibility | FR-031/033 | Merging privacy into permissions |

No `NEEDS CLARIFICATION` remains. Product questions (custom role authorship OQ-11, group semantics OQ-12) use the registry defaults: Admin-only authorship; groups are permission-bearing.
