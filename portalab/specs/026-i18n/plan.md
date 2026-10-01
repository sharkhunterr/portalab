# Implementation Plan: Internationalization & Localization (i18n)

**Branch**: `026-i18n` | **Date**: 2026-10-01 | **Spec**: `specs/026-i18n/spec.md`
**Scope**: Technical plan for the **i18n capability only** (spec 026). Cross-spec dependencies are
identified but their plans belong to their own specs. No code, no tasks, no product-decision changes.

**Sources of truth (priority order)**: Constitution v1.0.0 → `decisions/CANONICAL_DECISIONS.md` →
Product Blueprint → `decisions/TRACEABILITY_MATRIX.md` → this spec (026) → other specs (for boundaries
only) → existing repo (none: docs/specs only).

## Constitution Check (gate — must pass before/through planning)

- **I Product Integrity** ✅ plan preserves all FR-001..036; no rule weakened. **XI Functional vs
  Presentation** ✅ language/locale/tz = representation only (FR-035). **XII Accessibility** ✅ floor WCAG
  2.2 AA (CD-027) across localized/RTL/verbose UI. **XX Simplicity & no duplication** ✅ no 2nd config
  engine (CD-011), no 2nd rules engine (CD-010), no 2nd event model (CD-012), no 2nd audit (CD-013) — i18n
  consumes owners. **VI Security / VII Privacy** ✅ i18n policy gated + audited; preferences are personal
  data (021); secrets never in catalogs/logs. **IV Event-Driven** ✅ reuses 007 backbone + dedup. **IX
  Resilience** ✅ missing-translation fallback never breaks UI. **XIX Versioning** ✅ translation changes
  never rewrite historical business data. No violations → **gate PASS**; no Complexity-Tracking entries
  required.

## 1. Technical Context

- **Deployment**: self-hosted, single-tenant personal portal (containerized). Optimize for operator
  simplicity and offline/air-gapped capability — **no mandatory external runtime service for i18n**.
- **Repository state**: no implementation exists; this is the first plan. A **portal-wide technical
  baseline** is *proposed* here (not unilaterally locked): modular monolith backend exposing capability
  contracts; SPA frontend; relational DB (PostgreSQL proposed) for domain/config/content + the append-only
  event store (owned by 007). Flagged as **PROPOSED (portal-level, ratify once)** — see §16; i18n's own
  contracts are kept stack-agnostic so a different baseline would not invalidate this plan.
- **i18n-specific technical choices (confirmed by this plan, i18n-scoped)**:
  - **Message format**: ICU MessageFormat (interpolation, plural categories, select/gender) — satisfies
    FR-011/012 and forbids naive concatenation by construction.
  - **Locale data**: CLDR (dates/times/numbers/units/first-day-of-week/relative formats, plural rules).
  - **Time**: store instants as **UTC absolute** (aligned with CD-012 `occurred_at`); render via IANA
    tz database + CLDR; standard Intl/Temporal-style formatting.
  - **Catalogs**: namespaced resource bundles (core + per-module + per-plugin), versioned, DB-backed for
    admin-managed strings/content with build-time base bundles.
- **Non-goals (per spec)**: machine-translation is optional/future (OQ-127) via a provider abstraction,
  never a hard dependency; no second configuration/rules/event/audit engine.

## 2. Architecture

i18n is a **cross-cutting capability** (not a module), exposed as a set of contracts every surface
consumes. It sits beside the other cross-cutting capabilities and depends on Administration
(configuration), Users (preferences), Events & History (instants/events), Permissions/Privacy, and
Observability.

```
            ┌─────────────── i18n Capability (spec 026) ───────────────┐
Request ───▶│ Locale Resolution ─▶ LocaleContext{language,locale,tz}    │
            │        ▲ reads enabled langs/default/fallback (Admin 020) │
            │        ▲ reads user prefs (Users 002)                     │
            │ Translation Catalogs (ICU) ── fallback chain ── missing   │
            │ Formatting (CLDR) ── dates/numbers/units/relative         │
            │ Time rendering (UTC→tz, DST, ambiguous/nonexistent rule)  │
            │ Multilingual Content model (source vs translated state)   │
            └───────────────────────────────────────────────────────────┘
   consumed by: Shell(004) Search(008) Notifications(010) Content(011)
                Gamification(013) Campaigns(014) Marketplace(015)
                Statistics(017) AI(018) Media(024) A11y/RTL(022) Plugins(023)
   emits/uses:  Events&History(007)  Observability(025)  Audit(007+003)
```

