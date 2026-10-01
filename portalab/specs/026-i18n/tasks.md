---
description: "Implementation task list — Internationalization & Localization (i18n), spec 026"
---

# Tasks: Internationalization & Localization (i18n)

**Spec**: `specs/026-i18n/spec.md` · **Plan**: `specs/026-i18n/plan.md` · **Date**: 2026-10-01
**Sources of truth**: Constitution → CANONICAL_DECISIONS.md → Blueprint → TRACEABILITY_MATRIX.md → spec 026
→ plan 026 → repo (no implementation exists yet).

**Conventions**
- Task IDs: `T0xx` (i18n-owned implementation) · `D-0xx` (cross-spec dependency/reference — **not**
  implemented here; a prerequisite owned by another spec).
- Types: Foundation · Data Model · Domain Logic · API/Contract · Integration · UI · Permissions ·
  Security · Configuration · Events · Observability · Migration · Testing · Documentation.
- Every i18n task cites FR / US / AC (acceptance criteria = the numbered acceptance scenarios, e.g.
  `US1-AS3`). `[P]` in the parallel groups (§2) marks safe parallelism.
- **No code is written here; this is the task list only.** Canonical ownership (CD-010/011/012/013/016/
  020/022/023/025) is respected: i18n consumes those owners and implements none of them.

## Cross-Spec Dependency / Reference Tasks (NOT implemented here)

> These are prerequisites owned by other specs. i18n builds against their contracts (stubs) where
> possible; full integration needs them. Listed so sequencing is explicit; **do not implement them in
> this spec.**

- **D-020** Administration configuration mechanism (Global→Module→Plugin→User, CD-011) — needed by T013.
- **D-002** Users preference storage (language/locale/tz as personal data) — needed by T003, T017.
- **D-007** Events & History backbone + UTC instant model + dedup (CD-012) — needed by T012, T015–T017.
- **D-003** Permissions model (deny-by-default, server-side, audit) — needed by T014.
- **D-025** Portal Observability sink — needed by T008, T029.
- **D-022** Accessibility floor (WCAG 2.2 AA, CD-027) — needed by T028.
- **D-005** Connectors provenance/source-of-truth (CD-014/026) — needed by T020.
- **D-023** Extensibility model (plugin manifest/registration) — needed by T021.

---

## Phase 1 — Foundation & Resolution Contracts

### T001 — Define the LocaleContext contract
- **Type**: Foundation / API-Contract
- **Description**: Define the shared, stack-agnostic `LocaleContext` value `{ language, locale, timeZone,
  direction (LTR/RTL), fallbackChain }` consumed by every surface. No logic — the data contract only.
- **Dependencies**: none
- **Parallelizable**: Yes
- **FR**: FR-001, FR-005, FR-007 · **US**: US1, US2 · **AC**: US1-AS1, US2-AS1
- **DoD**: `LocaleContext` type published as a core contract; documented; referenced by T003/T026/T034.

### T002 — Define config-read & user-preference provider interfaces (stubs)
- **Type**: Foundation / API-Contract
- **Description**: Define the interfaces C1 consumes: a config reader (enabled languages, default language,
  fallback chain, default locale/tz — from Administration D-020) and a user-preference reader
  (language/locale/tz — from Users D-002). Provide in-memory stubs for isolated testing.
- **Dependencies**: D-020, D-002 (contracts only)
- **Parallelizable**: Yes
- **FR**: FR-003, FR-028, FR-029 · **US**: US1, US10 · **AC**: US10-AS1
- **DoD**: provider interfaces + test stubs; no second config store introduced (reads via D-020).

### T003 — Implement the Locale Resolution Service (C1)
- **Type**: Domain Logic
- **Description**: Deterministic resolution of the triplet: language chain (user pref → portal default →
  ultimate fallback, within enabled languages), locale chain (user → default → portal), tz chain (user →
  default/system). Language, locale, and tz resolved independently.
- **Dependencies**: T001, T002
- **Parallelizable**: No
- **FR**: FR-003, FR-004, FR-005, FR-007 · **US**: US1, US2 · **AC**: US1-AS1..4, US2-AS1..3
- **DoD**: pure/side-effect-free function; unit tests for every branch (no pref, disabled selected
  language, mismatched language≠locale); no UI-only logic.

