# Feature Specification: Confined Extensions (Like Jellyfin's: a Feature, its Interface and its Navigation in One Package — Safely)

**Feature Branch**: `030-confined-plugins`
**Created**: 2026-10-16
**Status**: Draft
**Input**: User description: "Confined plugins — plugins that add whole new features to Portalab (an internal chat, a forum, a new kind of product in the shop…) run apart from Portalab with only the capabilities the Admin grants, through extension points Portalab provides (storage, routes, permissions, pages, navigation, live channels, jobs, notifications, search, events, privacy, product types, settings, network to listed hosts), so a malicious or faulty plugin installed unknowingly cannot read the portal's data, steal secrets, reach the outside or harm the server — like Jellyfin's plugins but safe — without breaking spec 023's plugins or any existing feature (issues #142, #144). Widened the same day: « like
Jellyfin » means Jellyfin's extensions — one extension brings a feature and changes the member experience
radically (new pages, tabs, home sections, buttons in the player and on media, navigation, its own looks or a
complete interface) — all in one package, installed, reviewed and removed together, and safe."

## Role of This Document

This is a **detailed feature specification** for **confined plugins**: the way a plugin adds a complete new
feature — its data, its operations, its pages, its live updates, its jobs, its notifications, its search
results, a new kind of product — while running **apart** from Portalab, able to use only the capabilities
the Admin granted it. It refines Extensibility (`023`: registry, lifecycle, review and consent, quarantine,
per-plugin data, extension points), and works with the exposure catalog (`029`, reduced: every operation of
the portal labelled read, action, committing action or forbidden), Visual Packs (`028`: looks, widgets and
scripts in sandboxes, data contracts), the Marketplace (`015`), Events (`007`), Notifications (`010`), Search (`008`), the
Dashboard (`009`), Roles & Permissions (`003`), Administration (`020`), Privacy (`021`) and Observability
(`025`), under the project Constitution (`.specify/memory/constitution.md`).

**Why this spec exists**: spec 023's code plugins run inside Portalab's own process; a static check of their
imports is defence in depth, not confinement — a malicious plugin written to slip past it could read the
whole database and the secrets, send them out, or alter the server's files (issue #142). Yet the portal is
meant to grow by plugins — a chat, a forum, polls, new kinds of products, new integrations — the way media
servers grow through their plugin catalogs. This spec makes a plugin's power **exactly** what it was
granted, reviewed in plain words by the Admin, and enforced by Portalab whatever the plugin's code tries.