**Capability boundary rule**: surfaces call i18n **contracts** (`LocaleContext`, `t()`, `format.*`,
content-localization) — they never embed their own locale/translation logic (principle XX).

## 3. Component Boundaries

Each component has: responsibility · dependencies · key interface · key constraint · testing implication.

- **C1 — Locale Resolution Service** (backend, pure/deterministic)
  - *Responsibility*: resolve the `(language, locale, timeZone)` triplet for a request/render via the
    fallback chains (FR-003/004/005), within admin-enabled languages.
  - *Deps*: Administration config (020) for default/enabled/fallback/default-locale-tz; Users (002) for
    stored preferences.
  - *Interface*: `resolveLocaleContext(user?, request?) → LocaleContext`.
  - *Constraint*: deterministic & side-effect-free; language ⟂ locale ⟂ tz resolved independently.
  - *Testing*: unit matrix over preference/disabled-language/no-preference cases.
- **C2 — Translation Catalog Service** (backend + build)
  - *Responsibility*: store/serve ICU catalogs per language/namespace (core, module, plugin); apply
    fallback for missing keys (FR-013); never break UI.
  - *Deps*: Extensibility (023) for plugin catalogs; Observability (025) for missing-key metrics.
  - *Interface*: `getCatalog(namespace, language) → Catalog`; `resolveKey(key, language) → {value, usedFallback}`.
  - *Constraint*: missing key ⇒ fallback value + observability signal, never empty/throw.
  - *Testing*: missing-key fallback; plugin namespace merge; no cross-namespace leakage.
- **C3 — Message Renderer (ICU runtime)** (shared contract; backend + frontend)
  - *Responsibility*: render `t(key, vars, {count, select})` via ICU — interpolation, plural, select/
    gender (FR-011/012).
  - *Interface*: `t(key, vars?) : string` bound to a `LocaleContext`.
  - *Constraint*: no sentence assembly by concatenation; plural categories per active language.
  - *Testing*: plural rules across languages with distinct categories (e.g., 0/1/few/many).
- **C4 — Formatting Service (CLDR)** (shared contract)
  - *Responsibility*: format dates/times (12/24h), numbers (separators), units, currency display,
    relative times, first-day-of-week per **locale** (FR-005/006); representation only.
  - *Interface*: `format.date/time/number/unit/relative(value, localeContext)`.
  - *Constraint*: changes representation, never stored values.
  - *Testing*: locale pairs (language≠locale), 12/24h, separators, units.
- **C5 — Time-Zone Rendering Service**
  - *Responsibility*: render UTC absolute instants in the user tz; DST transitions; ambiguous/nonexistent
    local-time rule; carry a reference tz when a schedule intends wall-clock (FR-008/009/010).
  - *Deps*: Events & History (007) for instant storage model.
  - *Interface*: `renderInstant(utcInstant, tz, localeContext)`; `resolveLocalTime(wallClock, tz, policy)`.
  - *Constraint*: evaluation by absolute instants; documented DST-gap/overlap resolution.
  - *Testing*: DST boundary, gap, overlap; multi-viewer rendering of one instant.
- **C6 — Multilingual Content Model & Service**
  - *Responsibility*: represent source language + per-language versions + translation state (source/
    translated/untranslated) for content domains; presentation-layer translation for external content
    without overwriting source (FR-014..019).
  - *Deps*: Content (011), Media/external via Connectors (005) for provenance (CD-014/026).
  - *Interface*: `getLocalizedContent(contentRef, localeContext) → {version, language, state, isFallback}`.
  - *Constraint*: source never overwritten; external source content preserved.
  - *Testing*: fallback + not-translated indication; external content not mutated.
- **C7 — i18n Admin Settings (declared INTO Administration config)**
  - *Responsibility*: declare i18n config schema (default language, enabled/disabled languages, fallback,
    default locale/tz policy) into the Administration hierarchy (FR-028/029).
  - *Deps*: Administration (020) config mechanism (CD-011).
  - *Interface*: config schema registration + typed getters (no separate store).
  - *Constraint*: NO second config engine; admin policy constrains user prefs, prefs retained.
  - *Testing*: hierarchy resolution Global→Module→Plugin→User; policy-override + retention.