### T004 — Language registry data model
- **Type**: Data Model / Migration
- **Description**: Model a Language `{ code(BCP-47, unique), displayName(s), direction(LTR/RTL),
  fallbackLanguage, enabled-policy reference }`; seed the baseline language set (default per OQ-126) and
  the portal default; migration. Enablement policy value lives in D-020 config, not duplicated here.
- **Dependencies**: none (seed values coordinate with OQ-126)
- **Parallelizable**: Yes
- **FR**: FR-001, FR-004, FR-031 · **US**: US1, US11 · **AC**: US1-AS1
- **DoD**: schema + unique-code constraint + fallback self-reference + migration; never hard-deletes a
  referenced language (enforced in T030).

## Phase 2 — Translation Catalogs & ICU Runtime

### T005 — Translation catalog/entry data model
- **Type**: Data Model / Migration
- **Description**: Model Catalog Entry `{ namespace(core/module/plugin), key, language, icuMessage,
  catalogVersion }`; index `(namespace, language, key)`; migration. No secrets/PII in keys or values.
- **Dependencies**: T004
- **Parallelizable**: Yes
- **FR**: FR-011, FR-033 · **US**: US4 · **AC**: US4-AS1
- **DoD**: schema + index + migration; versioned by `catalogVersion`.

### T006 — Catalog Service with fallback (C2)
- **Type**: Domain Logic
- **Description**: Load/serve a catalog per `(namespace, language)`; merge plugin namespaces without
  leakage; `resolveKey(key, language) → { value, usedFallback }` applying the fallback chain; emit a
  missing-key signal (T008) instead of empty/throw.
- **Dependencies**: T005, T003
- **Parallelizable**: No
- **FR**: FR-013, FR-026 · **US**: US4, US9 · **AC**: US4-AS3, US9-AS2
- **DoD**: service + unit tests (missing-key fallback renders cleanly; namespace isolation).

### T007 — ICU Message Renderer (C3)
- **Type**: Domain Logic
- **Description**: `t(key, vars, { count, select })` rendering ICU MessageFormat — interpolation, plural
  categories, select/gender — bound to a `LocaleContext`. Forbid naive concatenation by construction.
- **Dependencies**: T006, T001
- **Parallelizable**: No
- **FR**: FR-011, FR-012 · **US**: US4 · **AC**: US4-AS1, US4-AS2
- **DoD**: renderer + tests across ≥2 languages with distinct plural categories (0/1/few/many); a
  concatenation-detection lint/test guard.

### T008 — Missing-translation & fallback-rate signals
- **Type**: Observability
- **Description**: Emit missing-translation key counts (by namespace/language) and fallback-rate to Portal
  Observability (D-025); no secrets. Feeds the functional-health view (T029).
- **Dependencies**: T006, D-025
- **Parallelizable**: Yes (after T006)
- **FR**: FR-013 (+ plan §11) · **US**: US4 · **AC**: US4-AS3
- **DoD**: signal emission + test; consumes the 025 sink contract (no separate monitoring).

## Phase 3 — Formatting & Time Zones

### T009 — Bundle CLDR locale dataset + access layer
- **Type**: Integration (reference data)
- **Description**: Integrate CLDR data (dates/times/numbers/units/first-day-of-week/relative/plural rules)
  as **bundled data** (offline/self-host); versioned access layer.
- **Dependencies**: none
- **Parallelizable**: Yes
- **FR**: FR-005 · **US**: US2 · **AC**: US2-AS1
- **DoD**: dataset integrated, versioned; offline-capable; update path defined (T032).

### T010 — Formatting Service (C4)
- **Type**: Domain Logic
- **Description**: Format date/time (12/24h), number (decimal/thousands separators), units, currency
  display, relative times, first-day-of-week per **locale**; representation only (never mutates values).
- **Dependencies**: T009, T003
- **Parallelizable**: No
- **FR**: FR-005, FR-006, FR-007 · **US**: US2 · **AC**: US2-AS1..3
- **DoD**: service + tests for locale pairs (language≠locale), 12/24h toggle, separators, units; an
  explicit "underlying value unchanged" test (supports FR-035).

