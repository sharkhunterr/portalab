# Contract: Household API (`/api/v1/household`, permission `users.self.manage`)

| Method & path | Who | Body → answer |
|---|---|---|
| GET `/session` | any household member | → `{enabled, owner_id, active_id, must_choose, members[{id, display_name, kind, color, has_avatar, has_pin, needs_pin}]}` |
| POST `/switch` | any | `{user_id, pin?}` → `{active_id}`; 403 `household.wrong_pin`, 429 `household.pin_throttled` (`retry_after`), 404 `household.member_not_found` |
| GET `` | any | → `{enabled, owner_id, me, can_manage, max_profiles, palette, totals, members[… progress, community_visible, restrictions?]}` (restrictions: to the master and to the profile itself) |
| POST `/profiles` | master | `{display_name, kind, color?, pin?}` → 201 `{id}`; 409 `household.limit` |
| PATCH `/profiles/{id}` | master | `{display_name?, color?, kind?, restrictions?, community_visible?, position?}` → 204 |
| DELETE `/profiles/{id}` | master | → 204 (deletion at once, its sessions revoked) |
| PUT `/members/{id}/pin` | master (any member), profile (itself, with `current`) | `{pin|null, current?}` → 204 |
| GET `/profiles/{id}/activity` | master (or the profile) | → `{last_seen_at, economy[], requests[]}` |
| GET `/requests` | master: all; profile: its own | → `[AccessRequestOut]` |
| POST `/requests` | profile | `{kind: "media", ref, title, rating?, note?}` → `{id, status, created}` |
| POST `/requests/{id}/decision` | master | `{approve, days?}` → 204; 409 `household.request_answered` |

Profiles get `household.owner_only` (403) on management routes and on `/me/password`, `/me/mfa*`,
`/me/sessions*`, `/me/deletion*`, `/me/export*`, `/auth/oidc*`. A title above a profile's age answers
`household.restricted` (403, extensions `object_id`, `name`, `rating`). `GET /api/v1/me` gains `profile_of`
and `household_profiles`. Notifications: category `identity.household`, templates `household:notify.request`,
`household:notify.approved`, `household:notify.denied`.
