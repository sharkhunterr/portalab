# Gamification & economy (spec 013 — Slice A)

Three **separate values**, never converted into one another and never bought with money:

| Value | Earned from | Spent | Notes |
|---|---|---|---|
| **XP** | reward rules, achievements, manual/automation grants | never | the **Level** is derived from total XP |
| **Contribution** | rules, recognised contributions (016 conversions), grants | never | |
| **Coins** | rules, achievements, grants | Marketplace (015), Community funding | destroyed at final account deletion |

## The ledger

`gamification.transactions` is append-only (database triggers reject `UPDATE`, `DELETE`, `TRUNCATE`). Every
change is a new row: `grant`, `manual`, `spend`, `refund` (references the spend), `correction` (references
the corrected grant), `destruction`, and for funding `reserve` / `reserve_release` / `reserve_consume`.
Each row stores the value, signed delta, source, rule key and version, trigger event, base amount,
multiplier, applied modifiers and guard effects. `idempotency_key` is unique: replays return the original
transaction.

`gamification.balances` is a cache updated **in the same transaction** (`amount >= 0`; debits are guarded,
an overdraft raises `economy.insufficient_coins`). Writes are serialized per user with an advisory lock.
Verification recomputes balances from the ledger: `portalab economy verify` (exit 4 on drift) or
`GET /api/v1/admin/economy/verify`.

## Spending (other modules)

Use the `economy.service` capability — never the tables:

```python
economy = capabilities.system_providers("economy.service")[0].provider
tx = await economy.spend(user, 30, reason="Poster", source_kind="marketplace",
                         source_ref="item:42", idempotency_key=f"order:{order_id}", session=uow.session)
await economy.refund(tx.id, reason="cancelled", idempotency_key=f"refund:{order_id}")
reservation = await economy.reserve(user, 100, source_ref="project:7", idempotency_key=f"pledge:{pledge_id}")
await economy.release(reservation.id, reason="project failed")   # or consume(reservation.id)
```

Passing `session` makes the economy write part of the caller's transaction (atomic multi-module
operations). Reserved Coins leave the spendable balance until released or consumed.

## Reward rules

Rules are economy configuration, not a generic rules engine (generic WHEN/IF/THEN belongs to Automations
019). A rule is a closed record:

```json
{
  "event_type": "media.playback_finished",
  "predicate": [{"field": "media_type", "op": "in", "value": ["movie", "episode"]}],
  "grants": [{"value": "xp", "per_unit": {"field": "minutes", "factor": 0.5, "max": 100}},
             {"value": "coins", "amount": 5}],
  "multiplier": 1.0,
  "limits": {"cooldown_seconds": 60,
             "caps": [{"period": "day", "max_amount": 200, "value": "xp"}],
             "diminishing": {"kind": "geometric", "period": "day", "factor": 0.8}}
}
```

* predicates and `per_unit` fields may only use attributes the event type declares `rewardable` (007);
* every save creates a **draft version**; publishing makes it effective *now*; older versions are never
  edited; the version **in force at the event's `occurred_at`** decides (late events use their own time);
  retiring stops the rule for later events;
* `POST /admin/gamification/rules/{key}/simulate` dry-runs a definition against sample events (no write);
* the consumer `gamification.rewards` marks each event applied once (redeliveries are no-ops) and writes
  grants with idempotency `rule:<event>:<rule>:<value>`.

## Modifiers and anti-abuse

