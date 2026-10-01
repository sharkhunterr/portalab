# Data Model — Gamification & Economy (schema `gamification`)

FKs only intra-module or to `identity.users(id)`; event/source references are opaque.

## Ledger & balances
- **gamification.transactions** (append-only; triggers forbid UPDATE/DELETE): `id` UUIDv7 · `seq` bigserial · `user_id` FK · `value` (`xp|contribution|coins`) · `delta` bigint · `kind` (`grant|spend|refund|correction|destruction|manual`) · `source_kind` (`reward_rule|achievement|quest|daily|challenge|manual|marketplace|community_funding|system`) · `source_ref` · `rule_key` null · `rule_version` null · `trigger_event_id` null · `idempotency_key` unique · `base_amount` · `multiplier` numeric(8,4) · `modifiers` jsonb (`[{source_ref, factor}]`, capped flag) · `guards` jsonb (cooldown/cap/diminishing effects) · `actor_user_id` FK null (admin for manual) · `reason` text null · `reverses_transaction_id` FK self null · `occurred_at` · `recorded_at`. Indexes `(user_id, value, seq)`, `(source_kind, source_ref)`.
- **gamification.balances** (derived cache): `user_id` FK · `value` · `amount` bigint CHECK `amount >= 0` · `last_seq` · `level` int null (xp only) · `curve_version` · PK `(user_id, value)`.
- **gamification.withheld** (bounded retention): `id` · `user_id` · `value` · `proposed_delta` · `reason` (`cooldown|cap|anomaly`) · `rule_key/version` · `trigger_event_id` · `status` (`flagged|approved|rejected|dropped`) · `reviewed_by` · `occurred_at`.

- **gamification.reservations**: `id` · `user_id` FK · `amount` · `source_kind` (`community_funding`) · `source_ref` · `status` (`active|released|consumed|destroyed`) · `reserve_tx_id` · `resolution_tx_id` null · `created_at` · `resolved_at` null. Ledger kinds add `reserve|reserve_release|reserve_consume`; available balance = balance − active reservations (never negative). Final deletion releases then destroys all reservations (CD-005, decided 2026-10-01).

## Definitions (versioned; effective by instant)
- **gamification.reward_rules**: `key` · `version` · `status` (`draft|active|retired`) · `effective_from` timestamptz · `definition` jsonb (event_type, predicate, grants[], multiplier, limits{cooldown_s, caps[], diminishing}) · `created_by` · `created_at`. PK `(key, version)`; append-only versions.
- **gamification.level_curves**: `version` · `effective_from` · `definition` jsonb (formula/parameters) · PK `version`.
- **gamification.achievements**: `key` · `version` · `effective_from` · `definition` jsonb (criteria, reward grants, visibility hidden/visible, icon/label keys) · PK `(key, version)`.
- **gamification.quests** (slice C): `key` · `version` · `kind` (`quest|daily|challenge`) · `definition` jsonb (criteria steps, period `none|day|week`, window start/end, `campaign_ref` null, reward grants, repeatable) · `effective_from`.

## Progress state
- **gamification.counters**: `user_id` FK · `counter_key` · `value` bigint · `updated_at` · PK both (event-count criteria).
- **gamification.usage_windows**: `user_id` FK · `rule_key` · `window_kind` · `window_start` · `count` · `amount` · PK all (cooldown/cap/diminishing).
- **gamification.user_achievements**: `user_id` FK · `achievement_key` · `version` · `unlocked_at` · `transaction_ids` · unique `(user_id, achievement_key)`.
- **gamification.quest_progress** (slice C): `user_id` FK · `quest_key` · `period_key` · `progress` jsonb · `completed_at` null · PK `(user_id, quest_key, period_key)`.
- **gamification.anomaly_flags**: `id` · `user_id` FK · `kind` · `evidence` jsonb (counts/thresholds, no content) · `status` (`open|dismissed|confirmed`) · `reviewed_by` · timestamps.
- **gamification.leaderboard_snapshots** (slice B): `metric` · `period` · `computed_at` · `entries` jsonb (rank, user_id, score) · PK `(metric, period)`.

## Settings (declared into 020)
`economy.maxTotalBoost` (default 5.0), `economy.manualGrantConfirmThreshold`, `economy.anomaly.maxGrantsPerHour|maxCoinsPerDay`, `economy.timezone` (defaults to `i18n.defaultTimeZone`), `economy.leaderboards.metrics|refreshMinutes|includeCoins`, `economy.withheldRetentionDays`, `economy.levelCurve.active`. User: visibility of progression via 021 datum `progression`.

## Events (via 007; no PII)
Produced: `reward.granted` (dedup `idempotency_key`), `user.level_up` (dedup `(user_id, level)`), `achievement.unlocked` (dedup `(user_id, achievement)`), `quest.completed` (dedup `(user_id, quest, period)`), `economy.coins_spent|refunded|destroyed`, `economy.anomaly_flagged`, `economy.rule_published`. Consumed: any event type referenced by active rules/achievements/quests; `campaign.*` (modifier windows via port), erasure participant call.

## Privacy / retention
Ledger rows reference `identity.users(id)` (tombstone-safe) and contain no free text; balances/counters/progress deleted at final deletion; ledger retained anonymized per 021; withheld entries pruned by retention.
