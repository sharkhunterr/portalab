# Campaigns (spec 014)

A **campaign** is a time-bound themed context ("Halloween", "Spooky week") — not a domain event (CD-009). It
contributes **multiplier factors** to Gamification, campaign-scoped achievements, a theme overlay and
calendar entries. It never grants anything itself.

## Definition (closed schema)

```json
{
  "names": {"en": "Halloween", "fr": "Halloween"},
  "timezone": "Europe/Paris",
  "schedule": {"start_at": "2026-10-20T00:00:00", "end_at": "2026-11-01T00:00:00",
               "recurrence": {"kind": "yearly", "count": 5}},
  "modifiers": [
    {"id": "horror_xp", "value": "xp", "factor": 2, "when": {"media_kind": ["movie"], "genre": ["horror"]}},
    {"id": "title_xp", "value": "xp", "factor": 2, "when": {"title_contains": ["halloween"]}},
    {"id": "vip", "value": "coins", "factor": 1.5, "when": {"audience": {"kind": "roles", "roles": ["vip"]}}}
  ],
  "achievements": [{"key": "night_watcher", "definition": {"label": "Night watcher",
      "criteria": [{"kind": "event_count", "event_type": "media.playback_finished", "count": 5}],
      "rewards": [{"value": "coins", "amount": 50}]}}],
  "theme": {"theme_key": "pumpkin", "presentation_priority": 10},
  "ending_soon_hours": 24
}
```

Unknown fields, operators or expressions are rejected (`campaign.invalid_definition`); sizes and nested
definitions are bounded; the theme must exist in the 022 catalog (`ui.theme_catalog`).

## Schedule semantics

* Times are **wall clock in the campaign's time zone**, resolved through 026's DST policy (a time inside the
  spring gap moves forward; an ambiguous autumn time is the earlier one).
* Recurrence: `none`, `yearly` (Feb 29 → Feb 28 in common years) or `custom` (`every` N `days|weeks|months`;
  month-end anchors clamp to the last day). `count` occurrences are materialized ahead.
* The reconciler (`campaigns.reconcile`, every minute) opens and closes **activation intervals**. A boundary
  caught within tolerance is logged at its exact scheduled instant; after downtime the actual repair time is
  logged; an interval always closes at the scheduled end at the latest.
* `campaigns.activation_log` is the authoritative, append-only history: closed `[opened, closed)` ranges
  with an exclusion constraint against overlaps. Eligibility of any occurrence is "an interval contains its
  `occurred_at`", so late and duplicate events resolve identically, even after the campaign ended.
* Lifecycle events: `campaign.created|version_published|started|ending_soon|ended|paused|resumed|
  cancelled|archived` — each boundary event is emitted once (dedup per occurrence).

## Manual overrides

`POST /admin/campaigns/{id}/activate|deactivate` (reason + confirmation, audited): *activate* wins until the
end of the current occurrence (or `until`; outside a window `until` is required); *deactivate* wins until the
next scheduled start (or `until`) — the campaign shows **paused** within its window. The schedule then
resumes automatically. An override of the same kind already in force is a conflict
(`campaign.override_conflict`); an opposite one replaces it. `cancel` ends the campaign and cancels planned
occurrences; `archive` hides an ended campaign.

## Versions

Every edit publishes an append-only version effective now (confirmation required while active). The version
**in force at an occurrence's time** decides the modifiers; grants carry `campaign:<key>:<version>:<modifier>`
in their modifier records, so history is never rewritten. `GET /admin/campaigns/{id}/history` lists
versions, occurrences, intervals and overrides; `POST …/simulate` runs a sample occurrence through the real
resolver and conditions without writing anything.

## Conditions (closed catalog)

| Condition | Meaning |
|---|---|
| `activity` | the event type is one of these |
| `media_kind` | normalized media kind (`movie`, `series`, `book`…) |
| `genre` | canonical genre tags (case/diacritics-insensitive) |
| `title_contains` | NFKC + casefold + diacritics-insensitive substring of the effective or original title |
| `audience` | `all` · `roles` · `users` · `level_range` (via `gamification.progression`) |

All conditions of a modifier must hold. Attributes come from `activity.attributes` providers (Media 024
ships one; plugins may register theirs — no new operators). When a needed attribute is unknown or the
provider is unavailable, the modifier is **not applied** and `campaigns.attribute_failures` counts it.

## Combination with Gamification (CD-024)

Campaigns implements `economy.modifiers`: for an occurrence it returns one factor per matched modifier with
its reference — **never amounts**. Gamification multiplies the rule multiplier and every campaign factor,
caps the product at `economy.maxTotalBoost`, and still applies cooldowns, caps, diminishing returns and the
anomaly guard. One grant per occurrence and rule (idempotency).

## Achievements, theme, calendar, announcements

* Campaign achievements are offered to Gamification through `economy.definition_sources` (key
  `<campaign>.<achievement>`) only while the campaign is active; unlocking and rewards happen in the ledger.
* `GET /campaigns/active/presentation` returns the campaigns that concern the user and the overlay theme:
  highest priority, allowed by the 022 policy, unless the user chose `ui.campaignThemes = ignore`; the SPA's
  `ThemeProvider` keeps high contrast and the accessibility floor above it.
* `CalendarSource(kind="campaign")` (011), `campaigns.reader` (009 widget condition `campaign_active`, 017
  unlocks) and the `campaigns.active` dashboard widget.
* Announcements: configurable ones are Automations (019) reacting to `campaign.started|ending_soon|ended`
  with the notification action; before 019, `POST /admin/campaigns/{id}/announce` sends a manual broadcast
  (needs `notifications.broadcast`, audited).

## Recorded deviations (T032)

* Boundaries are handled by the per-minute reconciler only (no one-shot `run_at` jobs); intervals are
  logged at the exact boundary when caught within tolerance.
* Audiences support all / roles / users / level range; group audiences wait for a groups read port.
* `ui.theme_catalog` (allowed theme keys) was added to 022 and `economy.modifiers` now receives the full
  occurrence (`modifiers_for(user, event, value, at)`), as the 014 contract requires.
* Campaign quests are stored and exposed (`quests_active_at`) for 013 Slice C (step 24).
