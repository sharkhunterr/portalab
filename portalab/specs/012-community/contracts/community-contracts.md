# Contracts — Community

## Ports consumed
`ProgressionReader`, `LeaderboardService`, achievement/quest catalogs (013) · `identity.directory`, `is_active_account` (002) · `VisibilityFilter` (021) · **`ProjectLifecycle`** (015; stub until step 25): `register(proposal_ref, proposer)`, `state(project_ref)`, `accepts_votes(project_ref)`, `funding_summary(project_ref)` · `notifications.send` (010) · `MarkdownRenderer` (011) · `SearchProvider` SDK (008).

## Capability provided
`community.register_profile_section(key, provider, order, permission)` (plugins/modules add sections; each section returns `{state, data}`), `community.register_discovery_shelf(...)`, `CommunityReader.proposal(ref, viewer)` / `vote_count(ref)` for 015/013.

## HTTP (`/api/v1`)
| Path | Permission | Slice |
|---|---|---|
| GET `/community/members?q&cursor` · GET `/community/members/{id}` · GET `/community/members/{id}/sections/{name}` | `community.read` (default grant) + owner visibility | A |
| GET `/community/feed?cursor` | `community.read`; entries filtered per actor visibility | A |
| GET `/community/discovery/{shelf}` | `community.read` | A |
| GET `/community/leaderboards/{metric}?period` · GET `/community/me/position` | `community.read` (delegates to 013 + visibility/opt-out) | B |
| GET `/community/achievements` · GET `/community/quests` | `community.read` (delegates to 013; hidden stay hidden) | C |
| POST `/community/proposals` · GET `/community/proposals[/{id}]` · PATCH (proposer, until votable) · POST `…/withdraw` | create: `community.propose` (default all active); read: `community.read` | D |
| POST `/community/proposals/{id}/vote` · DELETE `…/vote` | **active account invariant** (explicit allow-listed rule, not a role permission) | D |
| POST/DELETE `/community/proposals/{id}/participation` · POST `…/participations/{pid}/recognize` | `community.participate` (default) / proposer or `community.moderate` | D |
| GET `/admin/community/moderation` · POST `…/proposals/{id}/approve|reject` | `community.moderate` (audited) | D |
Problem codes: `community.not_active_account`, `community.voting_closed`, `community.recognition_limit`, `community.self_recognition`, `community.visibility_denied`.
Explicitly **absent**: friends/followers/DM/likes/reactions/chat routes (guarded by a route-table test).

## Frontend
Members directory + profile (independent section frames), activity feed, discovery home, leaderboards page, achievements/quests page (read-only presentation), proposals list/detail (vote button, participation, help-wanted badge, lifecycle state from 015), moderation queue; profile section slots for plugins.
