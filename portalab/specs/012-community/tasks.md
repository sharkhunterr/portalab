---
description: "Task list — Community (spec 012)"
---

# Tasks: Community

**Input**: `specs/012-community/` · **Branch**: `012-community` · **Roadmap**: **Slice A** (Phases 1–5) = step 22; **Slice B** (Phase 6) = step 23; **Slice C** (Phase 7) = step 24; **Slice D** (Phases 8–10) = step 25 (with 015) · **Tests**: included.
Abbrev: **`CO/`** = `backend/src/portalab/modules/community`, **`CAP/`** = `backend/src/portalab/capabilities/community`, **`FC/`** = `frontend/src/features/community`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel · `D-002` directory + `is_active_account` · `D-003` authz · `D-007` events · `D-008` search SDK · `D-010` `send` · `D-011` Markdown renderer · `D-013` progression/leaderboards/achievements/quests (slices A/B/C of 013) · `D-020` settings · `D-021` visibility/retention · `D-022/004` UI · `D-015` project lifecycle/funding (slice D; `ProjectLifecycle` port stubbed until then).

## Phase 1: Setup (Slice A)
- [X] T001 Create `CAP/__init__.py`, `CO/{members,profiles,feed,leaderboards,achievements,quests,proposals,votes,participation,moderation,discovery,api,models}/__init__.py`, `backend/migrations/community/versions/`, `FC/{members,profile,feed,discovery,leaderboards,achievements,quests,projects,moderation}/`, `backend/tests/{unit,integration,contract,security}/community/`, `frontend/tests/{unit,e2e}/community/`
- [X] T002 [P] Declare settings (`community.feed.eventTypes`, `.feed.retentionDays`, `.members.listingDefault`, `.proposals.moderation`, `.proposals.allowedRoles`, `.recognition.maxPerDay`, `.recognition.pairCooldownDays`, `.discovery.*`) in `CO/settings.py`; permissions `community.read|propose|participate` (default grants), `community.moderate` (moderator/Admin, audited) in `CO/permissions.py`
- [X] T003 [P] Register 021 datum classes `member_listing`, `community_activity`, `projects`, `votes`; retention targets (feed, votes, participations); 020/021 export+erasure participant `CO/privacy.py`; event types `project.*`, `community.*` with 007
- [X] T004 Write `backend/tests/security/community/test_non_goals.py` (CI guard): OpenAPI paths and DB schema contain no friends/followers/graph/DM/likes/reactions/chat artifacts (patterns `friend|follow|message|dm|like|reaction|chat`), failing the build on any match; document the plugin-only chat extension point

## Phase 2: US1 — Members directory and community profiles within visibility (P1) 🎯 MVP (Slice A)
**Independent test**: viewers with different permissions see only what each owner's visibility and the viewer's permissions allow.
- [X] T005 [P] [US1] Write `backend/tests/security/community/test_profile_visibility.py`: matrix (owner/Community member/other viewer/Admin/moderator × Public/Community/Leaderboards-only/Private for identity, progression, achievements, activity, projects, directory listing); permission alone never reveals Private; Private sections absent (not "hidden"); non-Active accounts not listed; each section fails independently (fake 013 down ⇒ that section `unavailable`)
- [X] T006 [P] [US1] Write `backend/tests/integration/community/test_directory.py`: pagination, search by display name, visibility filtering, Active-only, no ordering by hidden attributes, empty result offers next action
- [X] T007 [US1] Implement `CAP/` contracts (`register_profile_section`, `register_discovery_shelf`, section result types), `CO/models` + Alembic revision (`feed_entries` in slice A), `CO/members/service.py`, `CO/profiles/assembler.py` with built-in sections `identity` (002), `progression`/`achievements` (013 `ProgressionReader`), `activity`, `projects` (stub until slice D)
- [X] T008 [US1] Implement routers `GET /community/members`, `GET /community/members/{id}`, `GET /community/members/{id}/sections/{name}` and frontend `FC/members/Directory.tsx`, `FC/profile/ProfilePage.tsx` (independent `FunctionalState` frames, plugin slots)

