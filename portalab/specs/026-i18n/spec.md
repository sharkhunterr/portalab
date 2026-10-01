# Feature Specification: Internationalization & Localization (i18n)

**Feature Branch**: `026-i18n`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Dedicated functional specification for Internationalization & Localization (i18n) — a transversal capability."

## Role of This Document

This is a **detailed feature specification** for i18n — the transversal capability that decides, for every
user-facing piece of information, **which language** it uses, **which locale** formats it, **which time
zone** applies, and **what happens when a translation is missing**. It conforms to and refines the
superior reference specification (`specs/001-portal-global-spec/spec.md`), **owns canonical decision
CD-023** (`decisions/CANONICAL_DECISIONS.md`), and composes with the owners of every mechanism it touches.
It draws on `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`, `product/GLOSSARY.md`,
`ux/UX_PRINCIPLES.md`, `ux/DESIGN_SYSTEM.md`, and `ux/THEMING.md`, under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0).

### What this spec OWNS vs CONSUMES (normative — no duplication, principle XX + CANONICAL_DECISIONS)

- **OWNS**: internationalization/localization **behavior and rules** — interface language resolution,
  locale formatting (dates/times/numbers/units/currency display), time-zone application, the translation
  model (interpolation, pluralization, fallback), the multilingual-content model (source vs translated vs
  untranslated), and the rules by which every surface chooses language/locale/time-zone.
- **CONSUMES / REFERENCES (does not re-define)**: the configuration system & hierarchy Global → Module →
  Plugin → User → **Administration (020) / CD-011** (i18n declares its settings into it, it does **not**
  build a second config engine); the generic WHEN/IF/THEN engine → **Automations (019) / CD-010** (i18n
  builds no rules engine); event idempotency/dedup → **Events & History (007) / CD-012**; authorization &
  privacy → **Roles & Permissions (003) + Privacy (021) / CD-002/016**; notification/email delivery →
  **Notifications (010)**; external-service sync & provenance → **Connectors (005) / CD-014/026**; search
  → **Search (008)**; AI → **AI (018) / CD-003**; presentation/theming/accessibility → **Personalization,
  Themes & A11y (022) / CD-027**; media identity/source conflict → **Media (024) / CD-026**.

**Hard boundary (CD — business rules are language-independent):** language/locale/time-zone affect
**representation only**; they MUST NEVER change business rules, permissions, source-of-truth, economy
values, statistical data, or historical records.

**Terminology**: **Language** = the human language of text (e.g., interface strings). **Locale** = the
regional formatting conventions (dates, numbers, first day of week, units). **Time zone** = the offset/
rules used to render instants. Language and Locale are **conceptually distinct** and independently
resolvable. Domain Event = a recorded fact; `occurred_at` = real occurrence instant (an absolute point in
time, time-zone-independent at storage).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Interface language resolution & fallback (Priority: P1)

A user's interface language is resolved from their preference (set at onboarding and changeable anytime)
within the admin-enabled languages, falling back deterministically when a preference is unset or a
language is later disabled — never breaking the UI.

**Why this priority**: Interface language is the most visible i18n behavior and the base case for every
other rule (fallback, disabled-language handling).

**Independent Test**: Set a preferred language; switch it; have the admin disable a language a user had
selected; confirm resolution follows preference → fallback chain, the UI never breaks, and the user is
informed when their language became unavailable.

**Acceptance Scenarios**:

1. **Given** admin-enabled languages and a portal default, **When** a user has no preference, **Then** the
   interface uses the portal default language (or a request-derived hint within enabled languages, if
   policy allows).
2. **Given** a user preferred language among enabled languages, **When** they use the portal, **Then** the
   interface renders in it; switching language takes effect immediately and persists (per Users 002 +
   Configuration CD-011).
3. **Given** a user's selected language is later disabled by the admin, **When** they next load the
   portal, **Then** it falls back deterministically (user preference → portal default → ultimate fallback)
   without breaking, and the user's original preference is retained for restoration if re-enabled
   (consistent with preserve/restore, CD-016 pattern).
4. **Given** any surface, **When** a string is missing in the active language, **Then** the fallback
   language string is shown and the UI never renders a broken/empty label.

### User Story 2 - Locale formatting distinct from language (Priority: P1)