### T011 — Bundle IANA tz database + ambiguous-time policy
- **Type**: Integration (reference data) / Configuration
- **Description**: Integrate IANA tz data (bundled); define `i18n.ambiguousTimePolicy` config key (DST
  gap/overlap resolution rule) and `i18n.unknownLanguagePolicy` placeholder (used by T020).
- **Dependencies**: none (policy keys registered via T013)
- **Parallelizable**: Yes
- **FR**: FR-010 · **US**: US3 · **AC**: US3-AS4
- **DoD**: tz data integrated; policies documented + registered as config keys.

### T012 — Time-Zone Rendering Service (C5)
- **Type**: Domain Logic
- **Description**: Render UTC absolute instants in the user tz; handle DST transitions; resolve
  ambiguous/nonexistent local times per policy; carry a reference tz when a schedule intends wall-clock.
  Instants are never mutated (CD-012).
- **Dependencies**: T011, T010, D-007
- **Parallelizable**: No
- **FR**: FR-008, FR-009, FR-010 · **US**: US3 · **AC**: US3-AS1..4
- **DoD**: service + tests (multi-viewer render of one instant; DST boundary/gap/overlap); consumes the
  007 instant model (D-007).

## Phase 4 — Admin Configuration Integration & Permissions

### T013 — Register i18n config schema into Administration hierarchy
- **Type**: Configuration
- **Description**: Declare i18n settings INTO the Administration config system (D-020), Global→Module→
  Plugin→User: `i18n.defaultLanguage`, `i18n.enabledLanguages[]`, `i18n.fallbackChain`,
  `i18n.defaultLocale`, `i18n.defaultTimeZone`, `i18n.unknownLanguagePolicy`, `i18n.ambiguousTimePolicy`.
  No separate config store/engine.
- **Dependencies**: T003, D-020
- **Parallelizable**: No
- **FR**: FR-028, FR-029 · **US**: US10 · **AC**: US10-AS1..3
- **DoD**: schema registered via the 020 API; hierarchy-resolution test (admin policy constrains user
  pref while the underlying preference is retained); zero second config framework.

### T014 — Enforce `i18n.manage` permission + audit for policy changes
- **Type**: Permissions / Security
- **Description**: Server-side, deny-by-default gate on i18n policy changes (default/enabled/fallback/
  default locale-tz, language enable/disable). Actor=Admin; resource=portal-global i18n policy; audited
  (actor/action/timestamp/context/result) via Events & History + Permissions (CD-013). AI/plugins/
  Automations cannot change policy without this permission.
- **Dependencies**: T013, D-003
- **Parallelizable**: No
- **FR**: FR-028, FR-034 · **US**: US10 · **AC**: US10-AS1
- **DoD**: server-side enforcement (no UI-only check) + audit entry + permission tests (allowed/denied).

### T015 — Produce `i18n.policy_changed` event + cache invalidation
- **Type**: Events
- **Description**: On policy change, emit `i18n.policy_changed` via Events & History (D-007); identity =
  config-change id; consumers invalidate catalog/format caches and Observability; idempotent invalidation.
- **Dependencies**: T013, D-007
- **Parallelizable**: No (after T013)
- **FR**: FR-033, FR-034 · **US**: US10 · **AC**: US10-AS3
- **DoD**: producer + consumer handler + dedup/idempotence test (duplicate delivery → single effect).

### T016 — Produce `i18n.translation_updated` event + invalidation
- **Type**: Events
- **Description**: On catalog change emit `i18n.translation_updated { namespace, language, catalogVersion }`;
  idempotent on `(namespace, language, version)`; invalidate affected catalog caches (ETag/version).
- **Dependencies**: T005, D-007
- **Parallelizable**: Yes (after T005)
- **FR**: FR-033 · **US**: US4 · **AC**: US4-AS3
- **DoD**: producer + consumer + idempotence test.

### T017 — Consume `user.preferences_updated` to invalidate LocaleContext
- **Type**: Events
- **Description**: Subscribe to `user.preferences_updated` (Users D-002); when language/locale/tz change,
  invalidate that user's resolved `LocaleContext`. Idempotent on event id.
- **Dependencies**: T003, D-002, D-007
- **Parallelizable**: Yes (after T003)
- **FR**: FR-002 · **US**: US1 · **AC**: US1-AS2 (switch takes effect)
- **DoD**: consumer handler + idempotence test; new preference honored on next resolution.

