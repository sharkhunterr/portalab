# Data Model — Community (schema `community`)

FKs only intra-module or to `identity.users(id)`; project lifecycle/funding references are opaque (`project_ref` = proposal id as known to Marketplace).

## Slice A — surfaces
- **community.feed_entries** (projection, rebuildable): `id` · `source_event_id` unique · `actor_user_id` FK · `kind` · `subject_ref` · `message_key` · `params` jsonb (ids/counters only) · `visibility_class` (`public|community`) · `occurred_at` · `created_at`. Index `(occurred_at desc)`, `(actor_user_id, occurred_at)`. Pruned by retention (default 180 days); removed with the actor on erasure.
- **community.feed_settings**: allow-listed event types are config (`community.feed.eventTypes`), not a table.
- **Profile sections** are runtime registrations (no table).

## Slice D — proposals, votes, participation
- **community.proposals**: `id` UUIDv7 · `kind` (`project|feature`) · `provenance_ref` null (e.g. Support feedback id) · `proposer_id` FK · `title` · `body_md` · `rendered_html` · `renderer_version` · `tags` text[] · `status` (`pending_moderation|open|withdrawn|rejected`) · `help_wanted` bool · `help_note` null · `lifecycle_ref` (opaque 015 id) null · `created_at` · `updated_at`. (Lifecycle state is read from 015.)
- **community.votes**: `proposal_id` FK · `user_id` FK · `cast_at` · `retracted_at` null · unique partial index on `(proposal_id, user_id) WHERE retracted_at IS NULL`. Personal data class `activity`.
- **community.vote_counts** (derived, transactional counter): `proposal_id` PK · `count` int — updated in the vote transaction.
- **community.participations**: `id` · `proposal_id` FK · `user_id` FK · `role` (`contributor|tester|helper`) · `status` (`active|withdrawn`) · `note` · `recognized_at` null · `recognized_by` FK null · `created_at`. Unique `(proposal_id, user_id, role)`.
- **community.recognition_log** (append-only): `id` · `participation_id` FK · `recognizer_id` FK · `recipient_id` FK · `created_at` — used for rate/pair limits and audit.
- **community.moderation_log** (append-only): `proposal_id` · `moderator_id` · `decision` · `reason` · `created_at`.

## Community events (decided 2026-10-01: Community owns them; the 011 Calendar aggregates them)
- **community.events**: `id` UUIDv7 · `title` · `description_md` · `rendered_html` · `starts_at` · `ends_at` null · `all_day` bool · `reference_tz` · `audience` (visibility tier: Public=all members|Community|role/group list) · `organizer_id` FK · `status` (`scheduled|cancelled`) · `version` · `created_at` · `updated_at`. Personal data: organizer ref only.

## Settings (declared into 020)
`community.feed.eventTypes`, `community.feed.retentionDays` (180), `community.members.listingDefault`, `community.proposals.moderation` (true), `community.proposals.allowedRoles` (all active), `community.recognition.maxPerDay` (5), `community.recognition.pairCooldownDays` (30), `community.discovery.*`. User visibility via 021 datums: `member_listing`, `progression`, `community_activity`, `projects`, `votes`.

## Events (via 007; ids/counters only)
Produced: `community.event_created|updated|cancelled` (dedup `(event_id, version)`), `project.created` (dedup `proposal_id`), `project.vote_added|vote_retracted` (dedup `(proposal_id, user_id, vote_seq)`), `project.participation_added|withdrawn`, `community.contribution_recognized` (dedup `participation_id`), `community.proposal_moderated`. Consumed: feed event types; `project.status_changed|funding_added` (015) for notifications/feed; account state events (voting eligibility); erasure participant calls.

## Privacy / retention
Votes, participations, feed entries, proposals = personal data (`activity`/`content`); erased/anonymized by the 020/021 participant (votes removed and counts decremented; proposals tombstone the proposer, keeping content only if the project has progressed per 021 policy); voter identities never exposed to others.
