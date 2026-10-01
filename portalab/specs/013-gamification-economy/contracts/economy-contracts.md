# Contracts — Gamification & Economy

## Python capability `capabilities/economy`
- `EconomyService.spend(user, amount, *, reason, source_kind, source_ref, idempotency_key) -> Transaction` (atomic, non-negative, raises `InsufficientCoins`) · `refund(transaction_id, *, reason, idempotency_key)` · `balance(user, value)` · `history(user, filters, cursor)`; used by Marketplace (015) and Community funding via 015.
- `RewardService.grant_manual(actor, user, value, amount, reason, ...)` (bounded admin action; callable by 019 as an action under the author's permissions) and `grant_contribution(user, amount, source_ref, idempotency_key)` (used by 016 conversion; subject to anti-abuse).
- `ProgressionReader` (for 017/015/012): `level(user)`, `xp/contribution/coins(user)`, `has_achievement(user, key)`, `progress(user)`.
- `ModifierProvider` (implemented by 014): `modifiers_for(user, event, value, at) -> list[Modifier{source_ref, factor}]`.
- Participants: 021/002 deletion saga `erasure_participant` (destroy Coins) and export contributor.
- Event field registry hooks: reward rules may only reference event attributes marked `rewardable` in 007's type registry.

## HTTP (`/api/v1`)
| Path | Permission | Slice |
|---|---|---|
| GET `/me/progression` | self | A |
| GET `/users/{id}/progression` | `gamification.read` + subject visibility (021) | A |
| GET `/me/economy/transactions?value&cursor` | self | A |
| GET `/me/achievements` · GET `/achievements/catalog` | self / `gamification.read` | A |
| GET/POST `/admin/gamification/rules[/{key}]` · POST `…/{key}/publish|retire|simulate` | `economy.rules.manage` (sensitive, audited, versioned) | A |
| POST `/admin/gamification/manual-grants` | `economy.grant` (sensitive, audited; ≥ threshold needs confirmation) | A |
| GET/PUT `/admin/gamification/level-curve` · achievements CRUD | `economy.rules.manage` | A |
| GET `/admin/economy/transactions?user&…` · GET `/admin/economy/verify` | `economy.audit` (audited access) | A |
| GET `/admin/economy/anomalies` · POST `…/{id}/approve|reject|confirm-abuse` | `economy.anomaly.review` (audited) | A |
| GET `/leaderboards/{metric}?period` · GET `/me/leaderboard-position` | `gamification.read`; visibility/opt-out | B |
| GET `/me/quests` · GET `/quests/catalog` · admin CRUD | self / `gamification.read` / `economy.rules.manage` | C |
Problem codes: `economy.insufficient_coins`, `economy.rule_invalid`, `economy.duplicate`, `economy.forbidden_conversion`.

## Frontend
Progression card/page (XP + level, Contribution, Coins shown separately), transaction history, achievements grid (locked/hidden/unlocked), admin rule editor with simulation, manual grant form with confirmation, anomaly review queue; (B) leaderboard views; (C) quests/daily objectives panel; dashboard widgets `gamification.progress|daily_objectives`.

## Integrations provided
Notification categories `gamification.reward|level_up|achievement|quest` (010 `send`, coalesced) · statistics pack `gamification` (017) · AI tool `progression.get` (018) · event types registered with 007.