- **C8 — Plugin i18n Contribution Hook**
  - *Responsibility*: let plugins declare supported languages/catalogs/fallback/translatable content
    (FR-026/027) via the Extensibility model; never impose a global language.
  - *Deps*: Extensibility (023).
  - *Interface*: plugin manifest i18n section + catalog registration.
  - *Constraint*: plugin missing-translation falls back; plugin cannot set portal global language.
  - *Testing*: plugin fallback; no global-language override.
- **C9 — i18n Frontend Runtime**
  - *Responsibility*: provide active `LocaleContext` to the SPA; load/cache catalogs; render ICU; switch
    **text direction (RTL)**; set content `lang`/`dir` for assistive tech; adapt to string length
    (FR-030/031).
  - *Deps*: Accessibility floor (022, CD-027); Shell (004).
  - *Interface*: client `t()`, `format.*`, `useLocaleContext()`, direction provider.
  - *Constraint*: localized/verbose/RTL UI meets WCAG 2.2 AA; no critical info truncated.
  - *Testing*: RTL mirroring; overflow; screen-reader lang attributes.
- **C10 — Capability Adapters** (thin, per consuming capability)
  - *Responsibility*: expose i18n contracts to Search (diacritics-insensitive, language-aware matching —
    FR-020), Notifications (recipient language/locale/tz templating — FR-022), AI (response language,
    fallback when model lacks language — FR-021), and presentation adapters for Marketplace/Gamification/
    Statistics (FR-023..025). Adapters carry **no** business logic — owners keep their rules.
  - *Testing*: each adapter bounded by permissions/privacy; representation-only.

## 4. Domain / Data Model

Entities introduced/owned by i18n (reuse existing concepts; do not duplicate Users/Config entities):

- **Language** — *purpose*: an available UI/content language. *Owner*: i18n (registry); enablement policy
  lives in Administration config. *Fields*: code (BCP-47), displayName(s), direction (LTR/RTL), fallback
  language, enabled(policy). *Lifecycle*: added (additive) → enabled/disabled → (never hard-deleted while
  referenced by prefs). *Identifier*: BCP-47 tag. *Versioning*: n/a (registry). *Audit*: enable/disable =
  sensitive (CD-013). *Retention*: persistent. *Privacy*: public config. *Events*: `i18n.policy_changed`.
- **Locale** — *purpose*: regional formatting profile (may be CLDR-derived). *Fields*: code, date/time/
  number/unit conventions, firstDayOfWeek, 12/24h default. *Identifier*: locale tag. Mostly **reference
  data (CLDR)**; overrides are config. *Privacy*: public.
- **Time-Zone Preference** — *purpose*: the tz used to render instants. *Owner*: value stored as a **User
  preference (Users 002 / personal data)**; i18n defines resolution. *Privacy*: personal (021).
- **Translation Catalog / Entry** — *purpose*: ICU strings per language/namespace. *Owner*: i18n.
  *Fields*: namespace, key, language, ICU message, catalogVersion. *Lifecycle*: versioned; add/update/
  deprecate. *Versioning*: **catalogVersion** (FR-033). *Audit*: admin-managed catalog edits audited.
  *Privacy*: public (no secrets). *Events*: `i18n.translation_updated`.
- **Localized Content Version** — *purpose*: per-language version of domain content (News/Wiki/Marketplace
  /etc.) with declared source language + translation state. *Owner*: the content domain; i18n owns the
  **model/contract**. *Fields*: contentRef, language, sourceLanguage, state(source/translated/untranslated),
  version. *Versioning*: content-domain versioning; **never rewrites historical business data** (FR-032).
  *Privacy*: inherits content's visibility (021). *Deletion*: follows content + Privacy lifecycle.
- **i18n Policy** — *purpose*: default language, enabled languages, fallback, default locale/tz. *Owner*:
  **stored in Administration config (020)**, not an i18n store. *Audit*: changes audited. *Events*:
  `i18n.policy_changed`.
- **User Language/Locale/TZ Preference** *(referenced, owned by Users 002 / Privacy 021)* — personal data;
  i18n defines resolution + retention follows 021.

Relationships: Language 1—n TranslationEntry; Language 1—1 fallbackLanguage; Content 1—n LocalizedContentVersion
(1 source); User 1—1 {language?, locale?, tz?} preference.