## Phase 5 — Multilingual Content Model

### T018 — LocalizedContentVersion data model
- **Type**: Data Model / Migration
- **Description**: Model `{ contentRef, language, sourceLanguage, state(source/translated/untranslated),
  version }`. Source language immutable; per-language versions. Model/contract only — does NOT duplicate
  the content entities owned by their domains (011/015/024).
- **Dependencies**: T004
- **Parallelizable**: Yes
- **FR**: FR-014, FR-015, FR-032 · **US**: US5 · **AC**: US5-AS1, US5-AS4
- **DoD**: schema + migration; source-immutable constraint; test proving a translation never rewrites
  historical business data (FR-032).

### T019 — Content Localization Service (C6)
- **Type**: Domain Logic
- **Description**: `getLocalizedContent(contentRef, ctx) → { version, language, state, isFallback }` —
  returns the user's language if available, else a defined fallback **with a not-translated indication**;
  never hides/breaks; source preserved.
- **Dependencies**: T018, T003
- **Parallelizable**: No
- **FR**: FR-016 · **US**: US5 · **AC**: US5-AS2, US5-AS3
- **DoD**: service + tests (fallback + indication; untranslated shown, not hidden).

### T020 — External-content presentation translation (C6)
- **Type**: Integration
- **Description**: Localize the **presentation** of external-sourced content without overwriting the
  stored source; apply `i18n.unknownLanguagePolicy` for content with no declared language; preserve
  provenance (CD-014/026, via Connectors D-005).
- **Dependencies**: T019, T011, D-005
- **Parallelizable**: No
- **FR**: FR-017, FR-018, FR-019 · **US**: US6 · **AC**: US6-AS1..3
- **DoD**: adapter + tests (source value not mutated; unknown-language handled, never discarded).

## Phase 6 — Capability Adapters & Plugin Hook

### T021 — Plugin i18n contribution hook (C8)
- **Type**: Integration / Extensibility
- **Description**: Via Extensibility (D-023), let a plugin declare `i18n { languages, catalogs, fallback,
  translatable content }`; register plugin catalogs under its namespace; a plugin cannot set the portal
  global language; plugin catalog failure is isolated and falls back.
- **Dependencies**: T006, D-023
- **Parallelizable**: Yes (after T006)
- **FR**: FR-026, FR-027 · **US**: US9 · **AC**: US9-AS1..3
- **DoD**: hook + tests (plugin fallback; no global-language override; failing plugin isolated — portal
  unaffected).

### T022 — Search language-aware matching contract (C10 → consumed by 008)
- **Type**: API/Contract
- **Description**: Expose normalization utilities for diacritics-insensitive, language-aware matching and
  result-language indication/fallback. i18n provides the normalization contract; **Search (008) owns the
  engine and performs the integration** (dependency ref, not implemented here).
- **Dependencies**: T003, T009
- **Parallelizable**: Yes
- **FR**: FR-020 · **US**: US7 · **AC**: US7-AS1
- **DoD**: normalization contract + tests; cross-spec hand-off note to 008.

### T023 — AI response-language contract (C10 → consumed by 018)
- **Type**: API/Contract
- **Description**: Contract for AI to answer in the user's language within permissions, fall back when the
  model lacks the language (indicating the limitation), and preserve cited sources' language. **AI (018)
  owns the integration** (dependency ref).
- **Dependencies**: T003
- **Parallelizable**: Yes
- **FR**: FR-021 · **US**: US7 · **AC**: US7-AS2, US7-AS3
- **DoD**: contract + tests (language selection + fallback indication); hand-off note to 018.

### T024 — Notifications localization contract (C10 → consumed by 010)
- **Type**: API/Contract
- **Description**: Template-localization helper so notifications/emails render in the recipient's
  language/locale/tz with interpolation + fallback. **Notifications (010) owns delivery** (dependency ref).
- **Dependencies**: T007, T010, T012
- **Parallelizable**: Yes
- **FR**: FR-022 · **US**: US7 · **AC**: US7-AS3
- **DoD**: helper + tests (recipient locale/tz; missing translation → fallback, delivery not blocked);
  hand-off note to 010.

