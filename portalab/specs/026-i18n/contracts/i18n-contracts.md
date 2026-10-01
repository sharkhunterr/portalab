# Contracts — i18n

## Python capability `capabilities/i18n` (consumed by all modules)
- `LocaleContext(language, locale, time_zone, direction, fallback_chain, hour_cycle, first_day_of_week)` — immutable value object.
- `LocaleResolver.resolve(request=None, user_id=None) -> LocaleContext` (deterministic, side-effect-free; chain: user preference ⊂ enabled → portal default → hard default `en`/`UTC`; language ⟂ locale ⟂ tz resolved independently).
- `MessageRenderer.t(key, ctx, vars=None, namespace=…) -> str` (ICU; fallback chain; missing ⇒ fallback value + stat, never raises).
- `Formatter.date|time|number|unit|currency|relative(value, ctx)`; `TimeRenderer.render_instant(utc, ctx)`, `resolve_wall_clock(local_dt, tz, policy) -> aware datetime`.
- `ContentLocalizer.get(content_kind, content_id, ctx) -> LocalizedContent{version, language, state, is_fallback}`; `register_version(...)`.
- `normalize_for_search(text, language) -> str` (consumed by 008); `ResponseLanguage.for_user(user_id)` (consumed by 018); `RecipientLocale.for_user(user_id)` (consumed by 010).
- `TranslationProvider` port (optional, none by default).
- **Ports implemented by 020**: `UserLocalePreferenceReader.get(user_id)`, `I18nPolicyReader.get()`.
- **Plugin hook**: manifest `i18n: {languages, catalogs, fallback}` registered through `register_plugin_catalog(plugin_id, bundle)`; plugin cannot change portal default language.

## HTTP (`/api/v1`)
| Path | Permission |
|---|---|
| GET `/i18n/context` | authenticated (self) → `LocaleContext` |
| GET `/i18n/languages` | authenticated (enabled languages with native names, direction) |
| GET `/i18n/catalogs/{namespace}?lang=` | authenticated; ETag = `catalog_version`; no secrets |
| GET/PUT `/admin/i18n/catalog-entries` | `i18n.manage` (audited) |
| GET `/admin/i18n/health` | `i18n.manage` (missing keys/fallback-rate) |
| GET `/i18n/content/{kind}/{id}?lang=` | the content domain's read permission (delegated) |
Policy changes go through 020 (`PUT /admin/config`) with `i18n.manage`. Problem codes: `i18n.invalid_message`, `i18n.placeholder_mismatch`, `i18n.language_unknown`.

## Frontend (`frontend/src/i18n`)
`<I18nProvider>` (fetches context + catalogs, sets `<html lang dir>`, exposes `useLocaleContext()`), `useT()`/`<T/>`, `useFormat()`, direction provider consumed by design system (022), per-route namespace loading, pseudo-locale support in dev.

## Tooling
`portalab i18n check|extract|pseudo` (backend) and `npm run i18n:check` (frontend) — ICU validity, placeholder/plural parity, unused/missing keys, bundle hash.
