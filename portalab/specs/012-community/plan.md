# Implementation Plan: Community

**Branch**: `012-community` | **Date**: 2026-10-01 | **Spec**: `specs/012-community/spec.md`
**Roadmap**: **Slice A** = Phase 7 step 22 *Community* (members, profiles, activity feed, discovery, non-goal guards); **Slice B** = step 23 *Leaderboards* (presentation of 013); **Slice C** = step 24 *Quests / Challenges* (presentation of 013); **Slice D** = step 25 *Community Projects / Funding* (proposals, votes, participation, help, recognition — paired with the 015 lifecycle/funding slice).

## Summary
Module `community` is a **composition layer**: per-viewer profile sections, a members directory, a derived activity feed, discovery shelves and presentation pages for leaderboards, achievements, quests and challenges, plus the Community-owned parts of projects — **proposals, votes, participation, recognition** — while Gamification (013) owns values/rankings/rewards, Marketplace (015) owns the project lifecycle and funding (CD-008), Identity (002) owns identity data and Privacy (021) owns visibility. It builds **no friends/followers/DM/likes/chat** (guarded by tests); chat can only arrive as a plugin.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: none · **Storage**: schema `community` · **Testing**: pytest real PG (visibility matrix, vote concurrency), route-table non-goal test, Vitest, Playwright + axe · **Constraints**: no Private data exposed by permission alone, votes free and independent of funding, active-account invariant for voting, sections degrade independently · **Scale**: community scale (≤ 10⁴ members, ≤ 10³ proposals).

## Constitution Check — PASS
I Product integrity (locked non-goals, vote/funding separation) · II/XX no engine re-implementation (013/015 own rewards/funding) · III plugin sections/chat via extension · VI/VII visibility and privacy (CD-016) · IX per-section degradation · XI/XII accessible surfaces. No violations.

## 1. Architecture
```
Viewer ─GET profile─▶ ProfileAssembler ─▶ sections[identity(002) | progression(013) | achievements(013) | activity(feed) | projects | plugin slots]
                          └ each ─▶ VisibilityFilter(owner pref × viewer) ─▶ {state, data}  (independent failure)
Events(007) ─▶ FeedProjector (allow-list, idempotent, Private actors skipped) ─▶ feed_entries ; read-time visibility re-check
Leaderboards/Achievements/Quests pages ─▶ 013 services (read) ─▶ presentation (opt-out/hidden rules from 013/021)
Proposals ─▶ ProposalService ─register─▶ ProjectLifecycle port (015) ; Votes ─▶ VoteService (active-account invariant, accepts_votes? , counter) ; Participation ─▶ Recognition ─event─▶ 013 reward rule
Discovery ─▶ shelves + SearchProviders(members, proposals) ; Admin/mod ─▶ moderation queue
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `MembersService` | directory listing within visibility | `identity.directory`, 021 | API/provider | Active only; visibility ≥ Community | privacy matrix |
| `ProfileAssembler` + section registry | per-viewer independent sections | sections providers | API | permission alone never reveals Private | per-section tests |
| `FeedProjector` / `FeedService` | project allow-listed events, read-time filtering | 007, 021 | consumer/API | idempotent; Private skipped; no reactions | projection tests |
| `LeaderboardView` / `AchievementsView` / `QuestsView` | presentation of 013 data | 013 ports | API | no re-definition; hidden stay hidden | delegation tests |
| `ProposalService` | create/edit/withdraw, optional moderation, lifecycle registration | 015 port, renderer | API | state from 015 only | proposal tests |
| `VoteService` | cast/retract/re-cast, counts, eligibility | `is_active_account`, `accepts_votes` | API | one active vote; free; no min level; independent of funding | concurrency/eligibility tests |
| `ParticipationService` + `Recognition` | participate, recognize once, limits, event | 013 (via event) | API | no self-recognition; per-day and pair limits | abuse tests |
| `ModerationService` | optional proposal moderation | authz | API | audited | moderation tests |
| `Discovery` + providers | shelves, search providers | 008 | API | visibility-bound; next-action empty states | discovery tests |
| Non-goal guard | route/schema scan for forbidden features | OpenAPI | CI test | fails build on match | guard test |
| Frontend | pages and slots | 022/004 | components | accessible; independent states | a11y/e2e |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/community-contracts.md`