Dates, times (12/24h), first day of week, numbers (decimal/thousands separators), units, currency display,
and relative times are formatted by the user's **locale**, which is resolvable independently of their
**language**.

**Why this priority**: Conflating language and locale is the classic i18n defect; the brief explicitly
requires them distinct.

**Independent Test**: Set language and locale to a mismatched pair (e.g., English language, French
locale); confirm text is English while dates/numbers follow the French locale; toggle 12/24h and first
day of week and confirm formatting changes without changing the underlying values.

**Acceptance Scenarios**:

1. **Given** a user with language L and locale R (L ≠ R allowed), **When** content renders, **Then** text
   uses L while dates/times/numbers/units use R.
2. **Given** locale settings (12/24h, first day of week, separators, units), **When** changed, **Then**
   representation changes while underlying stored values are unchanged.
3. **Given** relative times ("2 hours ago"), **When** rendered, **Then** they follow the locale's rules and
   the user's time zone (US3), and remain accessible/readable (CD-027).

### User Story 3 - Time zones for instants, schedules, DST (Priority: P1)

Absolute instants (events, campaigns, maintenance, automations, notifications, statistics periods,
newsletters) are stored time-zone-independently (`occurred_at`) and rendered in the user's time zone,
handling DST transitions and ambiguous/nonexistent local times correctly.

**Why this priority**: Time-zone and DST errors cause wrong reminders, wrong campaign windows, and wrong
stats; the brief enumerates many affected systems.

**Independent Test**: With users in different time zones, render the same instant; confirm each sees their
local time; schedule a campaign/automation across a DST boundary and confirm it fires at the intended
absolute instant; create a local time in a DST gap/overlap and confirm defined handling.

**Acceptance Scenarios**:

1. **Given** an absolute instant, **When** rendered for users in different time zones, **Then** each sees
   it in their own time zone; the stored instant is unchanged.
2. **Given** a scheduled campaign/automation/maintenance/notification, **When** it fires, **Then** it
   fires at the intended absolute instant regardless of viewer time zones, and schedule definitions state
   the reference time zone where a wall-clock time is intended (see OQ).
3. **Given** a DST transition during an active campaign/automation window, **When** evaluated, **Then** the
   window is interpreted consistently (by absolute instants) and does not double-fire or skip incorrectly.
4. **Given** an ambiguous or nonexistent local time (DST gap/overlap), **When** encountered, **Then** the
   system resolves it by a defined, documented rule rather than erroring.

### User Story 4 - Translation model: interpolation, pluralization, fallback (Priority: P1)

UI strings, error messages, notification/email bodies, administrative content, and system pages are
translated using variable interpolation and proper pluralization/grammatical forms — never naive string
concatenation — with fallback so missing translations never break the UI.

**Why this priority**: A correct translation model (not concatenation) is essential for languages with
different word order/plural rules; fallback protects resilience.

**Independent Test**: Render strings with variables and plural counts (0/1/many) in languages with
different plural rules; confirm correct forms; remove a translation and confirm fallback renders cleanly;
confirm no sentence is built by concatenating fragments.

**Acceptance Scenarios**:

1. **Given** a string with variables, **When** rendered, **Then** interpolation places values correctly for
   the language's grammar (no fixed-order concatenation).
2. **Given** a pluralized string, **When** rendered with counts 0/1/few/many, **Then** the correct plural/
   grammatical form for the active language is used.
3. **Given** a missing translation, **When** rendered, **Then** the fallback language string is shown and
   the UI remains intact (never an empty or broken label).
4. **Given** error messages/notifications/emails/system pages, **When** localized, **Then** they follow the
   same interpolation/pluralization/fallback rules.

### User Story 5 - Multilingual content: source vs translated vs untranslated (Priority: P2)

Content (News, Wiki, Marketplace products, Community Projects, Campaigns, Notifications, Documentation,
plugin content) distinguishes source language, translated content, untranslated content, and
multi-language availability, so a user sees the best available language with a clear indication when it is
not their preferred one.

**Why this priority**: Content is authored, not just UI strings; the product must represent translation
state without losing the source.

**Independent Test**: Author content in a source language; add a translation; leave another language
untranslated; view as users with different languages; confirm each sees their language when available,
a clear fallback+indication otherwise, and that the source is preserved.

