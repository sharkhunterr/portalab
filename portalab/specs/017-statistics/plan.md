# Implementation Plan: Statistics

**Branch**: `017-statistics` | **Date**: 2026-10-01 | **Spec**: `specs/017-statistics/spec.md`
**Roadmap**: Phase 4 step 14 *Statistics*. Builds on 007 (events, replay, `idempotent_effect`), 009 (widget bridge), 026 (formatting), 022 (`Chart`), 003/021 (permission, visibility, retention).

## Summary
Module `statistics` owns the **registry of admin-defined statistics** (closed-set declarative definitions, versioned), their **deterministic computation** as incremental projections of the event backbone, consumption controls (choose/filter/period/navigate/hide), **unlock conditions**, cross-service aggregation with honest partial/stale states, the **single authoritative provider interface** consumed by dashboard, gamification, campaigns, notifications, Wrapped, AI, recommendations and leaderboards, and Wrapped snapshots. It owns no domain data and no event store; users cannot author charts.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: `recharts` (frontend) · **Storage**: schema `stats` (definitions, buckets, members, unlocks, wrapped_*, rebuild_runs) · **Testing**: pytest real PG (replay determinism, idempotency), Vitest, Playwright + axe · **Constraints**: deterministic and replayable; cohort thresholds; locked ⇒ not computed; consumers see identical values; no secrets · **Scale**: personal/community; ≤ ~200 definitions, ≤ ~10⁷ events.

## Constitution Check — PASS
V provenance via event/source states · VI/VII permission, visibility and privacy-safe aggregation · IV event-driven, idempotent, replayable (CD-012) · IX partial/stale/unavailable states, source isolation · X/XII shared design system, accessible charts · XX no second rules engine (closed-set definitions and conditions), unlock sources owned by 013/014/015 · XIX definition versioning. No violations.

## 1. Architecture
```
007 events ─▶ per-definition consumers ─▶ stats.buckets (daily, statistics tz) + stats.members (distinct)   [idempotent_effect(stat,ver,event)]
Admin ─▶ DefinitionService (validate vs event field registry, version, activate/retire/rebuild via ReplayService)
Reader: StatisticsProvider.get(stat, subject, period, viewer)
          ├ permission (authorize) + definition permission
          ├ unlock evaluation (ports 013/014/015; locked ⇒ stop, nothing computed)
          ├ visibility/privacy (021 for other-user subjects; cohort suppression for aggregates)
          ├ bucket query (≤ maxBuckets) + period roll-up (statistics tz/first day) + trend vs previous period
          └ source states (006 health + projection watermark) ⇒ partial/stale/unavailable
Consumers: 009 widget bridge · 013 · 014 · 010 (Wrapped delivery) · 018 · 012 leaderboards
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `DefinitionService` | validate, version, activate/retire, rebuild | 007 field registry, `ReplayService` | admin API | closed set only; audited | schema/version tests |
| `PackRegistry` | built-in and plugin packs (plugin packs inactive) | capability registry | `register_definition_pack` | Admin enables | pack tests |
| `ProjectionConsumers` | fold events into buckets/members | 007 consumer API | `@consumer` per event type set | idempotent; replay-safe; no external effect | idempotency + replay tests |
| `PeriodResolver` | deterministic period boundaries, roll-ups | 020 settings | `resolve(period)` | single stats tz/first day | boundary/DST tests |
| `UnlockEvaluator` | evaluate condition trees, persist permanent unlocks, emit `statistics.unlocked` | ports 013/014/015 | `evaluate(user, defn)` | closed set; locked ⇒ no compute | matrix tests |
| `PrivacyGuard` | cohort threshold/suppression, subject visibility | 021 | `apply()` | suppress small cells | k-threshold tests |
| `StatisticsProvider` | authoritative read path | all above, 006 | contract | permission-bounded; deterministic | contract tests |
| `TrendCalculator` | delta/direction vs previous period | provider | internal | same period length/boundaries | unit |
| `WrappedService` | definitions, generation job, immutable snapshots, delivery | 010 port, jobs | API/job | per-user snapshots; preferences honored | snapshot tests |
| Frontend page/chart/card/Wrapped | present statistics | 022, 009 | components | accessible alternatives; states | a11y tests |
| Admin & health | status, lag, rebuild runs | 025 | `/admin/statistics/status` | audited | API tests |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/statistics-contracts.md`

