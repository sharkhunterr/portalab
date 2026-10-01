---
description: "Task list — Internationalization & Localization (spec 026), revised for the ratified stack"
---

# Tasks: Internationalization & Localization (i18n)

**Input**: `specs/026-i18n/` · **Branch**: `026-i18n` · **Roadmap**: Phase 3 step 10 · **Tests**: included. Replaces the earlier stack-agnostic task list (same coverage of FR-001..036; checklist format, split by user story).
Abbrev: **`I18N/`** = `backend/src/portalab/modules/i18n`, **`CAP/`** = `backend/src/portalab/capabilities/i18n`, **`FE/`** = `frontend/src/i18n`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel · `D-002` principal/preferences · `D-003` authz + `AuditSink` · `D-007` events/instants · `D-020` config (implements `UserLocalePreferenceReader`/`I18nPolicyReader`) · `D-022` direction provider · `D-004` shell slot · `D-025` health registration. Consumers (008, 010, 011, 013–015, 017, 018, 023, 024) integrate in their own plans.

## Phase 1: Setup
- [ ] T001 Create `CAP/__init__.py`, `I18N/{resolver,catalog,render,format,time,content,adapters,api,models}/__init__.py`, `backend/migrations/i18n/versions/`, `backend/locales/{en,fr}/core.json`, `FE/{provider,hooks,format,direction,pseudo}/`, `frontend/locales/{en,fr}/`, `backend/tests/{unit,integration,contract,security}/i18n/`, `frontend/tests/{unit,e2e}/i18n/`
- [ ] T002 [P] Add backend deps (`babel`, `tzdata`) in `backend/pyproject.toml` and frontend deps (`react-intl`, `@formatjs/cli`) in `frontend/package.json`; pin versions
- [ ] T003 [P] Declare settings (`i18n.defaultLanguage`, `.enabledLanguages`, `.fallbackChain`, `.defaultLocale`, `.defaultTimeZone`, `.unknownLanguagePolicy`, `.ambiguousTimePolicy`, `.schedulingDefault`; user `language|locale|timeZone|hourCycle|firstDayOfWeek`) in `I18N/settings.py`; permission `i18n.manage` (audited) in `I18N/permissions.py`; register user keys as `preference` class in the PII registry
- [ ] T004 Spike `docs/spikes/i18n-backend-renderer.md`: evaluate PyICU binding vs pure-Python ICU parser + Babel plurals against a shared golden-vector file `backend/tests/data/icu_vectors.json` (plural/select/gender/nested/escaping in ≥6 languages incl. multi-category ones); exit criterion: all vectors pass and the single image builds without unaccepted system packages; record the chosen adapter

## Phase 2: Foundational — contracts, schema, tooling
### Tests first
- [ ] T005 [P] Write `backend/tests/contract/i18n/test_contracts.py`: shapes of `LocaleContext`, `MessageRenderer`, `Formatter`, `TimeRenderer`, `ContentLocalizer`, ports `UserLocalePreferenceReader`/`I18nPolicyReader` (stubs satisfy them)
- [ ] T006 [P] Write `backend/tests/integration/i18n/test_schema.py`: tables, unique `(namespace,key,language)`, source rows in `localized_content_versions` immutable, language rows not deletable while referenced
### Implementation
- [ ] T007 Implement `CAP/` contracts (`LocaleContext` immutable value object, protocols, in-memory stubs for ports)
- [ ] T008 Implement `I18N/models` + Alembic revision for schema `i18n` (languages, catalog_entries, catalog_versions, localized_content_versions, missing_key_stats; seed `en`, `fr`; immutability trigger via 001 helper)
- [ ] T009 Implement the chosen renderer adapter from T004 in `I18N/render/adapter.py` behind `MessageRenderer` and wire the golden vectors into pytest
- [ ] T010 [P] Implement tooling `I18N/tools/check.py` (+ `portalab i18n check|extract|pseudo` CLI): ICU validity, placeholder/plural parity, unused/missing keys, bundle hash; and frontend `npm run i18n:check` using the same vectors file