### T025 — Presentation adapters for Marketplace/Gamification/Statistics (C10)
- **Type**: API/Contract
- **Description**: Representation-only localization contracts for labels/formats in Marketplace (015),
  Gamification (013), and Statistics (017); underlying transactions/rules/statistical data unchanged.
  Those specs own their integration (dependency refs).
- **Dependencies**: T007, T010
- **Parallelizable**: Yes
- **FR**: FR-023, FR-024, FR-025 · **US**: US8 · **AC**: US8-AS1..3
- **DoD**: adapter contracts + representation-only tests (no transaction/rule/data change); hand-off notes
  to 013/015/017.

## Phase 7 — Frontend Runtime, RTL & Accessibility

### T026 — Frontend i18n runtime (C9)
- **Type**: UI / Foundation
- **Description**: SPA runtime providing the active `LocaleContext`, catalog loading/caching (ETag/
  version), client `t()` / `format.*`, `useLocaleContext()`. Loading/empty/error states for catalog
  fetch; language switch takes effect immediately.
- **Dependencies**: T001, T006, T007, T010
- **Parallelizable**: No
- **FR**: FR-001, FR-005 · **US**: US1 · **AC**: US1-AS1, US1-AS2
- **DoD**: runtime + loading/empty/error states; cache invalidation on version change; switch-language
  integration test.

### T027 — RTL direction support (C9)
- **Type**: UI
- **Description**: Apply `dir`/`lang`; mirror layout/navigation/icons for enabled RTL languages; keep
  functional meaning unchanged. The specific RTL language set is a product decision (OQ-125) — the
  **capability** is implemented regardless.
- **Dependencies**: T026, T004
- **Parallelizable**: No
- **FR**: FR-031 · **US**: US11 · **AC**: US11-AS2
- **DoD**: RTL rendering + tests (mirroring correct; meaning unchanged); gracefully no-ops if no RTL
  language enabled.

### T028 — Localized UI meets WCAG 2.2 AA under verbose + RTL (C9)
- **Type**: UI / Accessibility
- **Description**: Ensure localized UI meets the accessibility floor (CD-027, via D-022): string-length
  resilience (no truncation/overlap hiding critical info), screen-reader `lang`/`dir` exposure, readable
  localized dates/numbers, keyboard/touch operability.
- **Dependencies**: T026, T027, D-022
- **Parallelizable**: No
- **FR**: FR-030 · **US**: US11 · **AC**: US11-AS1, US11-AS3
- **DoD**: automated + manual WCAG 2.2 AA checks pass under localized/verbose/RTL; overflow tests.

## Phase 8 — Observability, Migration, Security & Test Hardening

### T029 — i18n functional-health view (via Observability 025)
- **Type**: Observability
- **Description**: Surface missing-keys-per-language, fallback-rate, unresolved locales/time zones, and
  catalog load failures as a **functional-health** view via Portal Observability (D-025). No secrets/PII.
- **Dependencies**: T008, T012, D-025
- **Parallelizable**: Yes
- **FR**: FR-013 (+ plan §11) · **US**: US4, US11 · **AC**: US4-AS3
- **DoD**: signals integrated into 025; test; no duplicate monitoring system.

### T030 — Language-lifecycle migrations (add/disable/retain-restore)
- **Type**: Migration
- **Description**: Adding a language is additive; disabling retains user preferences and auto-restores on
  re-enable; never hard-delete a referenced language.
- **Dependencies**: T004, T003
- **Parallelizable**: No
- **FR**: FR-004, FR-033 · **US**: US1 · **AC**: US1-AS3
- **DoD**: migrations + tests (preference retention + auto-restore on re-enable).

### T031 — Catalog & preference migration on portal update
- **Type**: Migration
- **Description**: Catalog version migration; preference migration when a language/locale/option is
  renamed/removed — map to nearest/default, **never a silent reset** (OQ-107 default).
- **Dependencies**: T005, T026
- **Parallelizable**: Yes
- **FR**: FR-033 (+ spec FR-022 persistence) · **US**: US1 · **AC**: US1-AS3
- **DoD**: migration + tests (no silent reset; intent preserved).

### T032 — CLDR/IANA reference-data update migration (DST rule changes)
- **Type**: Migration
- **Description**: Scheduled data migration for CLDR and tz-DB updates (incl. DST rule changes) — changes
  rendering only; stored instants unchanged.