**Acceptance Scenarios**:

1. **Given** content with a declared source language, **When** stored, **Then** the source language is
   preserved and never overwritten by a translation.
2. **Given** content available in multiple languages, **When** viewed, **Then** the user sees their
   preferred language if available, else a defined fallback with an indication it is not their language.
3. **Given** untranslated content, **When** viewed, **Then** it is shown in its available language with a
   clear "not translated" indication (never hidden or broken).
4. **Given** admin-managed multilingual content, **When** edited, **Then** per-language versions are
   editable without destroying other languages or the source.

### User Story 6 - External-service data language & provenance (Priority: P2)

Data originating from external services (Plex, RomM, Grimmory, Seerr, future connectors) preserves its
source content and provenance; the portal localizes its **presentation** (labels, formats) but does not
arbitrarily overwrite externally sourced content merely to translate it.

**Why this priority**: Source-of-truth and provenance are locked (CD-014/026); i18n must not corrupt
external data under the guise of translation.

**Independent Test**: Ingest media/metadata from a source in its language; render it; confirm the source
text/provenance is preserved, portal chrome/labels are localized, and any translation of source content is
presented as a translation layer (not an overwrite).

**Acceptance Scenarios**:

1. **Given** external-sourced content, **When** displayed, **Then** the source content and provenance are
   preserved (CD-014/026); portal labels/formats around it are localized.
2. **Given** a request to translate external content, **When** applied, **Then** it is a presentation-layer
   translation that does not overwrite the stored source value.
3. **Given** external content with no declared language, **When** handled, **Then** it is treated per a
   defined rule (shown as-is with unknown-language handling; see OQ) and never discarded.

### User Story 7 - Search, AI, Notifications/Email localization (Priority: P2)

Search is language-aware (diacritics-insensitive matching, cross-language results, result-language
indication, fallback); the AI responds in the user's language within their permissions; notifications and
emails use the recipient's language/locale/time-zone with localized templates and fallback.

**Why this priority**: These three surfaces are where language most visibly meets behavior; each must
reuse its owner (Search 008, AI 018, Notifications 010) and never break on missing translations.

**Independent Test**: Search with/without diacritics across content in multiple languages; ask the AI a
question and confirm it answers in the user's language within permissions; trigger a notification and an
email and confirm they use the recipient's language/locale/time-zone with fallback.

**Acceptance Scenarios**:

1. **Given** multilingual content, **When** searched (via Search 008), **Then** matching is
   diacritics-insensitive and language-aware, results may span languages, each result's language is shown
   where useful, and fallback applies — all permission/privacy bounded.
2. **Given** a user language preference, **When** the AI (018) responds, **Then** it answers in that
   language within the user's permissions; if the model cannot support the requested language, it falls
   back by a defined rule and indicates the limitation; it preserves source language of cited material.
3. **Given** a notification/email, **When** produced (via Notifications 010), **Then** it uses the
   recipient's language/locale/time-zone with localized templates, interpolated variables, and fallback;
   missing translations never prevent delivery (fallback content is used).

### User Story 8 - Marketplace, Gamification, Statistics localization (representation only) (Priority: P2)

Marketplace (categories, products, descriptions, conditions, Community Projects, price formats),
Gamification (levels, achievements, quests, rewards, events, badges, titles, related notifications), and
Statistics (periods, dates, numbers, durations, percentages, units, chart labels, tooltips) are localized
in **representation only** — never changing historical transactions, business rules, or statistical data.

**Why this priority**: These domains carry economy/rules/data integrity (locked); i18n must localize their
presentation without touching their truth.

**Independent Test**: Switch language/locale and confirm Marketplace/gamification/statistics labels and
formats change while prices-as-Coins, reward rules, transaction history, and statistical values are
unchanged.

**Acceptance Scenarios**:

1. **Given** Marketplace content, **When** language/locale changes, **Then** categories/products/
   descriptions/conditions/price **formats** localize, while historical transactions and business rules
   are unchanged (CD-005/006).
2. **Given** gamification elements, **When** localized, **Then** level/achievement/quest/reward/badge/
   title labels and related notifications are translated, while the reward engine and rules remain
   language-independent (CD-004).
