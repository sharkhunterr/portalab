# Feature Specification: Content — News, Wiki & Calendar

**Feature Branch**: `011-content-news-wiki-calendar`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Content system (News, Wiki, Calendar)."

## Role of This Document

This is a **detailed feature specification** for the Content system — three distinct but
interconnectable domains: **News** (editorial broadcast content), **Wiki** (knowledge/help content),
and **Calendar** (unified time-based view of events, maintenance, campaigns, community events, and
deadlines). It conforms to and refines the superior reference specification
(`specs/001-portal-global-spec/spec.md`) and composes with Roles & Permissions
(`specs/003-roles-permissions/spec.md`), the Portal Core shell (`specs/004-portal-core-shell/spec.md`),
Events & History (`specs/007-events-history/spec.md`), Search & Command Palette
(`specs/008-search-command-palette/spec.md`), and Notifications (`specs/010-notifications/spec.md`),
under the project Constitution (`.specify/memory/constitution.md`, v1.0.0). It draws on
`product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`, `ux/UX_PRINCIPLES.md`, and
`ux/DESIGN_SYSTEM.md`.

Scope boundary: this spec owns the **three content domains and their interconnections**. It consumes
the authorization engine (read/create/modify/publish/delete permissions), the notification engine
(it triggers communications, it does not deliver them), the event/history backbone (versioning,
provenance), and the AI capability (Wiki pages usable by the AI, contextual help). It does **not** own
those engines, the maintenance/incident lifecycles (owned by Support/Services & Health — Calendar
displays them), or the campaign definition (owned by Gamification — Calendar displays it). It chooses
no technology and contains no implementation detail.

### Strict Domain Distinctions (normative)

The three domains are **distinct** and MUST NOT be conflated, but MUST be interconnectable:

- **News**: editorial, time-relevant broadcast content authored for an audience (announcements,
  highlights). Has a publication lifecycle and featuring. Not knowledge-base, not per-user state.
- **Wiki**: durable knowledge/help content organized into pages, versioned, usable by the AI and for
  contextual help. Not editorial/time-bound broadcast.
- **Calendar**: a unified time-based view that **aggregates** dated items (News-scheduled items,
  maintenance, campaigns, community events, deadlines) owned by various domains; the Calendar renders
  and links them without owning their lifecycles.

**Interconnection**: a News article MAY link to a Wiki page or a Calendar event; a Wiki page MAY link
to News/Calendar; a Calendar event MAY link to its source (maintenance, campaign, News). Links are
references, not merges — each item keeps its own identity, lifecycle, and permissions.

**Terminology**: create/modify/publish/delete are distinct permissions (per Roles & Permissions);
Domain Event = a recorded fact; `occurred_at` = real occurrence time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - News: author, publish, feature, archive (Priority: P1)

An editor creates a News article as a draft, edits it, publishes it to its audience, optionally
features it for a bounded duration, and later archives it; read/create/modify/publish/delete are
distinct permissions.

**Why this priority**: News is the editorial voice of the portal; its create→publish→feature→archive
lifecycle with distinct permissions is the core of the News domain.

**Independent Test**: As an editor, draft an article, edit it, publish it, feature it with a duration,
and archive it; confirm each step respects the matching permission and that a reader sees only
published (non-archived) items they are permitted to see.

**Acceptance Scenarios**:

1. **Given** create+modify permission, **When** an editor drafts and edits an article, **Then** the
   draft is saved and not visible to readers until published.
2. **Given** publish permission, **When** the editor publishes, **Then** the article becomes visible to
   its audience and a `news.published`-type event is recorded.
3. **Given** a published article, **When** it is featured with a duration, **Then** it is highlighted
   until the featuring duration elapses, after which it reverts to normal without being unpublished.
4. **Given** delete/archive permission, **When** the article is archived, **Then** it is no longer in
   active discovery while remaining retained per policy; readers no longer see it as current.
5. **Given** only read permission, **When** a user attempts to create/modify/publish, **Then** it is
   refused.

### User Story 2 - News: categories, discovery, and notifications (Priority: P2)

Readers discover News through categories, featured items, and the News discovery surface; publishing a
relevant article can trigger notifications per the notification engine and user preferences.