- **Dependencies**: T009, T011, T012
- **Parallelizable**: Yes
- **FR**: FR-010 · **US**: US3 · **AC**: US3-AS3
- **DoD**: update path + regression test (rendering updates; instants immutable).

### T033 — Edge-case & failure test suite
- **Type**: Testing
- **Description**: Cover spec Edge Cases: missing translation; disabled language still used; plugin without
  translation; external content without declared language; tz change during an active campaign (coord.
  014) / automation (coord. 019); DST gap/overlap; mixed-language content; notification right after a
  language change; deleted/anonymized user preferences (via 021); import/export of i18n config (via 020).
- **Dependencies**: T003, T006, T012, T019, T020, T021
- **Parallelizable**: Yes (after its deps)
- **FR**: FR-004, FR-010, FR-013, FR-017..019, FR-026, FR-036 · **US**: all · **AC**: Edge Cases
- **DoD**: each enumerated edge case has a passing test; none breaks the UI.

### T034 — Contract tests for all exposed i18n contracts
- **Type**: Testing
- **Description**: Contract/stability tests for `LocaleContext`, `t()`, `format.*`, content-localization,
  admin config schema, and plugin i18n registration — so consuming specs can rely on them.
- **Dependencies**: T001, T007, T010, T013, T019, T021
- **Parallelizable**: Yes
- **FR**: FR-001, FR-005, FR-011..016, FR-026, FR-028 · **US**: US1/US2/US4/US5/US9/US10 · **AC**: multiple
- **DoD**: contract tests green; breaking-change detection in place.

### T035 — Security/Privacy hardening (secrets + personal-data lifecycle)
- **Type**: Security / Privacy
- **Description**: Verify catalogs/logs/traces contain no secrets (tokens/keys/OIDC); treat user language/
  locale/tz as personal data under Privacy (021) — visibility, retention, deletion/anonymization.
- **Dependencies**: T008, T017, D-025
- **Parallelizable**: Yes
- **FR**: FR-036 (+ spec FR-031 secrets) · **US**: US-edge (deleted/anonymized user) · **AC**: Edge Cases
- **DoD**: secret-scan test; privacy-lifecycle test (preference anonymized/removed on final deletion).

### T036 — i18n contributor & operator documentation
- **Type**: Documentation
- **Description**: Document adding a language, authoring ICU catalogs (interpolation/plural, no
  concatenation), declaring plugin i18n, the config keys and hierarchy, fallback behavior, and RTL/a11y
  expectations. Reference CD-023.
- **Dependencies**: T007, T013, T021, T027
- **Parallelizable**: Yes
- **FR**: supports FR-011/012/026/028/031 · **US**: US4/US9/US10/US11 · **AC**: —
- **DoD**: docs committed under the repo; reviewed against CD-023.

## 1. Task Dependency Graph

```
Prereqs (other specs): D-020 D-002 D-007 D-003 D-025 D-022 D-005 D-023

T001 ─┬─▶ T003 ─┬─▶ T010 ─┬─▶ T012 ──▶ T032
T002 ─┘         │         │
T004 ──▶ T005 ──┼─▶ T006 ─┼─▶ T007 ──▶ T026 ─▶ T027 ─▶ T028
        │       │   │     │            ▲
        │       │   └─▶T008─▶T029       │
T009 ───┴───────┘   │                   │
T011 ───────────────┘                   │
                                        │
T013 ─▶ T014 ─▶ T015                    │
T013 ─▶ (config keys for T011)          │
T005 ─▶ T016                            │
T003 ─▶ T017                            │
T004 ─▶ T018 ─▶ T019 ─▶ T020            │
T006 ─▶ T021                            │
T003/T009 ─▶ T022                       │
T003 ─▶ T023                            │
T007/T010/T012 ─▶ T024                  │
T007/T010 ─▶ T025                       │
T004/T003 ─▶ T030   T005/T026 ─▶ T031   │
T033/T034/T035/T036 depend on their cited tasks ◀┘
```

Critical path: `T001/T002 → T003 → T010 → T012` (core resolution + formatting + time) and
`T004 → T005 → T006 → T007 → T026 → T027 → T028` (catalogs → runtime → RTL → a11y).

## 2. Parallel Execution Groups

