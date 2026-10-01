# Implementation Plan: Internationalization & Localization (i18n)

**Branch**: `026-i18n` | **Date**: 2026-10-01 (revised for the ratified stack) | **Spec**: `specs/026-i18n/spec.md`
**Roadmap**: Phase 3 step 10 *i18n*. Supersedes the earlier draft plan, which assumed "TypeScript end-to-end"; the stack is now **Python 3.12/FastAPI + PostgreSQL + React/TS** (spec 001 plan). Components, ownership and product rules are unchanged.

## Summary
Cross-cutting capability, not a module with business data: deterministic **LocaleContext** resolution (language ⟂ locale ⟂ time zone), ICU MessageFormat catalogs (base files + admin overrides), CLDR formatting, UTC-instant/IANA rendering with an explicit DST gap/overlap policy, the multilingual-content contract (source vs translated vs untranslated), adapters for search/AI/notifications/presentation specs, plugin catalog registration, accessibility and RTL support in the frontend runtime. It declares settings into Administration (no second config engine, CD-011), uses the 007 event model, 003 permissions with audit through `AuditSink`, and reports health through 025.

## Technical Context
**Backend**: Python 3.12, `Babel` (CLDR), stdlib `zoneinfo` + `tzdata`, a `MessageRenderer` adapter selected by spike (PyICU binding vs pure-Python ICU parser + Babel plurals) · **Frontend**: React 19/TS, `react-intl`/`@formatjs/intl`, native `Intl` · **Storage**: schema `i18n` (languages, catalog_entries, catalog_versions, localized_content_versions, missing_key_stats); base bundles as repo files · **Testing**: pytest (real PG), golden ICU vectors shared with Vitest, Playwright pseudo-locale/RTL + axe · **Constraints**: offline/air-gapped (no runtime external service), missing translation never breaks UI, representation-only (FR-035) · **Scale**: tens of languages max, thousands of keys.

## Constitution Check — PASS
I Product Integrity (FR-001..036) · XI representation vs function · XII WCAG 2.2 AA under verbose/RTL · XX no second config/rules/event/audit engine (CD-010/011/012/013) · VI/VII `i18n.manage` gated + audited, preferences are personal data (021) · IV reuse 007 · IX isolation/fallback · XIX historical business data never rewritten. No violations.