**Why this priority**: Discovery and categorization make News useful; the notification link is how News
reaches users without a parallel mechanism.

**Independent Test**: Publish articles in several categories, feature one; confirm discovery surfaces
and category filtering work, and that publication triggers a notification respecting user preferences
and permissions.

**Acceptance Scenarios**:

1. **Given** published articles in categories, **When** a reader browses News, **Then** they can
   discover items by category and see featured items highlighted.
2. **Given** a newly published article, **When** publication occurs, **Then** it MAY trigger a
   notification via the notification engine, respecting the reader's category/channel preferences and
   permissions (News and Notification remain distinct concepts).
3. **Given** a reader without permission for an article's audience, **When** browsing/notified, **Then**
   it is neither shown nor notified.

### User Story 3 - Wiki: rich pages with Markdown, media, diagrams, callouts (Priority: P1)

An editor authors Wiki pages using Markdown with images, links, tables, code blocks, Mermaid diagrams,
and callouts; pages render consistently and safely.

**Why this priority**: The Wiki is the knowledge base; rich, consistent authoring is its core value.

**Independent Test**: Create a page containing Markdown text, an image, internal/external links, a
table, a code block, a Mermaid diagram, and a callout; confirm all render correctly and safely (no
unsafe content execution, no secret exposure).

**Acceptance Scenarios**:

1. **Given** Wiki edit permission, **When** an editor authors a page with Markdown, images, links,
   tables, code, Mermaid, and callouts, **Then** all elements render correctly and consistently.
2. **Given** page content, **When** rendered, **Then** it is rendered safely (no unsafe execution, no
   leakage of secrets), and external/internal links are distinguishable.
3. **Given** a user without edit permission, **When** they view a page, **Then** they can read it (if
   permitted) but cannot edit/publish/delete it.

### User Story 4 - Wiki: history, comparison, restoration (Priority: P1)

Every Wiki page change is versioned; editors can view history, compare versions, and restore a prior
version; restoration is itself a new versioned change (history is not rewritten).

**Why this priority**: Versioned knowledge with safe rollback is essential to a trustworthy Wiki and
aligns with the "historical records not rewritten" principle.

**Independent Test**: Edit a page several times; view its history; compare two versions; restore an
earlier one; confirm the restoration appears as a new version and prior history remains intact.

**Acceptance Scenarios**:

1. **Given** a page edited multiple times, **When** history is viewed, **Then** each version is listed
   with author and timestamp.
2. **Given** two versions, **When** compared, **Then** the differences are shown clearly.
3. **Given** a prior version, **When** restored, **Then** the page content returns to it as a new
   version; the intervening history is preserved (not deleted/rewritten).

### User Story 5 - Wiki: organization, AI-usable pages, contextual help (Priority: P2)