`final = base · Π(rule multiplier, campaign modifiers)`, the product capped at `economy.maxTotalBoost`
(default 5) — campaign modifiers come from 014 through `economy.modifiers`; if that provider fails only the
rule multiplier applies (recorded `modifiers_unavailable`). Anti-abuse applies **after** multipliers and to
the three values alike: cooldown, diminishing returns, per-period caps (windows keyed by `occurred_at` in
`economy.timezone`), then the anomaly guard (`economy.anomaly.maxGrantsPerHour`,
`economy.anomaly.maxCoinsPerDay`). Withheld grants are recorded in `gamification.withheld`; anomalies open
a flag reviewed by `economy.manage`: approve (grants recorded), reject (dropped with a reason) or
confirm-abuse (also reverses the window's rule grants with correction transactions). Every decision is
audited; optional incident escalation with `economy.anomaly.escalateToIncident`.

## Levels and achievements

Level curve (versioned): level 1 at 0 XP, then `round(base · (n − 1)^exponent)` (default base 100,
exponent 1.5). Crossing a threshold emits one `user.level_up`; publishing a new curve recomputes cached
levels silently. Achievements are versioned definitions with closed criteria (`event_count`,
`level_at_least`, `value_at_least`, `statistic_at_least`) and optional rewards; they unlock once per user
(unique constraint) and emit `achievement.unlocked`. Hidden achievements stay hidden in the catalog until
unlocked. Campaign-scoped achievements come from `economy.definition_sources` providers while active.

## Grants outside rules

* Manual (`rewards.grant`): reason mandatory, marked `manual` with the administrator, audited; amounts at or
  above `economy.manualGrantConfirmThreshold` need a confirmation (`authz.confirmation_required`).
* Automations (019): actions `award.xp|coins|contribution` and `reward.unlock`, bounded by the author's
  permissions, idempotent, anomaly-guarded.
* Contributions (016): `gamification.grant_contribution` grants `economy.contribution.amount` once per source.

## Leaderboards (slice B)

Metrics `xp`, `level`, `contribution`, `achievements` (`economy.leaderboards.metrics`), plus `coins` only when
`economy.leaderboards.includeCoins` is on. Periods: `all` (balances), `month` and `week` (what was *earned*
in the window — grants, manual grants and corrections — with period starts in `economy.timezone`);
`level` is all-time only. A job materializes `gamification.leaderboard_snapshots` every
`economy.leaderboards.refreshMinutes` (checked every 5 minutes; a missing or out-of-period snapshot is
computed on first read). Only active accounts are ranked; ties go to the earliest attainment, then the id.

Visibility is applied **at read time** on the 021 `progression` datum with the *leaderboard* surface:
Public, Community and Leaderboards-only members appear, Private members do not — for Admins too. Ranks
count only the members the viewer may see (no gap reveals a hidden member) and the viewer always gets their
own position. Erasure drops the user from every snapshot at once.

`GET /api/v1/leaderboards` (offered metrics) · `GET /api/v1/leaderboards/{metric}?period=all|month|week` ·
`GET /api/v1/me/leaderboard-position?metric&period`. Presentation surfaces (Community 012) use the
`economy.leaderboards` capability (`LeaderboardReader.board(viewer, metric, period)`).

## Quests, daily objectives and challenges (slice C)

```json
{"kind": "daily", "label": "Listen today", "period": "day",
 "steps": [{"kind": "event_count", "event_type": "media.played", "count": 1}],
 "rewards": [{"value": "coins", "amount": 10}]}
```

* `quest` — steps over event counts, once (`period: none`) or each `week`;
* `daily` — a daily objective (`period: day`, or `week` for weekly objectives), reset each period;
* `challenge` — a **time-boxed quest** (OQ-62 default): a `window` (`starts_at`, `ends_at`) is required and
  only events inside it count.

Steps reuse the achievements' closed `event_count` criterion (with its `filter`). Periods are computed from
the event's `occurred_at` in `economy.timezone` (local calendar days and ISO weeks — DST-safe), so replays
and late events land in the period they happened in. Completion happens **once per (user, quest,
period)**; rewards go through the ledger (`source_kind` = `quest|daily|challenge`, idempotency
`quest:<user>:<key>:<period>:<value>`) and `quest.completed` (`quest`, `kind`, `period`; automatable,
community visibility) is emitted with the same dedup. Campaign quests come from 014 (`DefinitionSource`
offering `quests(at)`) and count only while the campaign is active.

`GET /api/v1/me/quests` (own progress) · `GET /api/v1/quests/catalog` (`gamification.read`) ·
`GET|PUT|DELETE /api/v1/admin/gamification/quests[/{key}]` (`gamification.manage`, audited). Widget
`gamification.daily_objectives`. Presentation surfaces read `economy.catalog` (`achievements_of`,
`unlocked_of`, `quests_of`).

## Privacy

Progression is the datum class `progression` (default private; the owner chooses its visibility, 021):
`GET /users/{id}/progression` answers 404 unless visible — a permission is not consent. Ledger views are
owner-only or `economy.manage` (audited). Final deletion releases and destroys reservations, records
`destruction` for the remaining Coins (and zeroes XP and Contribution the same way so the ledger still
balances), removes balances, counters and progress; ledger rows stay bound to the tombstoned user without
free text. Events carry ids and numbers only.

## Recorded deviations (T035)

* `gamification.applied_events` (not in the data model) records processed events so counters and grants
  happen exactly once; markers are pruned after 180 days.
* `gamification.progression_preferences` stores the owner's visibility level for `progression`.
* Rule simulation also accepts an unsaved draft definition.
* Final deletion zeroes XP and Contribution with `destruction` rows too (balance cache removed, ledger
  consistent).
* Leaderboards (Slice B) and quests/daily objectives/challenges (Slice C) come at roadmap steps 23 and 24.