## 5. API & Contracts

Exposed (stack-agnostic contracts; HTTP/RPC shape decided at foundation):

- **LocaleContext** resolution: `GET /i18n/context` (or server-injected) → `{language, locale, timeZone,
  direction, fallbackChain}`.
- **Catalogs**: `GET /i18n/catalogs/{namespace}?lang=` → ICU bundle (+ETag/version for caching); client
  `t(key, vars)`.
- **Formatting**: library contract `format.date/time/number/unit/relative(value, ctx)` (shared core).
- **Content localization**: `getLocalizedContent(contentRef, ctx)` consumed by content domains.
- **Admin i18n config**: schema registered into Administration config API (020) — `configuration.*` keys
  `i18n.defaultLanguage`, `i18n.enabledLanguages`, `i18n.fallback`, `i18n.defaultLocale`, `i18n.defaultTimeZone`.
- **Plugin i18n registration**: manifest `i18n: { languages, catalogs, fallback }` via Extensibility (023).

Consumed: Administration config read API (020); Users preferences (002); Events publish/subscribe (007);
Observability metrics sink (025).

Contract constraints: all read paths permission/privacy-bounded; catalogs carry **no secrets**; responses
cacheable with version invalidation on `i18n.policy_changed` / `i18n.translation_updated`.

## 6. Events

Reuse the **Events & History (007)** model and dedup (CD-012) — no second model.

- **Produced**:
  - `i18n.policy_changed` — producer: i18n/Admin; consumers: catalog/format caches, Observability (025),
    audit. Payload: changed keys (default/enabled/fallback/locale/tz), actor. Idempotency: config-change id.
  - `i18n.translation_updated` — producer: i18n; consumers: catalog caches, Observability. Payload:
    namespace, language, catalogVersion. Idempotency: (namespace, language, version).
- **Consumed**:
  - `user.preferences_updated` (Users 002) — when language/locale/tz change → invalidate the user's
    LocaleContext. Idempotent on event id.
- **Observability signals** (not domain events but metrics to 025): missing-translation key counter,
  fallback-rate, unresolved-locale/timezone occurrences.
- *Ordering*: none critical (cache invalidation is idempotent). *Persistence*: policy/translation changes
  historized per 007 retention; high-volume missing-key signals use Observability retention (025), not the
  business event store. *Failure*: a missed invalidation self-heals via version/ETag on next read.

## 7. Permissions & Security

Reuse Permissions (003), deny-by-default, server-side. Audit via 007+003 (CD-013).

| Operation | Actor | Permission | Resource/Scope | Server-side | Audit |
|---|---|---|---|---|---|
| Change i18n policy (default/enabled/fallback/default locale-tz) | Admin | `i18n.manage` (or `configuration.manage`) | portal-global config | yes | yes (sensitive) |
| Enable/disable a language | Admin | `i18n.manage` | language registry | yes | yes |
| Edit admin-managed multilingual **content** | Editor/role | content perms (`news.edit/publish`, `wiki.edit`) **per language** | content item | yes | yes (publish) |
| Set own language/locale/tz | User | `users.self.manage` (002) | own profile (personal data) | yes | per prefs policy |
| Plugin declares catalogs/languages | Admin install | `plugins.manage` (023) | plugin scope | yes | yes (install) |

- **AI / Automations / Plugins** use this same model — they consume LocaleContext/`t()` but cannot change
  i18n policy without `i18n.manage`; AI never exceeds the user (CD-003).
- **Secrets**: catalogs/logs/traces MUST exclude tokens/keys (FR-031 of 021 + §11). Catalog content is
  public config; never store PII in keys.

## 8. Configuration

All i18n configuration integrates with the **Administration configuration system (020 / CD-011)** along
`Global → Module → Plugin → User`. i18n **declares schema and defaults**; it does not build a framework.

- **Global**: `i18n.defaultLanguage`, `i18n.enabledLanguages[]`, `i18n.fallbackChain`, `i18n.defaultLocale`,
  `i18n.defaultTimeZone`, `i18n.unknownLanguagePolicy`, `i18n.ambiguousTimePolicy`.
- **Module/Plugin**: a module/plugin may declare supported languages/catalogs + module-scoped defaults
  (within Global policy).
