# Implementation Plan: Automation / Rules Engine

**Branch**: `019-automations` | **Date**: 2026-10-01 | **Spec**: `specs/019-automations/spec.md`
**Roadmap**: Phase 6 step 21 *Automations*. The single generic WHEN→IF→THEN engine (CD-010). Builds on 007 (triggers), 003 (principal/authorize/`ConfirmationService`), and the action/condition providers already planned in 010, 013, 014, 016, 018, 011, 005, 006.

## Summary
Module `automations` owns the **bounded** automation model (event/schedule trigger → deterministic condition tree → ≤ N sequential owner-registered actions), the permission-bounded runner (author or scoped system identity, re-evaluated at run time), approval gates for sensitive actions, loop/repeat prevention, timeouts, storm throttling/batching, auto-suspension, and a provenance-rich execution history. It executes **nothing itself**: every action is a handler registered by the owning domain. It is intentionally not a general workflow tool.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: `jsonschema` (already via 018) · **Storage**: schema `automations` · **Testing**: pytest real PG with fake clock/fake action owners, property tests for condition determinism, loop/storm tests, Vitest, Playwright · **Constraints**: no bypass of permissions, deterministic critical decisions, bounded steps/depth/time, isolation per execution, no payload bodies/secrets stored · **Scale**: tens of automations, up to ~10³ executions/min peak (throttled).

## Constitution Check — PASS
I/XX one engine, no parallel mechanisms (actions in owners) · II/III extensible triggers/actions via registries · IV event-driven, idempotent · VI default-deny, approvals, audit · IX isolation, timeouts, suspension · XVI AI assist-only, never the decider (CD-003) · XIII audit of sensitive actions. No violations.

## 1. Architecture
```
007 events (automatable types) ─▶ TriggerConsumer ─▶ Matcher (filter) ─▶ Gate(idempotency · dedup_window · cooldown · rate/storm · suspended? · depth/loop)
        └▶ executions row (status pending) ─▶ job automations_run
Scheduler (at/relative/recurring in tz via 026) ──────────────▲
Runner: load version ─▶ re-evaluate identity permissions ─▶ ConditionEvaluator (closed leaves; trace) ─▶ steps: for each action
           ├ authorize(identity, action.permission, resource)  ✗ ⇒ refused
           ├ sensitive/destructive ⇒ ApprovalGate (per-run or standing) ⇒ awaiting_approval
           ├ handler(principal=automation, params, ctx{chain_id, depth}) with per-action timeout ⇒ result
           └ emitted events carry provenance.automation{id, execution_id, depth}
Failure accounting ─▶ AutoSuspender ─▶ notify(010) ; History API/UI ; Dry-run (no side effects)
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `DefinitionService` | closed-schema validation, versions, publish, standing approvals | registries, `ConfirmationService`, audit | admin API | append-only versions; critical ⇒ confirmation | schema/publish tests |
| `Registries` | triggers, condition leaves, action types | domains | `register_*` | closed; owners only | registry tests |
| `TriggerConsumer` | 007 consumers for active trigger types | 007 | `@consumer` | idempotent | trigger tests |
| `Scheduler` | at/relative/recurring (≥ 1 h, no cron) | jobs, 026 | job | DST-safe | schedule tests |
| `Gate` | idempotency, dedup window, cooldown, rate, suspension, loop depth | `core.db` | internal | never silent | gate matrix tests |
| `ConditionEvaluator` | deterministic tree eval + trace | ports | `evaluate()` | order-independent; permission leaf never grants | property tests |
| `Runner` | orchestrate steps, timeouts, provenance | action registry | job | isolation per execution | runner tests |
| `IdentityGuard` | author/system identity checks at run | authz | internal | re-evaluated every run | permission tests |
| `ApprovalService` | per-run and standing approvals, expiry | `ConfirmationService`, 010 | API | approver authorization; params hash | approval tests |
| `AutoSuspender` | failure accounting, suspension, notification | 010 | internal | explicit re-enable | suspension tests |
| `HistoryService` | execution list/detail, retention | `core.db` | API | refs only; no secrets | privacy tests |
| `DryRun` | evaluate without effects | evaluator | API | zero writes outside dry-run log | tests |
| Templates | shipped presets | registries | API | validate at load | template tests |
| Frontend builder/history/approvals | authoring UX | 022 | components | accessible; schema-driven | a11y/e2e |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/automations-contracts.md`

## 5. Events
Consumed: all `automatable` event types referenced by active automations (idempotent), `plugin.state_changed`, `admin.config_changed`, account/role change events (⇒ identity re-review). Produced: `automation.created|published|paused|resumed|suspended|archived`, `automation.approval_requested|approval_decided`. Executions are table rows (no per-run events). Chain tracking via `provenance.automation` in events emitted by owner handlers; `correlation_id` = `chain_id`. Replays of 007 do not re-run automations (consumers marked `replay_safe=False`).

