# Implementation Plan: Events / Campaigns

**Branch**: `014-campaigns` | **Date**: 2026-10-01 | **Spec**: `specs/014-campaigns/spec.md`
**Roadmap**: Phase 6 step 20 *Campaigns / Events*. Builds on 013 (`ModifierProvider`, ledger), 026 (wall-clock/DST), 022 (themes), 011 (calendar source), 010/019 (announcements), 007, 020.

## Summary
Module `campaigns` owns the **time-bound, themed contextualization** (Halloween): definition with schedule/recurrence (wall-clock in the campaign time zone), manual activation with defined precedence, a **closed catalog of conditions** (media kind, genre, title, activity, audience), **modifiers supplied to Gamification** (which owns multiplicative combination with cap and anti-abuse), campaign-scoped achievements/quests exposed to Gamification, a theme overlay (presentation only), history and versioning. The authoritative activity record is an **append-only activation log with an exclusion constraint**, so eligibility is always decided at the occurrence's `occurred_at`. Configurable announcements are Automations (019) rules; Campaigns emits lifecycle events.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: none (PostgreSQL `btree_gist` extension for the exclusion constraint) · **Storage**: schema `campaigns` · **Testing**: pytest real PG with fake clock, property tests for schedule/DST, contract tests against the real 013 consumer, Vitest, Playwright · **Constraints**: no reward granting here, no second rule engine, history never rewritten, graceful degradation when attribute providers are down · **Scale**: tens of campaigns.

## Constitution Check — PASS
I/CD-009 Campaign vs Domain Event · II/XX Gamification owns granting/combination (CD-024), Automations own configurable communications (CD-010), theming engine in 022 · IV events + `occurred_at` eligibility · V versioned definitions/provenance · IX provider failure ⇒ no false grants · XI presentation-only theme · XII accessibility prefs win · XIII audited sensitive actions. No violations.

## 1. Architecture
```
Admin ─▶ DefinitionService (closed schema, versions append-only, effective_from) ─▶ OccurrencePlanner (recurrence in tz via 026) ─▶ occurrences
Scheduler jobs (run_at boundaries + per-minute reconciler) ─▶ IntervalManager ─▶ open_intervals / activation_log (EXCLUDE overlap) ─▶ events campaign.started|ending_soon|ended
Manual activate/deactivate ─▶ OverrideService (precedence R4, reason, confirmation, audit) ─▶ IntervalManager
013 RewardConsumer ─▶ ModifierProvider.modifiers_for(user, event, value, at)
      ─▶ ActiveResolver(at → campaigns+versions) ─▶ AudienceMatcher ─▶ ConditionMatcher ─▶ ActivityAttributeProvider(domains)  ⇒ Modifier[]
013 evaluators ─▶ CampaignContentProvider(achievements/quests active at) ; 011 ─▶ CalendarSource ; 009/017 ─▶ CampaignReader ; SPA ─▶ presentation overlay
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `DefinitionService` | validate closed schema, publish versions, state machine | `core.db`, audit | admin API | append-only; edits never retroactive | schema/version tests |
| `OccurrencePlanner` | expand recurrence (none/yearly/custom) in campaign tz | 026 `resolve_wall_clock` | internal | DST-safe, deterministic | schedule property tests |
| `IntervalManager` | open/close intervals, exclusion constraint, events | jobs | internal | atomic with events | boundary/overlap tests |
| `Scheduler` + reconciler | boundary jobs, repair missed boundaries | jobs | job | idempotent | downtime tests |
| `OverrideService` | manual activate/deactivate precedence/expiry | authz, `ConfirmationService` | API | recorded; auto-expiry | precedence tests |
| `ActiveResolver` | campaigns+version in force at instant | log + open interval | internal | pure on stored facts | historical resolution tests |
| `AudienceMatcher` / `ConditionMatcher` | closed catalog matching incl. normalized title/genre | `ProgressionReader`, authz, providers | internal | unknown ⇒ not applied | matching matrix tests |
| `ModifierProvider` impl | supply modifiers to 013 | resolver | capability | one per modifier/occurrence; no combination here | contract tests with 013 |
| `ContentProvider` | nested achievements/quests active at instant | resolver | capability | read-only | tests |
| `Presentation` | per-user theme overlay | 022 registry, policy | API | priority order; presentation only | policy tests |
| `Simulator` | dry-run evaluation | resolver | API | no writes | tests |
| `CalendarSource`/`CampaignReader`/events | integrations | 011/009/017/007 | ports | thin | contract tests |
| Frontend console + banner | admin UX, active display | 022 | components | accessible; closed catalog only | a11y/e2e |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/campaigns-contracts.md`