3. **Given** statistics, **When** language/locale/time-zone change, **Then** periods/dates/numbers/
   durations/percentages/units/labels/tooltips re-format, while the underlying statistical data is
   unchanged (Statistics 017).

### User Story 9 - Plugin-declared languages & translations (Priority: P2)

A plugin declares its supported languages, available translations, fallback, and translatable strings/
content via the common extensibility model; a plugin never imposes its own global language on the portal.

**Why this priority**: Extensibility must be uniform (CD / 023); plugins must participate in i18n without
creating language silos or overriding the portal language.

**Independent Test**: Install a plugin declaring some languages/translations; confirm its strings localize
within the portal's language/fallback rules, that missing plugin translations fall back cleanly, and that
the plugin cannot force the portal's global language.

**Acceptance Scenarios**:

1. **Given** a plugin, **When** installed, **Then** it declares supported languages, translations,
   fallback, and translatable strings/content via the extensibility model (023).
2. **Given** a plugin missing a translation for the active language, **When** rendered, **Then** it falls
   back per the portal's fallback chain without breaking.
3. **Given** a plugin, **When** active, **Then** it MUST NOT impose its own global language on the portal
   or other plugins; it participates in the portal's i18n resolution.

### User Story 10 - Administration of i18n settings (via Configuration, not a new engine) (Priority: P1)

The Admin configures i18n policy — default language, available/enabled/disabled languages, fallback,
default locale/time-zone policies — **through the existing Administration configuration system**
(Global → Module → Plugin → User), not a separate config engine.

**Why this priority**: The brief and CD-011 require i18n to use Administration's configuration, not build
a second one.

**Independent Test**: As Admin, set default language, enable/disable languages, set fallback and default
locale/time-zone policy via the configuration system; confirm effects propagate through the hierarchy and
user preferences remain within policy.

**Acceptance Scenarios**:

1. **Given** Administration configuration (020/CD-011), **When** the Admin sets i18n policy (default
   language, enabled languages, fallback, default locale/TZ), **Then** it is stored and applied via the
   existing hierarchy — i18n creates no second config engine.
2. **Given** an admin policy constraining language/locale, **When** it applies, **Then** it constrains
   user preferences while retaining the user's underlying preference where still permitted (CD-011/016).
3. **Given** a disabled language, **When** policy changes, **Then** affected users fall back per US1 and
   their stored preference is retained for restoration if re-enabled.

### User Story 11 - Accessibility & RTL across languages (Priority: P1)

Localized UI meets the accessibility floor (CD-027 / WCAG 2.2 AA) despite longer translated strings,
remains responsive and keyboard/screen-reader operable, renders localized dates/numbers readably, and
supports **right-to-left (RTL)** text direction where an RTL language is enabled.

**Why this priority**: Accessibility is transversal/locked; translation length and text direction are the
main i18n risks to layout and a11y.

**Independent Test**: Render UI in a verbose language and (if any RTL language is enabled) an RTL language;
confirm layouts adapt without truncation/overlap, keyboard/screen-reader navigation works, dates/numbers
are readable, and mirroring is correct for RTL.

**Acceptance Scenarios**:

1. **Given** longer translated strings, **When** rendered, **Then** responsive layouts adapt without
   truncating/hiding critical information (CD-027), consistent with Personalization/A11y (022).
2. **Given** an enabled RTL language, **When** rendered, **Then** the UI mirrors direction correctly
   (layout, navigation, icons as appropriate) while functional meaning is unchanged.
3. **Given** localized dates/numbers, **When** displayed, **Then** they are readable by screen readers and
   meet the accessibility floor; language is exposed to assistive tech where relevant (e.g., content
   language marking).

### Edge Cases

- **Missing translation**: fallback chain renders; UI never breaks; missing keys are observable (via
  Observability 025) for admins, without exposing secrets.
- **Disabled language still used by users**: affected users fall back; their stored preference is retained
  and auto-restored if re-enabled (CD-016 pattern).
- **Plugin without translation for active language**: falls back per portal chain; never breaks.
- **Content only in another language**: shown with a clear fallback + indication; source preserved.
- **Time-zone change during an active campaign**: campaign window is evaluated by absolute instants; the
  change affects rendering, not the campaign's firing instants.