## Phase 3: US2 — Activity feed from events within visibility (P2)
- [X] T009 [P] [US2] Write `backend/tests/integration/community/test_feed.py`: allow-listed events project once (duplicate delivery idempotent on `source_event_id`); Private actors never enter; visibility changes take effect at read time (entry disappears when actor turns Private); entries reference their source; localized by 026 at render; no like/reaction/comment fields; retention purge; erased with actor
- [X] T010 [US2] Implement `CO/feed/{projector,service}.py` (007 consumers, read-time `VisibilityFilter`), router `GET /community/feed`, frontend `FC/feed/Feed.tsx` (localized text, source links, accessible list)

## Phase 4: US8 — Discovery of community content (P3)
- [X] T011 [P] [US8] Write `backend/tests/integration/community/test_discovery_search.py`: shelves (new members, projects needing votes/help, recent unlocks, activity highlights) visibility-bound; `SearchProvider(kind="member")` conformance (008 kit) honoring listing visibility; empty states provide a next action; unpermitted/private items never surface
- [X] T012 [US8] Implement `CO/discovery/{shelves,providers}.py`, router `GET /community/discovery/{shelf}`, and frontend `FC/discovery/DiscoveryHome.tsx`

## Phase 4b: Community events (owner decided 2026-10-01; consumed by the 011 Calendar)
- [X] T013 [P] Write `backend/tests/integration/community/test_community_events.py`: create/edit/cancel events (title, sanitized Markdown description, start/end or all-day, reference time zone, audience tier); visibility per audience (CD-016/025); `community.event_created|updated|cancelled` emitted once; `CalendarSource(kind="community_event")` returns only permitted events with source links; cancelled events show as cancelled; 011 reminders re-check the source
- [X] T014 Implement `CO/events/service.py` (table `community.events`), routers `GET /community/events`, `POST/PATCH /community/events[/{id}]`, `POST /community/events/{id}/cancel` (`community.events.manage`, moderator/Admin, audited), the `CalendarSource` registration for 011, and frontend `FC/events/{EventList,EventEditor}.tsx`

## Phase 5: Slice A closure
- [X] T015 [P] Implement `GET` health/observability registration `CO/observability.py` (feed lag, section failure rates; 025 functional check) and dashboard widget stubs (`community.activity`) for 009
- [X] T016 [P] Add `/community/*` routes to the permission-matrix test (voting route allow-listed as "Active account invariant"), regenerate OpenAPI client, write `docs/community.md` (non-goals, visibility model, section registry, slice map)

## Phase 6: US3 — Leaderboards respecting visibility (P2) — Slice B (step 23)
- [X] T017 [P] [US3] Write `backend/tests/integration/community/test_leaderboards_view.py` (fake/real 013 slice B): metrics/periods delegated to `LeaderboardService`; opt-out and visibility honored (Private/hidden users absent); viewer sees own position; no private data by permission alone; 013 down ⇒ `unavailable` state without breaking the page
- [X] T018 [US3] Implement `CO/leaderboards/view.py`, routers `GET /community/leaderboards/{metric}`, `GET /community/me/position`, and frontend `FC/leaderboards/LeaderboardPage.tsx` (accessible table, metric/period selectors, own-rank highlight)

## Phase 7: US4 — Achievements, quests, challenges display — Slice C (step 24)
- [X] T019 [P] [US4] Write `backend/tests/integration/community/test_achievements_quests_view.py`: definitions and reward logic come from 013 (no re-definition); secret/hidden achievements revealed only after unlock; viewer sees others' unlocked achievements only per visibility; challenges rendered as time-boxed quests; progress shows only the viewer's own
- [X] T020 [US4] Implement `CO/achievements/view.py`, `CO/quests/view.py`, routers `GET /community/achievements`, `GET /community/quests`, and frontend `FC/achievements/{Showcase,QuestBoard}.tsx` (locked/hidden/unlocked states with text labels)

