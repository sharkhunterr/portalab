---
description: "Task list — Gamification & Economy (spec 013)"
---

# Tasks: Gamification & Economy

**Input**: `specs/013-gamification-economy/` · **Branch**: `013-gamification-economy` · **Roadmap**: **Slice A** (Phases 1–11) = step 19; **Slice B** (Phase 12) = step 23; **Slice C** (Phase 13) = step 24 · **Tests**: included.
Abbrev: **`GM/`** = `backend/src/portalab/modules/gamification`, **`CAP/`** = `backend/src/portalab/capabilities/economy`, **`FG/`** = `frontend/src/features/gamification`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel/jobs/outbox · `D-002/003` principal/authz/`ConfirmationService`/`AuditSink`, 002 deletion saga hooks · `D-007` events (consumers, `rewardable` attribute registry) · `D-010` `send`/categories · `D-017` stats (`statistic_at_least` provider, pack) · `D-020` settings · `D-021` visibility/retention · `D-022` UI. Stubbed until their specs: `ModifierProvider` (014), spend callers (015), `grant_contribution` callers (016), presentation (012).

## Phase 1: Setup
- [X] T001 Create `CAP/__init__.py`, `GM/{ledger,economy,rules,calculator,modifiers,antiabuse,consumers,levels,achievements,manual,anomaly,privacy,progression,verify,leaderboards,quests,api,models}/__init__.py`, `backend/migrations/gamification/versions/`, `FG/{progression,history,achievements,admin,leaderboards,quests}/`, `backend/tests/{unit,integration,contract,security}/gamification/`, `frontend/tests/{unit,e2e}/gamification/`
- [X] T002 [P] Declare settings (`economy.maxTotalBoost`, `economy.manualGrantConfirmThreshold`, `economy.anomaly.maxGrantsPerHour|maxCoinsPerDay`, `economy.timezone`, `economy.leaderboards.*`, `economy.withheldRetentionDays`, `economy.levelCurve.active`) in `GM/settings.py`; permissions `gamification.read` (default grant), `gamification.manage`, `rewards.grant`, `economy.manage` (Admin, sensitive, audited; 003 catalog names) in `GM/permissions.py`
- [X] T003 [P] Register datum class `progression` with 021 visibility, retention targets (withheld, usage windows), notification categories `gamification.reward|level_up|achievement|quest` (010), and event types with `rewardable` attribute declarations in the 007 registry

## Phase 2: Foundational — schema, ledger, level curve (Slice A)
### Tests first
- [X] T004 [P] Write `backend/tests/integration/gamification/test_ledger_immutability.py`: UPDATE/DELETE on `transactions` rejected by trigger (incl. as app role); unique `idempotency_key`; `reverses_transaction_id` integrity; balance `CHECK amount >= 0`; value enum restricted to xp/contribution/coins (no conversion kind)
- [X] T005 [P] Write `backend/tests/integration/gamification/test_balance_consistency.py`: balance equals Σ ledger after random operation sequences (property test); concurrent spends cannot overdraw; failure injection mid-transaction leaves ledger+balance+outbox consistent
- [X] T006 [P] Write `backend/tests/unit/gamification/test_level_curve.py`: monotonic thresholds, boundary crossing, multi-level jumps, curve version change recomputes cached level without emitting level-ups
### Implementation
- [X] T007 Implement `GM/models` + Alembic revision (ledger, balances, withheld, reward_rules, level_curves, achievements, counters, usage_windows, user_achievements, anomaly_flags) with immutability triggers via 001 helper
- [X] T008 Implement `GM/ledger/writer.py` (`LedgerWriter.record`: insert + balance guard + counters + level crossing + outbox in one TX) and `GM/levels/service.py` (versioned curve, derive level)

## Phase 3: US6 — Traceable, append-only economy transactions (P1) 🎯 MVP (Slice A)
**Independent test**: grants, spends, refunds, corrections and destruction are all new rows; balances derive from the ledger.
- [X] T009 [P] [US6] Write `backend/tests/integration/gamification/test_economy_service.py`: spend decreases balance atomically; overspend ⇒ `economy.insufficient_coins` with no side effects; refund creates new transaction referencing the original; idempotency key replays return the same transaction; Coins cannot be created from money (no such path); history cursor pagination owner-only
- [X] T010 [US6] Implement `GM/economy/service.py` (`EconomyService.spend/refund/balance/history`) registered as capability for 015/012, and routers `GET /me/economy/transactions`, `GET /me/progression`
- [X] T011 [US6] Implement `GM/verify/verifier.py` + CLI `portalab economy verify` and admin `GET /admin/economy/verify` (`economy.manage`): recompute balances from ledger, detect drift