- **Time-zone change affecting an automation**: schedule is evaluated by absolute instants (and its
  reference TZ where wall-clock is intended); no double-fire/skip.
- **DST transition**: windows interpreted by absolute instants; ambiguous/nonexistent local times resolved
  by a defined rule.
- **External content without declared language**: handled by a defined rule (shown as-is, unknown-language
  marked); never discarded (CD-014/026).
- **Mixed-language content**: represented honestly (per-part language where known); not force-translated;
  source preserved.
- **Locale-specific numbers/dates**: representation only; underlying values unchanged.
- **Notification generated immediately after language change**: uses the recipient's language/locale at
  send time per Notifications (010); defined behavior for in-flight content.
- **Deleted/anonymized user**: language/locale/TZ preferences are personal data handled per Privacy (021)
  deletion/anonymization; no language setting resurrects identifying data.
- **Import/export of i18n configuration**: validated and conflict-surfaced via Administration (020);
  historical business data is never rewritten by an i18n config import (CD-011/016).

## Requirements *(mandatory)*

### Functional Requirements

#### Interface Language
- **FR-001**: The portal MUST have a configurable default language and a set of admin-enabled available
  languages (declared via Administration configuration, CD-011).
- **FR-002**: A user MUST be able to set a preferred interface language (offered at onboarding, changeable
  anytime); the choice MUST persist and apply immediately (Users 002 + CD-011).
- **FR-003**: Interface language MUST resolve deterministically: user preference (within enabled
  languages) → portal default → ultimate fallback; a request-derived hint MAY be used only when no
  preference exists and policy allows.
- **FR-004**: When a user's selected language is disabled, the portal MUST fall back per FR-003 without
  breaking, retain the user's original preference, and auto-restore it if the language is re-enabled.

#### Localization (locale) — distinct from language
- **FR-005**: Locale MUST be resolvable independently of language; the system MUST format dates, times
  (12/24h), first day of week, numbers (decimal/thousands separators), units, currency display where
  applicable, and relative times per the user's locale.
- **FR-006**: Changing locale MUST change representation only; underlying stored values MUST be unchanged.
- **FR-007**: Language and locale MUST remain conceptually distinct and independently configurable.

#### Time Zones
- **FR-008**: Absolute instants MUST be stored time-zone-independently (`occurred_at`, per CD-012) and
  rendered in the user's time zone (with a configurable default/system time zone).
- **FR-009**: Scheduled events, campaigns, automations, maintenance, notifications, statistics periods,
  and newsletters MUST fire/aggregate by absolute instants; where a definition intends a wall-clock time,
  it MUST record its reference time zone.
- **FR-010**: DST transitions MUST be handled by absolute-instant evaluation (no double-fire/skip);
  ambiguous or nonexistent local times MUST be resolved by a defined, documented rule.

#### Translation
- **FR-011**: UI strings, error messages, notification/email bodies, administrative content, and system
  pages MUST be translatable with variable interpolation; sentences MUST NOT be built by naive string
  concatenation.
- **FR-012**: Translation MUST support pluralization and required grammatical forms per the active
  language.
- **FR-013**: A missing translation MUST fall back per the fallback chain and MUST NEVER break the UI or
  render empty/broken labels.

#### Multilingual Content
- **FR-014**: Content (News, Wiki, Marketplace products, Community Projects, Campaigns, Notifications,
  Documentation, plugin content) MUST distinguish source language, translated content, untranslated
  content, and multi-language availability.
- **FR-015**: The source language of content MUST be preserved and MUST NOT be overwritten by a
  translation.
- **FR-016**: When a user's preferred language is unavailable for a content item, the portal MUST show a
  defined fallback with a clear indication it is not the user's language (never hide/break).

#### External Services / Connectors
- **FR-017**: Data from external services MUST preserve source content and provenance (CD-014/026); the
  portal localizes presentation (labels/formats) but MUST NOT arbitrarily overwrite externally sourced
  content merely to translate it.
- **FR-018**: Translation of external content MUST be a presentation-layer translation that does not
  modify the stored source value.
- **FR-019**: External content with no declared language MUST be handled by a defined rule (shown as-is
  with unknown-language handling) and MUST NOT be discarded.