## 5. Events
Produced: `campaign.created|version_published|scheduled|started|ending_soon|ended|paused|resumed|cancelled|archived` (dedup `(campaign_id, occurrence_id, transition)`; written via the outbox in the same transaction as interval changes). Consumed: `admin.config_changed`, `plugin.state_changed`. Consumers of campaign events: 010/019 (announcements), 011 (calendar refresh), 009 (widgets), 017 (stats). Idempotent boundary jobs; duplicate/late domain events resolved by `occurred_at`.

## 6. Permissions & Security
`campaigns.read` (default grant; audience-filtered), `campaigns.manage` (Admin; sensitive, audited, `ConfirmationService` for activate/deactivate/edit-while-active/cancel). Definitions validated against the closed schema (no expressions, bounded sizes); no secrets in definitions/events; theme keys must exist in the registry and pass the 022 floor; announcement presets are text templates escaped on render. Naming note: the spec text mentions `events.manage`; this plan uses `campaigns.manage` because `events.manage` belongs to 007's event-store administration.

## 7. Configuration — `data-model.md` settings (declared into 020); boost cap lives in 013.

## 8. External Integrations — none.

## 9. Error Handling & Resilience
Scheduler down ⇒ reconciler repairs intervals on restart (history shows actual open times; modifiers resolve by log) · attribute provider unavailable ⇒ conditions unknown ⇒ no boost + diagnostics · `ProgressionReader` unavailable ⇒ level-range audience unknown ⇒ not applied · invalid definition ⇒ rejected at publish · overlapping interval attempt ⇒ constraint error handled as idempotent no-op · theme missing/unavailable ⇒ no overlay · 013 consumer duplicate calls ⇒ pure function, no side effects.

## 10. Observability
Active campaigns, boundary lateness, match rate vs unknown rate, provider failures, override usage; registers `campaigns` with 025 (functional: scheduler lag, active interval consistency).

## 11. Testing Strategy
Unit/property: recurrence expansion across DST/leap years/timezones; title/genre normalization (case, diacritics, localized genre names); condition matrix; override precedence/expiry; one-modifier-once-per-occurrence. Integration (real PG + fake clock): lifecycle start/ending_soon/end; downtime recovery; exclusion constraint; historical resolution by `occurred_at` for late events; version-in-force; **end-to-end with the real 013 consumer**: stacking (CD-024 cap), cooldown/caps still apply, no double grant; provider outage degrade. Security: permission matrix, audit of sensitive actions, schema abuse. Frontend: stepper validation, recurrence preview, simulation, banner and theme overlay with accessibility preferences. E2E: Halloween flow.

## 12. Migration / Versioning
Alembic revision for `campaigns` (`btree_gist`); definition `schema_version` + upgraders; append-only versions/log; contracts semver'd; seeded example (disabled) for docs only.

## 13. Cross-Spec Dependencies
Prerequisites: 001, 003, 007, 013 (`ModifierProvider` consumer, `economy.maxTotalBoost`), 020, 022 (theme registry), 026 (time), 021 (retention). Provides to: 013 (modifiers, campaign content), 011 (calendar), 009 (widget/conditions), 017 (`campaign_active` unlock), 019 (events/templates), 010. **Follow-ups required in earlier plans** (small, flagged): 013 `DefinitionSource` extension so evaluators can read campaign-scoped achievements/quests; 024 registers its `ActivityAttributeProvider` (genre/kind/title); 022 adds the user preference `ui.campaignThemes` (`allow|ignore`); 019 ships announcement automation presets.

## 14. Implementation Phases
1 Schema + definition service/schema + versions → 2 Occurrence planner + scheduler + intervals/log + events → 3 Overrides/manual activation → 4 Active resolver + audience/conditions + attribute provider registry → 5 `ModifierProvider` + integration tests with 013 → 6 Content provider (achievements/quests) → 7 Presentation overlay + calendar/reader ports → 8 Admin console (stepper, simulate, history) → 9 Observability/hardening/announcement presets.

## 15. Technical Decisions — `research.md` R1–R13.

## 16. Risks / Open Technical Questions
- **R1** OQ-65..69 use plan defaults (research; combination = CD-024, cap in 013); **product confirmation requested** (recurrence kinds, override auto-expiry, matching semantics).
- **R2** Cross-plan follow-ups (013/022/024/019) must be applied during their implementation; contract stubs here keep this plan independently testable.
- **R3** Title/genre matching depends on canonical tags from Media (024) and localized names via 026; mismatches degrade to "not applied".
- **R4** Clock/DST edge cases at boundaries: covered by property tests and the reconciler.
- **R5** Announcements wait for 019; manual announce is the interim path.

## Project Structure
```text
backend/src/portalab/{capabilities/campaigns, modules/campaigns/{definitions,planner,intervals,scheduler,overrides,resolver,matching,modifiers,content,presentation,simulate,api,models}} · backend/migrations/campaigns/versions/
frontend/src/features/campaigns/{console,banner,history,presentation}
```