- **User**: `language`, `locale`, `timeZone`, `twelveHourClock?`, `firstDayOfWeek?` (personal data via
  Users 002), constrained by admin policy; **preference retained** when policy overrides (CD-011/016).
- Resolution precedence for effective values = config hierarchy; i18n's Locale Resolution Service (C1)
  reads these. Changing policy emits `i18n.policy_changed` (cache invalidation).

## 9. External Integrations

- **CLDR locale data** and **IANA time-zone database**: bundled **reference data**, not runtime services —
  preserves self-hosted/offline operation. Updates (esp. DST rule changes) are **data migrations** (§13).
- **Machine translation**: **out of scope / optional future** (OQ-127). If ever added, it MUST be behind a
  provider abstraction, permission/privacy-bounded, and a **non-mandatory** dependency (portal fully
  functional without it) — mirrors the AI/MCParr optionality principle (CD-021). It MUST NOT overwrite
  source content (FR-015/018).
- **External-service content** (Connectors 005): i18n localizes *presentation* only; source text +
  provenance preserved (CD-014/026); unknown-language content handled by `i18n.unknownLanguagePolicy`.

## 10. Error Handling & Resilience

For every dependency/async path, defined behavior (FR-013 + spec Edge Cases):

| Condition | Behavior |
|---|---|
| Missing translation key | Fallback chain (lang → fallback → default); render fallback; emit missing-key signal (025); never empty/throw |
| Catalog load failure / timeout | Serve last cached/base bundle; degrade to fallback language; retry with backoff; never block render |
| Language disabled while user selected it | Fallback per chain; **retain** user preference; auto-restore if re-enabled |
| Plugin catalog failure/incompatible | Isolate (023); plugin strings fall back; portal unaffected |
| Unknown/invalid locale | Use default locale; flag via Observability |
| Unknown time zone | Use default/system tz; flag; never mis-render |
| Ambiguous/nonexistent local time (DST) | Apply `i18n.ambiguousTimePolicy` (documented rule, e.g., gap→shift-forward, overlap→earlier offset); never error |
| Config (020) read failure | Use safe defaults (portal default language/locale/UTC); degrade, don't crash |
| User-pref service (002) unavailable | Fall back to Global/default; render proceeds |
| Duplicate `policy_changed`/`translation_updated` | Idempotent cache invalidation (version/ETag) |
| External content without declared language | `i18n.unknownLanguagePolicy` (show as-is + unknown marker) |

**Isolation invariant**: an i18n sub-component failure (a catalog, a plugin bundle, the tz renderer) must
not bring down the portal; worst case the UI renders in the fallback language with default formats
(principle IX / CD).

## 11. Observability

Via **Portal Observability (025)** — no separate monitoring. Signals exposed (admin, permission-gated,
no secrets/PII):
- missing-translation keys (by namespace/language) + fallback-rate;
- unresolved locales / time zones;
- catalog load failures / latency; plugin-catalog errors;
- `i18n.policy_changed` / `i18n.translation_updated` audit trail (via 007+003).
Functional-health view: "language L has N missing keys / high fallback-rate" surfaces as a functional
(not technical) degradation per 025's two-axis model.

## 12. Testing Strategy

- **Unit**: Locale Resolution chain (preference/disabled/no-pref/fallback); ICU plural across languages
  with distinct plural categories; formatting per locale (12/24h, separators, units, first-day-of-week);
  tz rendering incl. DST boundary/gap/overlap; unknown-language/locale/tz policies.
- **Contract**: `LocaleContext`, `t()`, `format.*`, content-localization, admin config schema, plugin
  i18n registration — stable shapes consumers can rely on.
- **Integration**: config hierarchy resolution (Global→Module→Plugin→User); `user.preferences_updated`
  propagation / cache invalidation; external-content presentation translation preserving source.
- **Permission**: `i18n.manage` gating + audit entries; per-language content edit scoping; AI/plugin
  cannot change policy.
- **Event/idempotence**: duplicate `policy_changed`/`translation_updated` → single effective invalidation.
- **Migration**: add language (additive, no break); disable language (prefs retained/restored); catalog
  version migration; preference migration on portal update (map/default, no silent reset); CLDR/tz DB
  update (DST rule change) regression.
- **UI**: RTL mirroring (layout/nav/icons); verbose-string overflow (no truncation of critical info);
  screen-reader `lang`/`dir` exposure.