Wiki pages are organized (hierarchy/grouping/links); designated pages are usable by the AI (within the
reader's permissions) and power contextual help surfaced elsewhere in the portal.

**Why this priority**: Organization and AI/contextual-help integration are what make the Wiki a live
help system rather than a static dump, and are explicitly required.

**Independent Test**: Organize pages; mark pages AI-usable; invoke contextual help on a portal surface
and an AI question; confirm the AI/help draws on permitted Wiki pages and never exposes pages the user
may not read.

**Acceptance Scenarios**:

1. **Given** organized Wiki pages, **When** a user browses, **Then** the organization (hierarchy/
   grouping/links) aids navigation with no dead-ends.
2. **Given** AI-usable pages, **When** the AI answers or contextual help is shown, **Then** it draws on
   permitted Wiki content and is bounded by the user's permissions (never revealing unreadable pages).
3. **Given** contextual help on a surface, **When** invoked, **Then** it links to the relevant Wiki
   page(s) the user may read.

### User Story 6 - Calendar: unified view of dated items (Priority: P1)

A user sees a unified Calendar aggregating events, maintenance windows, campaigns, community events,
and deadlines they are permitted to see, each linking back to its source, with appropriate display
options.

**Why this priority**: The unified Calendar is explicitly required and is where time-based items from
many domains converge coherently.

**Independent Test**: Populate maintenance, a campaign, a community event, and a deadline; view the
Calendar; confirm all permitted items appear, are distinguishable by type, link to their source, and
that unpermitted items do not appear.

**Acceptance Scenarios**:

1. **Given** dated items from several domains, **When** the Calendar is viewed, **Then** permitted
   items appear, distinguishable by type (event, maintenance, campaign, community event, deadline).
2. **Given** a calendar item, **When** selected, **Then** it links to its source record (e.g., the
   maintenance detail, the campaign, the News article) without merging identities.
3. **Given** an item the user may not see, **When** the Calendar renders, **Then** it does not appear.
4. **Given** display options (e.g., month/week/list), **When** chosen, **Then** the Calendar renders
   accordingly and remains functionally complete on mobile.

### User Story 7 - Calendar: maintenance, campaigns, community events, deadlines, notifications (Priority: P2)

Calendar items of each kind are sourced from their owning domains (maintenance from Support/Services,
campaigns from Gamification, community events from Community, deadlines from relevant domains), and
upcoming items can trigger reminders via the notification engine.

**Why this priority**: The Calendar's value is in correctly reflecting authoritative sources and
reminding users, without owning those lifecycles (anti-duplication, principle XX).

**Independent Test**: Create a maintenance window and a campaign; confirm they appear on the Calendar
from their sources and that an upcoming item can trigger a reminder notification per preferences.

**Acceptance Scenarios**:

1. **Given** a maintenance window owned by Support/Services, **When** scheduled, **Then** it appears on
   the maintenance calendar sourced from that record (not re-authored in Calendar).
2. **Given** a campaign owned by Gamification, **When** active/scheduled, **Then** it appears on the
   Calendar referencing the campaign.
3. **Given** an upcoming Calendar item, **When** its reminder point is reached, **Then** the
   notification engine MAY produce a reminder, respecting preferences and permissions (Calendar
   triggers, Notifications delivers).

### User Story 8 - Three domains distinct but interconnectable (Priority: P1)

News, Wiki, and Calendar remain separate domains with their own lifecycles and permissions, but items
can reference each other (e.g., a News article links a Wiki how-to and a Calendar event).

**Why this priority**: "Distinct but interconnectable" is the explicit cross-cutting requirement for
this spec; conflation or isolation would both be wrong.

**Independent Test**: Create a News article that links a Wiki page and a Calendar event; confirm the
links resolve, each item keeps its own identity/lifecycle/permissions, and removing one does not
corrupt the others.

**Acceptance Scenarios**:

1. **Given** a News article, a Wiki page, and a Calendar event, **When** linked to each other, **Then**
   the links resolve for permitted users and each item retains its own identity and lifecycle.
2. **Given** a linked item is archived/deleted, **When** another references it, **Then** the referencing
   item degrades gracefully (shows the link as unavailable) without corruption.
3. **Given** differing permissions, **When** a user follows a link to an item they may not see, **Then**
   access is refused/omitted (links never bypass permissions or privacy).

### Edge Cases

- **Featuring duration elapses**: A featured News item reverts to normal (still published) when its
  featuring duration ends; it is not unpublished or deleted.
- **Scheduled publication**: An article scheduled to publish later becomes visible only at its
  scheduled time; before then it is a draft/scheduled state not visible to readers.
- **Archive vs delete (News)**: Archiving removes an item from active discovery while retaining it;
  deletion is a distinct, permissioned, audited action.
- **Wiki unsafe content**: Markdown/Mermaid/code/callouts render safely; no script execution, no
  secret leakage; untrusted embeds are sanitized.
- **Wiki restore**: Restoring a version is a new version; prior history is never rewritten or deleted.
- **Concurrent Wiki edits**: Simultaneous edits resolve without silent loss (conflict handling/last
  version visible); no change is lost without trace. (See OQ-52.)
- **AI-usable page permission**: The AI/contextual help never surfaces a Wiki page the asking user may
  not read; permission is evaluated per asking user, not per author.
- **Calendar item from a disconnected/removed source**: If a source record is removed, its Calendar
  entry degrades gracefully (shows unavailable) rather than displaying stale-as-current.
- **Overlapping calendar items**: Multiple items on the same day/time are all shown, distinguishable by
  type, without visual collapse that hides one.
- **Permission change after publish**: A reader losing permission stops seeing the News/Wiki/Calendar
  item on next evaluation; privacy is honored independently of permission.
- **Broken cross-link**: A link to an archived/deleted/forbidden item shows as unavailable rather than
  erroring or leaking the item's existence where that is sensitive.
- **Degraded mode**: If one domain's source is slow/unavailable, the others still render; the Calendar
  shows partial data per source rather than failing entirely.
- **News vs Notification confusion**: Publishing News does not itself create per-user notification
  state; it may trigger Notifications via the engine, which remain distinct.

## Requirements *(mandatory)*

### Functional Requirements

#### News — Lifecycle
- **FR-001**: The system MUST support creating and editing News articles as drafts not visible to
  readers until published, gated by create/modify permissions.
- **FR-002**: The system MUST support publishing a News article to its audience, recording a
  publication event; publish MUST be a distinct permission from create/modify.
- **FR-003**: The system MUST support scheduled publication: an article becomes visible only at its
  scheduled time.
- **FR-004**: The system MUST support featuring a published article for a bounded duration, after which
  it reverts to normal (still published) without being unpublished.
- **FR-005**: The system MUST support archiving a News article (removed from active discovery, retained
  per policy) and deletion as a distinct, permissioned, audited action.

#### News — Categories, Discovery, Notifications
- **FR-006**: News articles MUST support categories, and readers MUST be able to discover articles by
  category and via featured items and a discovery surface.
- **FR-007**: Publishing an article MAY trigger a notification via the notification engine, respecting
  the reader's category/channel preferences and permissions; News and Notification MUST remain distinct
  concepts.
- **FR-008**: Readers MUST only discover/receive News for audiences they are permitted to see; private
  data MUST NOT be exposed by permission alone.

#### Wiki — Authoring & Rendering
- **FR-009**: The Wiki MUST support pages authored in Markdown including images, internal/external
  links, tables, code blocks, Mermaid diagrams, and callouts, rendered consistently.
- **FR-010**: Wiki content MUST render safely: no unsafe execution, untrusted embeds sanitized, and no
  exposure of secrets.
- **FR-011**: Reading, creating, modifying, publishing, and deleting Wiki pages MUST be governed by
  distinct permissions.

#### Wiki — Versioning
- **FR-012**: Every Wiki page change MUST be versioned with author and timestamp.
- **FR-013**: Users MUST be able to view a page's history and compare two versions with clear
  differences.
- **FR-014**: Users MUST be able to restore a prior version; restoration MUST create a new version and
  MUST NOT rewrite or delete intervening history.

#### Wiki — Organization, AI, Contextual Help
- **FR-015**: The Wiki MUST support organization (hierarchy/grouping/links) that aids navigation with
  no dead-ends.
- **FR-016**: Designated Wiki pages MUST be usable by the AI and for contextual help, bounded by the
  asking user's permissions (never revealing pages the user may not read).
- **FR-017**: Contextual help surfaced elsewhere in the portal MUST be able to link to the relevant
  permitted Wiki page(s).

#### Calendar — Unified View
- **FR-018**: The Calendar MUST present a unified view aggregating dated items — events, maintenance,
  campaigns, community events, and deadlines — that the user is permitted to see.
- **FR-019**: Calendar items MUST be distinguishable by type and MUST link back to their source record
  without merging identities.
- **FR-020**: The Calendar MUST support display options (e.g., month/week/list) and MUST remain
  functionally complete on mobile.
- **FR-021**: Items a user may not see MUST NOT appear on the Calendar.

#### Calendar — Sources & Reminders
- **FR-022**: Calendar items MUST be sourced from their owning domains (maintenance from
  Support/Services, campaigns from Gamification, community events from Community, deadlines from
  relevant domains); the Calendar MUST NOT re-author or own those lifecycles.
- **FR-023**: An upcoming Calendar item MAY trigger a reminder via the notification engine, respecting
  preferences and permissions (Calendar triggers, Notifications delivers).
- **FR-024**: If a source record changes or is removed, its Calendar entry MUST reflect the change or
  degrade gracefully (not display stale-as-current).

#### Cross-Domain Interconnection
- **FR-025**: News, Wiki, and Calendar MUST remain distinct domains with their own lifecycles and
  permissions, while supporting references (links) between items.
- **FR-026**: A cross-link MUST resolve only for permitted users and MUST NOT bypass permissions or
  privacy; following a link to a forbidden item MUST be refused/omitted.
- **FR-027**: When a linked item is archived/deleted/forbidden, the referencing item MUST degrade
  gracefully (link shown unavailable) without corruption or leaking existence where sensitive.

#### Cross-Cutting (events, history, degraded mode)
- **FR-028**: Content changes (publish, archive, page version, restore, etc.) MUST emit domain events
  with `occurred_at` distinct from `received_at`; consumers MUST be idempotent where duplicates are
  possible.
- **FR-029**: Content history/provenance MUST be retained per policy; historized content MUST NOT be
  automatically public, and content MUST follow the privacy/deletion lifecycle.
- **FR-030**: If one content domain's source is slow/unavailable, the others MUST still render; the
  Calendar MUST show partial data per source rather than failing entirely.
- **FR-031**: Sensitive content actions (publish, delete, archive where configured sensitive) MUST be
  audited with actor, action, timestamp, context, and result.
- **FR-032**: All content MUST be searchable via Global Search per the user's permissions (News, Wiki,
  Calendar are listed searchable domains), and MUST use the shared Design System for consistency.