## 5. Events
Produced: `project.created`, `project.vote_added|vote_retracted`, `project.participation_added|withdrawn`, `community.contribution_recognized`, `community.proposal_moderated` (ids/counters only; dedup per data-model). Consumed: feed allow-list events (013, 016, 011 etc.), `project.status_changed|funding_added` (015 → feed + notifications to proposer/voters/participants through 010 with coalescing), account state events (voting eligibility), erasure participant. All consumers idempotent; ordering by `occurred_at`.

## 6. Permissions & Security
`community.read` (default grant) + owner visibility; `community.propose` and `community.participate` (default grants; configurable); **voting is an invariant of Active accounts** (explicit allow-list entry in the route-table test, not a role permission); `community.moderate` (moderator/Admin, audited); recognition by proposer or moderator only. Voter identities never exposed. All Markdown through the shared sanitized renderer. Manual Contribution grants are 013's (marked, audited).

## 7. Configuration — `data-model.md` settings (declared into 020).

## 8. External Integrations — none.

## 9. Error Handling & Resilience
Gamification/Economy/015 down ⇒ that block `unavailable`/`stale`, rest of page renders · lifecycle port absent ⇒ proposals open for votes, funding hidden · feed projector failure ⇒ quarantine/retry via 007, stale feed flagged · visibility service failure ⇒ fail closed (hide) · duplicate vote requests ⇒ idempotent · deleted/suspended voter ⇒ vote retained or removed per 021, counts consistent.

## 10. Observability
Feed lag, vote/proposal rates, recognition-limit hits, section failure rates; registers `community` with 025 (functional: feed projector lag within threshold).

## 11. Testing Strategy
Visibility matrix (owner/viewer/Public/Community/Leaderboards-only/Private × each section, feed, leaderboard, directory); non-goal route/schema guard; feed idempotency and read-time visibility change; vote concurrency (unique active vote), retract/re-cast, eligibility (Active only), independence from funding; recognition limits; moderation flows; delegation tests to fake 013/015; degraded sections; accessibility; E2E propose→vote→recognize.

## 12. Migration / Versioning
Alembic revisions for `community` (slice A first, D additive); feed projection rebuildable via 007 replay; contracts semver'd.

## 13. Cross-Spec Dependencies
Prerequisites: 001, 002 (directory, active-account port), 003, 007, 010, 011 (renderer), 013 (progression/leaderboards/achievements/quests slices A/B/C), 020, 021, 022/004, 008. **Slice D requires 015's lifecycle slice (step 25)**: `ProjectLifecycle` port stubbed until then. Exposes: profile/discovery slots to 023, `CommunityReader` to 015/013.

## 14. Implementation Phases
**A (22)**: 1 schema + non-goal guard → 2 members + profile assembler/sections → 3 feed projector/API → 4 discovery + providers. **B (23)**: 5 leaderboards page. **C (24)**: 6 achievements/quests/challenges pages. **D (25)**: 7 proposals + moderation → 8 votes → 9 participation + recognition + help-wanted → 10 notifications/lifecycle display → 11 hardening.

## 15. Technical Decisions — `research.md` R1–R12.

## 16. Risks / Open Technical Questions
- **R1** OQ-55..59: decision authority and reserved-funds rules belong to 015; Community defaults for voting/proposing/participation in research (R7, R8, R10). **Product confirmation requested** (vote retract/re-cast, moderation default off, help prompts scope, recognition limits).
- **R2** "Help prompts" interpreted minimally (help-wanted flag + participation) to avoid building a forum/chat; confirm.
- **R3** Slice D depends on 015's lifecycle for state/funding display; ordering enforced by the roadmap.
- **R4** Read-time visibility checks on feeds can be costly: bounded page size and per-actor preference caching.
- **R5** Voter privacy default (counts only) is a policy choice flagged for confirmation.

## Project Structure
```text
backend/src/portalab/{capabilities/community, modules/community/{members,profiles,feed,leaderboards,achievements,quests,proposals,votes,participation,moderation,discovery,api,models}} · backend/migrations/community/versions/
frontend/src/features/community/{members,profile,feed,discovery,leaderboards,achievements,quests,projects,moderation}
```