- **Accessibility**: automated + manual WCAG **2.2 AA** checks under localized, verbose, and RTL rendering
  (CD-027).
- **Failure/degraded**: missing catalog, unknown tz, config/pref service down, plugin catalog failure.

## 13. Migration / Versioning

- **Catalogs** carry `catalogVersion`; adding/updating translations is additive and versioned; historical
  **business** data is never rewritten by a translation change (FR-032).
- **Language lifecycle**: add = additive; disable = retain prefs + auto-restore on re-enable; never hard-
  delete a language still referenced by preferences/content versions.
- **Localized content**: per-language versions use the content domain's versioning; source language
  immutable; translations are new versions.
- **Preference migration on portal update**: if a language/locale/option is renamed/removed, map to
  nearest/default — **never silent reset** (FR-022 of spec, OQ-107 default).
- **Reference-data migrations**: CLDR and IANA tz updates (DST rule changes) are scheduled data migrations
  with regression tests; they change rendering only, never stored instants.

## 14. Cross-Spec Dependencies

1. **Prerequisites (must exist to fully integrate)**: Administration configuration (020 / CD-011); Users
   preferences (002); Events & History instants + backbone (007); Permissions (003). i18n can be built
   against their **contracts/stubs** in parallel, but integration needs them.
2. **Contracts this spec EXPOSES**: `LocaleContext` resolution; `t()` (ICU); `format.*` (CLDR); time-zone
   rendering; content-localization interface; i18n admin config schema; plugin i18n registration hook.
3. **Contracts this spec CONSUMES**: Administration config read (020); Users prefs (002); Events pub/sub
   (007); Observability sink (025); Accessibility floor (022); Connectors provenance for external content
   (005).
4. **Must be implemented before i18n is fully usable**: 020 (config), 002 (prefs), 007 (events/instants),
   003 (perms). (Foundation-level.)
5. **Implementable independently of other specs**: ICU runtime, CLDR formatting, tz rendering, the
   resolution/fallback algorithm, catalog storage/versioning.
6. **Depends on i18n afterward** (should consume its contracts; see Traceability DG-1): Shell (004),
   Search (008), Notifications (010), Content (011), Gamification (013), Campaigns (014) [wall-clock
   scheduling — OQ-128], Marketplace (015), Statistics (017), AI (018), Themes/A11y-RTL (022), Media
   (024), Plugins (023). Their i18n integration is planned **in their own plans**, not here.

## 15. Implementation Phases