Scope boundary: this spec **owns** the confined execution of plugins, their capabilities and grants, the
extension points listed below, the migration of 023's plugins, the deployment hardening that backs them
(#144) and the plugin SDK. It does **not** own extension repositories, signatures, updates from catalogs or
revocation (spec 031), nor the looks and interfaces packs bring (specs 028, 029), nor what a member may do (permissions,
economy and privacy rules stay those of their owning specs). It chooses no technology.

### Principles (normative)

- **A plugin can do exactly what it was granted**: nothing of the portal — data, secrets, files, network,
  other plugins — is reachable unless a capability the Admin accepted gives it, and Portalab enforces it
  whatever the plugin's code does.
- **Portalab stays the authority**: who may do what, the economy (coins, ownership, refunds), privacy and
  the audit trail stay Portalab's; a plugin asks, Portalab decides.
- **A plugin failure stays the plugin's**: crashes, loops, leaks and floods are contained; the rest of the
  portal keeps working (023's invariant, now enforced by confinement).
- **Nothing breaks**: Portalab works fully without any plugin; 023's plugins keep working, and moving them
  to confinement keeps their data.

## Clarifications

### Session 2026-10-16

- Q: What should plugins be able to add? → A: whole features — for instance an internal chat, a forum, a new
  kind of product in the shop, new integrations — the way a media server's plugins do.
- Q: Must existing features and plugins keep working? → A: yes, nothing that exists may break.
- Q: What does « like Jellyfin » mean? → A: Jellyfin's *extensions*, not its catalog: one extension may bring a
  feature and change the member experience radically — new pages, tabs, home sections, buttons in the player
  and on media, navigation entries, its own looks, even a complete interface — in one package. Jellyfin does
  it with plugins that have full access to the server and inject code into the web client; Portalab must
  offer the same reach through confined code, slots of its interface and packs (028, 029).
- Q: Who may install a plugin and grant its capabilities? → A: the Admin (023's reserved management), who
  reviews each capability in plain words; members see what a plugin's pages read of their data.

### Session 2026-10-17

Decided by default (the owner asked to chain autonomously; each can be revisited). Spec 029 was reduced the
same day to its exposure catalog, one « Interfaces » gallery and a safe mode: there is no broker, no complete
interface, no trust layer and no seal any more, and this spec no longer relies on them.

- Q: How are a plugin's pages and slot contributions drawn, now that 029 has no broker nor complete
  interfaces? → A: by Portalab, from declarative blocks (023's declarative pages, widened: text, figures,
  lists, tables, forms, buttons, media cards, player controls) filled by the plugin's own operations; a
  custom visual is a 028 sandboxed element (no network, data handed by Portalab); no plugin code ever runs
  in Portalab's page, and an extension package no longer holds a complete interface.
- Q: How deep is the confinement? → A: each plugin's code runs in a process of its own started by Portalab,
  with no database access, no secret, no network and no file of the portal; everything goes through
  Portalab, which checks it against the grants; limits (memory, time, processes, files) are enforced by the
  operating system. Where the system cannot deny the network or the files to the process, confined plugins
  are held unless the Admin accepts a weaker mode, shown with a permanent warning.
- Q: How are a plugin's committing actions confirmed without the seal? → A: by Portalab's own confirmation
  dialog, drawn by Portalab's components, showing the exact content the operation declares (what, to whom,
  how much); the plugin cannot style or word it.
- Q: How does « Skip intro » know where intros and credits are? → A: Portalab's player already skips intros
  and credits from the media server's markers (found while planning: it is built in), so the example player
  extension becomes « Moments »: members leave timestamped notes on a title, shown in the player at their
  moment, with a member setting to hide them and an administration setting for their length.

### Session 2026-10-18

- Q: What should a plugin be able to add to Portalab's screens, concretely? → A (owner): a « Playlist »
  plugin adds a « + Playlist » button on every media page, a page listing the playlists and a modal to create
  or edit one; a « Messenger » plugin adds an icon in the top bar that opens the conversations and lets the
  member send a message directly. So slots include the top bar (`header.action`, with a badge) and an
  object's actions (`media.actions`), and a slot's button may open a **surface** drawn by Portalab — a modal
  or a side drawer — holding blocks (forms filled with the current values for editing, a checklist « add
  to… », a live thread). These two become the slot examples (Playlist; Messenger, which is the Chat example);
  « Moments » and « Home sections » are no longer required examples.
- Q: Portalab's blocks look too uniform: may a plugin draw its own interface? → A (owner): yes — a plugin
  either uses the visuals Portalab provides (blocks, enriched as needed) or ships **its own views** (its
  modal like the notifications', a message button in a bottom corner opening a panel or a sidebar, the
  forum's and the playlists' own pages), which must always follow the member's theme, interface and palette.
  Decided by default: a view runs in spec 028's sandbox (an opaque origin, no network, no session) and acts
  only through Portalab (its own routes as the member, committing ones still confirmed by Portalab, its own
  live topics and surfaces); Portalab hands it the theme's tokens and a base kit on them, again whenever they
  change, keeps its frame (the plugin's name, closing) and shows the plugin's blocks instead in safe mode.
- Q: Where does a plugin's feature appear — a section of its own? → A (owner): in Portalab's own pages, as a
  tab of any page (the Forum a tab of Community): a plugin's navigation entry placed in one of Portalab's
  sections becomes a tab of those pages (their hub tabs). Its kinds of products appear in the shop's
  administration like Portalab's own.
- Q: A plugin's own kind of visual (Messenger's message bubbles): where is it sold and chosen? → A (owner):
  the plugin brings the kind and its product type (nothing written in Portalab), separate visual packs bring
  its looks; the look is chosen in Portalab's Appearance page, in a block of its own named by the kind (not
  inside the plugin), and the plugin wears the choice; the plugin's manifest names where the shop shows its
  products — one of the shop's departments and a shelf of its own there (`[[shelves]]`, reviewed with
  `product_types`; a visual kind goes among the interfaces) — and the administration shows that place.
