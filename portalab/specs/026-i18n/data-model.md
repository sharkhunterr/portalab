# Data Model — i18n (schema `i18n`)

## i18n.languages
`code` (BCP-47, PK) · `name_native` · `name_en` · `direction` (`ltr|rtl`) · `fallback_code` nullable FK→languages · `source` (`builtin|plugin:<id>|admin`) · `created_at`. **Enablement is NOT stored here** — it is `i18n.enabledLanguages` in 020 (CD-011). Rows are never deleted while referenced by preferences, catalogs or content versions (disable via config).

## i18n.catalog_entries (admin-managed overrides + admin-authored strings)
`id` · `namespace` · `key` · `language` FK · `message` (ICU) · `state` (`draft|published|deprecated`) · `catalog_version` int · `updated_by` FK `identity.users(id)` · `updated_at`. Unique `(namespace, key, language)`. Base (file) bundles are not in the DB. Validation at write: ICU syntax + placeholder parity with the source language.

## i18n.catalog_versions
`namespace` · `language` · `version` (content hash) · `published_at`. Used for ETag and invalidation.

## i18n.localized_content_versions (generic registry used by content domains)
`id` · `content_kind` · `content_id` · `language` FK · `source_language` FK · `state` (`source|translated|untranslated|machine_draft`) · `translation_of_version` nullable · `version` · `created_at`. Unique `(content_kind, content_id, language, version)`. **Source rows immutable.** Content text itself stays in the owning module's table (the registry holds language/state linkage only) — an i18n helper is provided for those modules' per-language tables.

## i18n.missing_key_stats (aggregate, bounded)
`namespace` · `language` · `key` · `count` · `first_seen_at` · `last_seen_at` — aggregated, pruned by retention; PII-free. Also exported to Observability.

## Reference data (not tables)
CLDR (Babel-bundled) and IANA tz (`tzdata`) — pinned dependency versions; updates are dependency bumps with regression tests.

## Settings declared into 020 (CD-011)
Global: `i18n.defaultLanguage` (`en`), `i18n.enabledLanguages`, `i18n.fallbackChain`, `i18n.defaultLocale`, `i18n.defaultTimeZone` (`UTC`), `i18n.unknownLanguagePolicy` (`show_as_is`), `i18n.ambiguousTimePolicy` (`gap_forward|overlap_earlier`), `i18n.schedulingDefault` (`absolute`). User: `language`, `locale`, `timeZone`, `hourCycle`, `firstDayOfWeek` (constrained by policy; preference retained).

## Events (via 007)
Produced: `i18n.policy_changed`, `i18n.translation_updated`, `i18n.language_added|disabled` (registry). Dedup `(namespace, language, catalog_version)` / `(config_change_id)`. Consumed: `admin.config_changed` (i18n.* + user locale keys), `plugin.state_changed` (catalog registration).

## Privacy / retention
User language/locale/tz = `preference` personal data (erased/exported by 020 participant per 021); catalogs/languages public configuration; no PII in keys/stats. Catalog entry edits audited via `AuditSink`.