### News Article State Model

**States**: Draft, Scheduled, Published, Featured (a published article with active featuring),
Archived.

**Transitions** (gated by the matching permission):

- Draft to Scheduled (set a future publication time) or Draft to Published (publish now)
- Scheduled to Published (at scheduled time)
- Published to Featured (feature with a duration) ; Featured to Published (featuring duration elapses)
- Published/Featured to Archived (archive) ; Archived MAY be restored to Published per policy
- Any to Deleted (distinct, permissioned, audited — not the same as Archived)

**Invariants**:
- Drafts/Scheduled are not reader-visible before publication.
- Featuring never changes published-visibility; it only highlights for its duration.
- Archiving retains the item (removed from active discovery); deletion is separate and audited.

### Wiki Page Versioning Model

- Each save creates a new immutable version (author, timestamp, content).
- History lists all versions; comparison shows differences between any two.
- Restore applies a prior version's content as a NEW version; prior versions are never rewritten.

### Content-Related Domain Events

Names aligned with the Event Model; each carries actor/context, item reference, metadata, version.

- `news.created`, `news.updated`, `news.published`, `news.featured`, `news.unfeatured`,
  `news.archived`, `news.deleted`
- `wiki.page_created`, `wiki.page_updated`, `wiki.version_restored`, `wiki.page_deleted`
- `calendar.item_added` (reference to a source), `calendar.item_updated`, `calendar.item_removed`
- Referenced (owned elsewhere): `maintenance.scheduled/started/ended`, `event.started/ended`
  (campaign), community-event lifecycle events.

