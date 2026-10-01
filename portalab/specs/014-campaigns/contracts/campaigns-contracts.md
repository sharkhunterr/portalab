# Contracts — Campaigns

## Python capability `capabilities/campaigns`
- **Implements `ModifierProvider`** (013): `modifiers_for(user, event, value, at) -> list[Modifier{source_ref, factor}]` — active campaigns at `at` (activation_log), version in force at `at`, audience match, conditions via `ActivityAttributeProvider`, each modifier at most once per occurrence.
- `ActivityAttributeProvider` Protocol (registered by domains, e.g. 024): `handles(event_type) -> bool`, `attributes(event) -> Attributes{media_kind?, genres[], title?, …} | Unavailable`.
- `CampaignReader`: `is_active(key, at)`, `active_for_user(user, at) -> list[CampaignRef]`, `occurrences(range)`.
- `CampaignContentProvider` (for 013 evaluators): `achievements_active_at(at)`, `quests_active_at(at)` (nested definitions with `campaign_ref`).
- `CalendarSource(kind="campaign")` (011) · `CampaignPresentation.for_user(user, at)` (theme overlay).

## HTTP (`/api/v1`)
| Path | Permission |
|---|---|
| GET `/campaigns/active` · GET `/campaigns/active/presentation` | authenticated (audience-filtered) |
| GET `/campaigns/{key}` (public view of definition: name, window, modifiers summary within audience) | `campaigns.read` |
| GET/POST `/admin/campaigns` · GET/PUT `/admin/campaigns/{id}` (publishes new version) | `campaigns.manage` (sensitive, audited, confirmation on active edits) |
| POST `/admin/campaigns/{id}/activate|deactivate|cancel|archive` (`until`, `reason`) | `campaigns.manage` (sensitive, audited) |
| POST `/admin/campaigns/{id}/simulate` | `campaigns.manage` |
| GET `/admin/campaigns/{id}/history` (versions, occurrences, activation log, overrides) | `campaigns.manage` |
| POST `/admin/campaigns/{id}/announce` (manual broadcast via 010) | `campaigns.manage` + `notifications.broadcast` |
Problem codes: `campaign.invalid_definition`, `campaign.schedule_conflict`, `campaign.not_editable`, `campaign.override_conflict`.

## Frontend
Active-campaign banner/page (audience-aware), admin console: definition stepper (schedule + recurrence preview in tz, modifier/condition builder from closed catalog, theme picker, nested achievements/quests, announcements presets), simulation tool, history timeline; `CampaignPresentationProvider` feeding the 022 theme overlay; widget `campaigns.active` (009).

## Extension point (023)
Plugins may register `ActivityAttributeProvider`s and condition attributes for their event types; no new condition operators.