- **G1 (start now, no cross deps)** `[P]`: T001, T002, T004, T009, T011 — independent foundations/data.
  *Shared contract*: none produced yet; they only define types/data.
- **G2 (after T003)** `[P]`: T010 and T017 — formatting vs pref-invalidation are independent once the
  resolver exists.
- **G3 (after T005/T006)** `[P]`: T008, T016, T021 — observability signal, translation event, plugin hook
  share only the catalog contract (stable after T006).
- **G4 (contracts, after T003/T007/T010/T012)** `[P]`: T022, T023, T024, T025 — capability adapters are
  independent contracts consuming resolver/renderer/formatter; integration owned by other specs.
- **G5 (migrations/tests, after their deps)** `[P]`: T030, T031, T032, T033, T034, T035, T036 — distinct
  files/areas.
- **Serial (shared mutable surfaces, do NOT parallelize)**: T003→T010→T012; T006→T007; T013→T014→T015;
  T026→T027→T028 (frontend runtime evolves the same surface).

## 3. Requirement → Task Traceability

| FR | Tasks |
|---|---|
| FR-001 interface language | T001, T003, T004, T026 |
| FR-002 preference honored immediately | T017 (+ D-002) |
| FR-003 resolution chain | T002, T003, T013 |
| FR-004 disabled-language fallback + retain | T003, T030 |
| FR-005 locale formatting | T009, T010, T001 |
| FR-006 representation only | T010 |
| FR-007 language ⟂ locale | T003, T010 |
| FR-008 instants rendered in user tz | T012 |
| FR-009 scheduled items absolute + reference tz | T012 (coord. D-007/014/019) |
| FR-010 DST / ambiguous | T011, T012, T032 |
| FR-011 interpolation, no concat | T007, T005 |
| FR-012 plural / grammatical forms | T007 |
| FR-013 missing → fallback, never break | T006, T008 |
| FR-014 content source/translated/untranslated | T018 |
| FR-015 source preserved | T018, T020 |
| FR-016 fallback + indication | T019 |
| FR-017 external presentation localize, preserve source | T020 |
| FR-018 translation = presentation layer | T020 |
| FR-019 unknown-language handling | T020 |
| FR-020 search language-aware | T022 (integration owned by 008) |
| FR-021 AI response language | T023 (integration owned by 018) |
| FR-022 notifications/email localized | T024 (delivery owned by 010) |
| FR-023 marketplace representation-only | T025 |
| FR-024 gamification representation-only | T025 |
| FR-025 statistics representation-only | T025 |
| FR-026 plugin declares langs/catalogs | T021 |
| FR-027 plugin not impose global language | T021 |
| FR-028 admin config | T013, T014 |
| FR-029 admin policy constrains + retains pref | T013, T014, T030 |
| FR-030 accessibility floor | T028 |
| FR-031 RTL | T004, T027 |
| FR-032 translation change ≠ rewrite history | T018, T031 |
| FR-033 language lifecycle / versioning | T005, T030, T031 |
| FR-034 audit i18n changes | T014, T015 |
| FR-035 business-rule independence | T010, T012, T025 |
| FR-036 preferences = personal data (privacy) | T035 |

**All 36 FRs have ≥1 task. No FR is silently unimplemented.**

## 4. Acceptance Criteria → Test Traceability

| User Story (AC) | Test task(s) |
|---|---|
| US1-AS1..4 (language resolution/switch/disable) | T003, T026, T030 |
| US2-AS1..3 (locale formatting; language≠locale) | T010 |
| US3-AS1..4 (tz render; DST; ambiguous) | T012, T032 |
| US4-AS1..3 (ICU plural; missing→fallback) | T007, T006, T008 |
| US5-AS1..4 (content source/translated/fallback) | T018, T019 |
| US6-AS1..3 (external content; source preserved; unknown lang) | T020 |
| US7-AS1 (search) / AS2-3 (AI) / AS3 (notif) | T022 / T023 / T024 |
| US8-AS1..3 (marketplace/gamification/statistics repr-only) | T025 |
| US9-AS1..3 (plugin i18n; fallback; no global override) | T021 |
| US10-AS1..3 (admin config via hierarchy; policy + retain) | T013, T014, T015 |
| US11-AS1..3 (WCAG 2.2 AA; RTL; readable localized) | T028, T027 |
| Edge Cases (all) | T033 (+ T035 privacy, T032 DST) |