### Key Entities

- **NewsArticle**: Editorial item with title/body (rich), category(ies), audience, publication state,
  featuring window, author, timestamps.
- **News Category**: A grouping for discovery/filtering.
- **Featuring**: A time-bounded highlight of a published article.
- **WikiPage**: A knowledge page with rich content (Markdown, media, links, tables, code, Mermaid,
  callouts), organization placement, AI-usable flag, and version history.
- **Wiki Version**: An immutable prior state of a page (author, timestamp, content).
- **Wiki Organization**: Hierarchy/grouping/links structuring pages.
- **CalendarItem**: A dated entry referencing a source record (maintenance, campaign, community event,
  News-scheduled item, deadline), with type and display info — not an owner of the source lifecycle.
- **Cross-Link / Reference**: A permission-respecting link between a News/Wiki/Calendar item and
  another item.
- **Permission/Privacy (referenced)**: read/create/modify/publish/delete gating; visibility engine.
- **Notification/AI/Search (referenced)**: trigger target, knowledge consumer, discovery surface.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: News, Wiki, and Calendar are conflated (merged identity/lifecycle) in 0% of cases while
  cross-links resolve for permitted users in 100% of valid cases.
- **SC-002**: read/create/modify/publish/delete are enforced as distinct permissions for News and Wiki
  in 100% of attempts (e.g., read-only users publish in 0% of attempts).