#### Search
- **FR-020**: Search (008) MUST be language-aware and diacritics-insensitive, MAY return results across
  languages, MUST indicate a result's language where useful, and MUST apply fallback — all permission/
  privacy bounded. (Matching behavior is defined here; the search engine remains owned by 008.)

#### AI
- **FR-021**: The AI (018) MUST respond in the user's preferred language within the user's permissions,
  handle multilingual context/sources, MAY optionally translate, MUST preserve cited sources' language,
  and MUST fall back by a defined rule (indicating the limitation) when the requested language is
  unsupported.

#### Notifications & Email
- **FR-022**: Notifications and emails (010) MUST use the recipient's language/locale/time-zone with
  localized templates, interpolated variables, and fallback; missing translations MUST NOT prevent
  delivery (fallback content is used).

#### Marketplace / Gamification / Statistics (representation only)
- **FR-023**: Marketplace localization (categories, products, descriptions, conditions, Community
  Projects, price formats) MUST NOT alter historical transactions or business rules (CD-005/006).
- **FR-024**: Gamification localization (levels, achievements, quests, rewards, events, badges, titles,
  related notifications) MUST NOT change the reward engine or rules (CD-004); rules are
  language-independent.
- **FR-025**: Statistics localization (periods, dates, times, numbers, durations, percentages, units,
  chart labels, tooltips) MUST change representation only, never the underlying statistical data (017).

#### Plugins
- **FR-026**: Plugins MUST be able to declare supported languages, available translations, fallback, and
  translatable strings/content via the extensibility model (023).
- **FR-027**: A plugin MUST NOT impose its own global language on the portal or other plugins; it
  participates in the portal's i18n resolution and fallback.

#### Administration (via Configuration, not a new engine)
- **FR-028**: Administration (020/CD-011) MUST be able to configure default language, available/enabled/
  disabled languages, fallback, and default locale/time-zone policies — through the existing configuration
  hierarchy; i18n MUST NOT create a second configuration engine.
- **FR-029**: Admin i18n policy MUST be able to constrain user preferences while retaining the user's
  underlying preference where still permitted (CD-011/016).

#### Accessibility & RTL
- **FR-030**: Localized UI MUST meet the accessibility floor (CD-027 / WCAG 2.2 AA) despite longer
  translated strings, remaining responsive and keyboard/screen-reader operable, with readable localized
  dates/numbers (Personalization/A11y 022).
- **FR-031**: The product MUST support right-to-left (RTL) text direction where an RTL language is enabled,
  mirroring layout/navigation correctly while functional meaning is unchanged. The specific set of RTL
  languages to support is NOT fixed here (see OQ-125) — the capability is required, the language list is a
  product decision.

#### Versioning & Audit
- **FR-032**: Translation/language changes MUST NOT rewrite historical business data (transactions,
  rewards, acceptances, historized events) — representation changes only (CD-004/005/012).
- **FR-033**: The system MUST handle language lifecycle: adding languages, disabling languages, changing
  translated content, and plugins adding/removing language support — with fallback and preference
  retention (FR-004/016/027); historical content versions MUST be preserved per Content/Versioning rules.
- **FR-034**: i18n policy changes (default/enabled languages, fallback, locale/TZ policy) and
  administrative multilingual-content edits MUST be auditable via the existing Audit/Events/Administration
  rules (CD-013); i18n MUST NOT define a separate audit mechanism.

#### Business-rule independence (cross-cutting)
- **FR-035**: Language, locale, and time zone MUST affect representation only and MUST NEVER change
  business rules, permissions, source-of-truth, economy values, statistical data, or historical records.
- **FR-036**: User language/locale/time-zone preferences are personal data and MUST follow Privacy (021)
  for visibility, retention, deletion, and anonymization.

### Resolution Model (how every surface decides language / locale / time zone)

For any user-facing piece of information, the triplet resolves independently:

- **Language**: content's own language if the user prefers it → user preferred language → portal default
  → ultimate fallback (all within admin-enabled languages). Missing string → fallback chain (never break).
- **Locale**: user locale → admin default locale → portal default. Affects formatting only.
- **Time zone**: user time zone → admin/system default. Applied at render to absolute instants.