## 1. Architecture
```
Request/Job ─▶ LocaleResolver ◀─ I18nPolicyReader / UserLocalePreferenceReader (ports, implemented by 020)
                    └▶ LocaleContext{language, locale, tz, direction, fallback_chain}
MessageRenderer(t) ◀ CatalogService ◀ base bundles (files) ⊕ i18n.catalog_entries (overrides)  [ETag = catalog_version]
Formatter(Babel) · TimeRenderer(zoneinfo)  · ContentLocalizer(localized_content_versions)
HTTP: /i18n/context · /i18n/languages · /i18n/catalogs/{ns} · /admin/i18n/*
SPA: I18nProvider ─ react-intl + Intl ─ <html lang dir> ─▶ design system (022) direction provider
Events (007): i18n.policy_changed · i18n.translation_updated  ◀ consumes admin.config_changed
Adapters: search(008) · AI(018) · notifications(010) · presentation (013/015/017) · plugins(023)
```
Capability boundary: surfaces call i18n contracts only; no module embeds its own locale/translation logic.

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| C1 `LocaleResolver` | resolve triplet through fallback chains within enabled languages | ports (020), 002 principal | `resolve()` | pure/deterministic; independent axes | resolution matrix |
| C2 `CatalogService` | merge base ⊕ overrides, versioning, fallback, plugin namespaces | files, `i18n.catalog_entries`, 023 | `get_catalog`, `resolve_key` | missing ⇒ fallback + stat, never raises; no cross-namespace leak | fallback & merge tests |
| C3 `MessageRenderer` | ICU render (interpolation, plural, select) | adapter (spike T004) | `t()` | no concatenation; plural per language | golden vectors (shared with JS) |
| C4 `Formatter` | CLDR date/time/number/unit/currency/relative, 12/24h, first day of week | Babel | `format.*` | representation only | locale-pair tests |
| C5 `TimeRenderer` | UTC→tz, DST rules, wall-clock resolution | zoneinfo | `render_instant`, `resolve_wall_clock` | evaluation on absolute instants; gap/overlap policy | DST boundary tests |
| C6 `ContentLocalizer` | per-language versions, state, fallback indication, external-content presentation translation | registry, 005 provenance | `get`, `register_version` | source immutable; MT optional | immutability tests |
| C7 Settings declaration | declare `i18n.*` keys + user keys | 020 | `declare_setting` | no own store | hierarchy/policy-retention tests |
| C8 Plugin hook | register plugin catalogs/languages | 023 | `register_plugin_catalog` | cannot set global language | isolation tests |
| C9 Frontend runtime | provider, `t`, format, `lang`/`dir`, namespace lazy-load, pseudo-locales | 022, 004 | hooks/components | WCAG 2.2 AA; no critical truncation | RTL/overflow/axe |
| C10 Adapters | search normalization, AI response language, recipient locale, presentation helpers | 008/018/010 | functions | no business logic | contract tests |
| C11 Admin & health | catalog-entry API, missing-key stats, 025 functional component | 003, 025 | routers | `i18n.manage`, audited | permission tests |
| C12 Tooling | `portalab i18n check|extract|pseudo`, CI gates | CI | CLI | placeholder/plural parity | CI self-test |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/i18n-contracts.md`

## 5. Events
Produced `i18n.policy_changed` (changed keys, actor; dedup config-change id), `i18n.translation_updated` (namespace, language, version; dedup tuple), `i18n.language_added|disabled`. Consumed `admin.config_changed` (i18n.* and user locale keys) → bump `locale_epoch`; `plugin.state_changed` → register/unregister plugin catalogs. All idempotent; a missed invalidation self-heals via ETag on next read. High-volume missing-key signals go to Observability metrics, not the event store.

## 6. Permissions & Security
| Operation | Permission | Audit |
|---|---|---|
| change i18n policy / enable-disable language | `i18n.manage` (via 020) | yes, sensitive |
| edit admin-managed catalog entries | `i18n.manage` | yes |
| set own language/locale/tz | `users.self.manage` | per preference policy |
| edit multilingual content per language | owning module permission | publish audited |
| plugin catalogs | `plugins.manage` (023) | install audited |
AI/automations/plugins consume LocaleContext but cannot change policy. Catalogs carry no secrets or PII; ICU input from admins is validated and rendered with output escaping (no markup execution; HTML only through the content sanitizer of the owning module).

## 7. Configuration — see data-model "Settings declared into 020".

## 8. External Integrations
None at runtime. CLDR/IANA data ship as pinned dependencies (offline). `TranslationProvider` is an optional port, absent by default (OQ-127).

## 9. Error Handling & Resilience
Missing key ⇒ fallback chain, render, count · catalog load failure ⇒ last cached/base bundle, retry with backoff · disabled language ⇒ fallback, preference retained and auto-restored · unknown locale/tz ⇒ defaults + flag · DST gap/overlap ⇒ policy, never error · 020 or identity unavailable ⇒ portal defaults (`en`/`UTC`) · plugin catalog invalid ⇒ plugin strings fall back, portal unaffected · renderer exception ⇒ raw key fallback string logged, UI continues · external content without language ⇒ `unknownLanguagePolicy`.

## 10. Observability
Metrics to 025: missing keys by namespace/language, fallback rate, unresolved locale/tz, catalog load latency/failures. Functional component `i18n` degrades when a language's fallback rate exceeds a configured threshold (functional axis). No PII.

## 11. Testing Strategy
Unit: resolution matrix; ICU plural/select vectors for languages with distinct categories (shared golden file run in pytest and Vitest); formatting for language≠locale pairs, 12/24h, separators, units; DST boundary/gap/overlap; unknown language/locale/tz. Contract: LocaleContext, catalog ETag, content localizer, settings schema, plugin registration. Integration: hierarchy Global→Module→Plugin→User with policy-retention; `admin.config_changed` propagation; content source immutability; external content untouched. Permission: `i18n.manage`; AI/plugin cannot change policy. Event/idempotence. Migration: add/disable language; preference retention on removed options; tz/CLDR bump regression. UI: RTL mirroring, pseudo-locale overflow, `lang`/`dir` exposure, axe under verbose/RTL. Failure: missing catalog, config down, renderer error.

## 12. Migration / Versioning
Alembic revision for schema `i18n` (+ seed `en`, `fr`); `catalog_version` content hash; additive language lifecycle; preference migration on update (map/default, never silent reset); CLDR/tzdata updates are dependency bumps with regression suites (rendering only, never stored instants).

## 13. Cross-Spec Dependencies
Prerequisites (planned earlier): 001 kernel, 002 (principal/preferences), 003 (`authorize`, audit), 007 (events/instants), 020 (config + the two reader ports), 022 (direction provider, a11y floor), 004 (shell `I18nProvider` slot), 025 (health). Exposes to: 008, 010, 011, 013, 014, 015, 017, 018, 023, 024 and all UI. Consuming specs plan their own integration.

## 14. Implementation Phases
1 Contracts & resolution → 2 Renderer spike + catalogs + tooling → 3 Formatting & time zones → 4 Settings, permissions, events → 5 Multilingual content model → 6 Adapters & plugin hook → 7 Frontend runtime, RTL & accessibility → 8 Observability, migrations, hardening.

## 15. Technical Decisions — `research.md` R1–R14.

## 16. Risks / Open Technical Questions
- **R1** Backend ICU renderer choice (R3 in research): resolved by spike T004 with shared golden vectors; exit criterion = all vectors pass and the single Docker image builds without extra system packages (or the extra package is accepted explicitly).
- **R2** Product questions OQ-125..129 use documented defaults (research R14), kept in config. **Product confirmation requested** (languages `en`+`fr`, scheduling default, unknown-language policy).
- **R3** Cache invalidation correctness: ETag/epoch design + idempotent consumers.
- **R4** RTL/a11y adoption depends on every consuming spec; provide lint, pseudo-locales and gallery coverage.
- **R5** Earlier TS i18n draft (stash on `spec/026-i18n`) is obsolete in structure; reuse only `languages`/resolution *test cases*, not code.

## Project Structure
```text
backend/src/portalab/{capabilities/i18n, modules/i18n/{resolver,catalog,render,format,time,content,adapters,api,models}} · backend/migrations/i18n/versions/ · backend/locales/<lang>/<namespace>.json (per module)
frontend/src/i18n/{provider,hooks,format,direction,pseudo} · frontend/locales/<lang>/*.json
```
