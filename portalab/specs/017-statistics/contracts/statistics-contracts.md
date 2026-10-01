# Contracts — Statistics

## Python capability `capabilities/statistics`
- `StatisticsProvider.get(stat_key, *, subject: SubjectRef, period: Period, filters, viewer: Principal) -> StatResult{state: available|partial|stale|locked|unavailable|insufficient_data|no_data, as_of, series|value, trend?{delta, direction, previous_period}, unlock_hint?, source_states[], definition_version}` — the single authoritative read path; enforces permission, privacy, unlock, cohort thresholds.
- `StatisticsProvider.catalog(viewer) -> list[CatalogEntry]` (available, locked-with-hint; hidden/disabled excluded).
- `Period` = `{kind: day|week|month|quarter|year|last_n_days|custom, start?, end?}` resolved with the statistics tz/first-day-of-week (deterministic).
- Ports consumed: `ProgressionReader` (013), `EntitlementReader` (015), `CampaignReader` (014), `health.service_state` (006), `notifications.send` (010), `VisibilityFilter` (021).
- Definition packs: `register_definition_pack(domain, pack)` (modules/plugins; plugin packs install inactive).
- Event field registry: 007 event types mark fields `aggregatable` (+ type, unit).

## HTTP (`/api/v1`)
| Path | Permission | Notes |
|---|---|---|
| GET `/statistics/catalog` | `statistics.read` (default grant) | filtered by permission/unlock; locked entries show hint only |
| GET `/statistics/{key}?subject=&period=&filters=` | `statistics.read` + definition permission | `StatResult`; subject defaults to self; other subjects only if visibility allows |
| GET `/me/statistics/preferences` / PUT | `users.self.manage` | hidden sections (only hideable) |
| GET `/me/wrapped`, GET `/me/wrapped/{id}` | `users.self.manage` | owner only |
| GET `/wrapped/community/{period}` | `statistics.read` | thresholds applied |
| GET/POST/PUT `/admin/statistics/definitions[/{key}]` · POST `…/{key}/activate|retire|rebuild` | `statistics.manage` (audited; rebuild sensitive + confirmation) | schema validation, versioning |
| GET/PUT `/admin/statistics/wrapped` · POST `…/generate` | `statistics.manage` | |
| GET `/admin/statistics/status` | `statistics.manage` | projection lag, rebuilds |
Problem codes: `statistics.unknown`, `statistics.locked`, `statistics.invalid_definition`, `statistics.period_invalid`, `statistics.too_many_buckets`.

## Frontend
`<StatisticsPage>` (catalog, period picker, filters, hide controls), `<StatChart>` (Recharts + a11y table/summary), `<StatCard>`, `<WrappedStory>`, widget bridge `statistics.card` registered with the 009 widget registry (data via `StatisticsProvider`).
