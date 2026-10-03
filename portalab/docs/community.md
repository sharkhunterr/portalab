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

## Leaderboards (slice B)

`/community/leaderboards` presents 013's leaderboards: metrics, periods, ranking, opt-out (Private) and
visibility all come from the `economy.leaderboards` provider; Community only adds display names. The
viewer's own position is always shown (`GET /api/v1/community/me/position`). When 013 is absent or failing
the view answers `state: "unavailable"` and the page keeps working.

## Achievements and quests (slice C)

`/community/achievements` shows 013's achievements and the viewer's own quests through `economy.catalog` —
Community stores no definition and no reward logic. Hidden achievements reveal nothing (not even a label)
until unlocked; another member's achievements (`GET /api/v1/community/achievements?member=<id>`) list
unlocked ones only, and only when that member's `progression` visibility allows this viewer (404
otherwise). Quests show the viewer's own progress only; challenges are flagged `time_boxed` with their end.

## Proposals, votes and participation (slice D)

* **Proposals** (`community.propose`, active accounts; optionally limited by
  `community.proposals.allowedRoles`): moderation is on by default — a proposal stays
  `pending_moderation`, visible to its proposer and moderators only, until a moderator approves it
  (`community.moderate`, audited, `community.proposal_moderated`). The Markdown body is sanitized (011).
  The proposer may edit until the proposal is open, withdraw it, and ask for help (`help_wanted`).
  A `project` proposal registers its lifecycle in Marketplace (015) and shows the state and public funding
  summary read from there; funding happens in Marketplace's flow (`/projects/{id}`). `project.created` is
  emitted once, when the proposal becomes visible. Support (016) converts feedback through
  `community.proposals.create`, keeping `provenance_ref` (idempotent).
* **Votes** — one free up-vote of support per **active account** (an invariant, not a configurable
  permission; allow-listed in the permission matrix), no minimum level; retract and re-cast while the
  lifecycle accepts votes (idea, proposal, open; `community.voting_closed` otherwise). Counts are public;
  who voted is private (each member sees their own vote). Voting never funds and funding is never a vote.
* **Participation** (`community.participate`) as contributor, tester or helper. The proposer or a
  moderator **recognizes** a participation once (`community.self_recognition`,
  `community.already_recognized`; at most `community.recognition.maxPerDay` per recognizer and one per
  recognizer → member pair every `community.recognition.pairCooldownDays` days —
  `community.recognition_limit`). It emits `community.contribution_recognized` (dedup participation), with
  the recognized member as actor, so a 013 reward rule credits **them**:

```json
{"event_type": "community.contribution_recognized", "grants": [{"value": "contribution", "amount": 10}]}
```

* Proposers, current voters and participants are notified of `project.status_changed`
  (`community.project`, coalesced per project). Discovery shows `projects` (open proposals, those asking
  for help first); the dashboard widget `community.projects` lists them too.
* Erasure removes votes (counts decremented), withdraws participations and detaches the proposer; the
  proposal content stays with the community.

## Settings

`community.feed.eventTypes`, `community.feed.retentionDays`, `community.members.listingDefault`,
`community.proposals.moderation`, `community.proposals.allowedRoles`, `community.recognition.maxPerDay`,
`community.recognition.pairCooldownDays`, `community.discovery.shelfSize`.

## API

| Path | Access |
|---|---|
| `GET /api/v1/community/members?q&cursor&limit` | `community.read` + `member_listing` |
| `GET /api/v1/community/members/{id}` · `GET …/sections/{name}` | `community.read` + each section's datum |
| `GET /api/v1/community/feed?cursor&limit` | `community.read` + actor visibility at read time |
| `GET /api/v1/community/discovery` · `GET …/discovery/{shelf}` | `community.read` |
| `GET /api/v1/community/events[?start&end]` · `GET …/events/{id}` | `community.read` + audience |
| `POST /api/v1/community/events` · `PATCH …/{id}` · `POST …/{id}/cancel` | `community.events.manage` |
| `GET|POST /api/v1/community/proposals` · `GET|PATCH …/{id}` · `POST …/{id}/withdraw` · `PUT …/{id}/help` | `community.read` / `community.propose` (slice D) |
| `POST|DELETE /api/v1/community/proposals/{id}/vote` | active-account invariant (`community.read` + active account) |
| `GET …/{id}/participations` · `POST|DELETE …/{id}/participation` · `POST …/participations/{pid}/recognize` | `community.read` / `community.participate` (proposer or moderator to recognize) |
| `GET /api/v1/admin/community/moderation` · `POST …/moderation/proposals/{id}/approve|reject` | `community.moderate` (audited) |
| `GET /api/v1/community/achievements[?member]` · `GET /api/v1/community/quests` | `community.read`; delegated to 013 (slice C) |
| `GET /api/v1/community/leaderboards` · `GET …/leaderboards/{metric}?period` · `GET /api/v1/community/me/position` | `community.read`; delegated to 013 (slice B) |

## Slice map

| Slice | Roadmap step | Content |
|---|---|---|
| A | 22 | directory, profiles, feed, discovery, community events, widget `community.activity` |
| B | 23 | leaderboards view (013 slice B) |
| C | 24 | achievements and quests display (013 slice C) |
| D | 25 | proposals, votes, participation and recognition, moderation, lifecycle display (015) |