## Phase 3: US1 — Interface language resolution & fallback (P1) 🎯 MVP
**Independent test**: preference → disabled-language → no-preference cases resolve deterministically with preference retained and restored.
- [ ] T011 [P] [US1] Write `backend/tests/unit/i18n/test_resolver.py`: matrix (preference enabled / disabled / absent / unknown; default disabled ⇒ hard default `en`); independence of language, locale, tz; preference retained and auto-restored when re-enabled; deterministic
- [ ] T012 [US1] Implement `I18N/resolver/resolver.py` (`LocaleResolver.resolve`, `for_user`) with `locale_epoch` cache invalidation
- [ ] T013 [US1] Implement routers `GET /i18n/context`, `GET /i18n/languages` in `I18N/api/router.py`
- [ ] T014 [US1] Implement consumer of `admin.config_changed` (i18n.* and user locale keys) bumping `locale_epoch`, and emit `i18n.policy_changed` / `i18n.language_added|disabled` via `EventPublisher` (dedup config-change id) in `I18N/events.py`

## Phase 4: US4 — Translation model: interpolation, plurals, fallback (P1)
- [ ] T015 [P] [US4] Write `backend/tests/unit/i18n/test_catalog_fallback.py`: missing key ⇒ fallback chain value + `missing_key_stats` increment, never raises/empty; base ⊕ override merge; no cross-namespace leakage; ETag = content hash
- [ ] T016 [P] [US4] Write `frontend/tests/unit/i18n/messages.test.tsx`: same golden vectors as backend; missing key falls back; no string concatenation lint
- [ ] T017 [US4] Implement `I18N/catalog/service.py` (base files + DB overrides, `catalog_version`, fallback resolution, stats aggregation) and `GET /i18n/catalogs/{namespace}` with ETag
- [ ] T018 [US4] Implement `FE/provider/I18nProvider.tsx`, `FE/hooks/useT.ts` (react-intl), per-route namespace lazy loading and cached last-good bundle on load failure
- [ ] T019 [US4] Implement admin catalog-entry API `GET/PUT /admin/i18n/catalog-entries` (`i18n.manage`, ICU syntax + placeholder-parity validation, audited, emits `i18n.translation_updated`)

## Phase 5: US2 — Locale formatting distinct from language (P1)
- [ ] T020 [P] [US2] Write `backend/tests/unit/i18n/test_formatter.py`: `en` language with `de-DE`/`fr-FR`/`en-US` locales; 12/24h, separators, units, currency display, relative time, first day of week; stored values unchanged
- [ ] T021 [US2] Implement `I18N/format/formatter.py` (Babel) and `FE/format/useFormat.ts` (`Intl`) honoring `hourCycle`/`firstDayOfWeek` overrides

## Phase 6: US3 — Time zones, schedules, DST (P1)
- [ ] T022 [P] [US3] Write `backend/tests/unit/i18n/test_time.py`: one instant rendered in several zones; DST gap and overlap resolved per `ambiguousTimePolicy` (never error); wall-clock schedule with reference tz fires once across transitions; unknown tz ⇒ default + flag
- [ ] T023 [US3] Implement `I18N/time/renderer.py` (`render_instant`, `resolve_wall_clock`, `next_occurrence(schedule, after)` helper for 014/019 with `absolute|wall_clock` mode)

## Phase 7: US10 — Administration of i18n settings (P1)
- [ ] T024 [P] [US10] Write `backend/tests/integration/i18n/test_admin_policy.py`: hierarchy Global→Module→Plugin→User resolution; policy narrows user choice while preference retained; `i18n.manage` required; every change audited via `AuditSink`; AI/plugin principals cannot change policy
- [ ] T025 [US10] Implement settings declarations wiring (T003) against 020 `declare_setting` with validation (BCP-47, enabled ⊇ default, fallback acyclic) and conformance of the 020-implemented ports via contract test in `backend/tests/contract/i18n/test_ports_conformance.py`

## Phase 8: US11 — Accessibility & RTL across languages (P1)
- [ ] T026 [P] [US11] Write `frontend/tests/e2e/i18n/rtl-pseudo.spec.ts`: pseudo-locales (`en-XA` verbose, `ar-XB` RTL) — layout mirrored, no critical info truncated, `lang`/`dir` set on `<html>` and on mixed-language fragments, axe passes
- [ ] T027 [US11] Implement `FE/direction/DirectionBridge.tsx` feeding the design-system direction provider (022) and `FE/pseudo/` pseudo-locale generator for dev/CI
- [ ] T028 [US11] Add language/locale/time-zone selectors (onboarding + profile) in `frontend/src/features/settings/LanguageSettings.tsx` honoring policy locks via `PolicyField` (022) and keyboard/touch operability

