# Implementation Plan: Gamification & Economy

**Branch**: `013-gamification-economy` | **Date**: 2026-10-01 | **Spec**: `specs/013-gamification-economy/spec.md`
**Roadmap**: **Slice A** = Phase 6 step 19 *Gamification* (ledger, values, levels, reward rules, multipliers, anti-abuse, versioning, admin rewards, achievements, deletion, progression); **Slice B** = Phase 7 step 23 *Leaderboards*; **Slice C** = Phase 7 step 24 *Quests / Challenges* (quests, daily objectives, challenges). Builds on 007 (events), 010 (send), 017 (stats), 020, 021, 002 deletion saga.

## Summary
Module `gamification` owns the **three separate values** (XP, Contribution, Coins), the **append-only transaction ledger** with transactional balances (never negative, never rewritten), **versioned reward rules** applied deterministically to domain events with idempotency, derived **Levels**, **achievements**, multiplicative **modifiers with a configurable cap** (CD-024) supplied by Campaigns, **anti-abuse** (cooldown, caps, diminishing returns, anomaly withholding with admin review), manual admin rewards, Coin destruction on final deletion, and authoritative progression read APIs. Leaderboards (B) and quests/daily objectives/challenges (C) are later slices of the same module. Spending surfaces (Marketplace, Community funding) call its service layer; it never owns them.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: none · **Storage**: schema `gamification` (ledger with immutability triggers) · **Testing**: pytest real PG (concurrency/race tests for spend and idempotency, trigger tests), property tests for combination/caps/curves, Vitest, Playwright · **Constraints**: no real-money Coins, no conversion between values, ledger immutability, deterministic reconstruction, failures never corrupt balances (transactional) · **Scale**: personal/community (≤ 10⁶ ledger rows/yr).

## Constitution Check — PASS
I Product integrity (exactly three values; level derived) · IV event-driven, idempotent (CD-012) · V provenance/versioned rules · VI/VII Coins destroyed on deletion, visibility honored · IX failure ⇒ no balance corruption · XIII audit of sensitive economy actions · XX no generic rule engine (R2 boundary; generic automations in 019), modifiers from 014, funding lifecycle in 015 (CD-008). No violations (R2 boundary flagged).

## 1. Architecture
```
007 events ─▶ RewardConsumer (per-user advisory lock) ─▶ RuleResolver(version at occurred_at) ─▶ GrantCalculator(base)
      ─▶ AntiAbuse(cooldown · diminishing · amount caps · anomaly) ─▶ Modifiers(rule × 014 ModifierProvider, multiplicative, cap) ─▶ cap-aware final
      ─▶ LedgerWriter(TX: insert transactions + update balances + counters + level crossing + outbox events)
      └▶ AchievementEvaluator (counters, 017 stat, level) ─▶ LedgerWriter(source_kind=achievement)
Other modules ─▶ EconomyService.spend/refund (atomic non-negative) ─▶ LedgerWriter
Admin ─▶ rules (versioned, simulate, publish) · manual grants · anomaly review · verify
Deletion saga ─▶ GamificationErasureParticipant ─▶ destruction tx + purge balances/progress
Slice B: LeaderboardJob ─▶ snapshots ; Slice C: QuestEvaluator(period keys in economy tz) ─▶ LedgerWriter
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `LedgerWriter` | single write path: insert tx, update balance, counters, level, outbox | `core.db` | `record()` | atomic; triggers forbid UPDATE/DELETE; non-negative | race/immutability tests |
| `EconomyService` | spend/refund/balance/history | LedgerWriter | capability | idempotent; `InsufficientCoins`; refund = new tx | concurrency tests |
| `RuleStore` + `RuleResolver` | versioned rules, effective-by-instant resolution, simulation | 020 audit | admin API | closed schema; append-only versions | version-resolution tests |
| `GrantCalculator` | base amounts (fixed/per-unit) | rules | internal | integer math, rounding policy | property tests |
| `ModifierCombiner` | multiplicative combine + cap | `ModifierProvider` (014) | internal | cap from config; deterministic order | property tests |
| `AntiAbuse` | cooldown, diminishing, caps, anomaly | `usage_windows` | internal | applies after multipliers; `occurred_at` windows | guard tests |
| `RewardConsumer` | 007 consumers for event types in active rules | 007 | `@consumer` | idempotent, per-user lock | idempotency/late-event tests |
| `LevelService` | curve, derive level, level-up detection | curves | internal | level never a balance | curve tests |
| `AchievementEvaluator` | counters + criteria, unlock once | counters, 017 port | internal | unique unlock; rewards via ledger | unlock tests |
| `ManualRewards` | admin grants with reason, threshold confirmation | authz, `ConfirmationService` | API | marked manual; audited | permission/audit tests |
| `AnomalyService` | withheld queue, approve/reject/confirm abuse (correction tx) | ledger | API | no silent drops | review tests |
| `ErasureParticipant` | destroy Coins, purge | 002/021 | participant | idempotent saga step | deletion tests |
| `ProgressionAPI` | progression, history, achievements | visibility 021 | API | separate values; visibility | privacy tests |
| `Verifier` | recompute balances, `--replay` drift check | ledger/events | CLI/API | read-only | verify tests |
| (B) `LeaderboardService` | snapshots, ranks, opt-out | balances/ledger, 021 | API | visibility-bound | ranking tests |
| (C) `QuestEvaluator` | quests/daily/challenges, period keys | counters, stats tz | internal | once per period | period tests |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/economy-contracts.md`