- **SC-003**: A featured News item reverts to normal (still published) when its featuring duration ends
  in 100% of cases; featuring unpublishes/deletes it in 0% of cases.
- **SC-004**: Wiki pages render Markdown, images, links, tables, code, Mermaid, and callouts correctly
  and safely in 100% of defined cases; unsafe execution or secret leakage in 0% of cases.
- **SC-005**: Restoring a Wiki version produces a new version and preserves prior history in 100% of
  cases (history rewritten/deleted in 0% of cases).
- **SC-006**: AI/contextual help surfaces a Wiki page the asking user may not read in 0% of cases.
- **SC-007**: The Calendar shows an item the user is not permitted to see in 0% of cases; permitted
  items from all source domains appear and link to their source in 100% of valid cases.
- **SC-008**: Calendar items are re-authored/owned by the Calendar (instead of sourced) in 0% of cases
  (sourced from owning domains in 100%).
- **SC-009**: A slow/unavailable single content source blocks the other content domains in 0% of cases;
  the Calendar shows partial-by-source rather than failing entirely in 100% of such cases.
- **SC-010**: Following a cross-link to a forbidden/removed item leaks its sensitive existence or
  corrupts the referencing item in 0% of cases.

## Assumptions

- The notification engine (delivery, preferences) is owned by `specs/010-notifications`; this spec only
  triggers communications (News publish, Calendar reminders).
- Maintenance/Incident lifecycles are owned by Support/Services & Health; campaign definitions by
  Gamification; community events by Community; deadlines by their relevant domains. The Calendar
  displays and links them. (Exact deadline sources flagged as OQ-50.)
- The authorization, privacy/visibility, event/history, AI, and search engines are owned by their
  specs; this spec composes with them.
- The exact Markdown/Mermaid/callout feature set and sanitization policy follow the Design System and a
  safe-rendering standard; this spec requires the capabilities and safety, not a specific renderer.
  (Flagged as OQ-51.)
- Whether the Wiki supports collaborative concurrent editing or last-writer-with-history is a product
  decision. (Flagged as OQ-52.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-50 (Deadline sources)**: Confirm what "deadlines" on the Calendar represent and which domains own
  them (e.g., community project funding deadlines, maintenance windows, campaign end dates) so the
  Calendar sources rather than invents them.
- **OQ-51 (Wiki rendering/safety standard)**: Confirm the supported Markdown/Mermaid/callout feature set
  and the sanitization/safe-rendering policy for embeds, code, and images.
- **OQ-52 (Wiki concurrent editing)**: Confirm the editing model (last-writer-wins with full history,
  explicit locking, or collaborative merge) and how conflicts are surfaced.
- **OQ-53 (News audience model)**: Confirm how a News article's audience is defined (role/group/public/
  community) and how it composes with privacy and categories.
- **OQ-54 (Featuring precedence)**: Confirm how multiple simultaneously-featured articles are ordered/
  limited (max featured, priority) to avoid an overcrowded featured surface.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/003-roles-permissions/spec.md` (read/create/modify/publish/delete; `news.publish`,
  `wiki.edit`), `specs/004-portal-core-shell/spec.md` (navigation, degraded states, Design System),
  `specs/007-events-history/spec.md` (content events, versioning/provenance), `specs/008-search-command-palette/spec.md`
  (News/Wiki/Calendar are searchable domains), and `specs/010-notifications/spec.md` (publish/reminder
  triggers; News≠Notification distinction).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `ux/UX_PRINCIPLES.md`, `ux/DESIGN_SYSTEM.md`, `architecture/DATA_MODEL.md`, `architecture/EVENT_MODEL.md`.
- Related specs (not owned here): Support/Services & Health (maintenance/incident sources), Gamification
  (campaigns), Community (community events, community-project deadlines), AI (knowledge consumption),
  and the Privacy spec (021) (visibility engine).