## 6. Permissions & Security
`automations.read|manage|approve` (Admin in v1). Every action authorized against the identity's current rights; system identity limited to declared scopes ≤ Admin's rights at publish. Sensitive/destructive actions need approval (R7); AI output cannot flow into sensitive params or conditions (validated at publish). No secrets in params (schema + redaction); templating limited to declared event attributes; trigger payload bodies never stored. Audit via `AuditSink` for publish/approvals/sensitive executions (author, action, timestamp, context, result).

## 7. Configuration — `data-model.md` settings (declared into 020).

## 8. External Integrations — none (through action owners).

## 9. Error Handling & Resilience
Action exception ⇒ step failed, `on_error` policy, execution isolated · timeout ⇒ cancel + `timeout` status · worker crash ⇒ job re-claimed, unique execution key prevents double effects (handlers idempotent by `idempotency`) · owner domain unavailable ⇒ step `failed` (counts toward suspension) · approval expiry ⇒ not executed · storm ⇒ batch/throttle with records · definition referencing removed action type (plugin disabled) ⇒ automation paused with reason.

## 10. Observability
Executions/min by status, durations, suspended count, loop/storm preventions, approval latency, queue lag; registers `automations` with 025 (functional: scheduler on time, no stuck `awaiting_approval` beyond TTL).

## 11. Testing Strategy
Unit/property: condition determinism (shuffled evaluation order, depth limit), template substitution safety, schedule computation (tz/DST, min interval), gate matrix. Integration (real PG + fake owners): trigger → run → history; permission re-evaluation (author demoted ⇒ refused); approvals (approve/reject/expire, params hash tamper); loops (A→B→A, depth 3); repeat prevention (duplicate event, dedup window, cooldown); timeouts; storm batching; auto-suspension and re-enable; AI-boundary validation; plugin action isolation; privacy of history. Contract: registered owner action conformance (010 `communication.produce`, 013 award, 016 ticket/incident). Frontend: builder validation, dry-run display, approvals inbox, accessibility. E2E: campaign announcement automation.

## 12. Migration / Versioning
Alembic revision for `automations`; definition `schema_version` + upgraders; append-only versions; action/condition contracts semver'd; templates validated in CI.

## 13. Cross-Spec Dependencies
Prerequisites: 001, 003, 007, 020, 021, 022, 026. Action owners (registered when present): 010 (planned), 013, 016, 011, 005, 018, 006. Condition sources: 013, 014, 006. **Follow-ups in earlier plans**: 007 event-type registry per-field flags (`automatable`, `rewardable`, `aggregatable`) and `provenance.automation` convention; 013 `grant_via_automation` (anti-abuse-bound, source_kind=automation) alongside `grant_manual`; 016 `tickets.create`/`incidents.create` safe for non-interactive principals; 018 read-only `ai.invoke` facade; 011 `content.publish` action wrapper. Consumers: 014 (announcement presets), 010 (`communication.produce`).

## 14. Implementation Phases
1 Schema, registries, definition validation/versions → 2 Trigger consumer + gate + runner + history (event triggers, `communication.produce`) → 3 Condition evaluator + permission re-evaluation → 4 Approval gate + sensitive catalog → 5 Loop/repeat/timeout/storm controls → 6 Auto-suspension → 7 Schedule triggers → 8 Owner action wiring (013/016/011/005/018/others) → 9 Builder UI, dry-run, templates → 10 Observability/hardening.

## 15. Technical Decisions — `research.md` R1–R14.

## 16. Risks / Open Technical Questions
- **R1** OQ-90..94 use plan defaults (research); **product confirmation requested** (schedule scope, thresholds, critical catalog, authoring scope, AI boundary).
- **R2** Cross-plan follow-ups (007/013/016/018/011) must land with their implementations; stubs and contract tests here keep the engine independently testable.
- **R3** Closed condition catalog may feel restrictive; extension is through new leaves added by core specs, deliberately not user code.
- **R4** Chain tracking relies on action handlers propagating provenance (conformance test per action type).
- **R5** Admin-only authoring (v1) limits adoption; per-user authoring is designed-for but disabled until bounded further.

## Project Structure
```text
backend/src/portalab/{capabilities/automations, modules/automations/{definitions,registries,triggers,scheduler,gate,evaluator,runner,identity,approvals,suspender,history,dryrun,templates,api,models}} · backend/migrations/automations/versions/
frontend/src/features/automations/{builder,history,approvals,templates}
```