Only phases appropriate to i18n (no task breakdown — that's `/speckit.tasks`).

- **Phase 1 — Foundation & resolution contracts**: `LocaleContext`, triplet model, resolution + fallback
  chains; stub config/pref providers. (C1; contracts for §5.)
- **Phase 2 — Translation catalogs & ICU runtime**: catalog storage/versioning, namespacing, `t()` ICU
  rendering, missing-key fallback + observability hook. (C2, C3)
- **Phase 3 — Formatting & time zones**: CLDR formatting, tz rendering, DST + ambiguous/nonexistent rules,
  relative times. (C4, C5)
- **Phase 4 — Admin config integration & permissions**: register i18n schema into Administration config
  hierarchy; `i18n.manage` gating + audit; policy/translation events. (C7, §7, §6)
- **Phase 5 — Multilingual content model**: `LocalizedContentVersion` + translation state + external-
  content presentation translation (source preserved). (C6)
- **Phase 6 — Capability adapters & plugin hook**: shell/search/notifications/AI/media/stats/marketplace/
  gamification presentation adapters; plugin i18n declaration. (C8, C10)
- **Phase 7 — Frontend runtime, RTL & accessibility**: SPA runtime, direction switching, `lang`/`dir`,
  string-length resilience; WCAG 2.2 AA under localization/RTL. (C9)
- **Phase 8 — Observability, migration & test hardening**: missing-key/fallback metrics to 025;
  CLDR/tz-DB migration path; full test matrix (§12).

Ordering: 1→2→3 are the self-contained core (buildable now); 4→5 require Administration/Users/Content
contracts; 6→7 require consuming capabilities' surfaces; 8 spans all.

## 16. Technical Decisions & Trade-offs

| Decision | Rationale | Trade-off / Alternative rejected |
|---|---|---|
| **ICU MessageFormat** for strings | Correct plural/select/gender + interpolation; structurally forbids concatenation (FR-012) | Learning curve; heavier than printf — rejected printf/concat (cannot satisfy plural grammar) |
| **UTC absolute storage + IANA tz rendering** | DST-safe, single source of truth for instants; aligns CD-012 | Rendering cost; rejected local-time storage (DST/ambiguity bugs) |
| **CLDR locale data** (bundled) | Correct, comprehensive formatting; offline/self-host | Data size + periodic updates; rejected hand-rolled formats (locale bugs) |
| **Catalogs: namespaced, versioned, DB + base bundles** | Admin/plugin-managed strings + cache invalidation via events | Cache-invalidation complexity (mitigated by version/ETag) |
| **i18n config declared INTO Administration (020)** | CD-011: one config system | None (explicitly avoids a 2nd engine) |
| **No runtime MT dependency** (MT optional/future) | Self-host/offline; preserves source (CD-014/026) | Less auto-translation now; acceptable (OQ-127 deferred) |
| **Contracts kept stack-agnostic** | i18n survives the portal-wide stack decision | Slightly more abstraction up front |
| **PROPOSED portal baseline**: modular monolith + SPA + PostgreSQL + (proposed) TypeScript end-to-end | Simplicity, self-host, shared i18n tooling (ICU/Intl) across FE/BE, plugin-friendly | **Not yet ratified** — belongs to a foundation plan; flagged, not locked |

## 17. Risks / Open Technical Questions

- **R1 — Portal baseline not yet ratified**: no foundation plan exists; §1/§16 *propose* a baseline. Risk
  if a different stack is later chosen. *Mitigation*: i18n contracts are stack-agnostic; only the frontend
  runtime (C9) and catalog transport bind to the stack.
- **R2 — Dependency on unplanned foundations**: Administration config (020), Users (002), Events (007),
  Permissions (003) have specs but **no plans yet**. i18n Phases 4–5 depend on their contracts.
  *Mitigation*: build Phases 1–3 against stubs; sequence 020/002/007/003 foundation plans first.
- **R3 — Open product decisions** (not technical; from CANONICAL_DECISIONS §4 / spec OQ): **OQ-125** RTL
  language set, **OQ-126** baseline languages & defaults, **OQ-127** translation workflow (human/AI/both),
  **OQ-128** wall-clock-vs-absolute scheduling default (coordinate with Automations 019 / Campaigns 014
  plans), **OQ-129** unknown-language default. Plan proceeds with documented defaults; these gate only the
  *content/config values*, not the architecture.
- **R4 — Catalog cache invalidation correctness** under policy/translation changes. *Mitigation*:
  version/ETag + idempotent invalidation; self-healing on next read.
- **R5 — RTL/accessibility coverage** across all surfaces is only as good as each consuming spec's
  adoption (DG-1). *Mitigation*: provide the runtime + lint/tests; track adoption in consuming plans.

## Closing

**Assumptions**
- Current unit = `specs/026-i18n` (per `.specify/feature.json`).
- No implementation artifacts exist in the portalab repo; this is the first plan.
- Administration/Users/Events/Permissions will expose the contracts i18n consumes (their plans pending).
- Absolute instants are stored UTC (CD-012); rendering tz is a presentation concern owned here.

**Decisions made by this plan (i18n-scoped, within canonical boundaries)**
- ICU MessageFormat; CLDR locale data; UTC+IANA time handling; namespaced versioned catalogs; i18n config
  declared into Administration (no 2nd engine); observability via 025; no runtime MT dependency.
- A **proposed** portal-wide baseline (modular monolith + SPA + PostgreSQL + TS), explicitly flagged as a
  foundation-level decision to ratify once — not locked by this spec.

**Unresolved technical questions**
- R1 baseline ratification; R4 cache-invalidation detail; exact HTTP/RPC transport shapes (deferred to
  foundation). Product-level OQ-125..129 remain open but non-blocking for architecture.

**Dependencies on future plans**
- Foundation plans for 020 (configuration), 002 (users/preferences), 007 (events/instants), 003
  (permissions) should precede i18n Phases 4–5. Consuming-capability plans (004/008/010/011/013/014/015/
  017/018/022/023/024) will each plan their own i18n integration using the contracts in §5 — **not planned
  here**.

**Status**: plan complete for spec 026. `/speckit.tasks` NOT run; no code written; no product decisions
changed.