## Phase 9: US5 + US6 — Multilingual content and external data (P2)
- [ ] T029 [P] [US5] Write `backend/tests/integration/i18n/test_content_localizer.py`: source/translated/untranslated states; fallback with "not translated" indication; source version immutable; translation = new version; language change never rewrites historical business data
- [ ] T030 [P] [US6] Write `backend/tests/integration/i18n/test_external_content.py`: external text and provenance preserved; presentation translation never overwrites source; undeclared language follows `unknownLanguagePolicy`; no provider ⇒ feature absent, portal unaffected
- [ ] T031 [US5] Implement `I18N/content/localizer.py` (`ContentLocalizer.get/register_version`, registry helpers for owning modules) and `GET /i18n/content/{kind}/{id}` delegating read permission to the owner
- [ ] T032 [US6] Implement `TranslationProvider` port + presentation-translation path in `I18N/content/external.py` (optional, off by default, permission/privacy-bounded)

## Phase 10: US7 + US8 — Search, AI, notifications, presentation adapters (P2)
- [ ] T033 [P] [US7] Write `backend/tests/unit/i18n/test_adapters.py`: `normalize_for_search` (NFKC, casefold, diacritics folding, language-specific cases); `ResponseLanguage.for_user` with fallback when model lacks language; `RecipientLocale.for_user` returns recipient language/locale/tz (not sender)
- [ ] T034 [P] [US8] Write `backend/tests/unit/i18n/test_presentation.py`: representation-only helpers for dates/numbers/units/durations/percentages in Marketplace/Gamification/Statistics contexts never alter stored values or business rules
- [ ] T035 [US7] Implement `I18N/adapters/{search,ai,notifications}.py` per contracts (consumed by 008/018/010)
- [ ] T036 [US8] Implement `I18N/adapters/presentation.py` (duration/percentage/unit helpers, localized labels for categories via catalog keys) for 013/015/017

## Phase 11: US9 — Plugin-declared languages and translations (P2)
- [ ] T037 [P] [US9] Write `backend/tests/integration/i18n/test_plugin_catalogs.py`: plugin catalogs namespaced and merged; missing plugin translation falls back; plugin cannot set portal default/global language; invalid/incompatible bundle isolated; unregister on plugin disable
- [ ] T038 [US9] Implement `register_plugin_catalog`, manifest `i18n` validation and consumer of `plugin.state_changed` in `I18N/catalog/plugins.py`

## Phase 12: Observability, migration, security & polish
- [ ] T039 [P] Implement missing-key/fallback/load-failure metrics and register the `i18n` component with 025 (functional check: fallback rate threshold per language) in `I18N/observability.py`; `GET /admin/i18n/health`
- [ ] T040 [P] Write `backend/tests/integration/i18n/test_migrations.py`: add language (additive), disable (preferences retained/restored), removed option mapped not reset, tzdata/Babel bump regression suite re-run
- [ ] T041 [P] Write `backend/tests/security/i18n/test_catalog_security.py`: catalogs/logs/stats contain no secrets or PII; ICU input cannot inject markup/execute; personal data (language/locale/tz) covered by 020 export/erasure; retention of `missing_key_stats` registered with 021
- [ ] T042 [P] Add `/i18n/*`, `/admin/i18n/*` to the permission-matrix test, regenerate OpenAPI client, wire `portalab i18n check` and `npm run i18n:check` into the GitLab CI `validate` stage
- [ ] T043 [P] Write `docs/i18n.md` (contributor guide: keys, ICU rules, pseudo-locales, adding a language, plugin catalogs, operator settings)
- [ ] T044 Run `specs/026-i18n/quickstart.md` end-to-end and record deviations; record product confirmations for OQ-125..129 defaults

## Dependencies & Order
Setup → spike T004 → Foundational → US1 (MVP) → US4 → US2 → US3 → US10 → US11 → US5/US6 → US7/US8 → US9 → Polish. US2/US3 are independent once contracts exist; US10 needs 020; US11 needs 022/004; US9 needs 023 events (stub until then).
**Parallel examples**: T005/T006 · T011 with T015/T016 · T020/T022 · T029/T030 · T039–T043.
**MVP**: Phases 1–4 (resolution + catalogs/ICU with fallback + frontend provider).

## Format validation
44 tasks, all checkbox + ID + path; story labels only on story phases.