## Phase 8: US5 + US6 — Proposals and votes; lifecycle display — Slice D (step 25)
- [X] T021 [P] [US5] Write `backend/tests/integration/community/test_proposals.py`: any Active account may propose (policy-configurable); moderation (default on) holds proposals as `pending_moderation` until approved, then visible/votable; Markdown sanitized; proposal registers a lifecycle record through `ProjectLifecycle` (stub) and never stores lifecycle state; `project.created` emitted once; withdraw/edit rules; creation through `community.proposals.create` from Support feedback conversion keeps `provenance_ref` and kind `feature|project` (only `project` registers a funding lifecycle)
- [X] T022 [P] [US5] Write `backend/tests/integration/community/test_votes.py`: free vote with no minimum level; one active vote per account (concurrent duplicates ⇒ one); retract and re-cast while `accepts_votes`; non-Active accounts (inactive/suspended/pending-deletion/deleted) refused with `community.not_active_account`; voting never requires or implies funding and funding never counts as a vote; counts public, voters private; events `project.vote_added|vote_retracted` with dedup
- [X] T023 [US5] Implement `CO/proposals/service.py`, `CO/votes/service.py` (transactional counter, partial unique index), routers `POST/GET/PATCH /community/proposals`, `POST/DELETE /community/proposals/{id}/vote` (Active-account invariant dependency), moderation `CO/moderation/service.py` + `/admin/community/moderation*`
- [X] T024 [US6] Implement `ProjectLifecycle` port consumer (`CO/proposals/lifecycle.py`): show state/funding summary from 015 (stub until step 25), notifications for `project.status_changed` to proposer/voters/participants via 010 with coalescing, feed entries; frontend `FC/projects/{ProposalList,ProposalDetail,VoteButton,ModerationQueue}.tsx` (lifecycle state with icon+text; funding link to 015 flow) and dashboard widget `community.projects` (proposals open for votes/funding, REQ-018) registered with 009

## Phase 9: US7 — Contribution and user-to-user help — Slice D
- [X] T025 [P] [US7] Write `backend/tests/integration/community/test_participation_recognition.py`: participate as contributor/tester/helper; proposer or moderator recognizes once per participation; self-recognition refused; per-recognizer daily and per-pair monthly limits; emits `community.contribution_recognized` (dedup `participation_id`) which a 013 rule turns into Contribution (real 013 test: idempotent, anti-abuse applies, attributed to the contributor); manual grants go through 013 (marked/audited); no DM/chat/follow involved
- [X] T026 [US7] Implement `CO/participation/service.py` + `recognition.py` (limits, `recognition_log`), routers `POST/DELETE /community/proposals/{id}/participation`, `POST …/participations/{pid}/recognize`, `help_wanted` flag handling, and frontend `FC/projects/{ParticipationPanel,HelpWantedBadge}.tsx`; ship the 013 reward-rule definition example for `community.contribution_recognized` in `docs/community.md`

## Phase 10: Polish & cross-cutting
- [X] T027 [P] Write `backend/tests/security/community/test_privacy_authz.py`: voter identities never exposed; IDOR on proposals/participations; moderation actions audited; erasure removes votes (counts decremented), participations and feed entries; XSS corpus in proposal bodies/help notes
- [X] T028 [P] Write `frontend/tests/e2e/community/journey.spec.ts`: propose → vote → participate → recognize; keyboard-only; degraded section rendering with a stopped dependency; mobile layout
- [X] T029 [P] Update permission-matrix test/OpenAPI client for slice routes, finalize `docs/community.md`; confirm the non-goal guard (T004) still passes with all routes

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [X] T030 [P] Expose owner-tagged registration on the profile-section and discovery-shelf registries: `register(..., owner="module:<id>|plugin:<key>")` and `unregister(owner)`, with a test in `backend/tests/unit/community/test_registry_owner.py` proving all contributions of an owner disappear (required by 023's conformance sweep, F20)

- [X] T031 Run `specs/012-community/quickstart.md` end-to-end per slice; record deviations and open product confirmations (OQ-55..59 defaults, help prompts scope, voter privacy)

## Dependencies & Order
**A**: Setup → non-goal guard → US1 (MVP) → US2 → US8 → closure. **B** needs 013 slice B. **C** needs 013 slice C. **D** (US5/US6/US7) needs proposals before votes, votes before recognition; lifecycle display needs 015 (stub earlier).
**Parallel examples**: T005/T006 · T009 with T011 · T021/T022 · T027/T028/T029.
**MVP (Slice A)**: Phases 1–2 (non-goal guard, directory, visibility-correct profiles).

## Format validation
31 tasks, all checkbox + ID + path; story labels only on story phases.