**Invariants**:
- Language ⟂ Locale ⟂ Time zone (independently resolvable).
- Representation only — never changes business rules, data, permissions, or history (FR-035).
- Fallback never breaks the UI (FR-013); source language preserved (FR-015/017).
- Owners of mechanisms (config, events, notifications, search, AI, etc.) are referenced, not duplicated.

### Cross-Spec Ownership Boundaries (explicit)

- **Administration / Configuration (020, CD-011)**: owns the config system + hierarchy; i18n declares its
  settings into it. i18n does NOT build a config engine.
- **Users / Profiles (002)**: owns the user's stored language/locale/time-zone preferences; i18n defines
  how they resolve.
- **Permissions / Privacy (003/021)**: own authorization and visibility; i18n preferences are personal
  data (021); i18n never alters permissions.
- **Notifications (010)**: owns delivery/templates/channels; i18n defines which language/locale/TZ each
  communication uses. No second notification engine.
- **Events & History (007, CD-012)**: owns instants/idempotency/dedup; i18n renders instants, never
  redefines them.
- **Automations (019, CD-010)**: owns the WHEN/IF/THEN engine; i18n provides language/locale/TZ context,
  not a rules engine.
- **Gamification (013)**: owns rules/economy; i18n localizes labels only (FR-024).
- **Marketplace (015)**: owns products/transactions; i18n localizes presentation only (FR-023).
- **Statistics (017)**: owns data/definitions; i18n localizes representation only (FR-025).
- **Connectors & Services (005/006, CD-014/026)**: own source data/provenance/sync; i18n localizes
  presentation, preserves source (FR-017).
- **Search (008)**: owns search; i18n defines language-aware matching behavior (FR-020).
- **AI (018, CD-003)**: owns AI; i18n defines response-language behavior within permissions (FR-021).
- **Plugins / Extensibility (023)**: own the extension model; i18n defines how plugins declare languages/
  translations (FR-026/027).
- **Accessibility (022, CD-027)**: owns the a11y floor; i18n ensures localized/RTL UI meets it (FR-030/031).
- **Data / Retention (021)**: owns retention/deletion; i18n preferences follow it (FR-036).
- **Versioning**: translation changes never rewrite historical business data (FR-032/033).

### Key Entities

- **Language**: an available human language (enabled/disabled by admin), with a fallback relationship.
- **Locale**: regional formatting conventions (date/time/number/units/first-day-of-week), independent of
  language.
- **Time Zone Preference**: the user/system time zone applied to render absolute instants.
- **Translation / Translation Key**: a translatable UI string with interpolation + plural/grammatical
  forms, resolved via the fallback chain.
- **Localized Content Version**: a per-language version of content with a declared source language and
  translation state (source/translated/untranslated).
- **i18n Policy (in Configuration)**: admin settings (default language, enabled languages, fallback,
  default locale/TZ) stored in Administration's config (CD-011) — not a separate store.
- **Plugin Language Declaration**: a plugin's supported languages/translations/fallback (via 023).
- **User Language/Locale/TZ Preference (referenced)**: personal data owned by Users (002)/Privacy (021).

## Success Criteria *(mandatory)*

For every user-facing piece of information it is determinable: which language, which locale, which time
zone, what happens if translation is missing, which source owns the data, which system owns the config,
and how it interacts with plugins/external services (FR-001..036 + Resolution Model).

### Measurable Outcomes

- **SC-001**: For 100% of user-facing surfaces, the language/locale/time-zone resolution is determinable
  from the Resolution Model.
- **SC-002**: A missing translation breaks the UI (empty/broken label) in 0% of cases (fallback renders in
  100%).
- **SC-003**: Language and locale are independently settable and honored (text in one, formats in the
  other) in 100% of defined mismatch cases.
- **SC-004**: Changing language/locale/time-zone changes business rules, economy values, statistical data,
  permissions, or historical records in 0% of cases (representation-only in 100%).
- **SC-005**: Scheduled campaigns/automations/maintenance/notifications fire at the intended absolute
  instant across viewer time zones and DST transitions in 100% of cases (no double-fire/skip).
- **SC-006**: A disabled language breaks access for affected users in 0% of cases; their original
  preference is retained and auto-restored on re-enable in 100% of cases.
