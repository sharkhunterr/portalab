# Community (spec 012)

Community is a **composition layer**: it owns surfaces — the members directory, profiles, the activity feed,
discovery shelves and community events (proposals, votes and participation arrive in slice D) — and **no
engine**. Progression, achievements, leaderboards and quests stay with Gamification (013); project
lifecycle and funding with 015.

## Non-goals (guarded)

There is deliberately **no** friends or followers graph, no direct messages, no likes, reactions or
comments, and no chat. `tests/security/community/test_non_goals.py` fails the build if any OpenAPI path or
`community` table/column carries such an artifact (the 018 assistant's own conversation messages are the
only allow-listed path: a user talking to the AI, not to another user). Chat, if ever wanted, is a
**plugin-only** extension point: a plugin may add a profile section or a discovery shelf, never a core
messaging surface.

## Visibility model

Every surface authorizes first (`require(community.read)`, granted to users by default) and then asks the
021 `VisibilityFilter` about each member's data — a permission alone never reveals Private data, for Admins
and moderators too.

| Datum class (owner) | Default | Governs |
|---|---|---|
| `member_listing` (community) | Community | appearing in the directory, member search and the profile's identity section |
| `community_activity` (community) | Community | feed entries (projection **and** read time) and the profile's activity section |
| `projects` (community) | Community | the projects section (slice D) |
| `votes` (community) | Private | which projects a member voted for (slice D) |
| `progression` (gamification) | Private | the progression and achievements sections |

Levels: Public ⊃ Community ⊃ Leaderboards-only (shown on leaderboards only) ⊃ Private. A section the viewer
may not see is **absent**, not "hidden"; a profile with nothing visible answers 404, like an unknown or
non-Active account. Members choose their levels in Privacy (020/021); Community provides the owner-held
preferences for its classes (`privacy.visibility_preference`).

## Profile sections

```python
from portalab.capabilities.community import ProfileSection, SectionResult, register_profile_section

async def badges(owner: UUID, viewer: Principal) -> SectionResult:
    return SectionResult("available", {"items": [...]})   # or "no-data" | "unavailable" | "stale"

register_profile_section(ProfileSection("plugin:acme.badges", "plugin:acme", "progression", badges, order=60))
```

Built-in sections: `identity`, `progression`, `achievements`, `activity`, `projects` (empty until slice D).
Each section is computed independently with a time budget: a failing or slow provider makes **that**
section `unavailable` and never breaks the page. The frontend renders known keys with a dedicated view and
any other section as plain values (`registerSectionView(key, View)` adds a view) — never server markup.

## Discovery shelves and search

`register_discovery_shelf(DiscoveryShelf(key, owner, provider, order, label_key, empty_action))`. Built-in:
`new_members`, `recent_unlocks`, `activity_highlights` — each uses the same visibility as its source
surface; an empty shelf offers `empty_action`. A failing shelf answers `unavailable` alone. Member search is
the 008 `SearchProvider(kind="member")`, scoped at source by `community.read` and `member_listing`.

Both registries are owner-tagged: `unregister(owner)` removes every contribution of a disabled plugin.

## Activity feed

The `community.feed` consumer projects domain events listed in `community.feed.eventTypes` (default
`achievement.unlocked`, `user.level_up`, `quest.completed`, `project.created`) **only** when the event
type's 007 visibility class is `public` or `community` and the actor currently allows
`community_activity`. Entries keep ids and scalar parameters, a localization key
`community:feed.<type>` and the source event id; projection is idempotent on `source_event_id`. Visibility
is checked again at read time, so a member turning Private disappears at once. Entries are kept
`community.feed.retentionDays` (180) days and erased with the member.

## Community events

Moderators/Admin (`community.events.manage`, audited) create, edit and cancel events: title, sanitized
Markdown description (011 renderer), start/end or all-day, reference time zone and an audience — `public`,
`community` (signed-in members) or `roles`. `community.event_created|updated|cancelled` are emitted once per
version. The 011 Calendar shows them through `CalendarSource(kind="community_event")`; reminders re-check
the event at fire time, so a cancelled or no-longer-permitted event is never announced.

## Settings

`community.feed.eventTypes`, `community.feed.retentionDays`, `community.members.listingDefault`,
`community.proposals.moderation`, `community.recognition.maxPerDay`,
`community.recognition.pairCooldownDays`, `community.discovery.shelfSize`.

## API (slice A)

| Path | Access |
|---|---|
| `GET /api/v1/community/members?q&cursor&limit` | `community.read` + `member_listing` |
| `GET /api/v1/community/members/{id}` · `GET …/sections/{name}` | `community.read` + each section's datum |
| `GET /api/v1/community/feed?cursor&limit` | `community.read` + actor visibility at read time |
| `GET /api/v1/community/discovery` · `GET …/discovery/{shelf}` | `community.read` |
| `GET /api/v1/community/events[?start&end]` · `GET …/events/{id}` | `community.read` + audience |
| `POST /api/v1/community/events` · `PATCH …/{id}` · `POST …/{id}/cancel` | `community.events.manage` |

## Slice map

| Slice | Roadmap step | Content |
|---|---|---|
| A | 22 | directory, profiles, feed, discovery, community events, widget `community.activity` |
| B | 23 | leaderboards view (013 slice B) |
| C | 24 | achievements and quests display (013 slice C) |
| D | 25 | proposals, votes, participation and recognition, lifecycle display (015) |