- Q: The rest of the hardening? → A (decided, owner left it open): per-module database roles (FR-025) are
  postponed — the risk they cover (a flaw in one module reading another's tables) is now far smaller than
  the one confinement removed, and they touch every module; the simulator is replaced by installing on a
  test portal, `portalab plugin new` giving the starting point.
- Q: What happens to 023's code plugins on an existing install at upgrade? → A: they keep running as they
  do (unconfined), with a permanent warning in the administration, until migrated; on a new install
  unconfined plugins are off; every newly installed code plugin runs confined.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A plugin installed unknowingly cannot harm the portal (Priority: P1)

The Admin installs a plugin that, unknown to them, tries to read the portal's database, the secrets, the
server's files, other plugins' data, or to send data out, to exhaust the server, or to escalate its rights.
Every attempt fails: the plugin only sees its own storage and the capabilities it was granted; its resource
use is bounded; its attempts are recorded and, past a threshold, it is quarantined (023) and the Admin
alerted. The rest of the portal is unaffected.

**Why this priority**: it is the reason for this spec (#142); every other story depends on it.

**Independent Test**: a probe plugin attempting each forbidden capability (portal data, secrets, files,
network to an unlisted host, other plugins' storage, unbounded memory or time, rights it was not granted)
reports every attempt refused; the portal's own journeys pass while it runs.

**Acceptance Scenarios**:

1. **Given** a confined plugin, **When** it tries to reach anything it was not granted, **Then** the attempt
   fails, is recorded, and nothing outside the plugin changes.
2. **Given** a plugin exceeding its memory, time or rate limits, **When** it happens, **Then** its call is
   stopped, the caller gets a clean failure, and repeated excesses quarantine it.
3. **Given** a plugin that crashes or loops, **When** members use the portal, **Then** every feature that does
   not belong to the plugin keeps working normally.
4. **Given** a quarantined plugin, **When** the Admin looks, **Then** they see why, its recorded attempts, and
   can disable, roll back or remove it (023).

---

### User Story 1b - One extension changes the experience as a whole, like Jellyfin's (Priority: P1)

The Admin installs one extension that, like the extensions of a media server, changes what members live:
for instance « Moments » — members leave timestamped notes on a title (« the twist is at 42:10 »), shown in the
player at their moment, a button in the player to add one, a setting in each member's preferences and one in
the administration — or
« Home sections » — new sections on the members' home (« Because you watched… », « Coming this week »), a new
navigation entry with its own pages, and a look of its own for them. Everything the extension brings — its
confined code, its contributions to Portalab's interface (slots), its looks (028) — is reviewed together, enabled together, updated, rolled back and removed together. Members can hide what it
adds to their own screens.

**Why this priority**: it is what the user means by « like Jellyfin »: extensions that reshape the experience,
not just add a page.

**Independent Test**: the example « Moments » extension is installed and reviewed as one package; a member adds
a moment in the player; another sees it appear at that time in the player and finds its preference in their
settings; the example « Home sections » adds sections and a navigation entry; removing either leaves no trace
in any screen and keeps its data.

**Acceptance Scenarios**:

1. **Given** an extension package holding confined code, slot contributions and looks, **When** the Admin
   reviews it, **Then** one review shows everything it asks (capabilities, operations, slots, looks, scripts)
   and must be accepted as a whole before enabling.
2. **Given** an enabled extension, **When** members use the portal, **Then** its contributions appear in the slots
   it declared (player, media pages, home, navigation, settings…), with their rights, its looks applied.
3. **Given** a member, **When** they hide a contribution of an extension on their screens, **Then** it stays hidden
   for them only, and comes back if they restore it.
4. **Given** an extension disabled, rolled back or removed, **When** members browse, **Then** all of its
   contributions, looks and pages disappear or change together; its data is kept (023).
5. **Given** an extension that reorders or hides Portalab's own home sections or navigation entries by default,
   **When** a member prefers Portalab's order, **Then** they can restore it; no extension can remove a core
   function, nor the administration, security, account or sign-in pages.

---

### User Story 2 - A plugin adds a complete feature: a forum (Priority: P1)

The Admin installs a « Forum » plugin. Its review lists, in plain words, what it asks: its own storage, its
operations (list topics, read, post, moderate), its permissions (read, post, moderate — mapped to roles like
any permission), a navigation entry, its pages, notifications to followers, search results, events
(« a topic was posted ») and the export and deletion of a member's posts for privacy. Once enabled,
members find « Forum » in the navigation, read and post with their rights, get notified, find topics in the
portal's search; a post is published only after Portalab's own confirmation (exact content shown). Disabling it removes its
entry and pages cleanly and keeps its data (023).

**Why this priority**: it is the representative « new feature » the user asked for, exercising most
extension points.

**Independent Test**: the example Forum plugin installs, is reviewed and enabled; a member posts and another
is notified and finds it by search; the privacy export of the member contains their posts; disabling and
re-enabling keeps the posts.

**Acceptance Scenarios**:

1. **Given** a plugin's version, **When** the Admin reviews it, **Then** each requested capability is listed in
   plain words and must be accepted before enabling.
2. **Given** an enabled plugin, **When** a member uses its pages, **Then** its operations run with the member's
   rights, its permissions behave like any portal permission, and committing actions are confirmed by
   Portalab.
3. **Given** a plugin's data, **When** a member asks for their export or deletion (021), **Then** the plugin's
   part is included, within the usual delays.
4. **Given** a disabled plugin, **When** members browse, **Then** none of its entries, pages, widgets or search
   results remain, and its data is kept.

---

### User Story 3 - A plugin adds a live feature: an internal chat (Priority: P2)

A « Chat » plugin offers rooms and direct messages that update live, shows who is present, notifies mentioned
members, lets moderators act, and limits flooding. It uses Portalab's live channels (no connection of its
own), its storage, notifications and moderation; members' blocks and privacy choices (012, 021) apply.

**Why this priority**: live features are the most demanding extension point (presence, delivery delays,
moderation, abuse).

**Independent Test**: two members exchange messages in a room and directly, see each other's presence,
receive mentions, a moderator removes a message, a member who blocked another does not receive their
messages; delivery stays within the stated delay while the plugin is under load.

**Acceptance Scenarios**:

1. **Given** members in a room, **When** one posts, **Then** the others receive it live within the stated delay.
2. **Given** a member's block or privacy choice, **When** the chat delivers, **Then** it is respected exactly as
   in Portalab's own features.
3. **Given** a flood of messages, **When** it exceeds the plugin's limits, **Then** it is slowed and the portal
   stays responsive.

---

### User Story 4 - A plugin adds a new kind of product to the shop (Priority: P2)

A plugin declares a new product type (for instance « a custom avatar commission », « a server slot »): what a
product of this type holds (its schema), what happens when it is bought, activated, refunded or taken back,
and how its card is drawn (in a sandbox, 028). The Admin creates products of this type in the shop like any
other; buying, paying in coins, owning, refunding and gifting stay the shop's own (015) — the plugin is told,
never handles the coins.

**Why this priority**: the shop is a central extension surface; the economy must stay untouchable.

**Independent Test**: the example product type is installed; the Admin creates a product; a member buys it
(confirmed by Portalab's own dialog), the plugin's activation runs; a refund runs its deactivation; the
member's coins move only through the shop.

**Acceptance Scenarios**:

1. **Given** a plugin product type, **When** a member buys a product of it, **Then** the shop debits the coins,
   records the ownership and then tells the plugin to activate it.
2. **Given** an activation that fails, **When** it happens, **Then** the shop applies its usual rule (the
   purchase is refunded or kept pending), never a lost payment.
3. **Given** a plugin, **When** it tries to change a balance, an ownership or a price, **Then** it cannot.

---

### User Story 5 - A plugin integrates an outside service, through listed hosts only (Priority: P2)

A plugin that needs an outside service (a game server, a weather or lyrics provider) declares the hosts it
talks to; the Admin accepts them at review; all its outgoing traffic goes through Portalab, only to those
hosts, recorded; credentials it needs are entered in its settings page and kept by Portalab, handed only to
calls to its listed hosts.

**Why this priority**: integrations are a main reason for plugins, and the main exfiltration risk.

**Independent Test**: the plugin reaches its listed host; a call to any other host fails and is recorded; its
credentials never appear in its storage, logs or pages.

**Acceptance Scenarios**:

1. **Given** a plugin with listed hosts, **When** it calls one, **Then** the call succeeds within its limits.
2. **Given** a call to an unlisted host or address, **When** it happens, **Then** it fails and is recorded.
3. **Given** a plugin's credentials, **When** it runs, **Then** it never reads them; Portalab adds them to calls
   to the listed hosts only.

---

### User Story 6 - 023's plugins keep working (Priority: P2)

Plugins installed under spec 023 keep working after the upgrade: declarative plugins unchanged; code plugins
are offered a migration to confinement that keeps their data; until migrated, they keep running unconfined
on an existing install (off on a new install), with a permanent warning.

**Why this priority**: « nothing breaks » is a requirement; it also defines the path off the old model.

**Independent Test**: on a portal with 023 plugins installed, after the upgrade, declarative plugins work
unchanged, a code plugin either runs (unconfined allowed, warning shown) or is held with a clear message,
and migrating it keeps its data.

**Acceptance Scenarios**:

1. **Given** a declarative 023 plugin, **When** the portal is upgraded, **Then** it works unchanged.
2. **Given** a 023 code plugin and unconfined plugins not allowed, **When** the portal starts, **Then** it is
   held (not run), its data kept, the Admin told how to migrate or allow it.
3. **Given** a migrated plugin, **When** it runs confined, **Then** its data and its members' contents are
   unchanged.

---

### User Story 7 - A plugin author builds a feature with confidence (Priority: P3)

A plugin author starts from a template, writes their feature against Portalab's plugin SDK (its extension
points and capabilities, typed), runs it locally against a simulated Portalab, and checks it with the offline
analysis tool; five examples (Forum, Chat, a product type, « Moments », « Home sections ») show every extension
point.

**Why this priority**: the ecosystem lives from authors; it does not change safety.

**Independent Test**: from the template, an author builds a minimal feature, runs it against the simulator,
and the analysis reports what the Admin's will.

**Acceptance Scenarios**:

1. **Given** the template and SDK, **When** an author builds a plugin, **Then** it runs locally against the
   simulator with sample data for each extension point.
2. **Given** a plugin, **When** the offline tool analyses it, **Then** it reports its requested capabilities and
   any blocking finding as the Admin's analysis would.

---

### Edge Cases

- An extension's package holds a look or a widget that analysis refuses (028): the whole package is blocked,
  not part of it.
- An extension contributes to a slot that a later Portalab version renames or removes: the contribution is
  held, the Admin told; the rest of the extension keeps working.
- A member uses another interface (028 themes, navigations and looks): slot contributions stay drawn by
  Portalab inside it, styled by the interface's tokens like any of Portalab's own components.
- A member is in safe mode (029): contributions drawn by Portalab stay; sandboxed visuals of an extension do
  not load, like any pack content.
- The operating system cannot confine the plugin process (no network or file denial available): confined
  plugins are held unless the Admin accepts the weaker mode, with a permanent warning.
- A title has no moment yet: « Moments » shows only its button to add one.

- A plugin asks for a capability Portalab does not offer: blocking at analysis.
- A plugin update asks for more capabilities: the new ones are reviewed before the update applies (023 keeps
  the previous version running meanwhile).
- A plugin's storage grows without bound: a quota applies; past it, writes fail cleanly and the Admin is told.
- A plugin's operation is slow: it times out within its budget; the member gets a clean failure.
- Two plugins claim the same navigation place, product type key or route: deterministic resolution (023)
  and a blocking finding for duplicates of keys.
- A plugin produces malformed events: validated and quarantined by the event backbone (007/023).
- A member is deleted (021): every plugin's data about them is deleted or anonymised as declared.
- A plugin in quarantine has live connections (chat): they are closed cleanly; members are told the feature
  is unavailable.
- The portal runs without the confined runtime available: confined plugins are held; the core works.
- A plugin's page or sandboxed visual asks for an operation the plugin did not declare: refused.
- Backups and restores include plugins' storage; a restored plugin keeps its grants.

## Requirements *(mandatory)*

### Functional Requirements

**Confinement**

- **FR-001**: A code plugin MUST run in a process of its own, apart from Portalab's, with access to nothing of
  the portal (database, secrets, files, network, other plugins, the host system) except through the
  capabilities it was granted, every request going through Portalab; where the operating system cannot deny
  it the network and the portal's files, it MUST be held unless the Admin accepts a weaker mode, shown with
  a permanent warning.
- **FR-002**: Each plugin MUST have limits of memory, processing time per call, concurrent calls, storage and
  call rate; exceeding them MUST stop the call cleanly, and repeated excesses MUST quarantine the plugin (023).
- **FR-003**: Forbidden attempts MUST fail without effect, be recorded with the plugin's identity and count
  toward quarantine; the Admin MUST be alerted on quarantine.
- **FR-004**: A plugin failure (crash, hang, leak, flood) MUST NOT affect features that do not belong to it.

**Capabilities and review**

- **FR-005**: A plugin MUST declare every capability it needs in its manifest; Portalab MUST offer a closed
  list of capabilities (below), each described in plain words; an unknown capability MUST block the version.
- **FR-006**: The Admin MUST accept each requested capability at review before a plugin is enabled or updated;
  an update requesting more MUST be reviewed again while the previous version keeps running.
- **FR-007**: A plugin's granted capabilities MUST be visible to the Admin at any time and revocable;
  revoking one MUST take effect immediately.

**Extension points (capabilities)**

- **FR-008 Storage**: a plugin MAY have its own storage, isolated from the portal's and other plugins' data,
  within a quota; it MUST be included in backups.
- **FR-009 Operations**: a plugin MAY expose operations under its own namespace, each declaring the
  permission it needs and its exposure label (029's catalog: read, action, committing action); Portalab MUST
  authenticate the member and check the permission before the plugin is called, pass it only the member's
  identity and the request, and confirm a committing action in its own dialog with the exact content the
  operation declares before calling it.
- **FR-010 Permissions**: a plugin MAY declare permissions that integrate into roles like any portal
  permission (003); reserved permissions MUST NOT be declarable.
- **FR-011 Pages, navigation, widgets**: a plugin MAY add pages, navigation entries, dashboard widgets and
  enrichments of existing pages at the extension points of 023; Portalab MUST draw them from declarative
  blocks filled by the plugin's operations, and a custom visual MUST be a 028 sandboxed element; no plugin
  code runs in Portalab's page.
- **FR-012 Live channels**: a plugin MAY publish to members over Portalab's live channels, filtered by the
  members' rights, blocks and privacy choices; it MUST NOT hold connections of its own.
- **FR-013 Events and jobs**: a plugin MAY consume and produce domain events (007), idempotently and
  validated, and run scheduled or queued jobs through Portalab's job system within its limits.
- **FR-014 Notifications, search, moderation**: a plugin MAY send notifications through Portalab (010,
  respecting members' preferences), provide search results (008, filtered by rights) and use moderation (012).
- **FR-015 Privacy**: a plugin storing members' data MUST provide its export and deletion (021); a plugin
  that does not MUST NOT be enabled.
- **FR-016 Product types**: a plugin MAY declare product types for the shop: a schema of what a product holds,
  activation, deactivation and refund hooks, and a card drawn in a sandbox; buying, coins, ownership,
  refunds and gifts MUST stay the shop's (015); a failed activation MUST follow the shop's rule, never lose a
  payment.
- **FR-017 Settings and credentials**: a plugin MAY declare settings, shown by Portalab as a form; secret
  settings MUST be kept by Portalab and never readable by the plugin, only added to its calls to listed hosts.
- **FR-018 Network**: a plugin MAY reach outside hosts it lists and the Admin accepts; its outgoing traffic
  MUST go through Portalab to those hosts only, be recorded and rate-limited; private network addresses MUST
  be refused unless explicitly listed.
- **FR-019 Portal data**: a plugin MAY reach portal data only through operations of the exposure catalog (029)
  labelled read or action and accepted at review, with the acting member's rights or, for jobs, through
  capabilities granted for that purpose; forbidden and unlabelled operations MUST be refused, committing ones
  MUST NOT be callable by a plugin without the member's confirmation.

**Compatibility and migration**

- **FR-020**: Declarative plugins of 023 MUST keep working unchanged.
- **FR-020a**: On an existing install, 023's code plugins MUST keep running as before at upgrade (unconfined,
  permanent warning) until migrated; on a new install unconfined plugins MUST be off; a newly installed code
  plugin MUST run confined.
- **FR-021**: Code plugins of 023 MUST be offered a migration to confinement preserving their data; until
  migrated they MUST run only while unconfined plugins are allowed (FR-020a), with a permanent warning in the
  administration.
- **FR-022**: 023's invariants (disabling keeps data, removes UI cleanly; core fully functional without
  plugins; dependencies, compatibility, versions; quarantine) MUST keep holding.

**Defence in depth (deployment)**

- **FR-023**: The delivered image MUST run without administrator rights, with its files read-only outside the
  data volumes.
- **FR-024**: Portalab MUST support an outbound allow-list (the configured services, pack sources, sign-in
  providers, plugins' accepted hosts) and refuse other outgoing connections when the administrator enables it.
- **FR-025**: Each Portalab module MUST access only its own data in the database (least privilege per module).
- **FR-026**: The audit trail MUST be able to be copied off the machine as it is written.

**Extensions as one package (like Jellyfin's)**

- **FR-028**: An extension package MAY hold, together: confined code (this spec), contributions to Portalab's
  interface slots (below) and visual pack elements (028: looks, widgets, booster scenes, interfaces); it MUST
  be analysed, reviewed (one review listing everything it asks), enabled,
  updated, rolled back, disabled and removed as one.
- **FR-029**: Portalab's interface MUST offer named slots an extension may contribute to: navigation entries
  and sections, pages, actions in the top bar (an icon with a count), tabs on existing pages, home
  sections, actions and panels on objects (a title, a person, a profile, a ticket, a product…), the media
  player (controls, overlays at given moments, chapter marks), member settings and administration settings
  panels, dashboard widgets (028), notification kinds and search result kinds; a slot's action MAY open a
  surface drawn by Portalab (a modal or a side drawer) holding the extension's blocks; each slot's content is declared as blocks Portalab draws with its own components
  (or a 028 sandboxed element), never on the administration, security, account or sign-in pages.
- **FR-029a**: An extension MAY ship its own views for its pages, surfaces and slots, including a launcher
  in a bottom corner of every screen and a floating panel; a view MUST run sandboxed with no network and no
  session, reach only its own extension's operations and live topics through Portalab, receive the member's
  theme tokens (kept in step with their changes) and stay inside a frame drawn by Portalab that names the
  extension; in safe mode its blocks MUST be shown instead.
- **FR-030**: In the player slot, an extension MUST receive only the title being played and, when it shows
  something, the moment it is for; it MAY declare overlays at given times and simple actions (go to a time,
  open a form) that Portalab's player draws and performs; it MUST NOT receive the stream itself.
- **FR-031**: An extension MAY set default order and visibility of Portalab's own home sections and navigation
  entries; members MUST be able to restore Portalab's order and hide any contribution on their own screens;
  no extension MAY remove a core function.
- **FR-032**: Several extensions contributing to one slot MUST be ordered deterministically (023), the Admin
  able to reorder or hide any contribution portal-wide.
- **FR-033**: Example extensions « Playlist » (a « + Playlist » action on media pages opening a modal, a page
  of the member's playlists, a modal to create and edit one) and « Messenger » (a top-bar icon with the
  unread count opening a drawer with the conversations, sending directly, live) MUST be provided and pass
  analysis.

**Authoring**

- **FR-027**: Plugin authors MUST have an SDK of the extension points and capabilities, a simulated Portalab
  to run locally, a template, and the offline analysis tool; three example plugins (Forum, Chat, a product
  type) MUST be provided and pass analysis.

### Key Entities *(include if feature involves data)*

- **Confined plugin**: a 023 plugin whose code runs apart, with its manifest of requested capabilities,
  limits and status (running, held, quarantined).
- **Capability**: an entry of Portalab's closed list (storage, operations, permissions, pages, live channels,
  events, jobs, notifications, search, moderation, privacy, product types, settings, network hosts, portal
  data reads), with its plain-words description.
- **Grant**: per plugin version, the capabilities accepted by the Admin, when and by whom; revocable.
- **Plugin storage**: a plugin's own data, its quota and usage.
- **Plugin operation**: an operation in the plugin's namespace with its permission and exposure label.
- **Plugin product type**: a product type a plugin declares, its schema and hooks.
- **Listed host**: an outside host a plugin may reach, with its accepted settings and recorded calls.
- **Extension package**: one installable unit holding confined code, slot contributions and visual elements,
  with one manifest, one review and one lifecycle.
- **Slot contribution**: what an extension adds to a named slot of Portalab's interface, its order, and members'
  hidden choices.
- **Attempt record**: a forbidden or over-limit attempt by a plugin, counted toward quarantine.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In an isolation campaign of probe plugins (portal data, secrets, files, unlisted network, other
  plugins' storage, privilege escalation, unbounded resources), 100% of attempts are refused and recorded.
- **SC-002**: While a probe plugin crashes, loops or floods, 100% of the portal's own end-to-end journeys pass.
- **SC-003**: The example Forum plugin is installed, reviewed, enabled and used end to end (post, notify,
  search, export, disable, re-enable) by an administrator and two members in under 15 minutes.
- **SC-004**: Chat messages reach the other members of a room within 1 second for 95% of messages with 50
  members connected.
- **SC-005**: A plugin operation adds at most 50 ms to the time a member waits, for 95% of calls, compared to
  the same work done by Portalab itself.
- **SC-006**: 100% of 023's automated tests pass; declarative plugins work unchanged; a migrated code plugin
  keeps 100% of its data.
- **SC-007**: A purchase of a plugin product type never loses coins: in fault-injection tests where activation
  fails, 100% of purchases end refunded or pending per the shop's rule.
- **SC-009**: The example « Playlist » extension is installed as one package; a member adds a title to a new
  playlist from its media page in under 30 seconds, and removing the extension leaves 0 contributions on any
  screen.
- **SC-010**: Contributions in slots add at most 100 ms to the display of the page they appear on, for 95% of
  page views.
- **SC-008**: A plugin's credentials never appear in its storage, its logs or its pages (0 occurrences in the
  secret-scanning tests).

## Assumptions

- Plugins are written in languages the confined runtime supports; the plan chooses the runtime and the
  languages; authors of 023's code plugins get a migration guide.
- Confinement is enforced by Portalab and its runtime, not by the plugin's cooperation.
- The Admin remains trusted; this spec protects the portal and its members from plugins, not from the operator.
- The outbound allow-list (FR-024) is opt-in at first to avoid breaking existing installs, recommended in the
  documentation, and on by default for new installs once stable.
- Extension repositories, signatures, updates from catalogs and revocation are spec 031's.