## Phase 4: US7 — Administrative rewards and rule versioning (P1)
- [X] T012 [P] [US7] Write `backend/tests/unit/gamification/test_rule_versions.py`: version in force chosen by event `occurred_at`; new version never edits old; transactions keep `rule_key/version`; closed schema validation (unknown attributes/fields rejected); simulation performs no writes
- [X] T013 [P] [US7] Write `backend/tests/integration/gamification/test_manual_rewards.py`: requires `rewards.grant`; reason mandatory; marked manual with actor; audited; ≥ threshold requires confirmation; AI/automation callers bounded by acting principal; rule publish/retire audited and sensitive
- [X] T014 [US7] Implement `GM/rules/{store,resolver,simulate}.py`, routers `GET/POST /admin/gamification/rules[/{key}]`, `POST …/publish|retire|simulate`, `GM/manual/service.py` + `POST /admin/gamification/manual-grants`, and `FG/admin/{RuleEditor,SimulationPanel,ManualGrant}.tsx`

## Phase 5: US1 — Earn XP, Contribution, Coins deterministically from events (P1)
- [X] T015 [P] [US1] Write `backend/tests/integration/gamification/test_reward_consumer.py`: event → grants per rule version (fixed and per-unit formulas); duplicate and late delivery never double-grant; three values granted separately with transaction records (actor/source, amount, reason, rule version, timestamp); per-user serialization under concurrent events; late event evaluated at its own windows
- [X] T016 [US1] Implement `GM/calculator/calculator.py` and `GM/consumers/reward.py` (dynamic consumers per active rule event types, advisory lock per user, `idempotency_key=(event_id, rule_key)`), emitting `reward.granted`
- [X] T017 [US1] Implement notifications for rewards/level-ups via 010 `send` with coalescing-friendly dedup keys in `GM/notify.py` (FR-033: only through the notification engine)

## Phase 6: US4 — Multipliers and campaign modifiers (P1)
- [X] T018 [P] [US4] Write `backend/tests/unit/gamification/test_modifiers.py`: x2·x1.5 = x3 multiplicative (CD-024); cap `economy.maxTotalBoost` applied and recorded; deterministic order; modifier validity by `occurred_at`; provider unavailable ⇒ rule multiplier only with flag, base grant unaffected; modifiers never bypass anti-abuse
- [X] T019 [US4] Implement `GM/modifiers/combiner.py` and the `ModifierProvider` port stub (`CAP/modifiers.py`), integrating into the grant pipeline after base calculation and before cap-aware finalization

## Phase 7: US5 — Anti-abuse: cooldown, caps, diminishing returns, anomalies (P1)
- [X] T020 [P] [US5] Write `backend/tests/unit/gamification/test_antiabuse.py`: cooldown withholds/reduces repeats; per-period caps (rule and value level) trim to remaining cap; diminishing curves (geometric/steps); windows keyed by `occurred_at`; applied equally to XP/Contribution/Coins; multipliers cannot exceed caps
- [X] T021 [P] [US5] Write `backend/tests/integration/gamification/test_anomaly_review.py`: threshold breach ⇒ withheld + `anomaly_flagged` + flag row; admin approve ⇒ transaction created; reject ⇒ dropped with reason; confirm-abuse ⇒ correction transactions (never edits); every decision audited; no silent drops
- [X] T022 [US5] Implement `GM/antiabuse/{guards,windows}.py`, `GM/anomaly/service.py`, routers `GET /admin/economy/anomalies`, `POST …/approve|reject|confirm-abuse`, optional escalation to an Incident via 016 `support.incidents.create` (`economy.anomaly.escalateToIncident`), and `FG/admin/AnomalyQueue.tsx`

## Phase 8: US2 — Levels derived from XP (P1)
- [X] T023 [P] [US2] Write `backend/tests/integration/gamification/test_levels.py`: crossing emits one `user.level_up` (dedup `(user, level)`); level never spendable or stored as balance; reconstruction from ledger yields same level; display separate from other values
- [X] T024 [US2] Wire level-up detection into `LedgerWriter`, admin `GET/PUT /admin/gamification/level-curve`, and `FG/progression/ProgressionCard.tsx` (XP+level, Contribution, Coins shown separately)

## Phase 9: US3a — Achievements (P1)
- [X] T025 [P] [US3] Write `backend/tests/integration/gamification/test_achievements.py`: event-count/level/value/statistic criteria; unlock exactly once (unique constraint, concurrent events); reward through ledger with `source_kind=achievement`; `achievement.unlocked` emitted; hidden achievements not revealed in catalog until unlocked
- [X] T026 [US3] Implement `GM/achievements/evaluator.py` (counters, 017 `statistic_at_least` via port, definitions versioned), routers `GET /me/achievements`, `GET /achievements/catalog`, admin CRUD, and `FG/achievements/Grid.tsx` (locked/hidden/unlocked with text labels)

