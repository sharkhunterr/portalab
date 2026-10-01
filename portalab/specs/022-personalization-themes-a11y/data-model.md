# Data Model — Themes & UI preferences

## ui.themes (schema `ui`)
`id` · `key` unique · `name` · `source` (`builtin|admin|marketplace:<product>`) · `definition` jsonb (validated `ThemeDefinition`) · `schema_version` · `version` · `enabled` · `floor_report` jsonb (contrast results at registration) · `created_at` · `updated_at`. Built-ins seeded by migration (light, dark, high-contrast). Never hard-deleted while any user preference references it (disable instead).

## ThemeDefinition (document, not a table)
`tokens` (color roles, typography scale, spacing/density, radii, borders, shadows, motion durations/easings), `state_map` (state → {color role, icon id, label key}), `icons` (set id), `backgrounds`, `sounds` (event → asset ref), `notification_appearance` defaults (position, duration, style). Closed key set; unknown keys rejected.

## User UI preferences (stored in Administration config, user scope — NOT a new table)
`ui.theme`, `ui.density` (`compact|comfortable|spacious`), `ui.textScale` (0.85–2.0), `ui.contrast` (`default|high`), `ui.reducedMotion` (`system|on|off`), `ui.soundEnabled`, `ui.notificationPosition`, `ui.notificationDurationSeconds`, `ui.notificationStyle`, `ui.layoutPresets` (dashboard handled by 009).

## Admin policy (config, global scope)
`ui.allowedThemes[]`, `ui.defaultTheme`, `ui.forceReducedMotion?`, bounds for text scale; policy constrains user values while the stored preference is retained (CD-011).

## Events
`theme.changed` (user), `theme.policy_changed`, `accessibility.preference_changed` — emitted by the preference change path (020) with UI-specific types registered here. Dedup `(user_id, key, change_seq)`.

## Retention / privacy
Preferences are `preference` class personal data (erased/exported by 020's participant); themes are public configuration.