- **SC-007**: External-sourced content is overwritten merely to translate it in 0% of cases; source +
  provenance preserved in 100%.
- **SC-008**: Notifications/emails are delivered in the recipient's language/locale/time-zone with
  fallback in 100% of cases; a missing translation prevents delivery in 0% of cases.
- **SC-009**: A plugin imposes its own global language on the portal in 0% of cases; plugin strings fall
  back cleanly in 100% of missing cases.
- **SC-010**: i18n creates a second configuration engine in 0% of cases (all policy via Administration
  config); i18n creates a second rules/notification/audit engine in 0% of cases.
- **SC-011**: Localized UI (incl. verbose + RTL where enabled) meets the WCAG 2.2 AA floor in 100% of
  defined cases; critical info truncated/hidden by translation length in 0% of cases.
- **SC-012**: Pluralization/grammatical forms are correct for the active language in 100% of defined
  cases; sentences built by naive concatenation in 0% of cases.

## Assumptions

- The configuration system, event/instant model, notification delivery, search, AI, gamification/economy,
  marketplace, statistics, connectors, privacy, extensibility, and accessibility floor are owned by their
  specs (per CANONICAL_DECISIONS §1); i18n defines language/locale/TZ behavior and references them.
- Absolute instants are stored time-zone-independently (CD-012); "render in user TZ" is a presentation
  concern owned here.
- The specific baseline language set, default locale/TZ, and whether any RTL language ships initially are
  admin/product configuration, not fixed in this spec (OQ-125/126).
- "Public" audience means all authenticated members (CD-025); i18n introduces no anonymous-language
  concern beyond the sign-in surface.

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. Genuine product decisions; cross-cutting ones already
resolved in CANONICAL_DECISIONS are referenced, not re-opened.

- **OQ-125 (RTL language set)**: The Blueprint does not state which RTL languages must ship. The RTL
  **capability** is required (FR-031); the **specific language list** is an unresolved product decision —
  recorded here, not invented.
- **OQ-126 (Baseline language set & defaults)**: Confirm the initially shipped languages, the portal
  default language, and default locale/time-zone policy (admin config; product baseline to confirm).
- **OQ-127 (Content translation workflow)**: Confirm whether multilingual content is human-authored
  per-language, machine/AI-assisted, or both, and the review/approval flow for translations (ties to
  Content 011 + AI 018; the storage model is owned here, the workflow is a product choice).
- **OQ-128 (Wall-clock vs absolute scheduling default)**: Confirm, for schedules intended as "9:00 local",
  the default reference time zone and whether per-user local firing is ever intended (vs a single absolute
  instant) — aligns with Automations/Campaigns scheduling.
- **OQ-129 (Unknown-language handling default)**: Confirm the default treatment of content/external data
  with no declared language (assume portal default, mark unknown, or detect) — capability required, policy
  to confirm.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference), the project Constitution
  (v1.0.0), and `decisions/CANONICAL_DECISIONS.md` (owns CD-023; applies CD-002/003/004/005/006/010/011/
  012/013/014/016/025/026/027).
- Composes with (does not re-implement): `002-identity-users` (preference storage), `003-roles-permissions`
  (authz), `005-connectors` (source/provenance), `006-services-health`, `007-events-history` (instants/
  dedup), `008-search-command-palette` (search), `010-notifications` (delivery), `011-content-news-wiki-
  calendar` (multilingual content), `013-gamification-economy`, `014-campaigns` (scheduling), `015-
  marketplace`, `016-support`, `017-statistics`, `018-ai-capability`, `019-automations` (scheduling),
  `020-administration` (configuration owner), `021-privacy-data-lifecycle` (preference as personal data),
  `022-personalization-themes-a11y` (a11y floor / RTL presentation), `023-extensibility` (plugin language
  declarations), `024-media` (source content), `025-observability` (missing-translation observability).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `product/GLOSSARY.md`, `ux/UX_PRINCIPLES.md`, `ux/DESIGN_SYSTEM.md`, `ux/THEMING.md`,
  `features/FEATURE_CATALOG.md` (CORE-017 Internationalization).
- Contradictions check: none found with specs 001–025; this spec closes audit finding **P1** (i18n
  missing) and anchors the former OQ-36/66/81/109 here (per CD-023).