## Phase 10: US8 — Final account deletion destroys remaining Coins (P1)
- [X] T027 [P] [US8] Write `backend/tests/integration/gamification/test_deletion.py`: saga step records `destruction` transaction(s) for remaining Coins (balance → 0), purges balances/counters/progress, keeps ledger rows bound to the tombstoned user id with no free text, excludes user from leaderboards; idempotent on retry; no refund/transfer path; export contributor lists the user's own transactions
- [X] T028 [US8] Implement `GM/privacy/participant.py` (erasure + export participants for 002/021) and visibility integration for `GET /users/{id}/progression`

## Phase 11: Slice A closure — progression APIs, observability, integrations
- [X] T029 [P] [US9] Write `backend/tests/security/gamification/test_progression_privacy.py`: another user's progression only per 021 visibility; ledger views owner/`economy.manage` only (audited); no private data exposed by permission alone; no PII in events
- [X] T030 [P] Register `ProgressionReader` for 017/015/012, statistics pack `backend/definitions/packs/gamification.json` (017), dashboard widgets `gamification.progress` (009), AI tool `progression.get` (018), `GM/observability.py` (grants/s, withheld by reason, drift, consumer lag; 025 registration)
- [X] T031 [P] Add `/me/progression`, `/me/economy/*`, `/me/achievements`, `/achievements/*`, `/admin/gamification/*`, `/admin/economy/*` routes to the permission-matrix test, regenerate OpenAPI client, write `docs/economy.md` (values, ledger rules, rule authoring, modifier cap, anti-abuse, verification)

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [X] T032 Add Coin **reservations** for Marketplace funding (CD-008): table `gamification.reservations`, ledger kinds `reserve|reserve_release|reserve_consume`, `EconomyService.reserve/release/consume`, and an optional caller unit of work on `spend/refund/reserve` for atomic multi-module transactions; test `backend/tests/integration/gamification/test_reservations.py` (available balance, never negative, idempotent, final deletion destroys reservations) (F3)
- [X] T033 Implement `RewardService.grant_via_automation(...)` (anti-abuse-bound, `source_kind=automation`, author-bounded) and register the 019 action types `award.xp|coins|contribution` and `reward.unlock`; test `backend/tests/contract/gamification/test_automation_awards.py` (F4)
- [X] T034 Add a `DefinitionSource` extension point so achievement/quest evaluators also read campaign-scoped definitions from 014 `CampaignContentProvider` while the campaign is active; test `backend/tests/unit/gamification/test_definition_sources.py` (F5)

- [X] T035 Run `specs/013-gamification-economy/quickstart.md` steps 1–7 end-to-end; record deviations and open product confirmations (OQ-60..64 defaults, R2 boundary)

## Phase 12: Slice B — Leaderboards (step 23) — US9
- [X] T036 [P] [US9] Write `backend/tests/integration/gamification/test_leaderboards.py`: metrics (xp, level, contribution, achievements; Coins only when enabled); periods all-time/month/week from ledger windows; visibility/opt-out (021 levels: Public/Community/Leaderboards-only/Private) honored; viewer always sees own rank; ties deterministic; tombstoned users excluded; no private data exposed
- [X] T037 [US9] Implement `GM/leaderboards/{service,job}.py` (snapshots every `refreshMinutes`), routers `GET /leaderboards/{metric}`, `GET /me/leaderboard-position`, and `FG/leaderboards/Leaderboard.tsx` (accessible table, own-rank highlight, states)

## Phase 13: Slice C — Quests, daily objectives, challenges (step 24) — US3b
- [ ] T038 [P] [US3] Write `backend/tests/integration/gamification/test_quests.py`: quest/daily/challenge criteria over counters; period keys in `economy.timezone` incl. DST; daily reset; completion once per `(user, quest, period)`; reward auto-granted via ledger; `quest.completed` emitted; campaign-linked quests respect campaign window (014 stub); duplicate/late events safe
- [ ] T039 [US3] Implement `GM/quests/{evaluator,service}.py`, routers `GET /me/quests`, `GET /quests/catalog`, admin CRUD (`gamification.manage`), widget `gamification.daily_objectives` (009), and `FG/quests/QuestPanel.tsx`
- [ ] T040 Run quests/leaderboard quickstart extensions; update `docs/economy.md`; record Slice B/C completion

## Dependencies & Order
**Slice A**: Setup → Foundational → US6 (ledger/service) → US7 (rules/versioning/manual) → US1 (consumer) → US4 → US5 → US2 → US3a → US8 → closure. **Slice B** needs ledger + visibility (021). **Slice C** needs counters + economy tz + (optionally) 014 campaigns.
**Parallel examples**: T004/T005/T006 · T012/T013 · T018 with T020 · T029/T030/T031.
**MVP (Slice A)**: Phases 1–5 (ledger, economy service, versioned rules, event-driven rewards).

## Format validation
40 tasks, all checkbox + ID + path; story labels only on story phases.