## 5. Events
Produced (no PII): `reward.granted`, `user.level_up`, `achievement.unlocked`, `quest.completed` (C), `economy.coins_spent|refunded|destroyed`, `economy.anomaly_flagged`, `economy.rule_published`; emitted through the outbox in the same transaction as the ledger write; dedup keys per data-model. Consumed: event types of active rules/achievements/quests (idempotent via `idempotency_key` unique + `ctx.idempotent_effect`), `campaign.*` for modifier windows (through the port). Per-user ordering by advisory lock; late events evaluated at their `occurred_at` windows (R8).

## 6. Permissions & Security
`gamification.read` (default grant) with 021 visibility for other users; `economy.rules.manage`, `economy.grant`, `economy.audit`, `economy.anomaly.review` — Admin-only, sensitive, audited (`AuditSink`, confirmation above thresholds / for rule publish). AI/automations call `grant_manual` only as the acting principal with these permissions. No API to convert values or create Coins from money; ledger tables write-protected by triggers and a restricted DB role is documented for production. Ledger rows hold no free-text PII.

## 7. Configuration — `data-model.md` settings (declared into 020).

## 8. External Integrations — none.

## 9. Error Handling & Resilience
Transaction failure ⇒ nothing partially applied (single DB transaction incl. outbox) · duplicate/late events ⇒ idempotent no-op · overspend ⇒ `InsufficientCoins` without side effects · modifier provider (014) unavailable ⇒ rule multiplier only (recorded `modifiers_unavailable`) and flagged, never blocks base grants · anomaly detector failure ⇒ fail open on detection but caps/cooldowns still enforced · consumer crash ⇒ re-claim, idempotency prevents duplicates · notification failure ⇒ reward unaffected.

## 10. Observability
Grants/sec, withheld counts by reason, anomaly flags, ledger-vs-balance drift (verify job), spend failures, rule version in force, consumer lag; registers `gamification` with 025 (functional: consumer lag, drift = 0).

## 11. Testing Strategy
Unit/property: modifier product and cap, rounding, curve monotonicity, cooldown/cap/diminishing windows, version-by-instant resolution. Integration (real PG): grant idempotency under concurrent duplicates; spend race (two concurrent spends cannot overdraw); ledger immutability (UPDATE/DELETE rejected); balance = Σ ledger; manual grant audit; achievement unique unlock; late/out-of-order events; deletion saga step; `verify` and `verify --replay`; privacy of progression/ledger views. Contract: `ProgressionReader`, `ModifierProvider` (fake 014), `EconomyService` consumers (fake 015). Frontend: separate display of three values, history, admin simulation, confirmation flows. E2E: earn → level-up notification → achievement.

## 12. Migration / Versioning
Alembic revisions for `gamification` (slice A first, B and C additive); immutability triggers via 001 helper; rule/curve/achievement versions append-only; DB-role hardening documented; capability contracts semver'd.

## 13. Cross-Spec Dependencies
Prerequisites: 001, 002 (deletion saga participant hooks), 003, 007 (event registry `rewardable` attributes, consumers), 010 (categories/`send`), 017 (provider for `statistic_at_least`, stat unlock reads `ProgressionReader`), 020, 021 (visibility datum `progression`), 022. Consumers: 014 (modifiers/campaign quests), 015 (spend/refund, level/achievement conditions), 012 (presentation of progress/leaderboards/quests), 016 (`grant_contribution`), 019 (manual grant action), 018 (progression tool). Domain event sources: 024 (media), 011, 016, 012…

## 14. Implementation Phases
**Slice A (step 19)**: 1 schema + ledger + balances + immutability → 2 EconomyService (spend/refund) → 3 rules store/versioning/resolver/simulate → 4 reward consumer + calculator + idempotency → 5 modifiers (port) + anti-abuse → 6 levels → 7 achievements → 8 admin (manual grants, anomaly review, verify) → 9 deletion participant + progression APIs/UI.
**Slice B (step 23)**: 10 leaderboards. **Slice C (step 24)**: 11 quests/daily objectives/challenges.

## 15. Technical Decisions — `research.md` R1–R14.

## 16. Risks / Open Technical Questions
- **R1** OQ-60..64 use plan defaults (research); **product confirmation requested** (curve, anomaly thresholds, challenge modeling, no conversion, cap value).
- **R2** Ownership boundary of reward rules vs the Automations engine (CD-010): reward rules are economy config limited to ledger grants; confirm this reading before 019 is planned.
- **R3** Determinism for late events relies on `occurred_at`-window evaluation; strict replay equivalence is verified by `verify --replay` and may report documented, benign drifts.
- **R4** Hot-user contention (advisory lock) acceptable at community scale.
- **R5** 014 modifiers arrive later: until then only rule multipliers apply (port stub).
- **R6** Production DB-role hardening for the ledger is an operations concern (documented).

## Project Structure
```text
backend/src/portalab/{capabilities/economy, modules/gamification/{ledger,economy,rules,calculator,modifiers,antiabuse,consumers,levels,achievements,manual,anomaly,privacy,progression,verify,leaderboards,quests,api,models}} · backend/migrations/gamification/versions/
frontend/src/features/gamification/{progression,history,achievements,admin,leaderboards,quests}
```