**Every acceptance scenario maps to ≥1 test task.**

## 5. Cross-Spec Dependencies

- **Prerequisites (must exist to integrate)**: D-020 (config), D-002 (prefs), D-007 (events/instants),
  D-003 (permissions), D-025 (observability), D-022 (a11y floor), D-005 (provenance), D-023 (extensibility).
- **Contracts this spec EXPOSES (consumed elsewhere)**: `LocaleContext`, `t()`, `format.*`, tz rendering,
  content-localization, admin i18n config schema, plugin i18n hook, Search normalization (T022), AI
  response-language (T023), Notifications localization (T024), presentation adapters (T025).
- **Integration owned by other specs (NOT implemented here)**: Search 008 (T022), AI 018 (T023),
  Notifications 010 (T024), Marketplace 015 / Gamification 013 / Statistics 017 (T025), and every other
  text-rendering consumer (004/011/024) — each adopts the contracts in their own tasks.
- **No duplicated work**: i18n implements none of 020/002/007/003/025/022/005/023/008/010/013/015/017/018.

## 6. Risks / Blockers

- **B1 (blocker for Phases 4–5)**: D-020 (config) and D-002 (prefs) have no plans/tasks yet. Phases 1–3
  proceed against stubs (T002); T013/T017/T019 need the real contracts.
- **B2 (blocker for T012/T015/T017)**: D-007 (events/instants) must expose the UTC instant model + event
  bus. Mitigation: stub instant source for T012 unit tests.
- **R3 (non-blocking, product OQ)**: OQ-125 (RTL language set), OQ-126 (baseline languages/defaults),
  OQ-127 (translation workflow), OQ-128 (wall-clock vs absolute scheduling default — coordinate T012 with
  014/019), OQ-129 (unknown-language default). Tasks proceed with documented defaults; these gate seed/
  config values, not the architecture.
- **R4 (non-blocking)**: portal-wide stack not ratified (plan R1). Only T026–T028 (frontend) bind to the
  stack; keep T001–T025 contracts stack-agnostic.

## 7. Final Completeness Check

- **Requirements without tasks**: **none** (FR-001..036 all mapped, §3).
- **Acceptance criteria without tests**: **none** (US1..11 all mapped, §4; Edge Cases → T033/T035/T032).
- **Tasks without requirement traceability**: enabling/support tasks only — T001/T002 (contracts),
  T009/T011 (reference data), T026 (runtime), T029 (observability), T034 (contract tests), T036 (docs),
  and the `D-0xx` cross-spec refs. These are traced to FR *groups* or are intentionally non-FR
  (infrastructure/docs/dependency). **No functional task lacks traceability.**
- **Missing migrations**: **none** — T004, T005, T018 (schema+migration), T030 (language lifecycle), T031
  (catalog/preference on update), T032 (CLDR/tz reference-data).
- **Missing permission enforcement**: **none** — T014 enforces `i18n.manage` server-side + audit;
  content-edit permissions delegated to content specs (noted); user self-service via `users.self.manage`
  (002). No UI-only checks.
- **Missing edge-case coverage**: **none** — T033 covers the spec's enumerated edge cases; T032 (DST),
  T035 (deleted/anonymized user).
- **Missing observability**: **none** — T008 (missing-key/fallback signals) + T029 (functional-health
  view) via Observability 025; no duplicate system.
- **Missing i18n/accessibility**: N/A for i18n itself (this is the i18n spec); **accessibility** covered by
  T028 (WCAG 2.2 AA) + T027 (RTL).

### Definition of Done (spec 026 overall)
Complete when: all FR-001..036 implemented via T001–T036; all US1..11 acceptance scenarios covered by
tests (§4); `i18n.manage` enforced + audited; all error/degraded states (§plan 10) handled; events
`i18n.policy_changed` / `i18n.translation_updated` emitted and `user.preferences_updated` consumed
idempotently; migrations T030–T032 exist and pass; tests T033–T035 green; WCAG 2.2 AA + RTL satisfied
(T027/T028); observability signals live (T008/T029); and no canonical ownership boundary is violated
(no 2nd config/rules/event/audit/monitoring system).

> `/speckit.tasks` output only — nothing implemented, no command run, no commit created.