## 5. Events
Consumed: event types referenced by active definitions (idempotent via `ctx.idempotent_effect`, ordering by `occurred_at` irrelevant for additive measures), `admin.config_changed` (tz/first-day ⇒ flag rebuild required), `plugin.state_changed` (pack activation). Produced: `statistics.definition_changed`, `statistics.unlocked`, `statistics.wrapped_generated` (dedup keys per data-model). Late/out-of-order events land in their `occurred_at` bucket (FR-022); replays never re-emit external effects.

## 6. Permissions & Security
Read: `statistics.read` + definition `required_permission`; subject ≠ self only when visibility allows (021); admin: `statistics.manage` (audited; rebuild/activate sensitive with `ConfirmationService`). AI and automations call the provider as the acting principal (CD-003). Exports/Wrapped contain no secrets; member hashes salted with a server secret (`core.secrets`).

## 7. Configuration — `data-model.md` settings.

## 8. External Integrations — none (unlock sources through ports; delivery through 010 port).

## 9. Error Handling & Resilience
Source down ⇒ `partial`/`stale` with `as_of` · consumer lag ⇒ `stale` beyond threshold · unlock port unavailable ⇒ treat as locked (fail closed) with `unavailable` hint · too many buckets ⇒ 422 with narrower-range hint · invalid definition ⇒ rejected at activation · projection failure ⇒ 007 quarantine/retry, stat shows `stale` · cohort too small ⇒ `insufficient_data` · wrapped generation failure per user ⇒ retried, others unaffected.

## 10. Observability
Projection lag per definition, bucket write rate, provider latency, locked/insufficient ratios, rebuild durations; registers `statistics` with 025 (functional: freshness of hot definitions within threshold).

## 11. Testing Strategy
Unit: definition schema (closed set, unknown field rejection), period resolver (DST, week start, month ends), trend, unlock tree, cohort suppression. Integration (real PG): projection correctness vs oracle SQL over seeded events; duplicate/out-of-order events; replay equals live; forward_only vs rebuild; cross-service partial/stale with health stub; permission/privacy per viewer; locked not computed (query-count assertion); Wrapped snapshot immutability. Contract: provider consistency across consumers (same inputs ⇒ same output). Frontend: chart a11y (table alt, summary), hide only hideable, period/filter changes. E2E: dashboard widget parity with page values.

## 12. Migration / Versioning
Alembic revision for `stats`; definitions append-only versions; `schema_version` upgraders; statistics tz change = audited rebuild job; partitioning of `buckets` by year when volume requires (not initially).

## 13. Cross-Spec Dependencies
Prerequisites: 001, 003, 007 (aggregatable field registry, consumer API, replay), 020 (settings), 021 (visibility/retention), 009 (widget registry), 022 (`Chart`), 026 (formatting). Ports implemented later by 013/014/015/010 (stubs until then; unlock conditions using them stay inactive). Domain definition packs delivered by owning specs (Media 024, Community 012, Gamification 013, …); starter packs here: users/activity (002 events) and services (006 events). Exposes provider to 009, 013, 014, 010, 018, 012.

## 14. Implementation Phases
1 Definition schema + registry + field registry hooks → 2 Projection consumers + buckets/members + replay → 3 Period resolver + provider core + REST → 4 Privacy guard + permission integration → 5 Unlock evaluator → 6 Frontend page/charts/hide → 7 Cross-service sources/partial/stale → 8 Trends + dashboard widget bridge → 9 Wrapped → 10 Admin/observability/hardening + starter packs.

## 15. Technical Decisions — `research.md` R1–R12.

## 16. Risks / Open Technical Questions
- **R1** OQ-80..84 use plan defaults (research); **product confirmation requested** (authorship, time-zone rule, cohort size, re-lock, freshness).
- **R2** Exact distinct counts via `members` grow with scale; revisit with HyperLogLog only if measured (documented limit).
- **R3** Domain coverage (FR-009) completes as domain specs add packs and event field registrations; starter set limited now.
- **R4** Statistics-timezone change requires a full rebuild; operationally rare, audited.
- **R5** Percentile/median measures excluded from the closed set in v1 (flagged).
- **R6** Cross-service dedup quality depends on 005/007 canonical references (CD-015).

## Project Structure
```text
backend/src/portalab/{capabilities/statistics, modules/statistics/{definitions,packs,projection,period,unlock,privacy,provider,trend,wrapped,api,models}} · backend/migrations/stats/versions/
frontend/src/features/statistics/{StatisticsPage,charts,cards,wrapped,preferences} · backend/definitions/packs/{users,services}.json
```
