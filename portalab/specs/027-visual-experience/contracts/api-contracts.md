# API Contracts: Visual Experience (027)

All routes are under `/api/v1`, authenticated, permission-checked server-side exactly as today. Errors are
RFC 9457 problem documents (`code` extension). Only **changed or new** contracts are listed.

## Navigation

### `GET /me/navigation` (changed — additive)
`AUTHENTICATED`; ETag / 304 unchanged.

```jsonc
{
  "version": "…", "degraded": false,
  "sections": [
    { "key": "support", "label_key": "nav.section.support", "icon": "life-buoy",
      "audience": "everyone", "direct": false,
      "entries": [ { "key": "support.tickets", "label_key": "nav.support.tickets", "icon": "ticket",
                     "route": "/support/tickets" } ] },
    { "key": "admin", "label_key": "nav.section.admin", "icon": "shield", "audience": "administration",
      "direct": false, "entries": [],
      "topics": [ { "key": "access", "label_key": "nav.topic.access", "entries": [ … ] } ] }
  ],
  "personal": [ { "key": "identity.account", … } ],
  "groups": [ … ]            // deprecated alias of 004 shape, removed in the next release
}
```
Guarantees: sections with no permitted entry are absent; `direct` only when exactly one entry and no
topics; `personal` holds section `me`; an authorization failure returns `degraded: true` with empty
sections (never more rights).

### `GET /admin/shell/layout` / `PUT /admin/shell/layout` (changed — additive)
`shell.manage`. Body gains `section_labels: {section_key: label_key}` (rename within existing i18n keys)
and accepts section keys in `group_order` / `groups_of`; unknown section or entry keys ⇒ 422
`shell.unknown_keys` (unchanged behavior). Response lists `sections` (registered keys) besides `entries`.

### Contribution declaration (capability, not HTTP)
`register_section({key, owner, label_key, icon, order_hint, audience, topics?, default_for?})` and
`register_contribution({... "group": "<section>", "topic": "<topic>"?})`. Plugins: sections must be
`plugin-<key>`; their navigation still requires a permission.

## Dashboard

### `GET /dashboard` (changed — additive)
Each instance gains `x`, `y` (desktop grid coordinates); `position` remains (derived reading order).

### `PUT /dashboard/arrangement` (new; replaces `PUT /dashboard/layout`, which stays as a deprecated alias
that flows the given order)
`SELF` (same guard as the existing `PUT /dashboard/layout`: the authenticated owner of the dashboard); header `If-Match: <layout_version>`.

```jsonc
// request
{ "items": [ { "id": "0190…", "x": 0, "y": 0, "w": 6, "h": 2 },
             { "widget_key": "gamification.progress", "x": 6, "y": 0, "w": 3, "h": 2 } ] }   // new instance
// 200
{ "layout_version": 12, "items": [ { "id": "…", "x": 0, "y": 0, "w": 6, "h": 2, "position": 0 }, … ] }
```
Server: validates every widget against the registry and policy (locked/mandatory/disabled — 009 R5/R6),
bounds (`0 ≤ x`, `x + w ≤ 12`, size limits), resolves overlaps and compacts upward with the shared
algorithm, recomputes `position`, returns the stored arrangement. Errors: 409 `dashboard.version_conflict`,
422 `dashboard.invalid_arrangement` (`extensions.items` = offending ids), 403 `dashboard.policy_locked`
(`extensions.widget`, `extensions.reason`). Omitted active instances are **not** removed (removal stays
`DELETE /dashboard/widgets/{id}`); hide/show stays `PATCH`.

### `PATCH /dashboard/widgets/{id}` (changed — additive)
Body accepts `x`, `y` in addition to `w`, `h`, `status`, `config`; same validation + compaction.

### `POST /dashboard/widgets` (changed — additive)
Optional `x`, `y`; when absent the widget is placed at the first free position (top-left scan).

### `PUT /admin/dashboard/starter` (changed — additive)
Starter items accept optional `x`, `y`.

## Progression (live)

### SSE `GET /stream` — new topic `progression.changed`
```
event: progression.changed
data: {"xp": 1240, "level": 4, "level_floor": 1000, "next_level_at": 1600, "coins": 135,
       "reserved_coins": 0, "delta_xp": 40, "delta_coins": 5, "level_up": false}
```
Audience: the affected user only. Emitted once per committed ledger transaction affecting XP or Coins.

## Themes

### `POST /admin/ui/themes`, `PATCH /admin/ui/themes/{key}`, `POST /admin/ui/themes/check`,
### `GET /admin/ui/themes/{key}/floor-report` (changed — schema v2)
Accept `schemaVersion` 1 or 2 (1 upgraded with defaults); v2 vocabulary in `data-model.md` §5. Unknown
layout/motion values ⇒ 422 `theme.invalid` with the JSON path; floor failure ⇒ 422
`theme.floor_violation` (report includes `deviceClass` and `surface: "glass-fallback"` where relevant).

### `GET /ui/themes` (existing) returns `family` and `colorScheme` for each enabled theme.

### Preferences `GET/PATCH /me/preferences`
New user-tier keys `ui.colorMode`, `shell.navigation.expanded`, `shell.welcome.dismissedAt` (validated
by their declarations; policy-locked values ⇒ 403 as today).
