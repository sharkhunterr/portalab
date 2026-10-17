# Feature Specification: Trusted Interfaces (Complete Interfaces by Packs, Trust Layer, Broker, Hardened Looks)

> **Scope revision 2026-10-17** — reduced to the exposure catalog, the « Interfaces » gallery, safe mode and fixes; complete interfaces, trust layer, seal, hardened looks and pack origin dropped, budget postponed. See [SCOPE-REVISION.md](SCOPE-REVISION.md).

**Feature Branch**: `029-trusted-interfaces`
**Created**: 2026-10-16
**Status**: Draft
**Input**: User description: "Trusted interfaces — complete interfaces brought by packs, made safe by a trust layer (follow-up of spec 028; issues #140, #141, #143 and the architecture discussion of 2026-10-16). Let a visual pack replace Portalab's whole interface (layout, pages, navigation, transitions, sound, 3D/HD effects, any framework) — like Jellyfin's themes and clients, but safe for members and the server — while today's interface stays the built-in default and nothing that exists breaks. Complete interface packs confined on a separate origin; a broker with an exposure catalog of the portal's operations; a trust layer (confirmations, prices, rarities, draw results, amounts, identity, security drawn by Portalab above everything, a personal seal per member, an exit control and a safe mode); hardening of today's looks (no escaping their box, no literal text, budgets with fallback, separate origin); an SDK, an example pack, measures and visual probes at the Test step; full compatibility with what exists. Out of scope: server-side code from packs (spec 030), extension repositories and signatures (spec 031), protecting members from a malicious server operator."

## Role of This Document

This is a **detailed feature specification** for **trusted interfaces**: a pack may bring a *complete*
interface — its own layout, pages, navigation, transitions, sounds and visual effects, built with whatever
the author likes — that replaces Portalab's interface for the members who choose it, without ever being able
to act as them behind their back, deceive them about what they commit to, read more than they may, or send
anything out. It extends Visual Packs (`028`: the pack format, registry, six-step workflow, sandbox, data
contracts, economy decided at review), and relies on Personalization & Themes (`022`), the Visual Experience
(`027`), the Marketplace (`015`), Gamification (`013`), the Dashboard (`009`), Media (`024`), Roles &
Permissions (`003`), Administration (`020`) and Privacy (`021`), under the project Constitution
(`.specify/memory/constitution.md`).

**Why this spec exists**: spec 028 lets packs dress Portalab's interface (palettes, looks, a navigation of
their own, widgets, booster scenes), but the interface itself stays Portalab's. Members and administrators
want what media servers' communities offer — interfaces that look and feel completely different. Giving a
pack the whole screen is only acceptable if what engages a member (a purchase, a request, a deletion, a
draw, a price) can never be imitated or hidden, if the pack can only see and do what the member may, and if
it can never reach the outside. This spec adds that **trust layer** and the **broker** through which an
interface works, and closes the two weaknesses found in 028's looks (a stylesheet escaping its box, a look
writing misleading text — issues #140, #141), with run-time budgets for heavy visuals (#143).

Scope boundary: this spec **owns** the complete-interface element, the confinement of interfaces, the broker
and its exposure catalog, the trust layer (trusted confirmations, the member's seal, the exit control and
safe mode, the surfaces that always stay Portalab's), the host components an interface may place, the
hardening of looks, run-time budgets and fallbacks, the separate origin of pack content, the interface SDK
and the Test step's measures and probes. It does **not** add server-side code from packs (spec 030),
extension repositories, signatures or revocation (spec 031), nor change what a member may do or see
(permissions, economy, privacy rules stay those of their owning specs). It chooses no technology.

### Principles (normative)

- **A pack draws, Portalab decides**: whatever an interface shows, every read and every action goes through
  Portalab with the member's own rights, and the server checks everything again.
- **What engages is drawn by Portalab**: confirmations, prices, rarities, draw results, amounts, identity
  and security are always drawn by Portalab, above anything a pack draws, and can always be told apart from
  an imitation.
- **Nothing leaves**: no pack content — interface, look, widget, scene — can reach the network, a session,
  stored data of Portalab's, or another page.
- **The way back is always there**: a member can leave any interface at any time, and a failing interface
  gives way to Portalab's on its own.
- **Nothing breaks**: Portalab's interface stays the built-in default; everything spec 028 delivered keeps
  working unchanged.

## Clarifications

### Session 2026-10-16

- Q: How far may a pack change the interface? → A: completely — layout, pages, navigation, transitions,
  sound, 3D and HD effects, any framework — as long as it stays safe for members and the server.
- Q: Is today's interface replaced? → A: no; it stays the built-in default and the fallback; a complete
  interface is a choice a member makes among those the administrator published.
- Q: What about server-side features (a chat, a forum, a new kind of product)? → A: they belong to confined
  plugins (spec 030); an interface only shows and acts through the broker.
- Q: Who reviews what an interface may read and do? → A: the Admin, at the Review step of 028's workflow,
  accepting each operation the interface declares, like a widget's data contracts.

### Session 2026-10-17
- Q (user, after the POC run): are complete interfaces offered or sold? → A: sold in the shop like any look
  (their pack's price and rarity), the administrator may offer them at Review (supersedes « offered by
  default »).
- Q (user): may an interface limit what a member can reach (the administration…)? → A: no — like changing
  desktop environment under Linux, an interface is the shell and never removes a function. It is handed
  everything the member may open (every section and page, the administration for an administrator, the
  member's own menu) and may redraw any page its own way (its views); every other page — the dashboard
  and its widgets, the administration, the account, any section — is Portalab's, shown in the interface's
  content area without Portalab's header or menu, wearing the interface's theme. The dashboard stays the
  member's widgets (never one of its views); the administration, account, privacy and sign-in pages are
  never its views; no administration operation is ever open to a pack's code.
- Q (user): « themes » or « interfaces »? → A: what 028 called a theme is an interface: one « Interfaces »
  gallery holds Portalab's, the packs' and the complete ones.

Decided by default with the recommended option (the user asked to chain without approval; to revisit):

- Q: How is the separate origin of pack content reached by default? → A: a second port of the same server
  (Portalab's port + 1 unless configured), optionally a host name the administrator sets; it works on a local
  network with no DNS change.
- Q: What is a member's seal made of? → A: a symbol chosen among 48 and a colour among 12, with an optional
  word of up to 16 characters; Portalab assigns a random symbol and colour until the member chooses.
- Q: Is a complete interface a shop product? → A: like any 028 element — the Admin decides at Review whether
  it is sold (price, rarity), offered to everyone or a reward; offered by default.
- Q: Which host components does the first version provide? → A: the media player, the book reader, the
  framed avatar and the booster stage; others are added later, each labelled like an operation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A member always recognises a genuine confirmation and can always leave (Priority: P1)

Whatever interface a member uses — Portalab's, a dressed one, or a complete one brought by a pack — every
moment that engages them (buying, opening a booster, requesting a title, deleting something, publishing,
changing their account or security) is confirmed by Portalab in a layer above everything else, showing the
exact content and their **personal seal**: a word, an image or a colour they chose, that no pack ever
receives. A control drawn by Portalab (and a keyboard shortcut) brings them back to Portalab's interface at
any time; a **safe mode** (from their settings, or from an address they can bookmark) shows Portalab's
interface without any pack.

**Why this priority**: it is what makes every other freedom given to packs acceptable; without it, a pack
covering the screen could imitate a purchase or a sign-in.

**Independent Test**: with a test pack that draws a perfect imitation of a purchase confirmation, a member
sees the imitation without their seal and the genuine confirmation with it; the exit control and the
shortcut bring back Portalab's interface from any screen; the safe-mode address shows no pack content.

**Acceptance Scenarios**:

1. **Given** a member who chose a seal, **When** any committing action is confirmed, **Then** the
   confirmation is drawn above all pack content, shows the exact content of the action and the member's seal.
2. **Given** a pack, **When** it runs, **Then** it never receives the member's seal, by any means.
3. **Given** a member who never chose a seal, **When** they first meet a confirmation, **Then** Portalab
   assigns one and invites them to choose their own.
4. **Given** any interface on screen, **When** the member uses the exit control or the shortcut, **Then**
   Portalab's interface comes back at once, at the equivalent page when there is one.
5. **Given** the safe-mode address, **When** a member opens it, **Then** no pack content of any kind is
   loaded until they leave safe mode.
6. **Given** a pack, **When** the member opens administration, security, account or sign-in pages, **Then**
   those pages are always Portalab's own, without any pack content.

---

### User Story 2 - Today's looks can no longer escape their place or mislead (Priority: P1)

The looks of spec 028 (frames, banners, name styles, badges, notification styles, booster scenes, widget
styles, interfaces' stylesheets…) keep their full visual freedom inside their own element, but can no longer
cover the rest of the screen, sit above the trust layer, or write words of their own; what states a price,
a rarity, a draw result or an amount is always Portalab's text, out of any look's reach. Pack content is
served from a separate origin of its own.

**Why this priority**: it closes the two weaknesses found in 028 (#140, #141) for every pack already
published, before more freedom is given.

**Independent Test**: probe looks that try to cover the screen, to rise above a confirmation, or to replace
a card's rarity text by another are refused at analysis, neutralised at run time if they slipped in, and
the probes report « refused »; every published example pack still passes.

**Acceptance Scenarios**:

1. **Given** a look whose stylesheet would leave its element's box or rise above other content, **When** it
   is analysed, **Then** the finding is blocking and the reason is said in plain words.
2. **Given** a look that would inject literal text, **When** it is analysed, **Then** the finding is
   blocking; empty decorations stay allowed.
3. **Given** a booster card, a price or an amount dressed by a look, **When** it shows, **Then** its words
   are Portalab's and readable whatever the look does.
4. **Given** pack files and sandboxes, **When** a member's page loads them, **Then** they come from an
   origin separate from Portalab's own.

---

### User Story 3 - A member chooses a completely different interface (Priority: P1)

A member opens their appearance settings and chooses, among the interfaces the Admin published, one that
replaces Portalab's interface entirely — another layout, other pages, another navigation, its own sounds
and effects. They browse their media, their progression, their notifications and the shop through it; when
they buy, request or open something, Portalab's confirmation (with their seal) appears above it. They can
go back to Portalab's interface at any time.

**Why this priority**: it is the feature the user asked for — Portalab extensible like a media server's
clients and themes — and it builds on stories 1 and 2.

**Independent Test**: with the example complete interface published, a member can sign in, choose it, browse
the catalog, see their progression and notifications, request a title (confirmed by Portalab with the
seal), and leave it — while the interface never reaches the network nor sees a session.

**Acceptance Scenarios**:

1. **Given** published complete interfaces, **When** a member opens their appearance settings, **Then** they
   see each with its name, preview and what it reads of their data, and can choose one.
2. **Given** a member using a complete interface, **When** it shows their data, **Then** it shows only what
   they may see in Portalab's own interface, nothing more.
3. **Given** a member using a complete interface, **When** they act (mark read, favourite, play), **Then** the
   action happens with their rights; **When** the action engages them, **Then** Portalab confirms it first.
4. **Given** a complete interface that stops responding, crashes or exceeds its budget, **When** it happens,
   **Then** Portalab's interface comes back within seconds and the failure is counted for the administrators.
5. **Given** a member on a phone, **When** they use a complete interface, **Then** it receives the device's
   form and the member's preferences (language, reduced motion, text size) and works within them.

---

### User Story 4 - The Admin reviews what an interface may read and do (Priority: P2)

At the Review step of spec 028's workflow, the Admin sees the operations a complete interface declares — in
plain words, grouped as reads, simple actions and committing actions — and accepts each one; an interface
asking for a forbidden operation (administration, security, account, sign-in) cannot be published. New
operations Portalab gains later are closed to every interface until they are labelled.

**Why this priority**: it is the control point of what a complete interface can do; it reuses 028's review.

**Independent Test**: an interface declaring a forbidden operation is blocked at analysis; one declaring an
unknown operation is blocked; at run time, an operation it did not declare is refused even if the member
could do it in Portalab's interface.

**Acceptance Scenarios**:

1. **Given** an interface's version, **When** the Admin reviews it, **Then** each declared operation is listed
   with what it reads or does, its group, and must be accepted.
2. **Given** an operation labelled forbidden or not labelled at all, **When** an interface declares it,
   **Then** analysis blocks the version.
3. **Given** a running interface, **When** it asks for an operation it did not declare, **Then** it gets a
   refusal and nothing is called.
4. **Given** an operation the member may not do, **When** the interface asks for it, **Then** the answer is the
   same refusal Portalab gives the member anywhere else.

---

### User Story 5 - An interface places Portalab's own components (Priority: P2)

A complete interface shows a film, a book, an avatar or a booster's opening by designating a region of its
screen; Portalab draws its own player, reader, avatar or booster stage there, with the member's session and
rights, so no stream address, reading token or draw ever passes through the pack.

**Why this priority**: media and draws are what members use most; they must work in any interface without
handing the pack what lets one reach them.

**Independent Test**: the example interface plays a title and opens a booster through host components; the
interface frame never receives a stream address, a token or a draw before Portalab shows it.

**Acceptance Scenarios**:

1. **Given** a complete interface, **When** it places a player for a title, **Then** Portalab's player plays
   it in that region with the member's rights.
2. **Given** a host component in place, **When** the interface moves or resizes its region, **Then** the
   component follows; **When** the interface tries to draw over it, **Then** the component stays visible.
3. **Given** a booster opened from a complete interface, **When** cards are drawn, **Then** Portalab draws the
   draw (its scene may still be a pack's, per 028) and the interface learns the result only once shown.

---

### User Story 6 - Heavy visuals never make the portal unusable (Priority: P2)

Every pack visual — a complete interface, an HD look, a scene, a widget — runs within a budget (frames per
second, processor, memory) adapted to the device. Above it, its quality lowers, then it gives way to its
light version or Portalab's own; the member is told discreetly and the administrators see the failure on
the pack. Portalab's own controls (the trust layer, the exit control) stay responsive whatever a pack does.

**Why this priority**: freedom of visuals must not cost the members' comfort, especially on phones.

**Independent Test**: a deliberately heavy probe pack lowers its quality, then falls back, within the stated
delays; the exit control answers instantly while it runs.

**Acceptance Scenarios**:

1. **Given** a visual exceeding its budget, **When** it lasts, **Then** its quality lowers, then it falls back.
2. **Given** a member asking for less motion, **When** visuals show, **Then** they follow it (still frames or
   their light version).
3. **Given** any pack content running, **When** the member uses the trust layer or the exit control, **Then**
   it answers without delay.

---

### User Story 7 - A pack author builds a complete interface with confidence (Priority: P3)

A pack author starts from a project template and an SDK that lists every operation an interface may use,
typed from Portalab's description; a simulated broker lets them build and test offline; the offline analysis
tool checks their pack as the Admin's will. An example pack with a totally different interface shows every
capability. At the Test step, the Admin sees the interface's load time, frames per second and memory on a
desktop and a phone profile, and the results of automatic visual probes (nothing covers the trust layer's
controls; the texts the pack generates are listed).

**Why this priority**: the ecosystem lives from authors; it does not change members' safety.

**Independent Test**: from the template, an author builds the example interface offline, the analysis tool
reports no blocking finding, and the Admin's Test step shows its measures and probe results.

**Acceptance Scenarios**:

1. **Given** the SDK and the simulated broker, **When** an author builds an interface, **Then** they can run
   it offline with sample data for every operation.
2. **Given** a pack, **When** the offline tool analyses it, **Then** it reports what the Admin's analysis would.
3. **Given** a version at the Test step, **When** the Admin runs it, **Then** measures and probe results are
   shown and kept with the version.

---

### Edge Cases

- A complete interface asks for an operation Portalab added after the interface was published: it is
  unlabelled, hence refused, until it is labelled and the interface's new version is reviewed.
- The member's session expires while a complete interface is shown: Portalab's sign-in appears (Portalab's
  own page); afterwards the member comes back to the interface where they were.
- A pack draws a fake confirmation or a fake sign-in: it carries no seal, and no action can result from it.
- A committing action with free text (a comment, a ticket, a publication): Portalab shows the exact text in
  the confirmation; nothing is published without it.
- A pack tries to copy a member's data into something public (a post, a name): the committing action shows
  the exact content and the member decides.
- The pack of the interface a member uses is switched off, archived or removed: the member is moved back to
  Portalab's interface, their choice kept for when it comes back.
- An interface on a deep link (an address of Portalab's own page): Portalab opens the equivalent view of
  the interface when it declares one, else its own page.
- Several tabs: each runs the member's chosen interface; leaving it in one tab does not change the choice.
- An interface without a phone layout on a phone: Portalab's interface is used there, the choice kept for
  larger screens.
- An interface failing the accessibility floor: it is flagged at analysis (warning) and members are told at
  choice time; members needing it can keep Portalab's interface.
- Media playback and downloads: always through host components; an interface never handles a stream.
- An interface that keeps the member busy (endless animations, sounds): reduced motion and the member's
  sound preferences apply; the exit control is always there.
- The seal itself: the member can change it at any time from their account (a Portalab page); it is never
  shown inside pack content, nor sent to any pack, nor written in places a pack can read.
- Safe mode for the Admin: the administration never shows pack content anyway; safe mode also hides looks on
  the Admin's own pages elsewhere.

## Requirements *(mandatory)*

### Functional Requirements

**Trust layer**

- **FR-001**: Portalab MUST draw every confirmation of a committing action (purchase, booster opening,
  request, deletion, publication, account or security change, any action an operation labels committing)
  itself, above every pack content, in a way no pack content can cover, move or restyle.
- **FR-002**: Each confirmation MUST show the exact content of the action (what, how much, to whom, the exact
  text of any free text) and the member's seal.
- **FR-003**: Each member MUST have a personal seal — a symbol among 48 and a colour among 12, with an
  optional word of up to 16 characters — chosen in their account page; Portalab MUST assign a random symbol
  and colour until they choose; it MUST never be handed to, drawn inside or readable by any pack content.
- **FR-004**: Prices, rarities, draw results, amounts, the member's identity and security indications MUST
  be drawn as Portalab's own text wherever they appear, and stay readable whatever looks or interfaces do.
- **FR-005**: An exit control drawn by Portalab and a keyboard shortcut MUST be available on every screen of
  any interface and bring back Portalab's interface at once (at the equivalent page when there is one).
- **FR-006**: A safe mode MUST show Portalab's interface without any pack content, reachable from the
  member's settings and from an address they can bookmark; it MUST last until the member leaves it.
- **FR-007**: Administration, security, account, sign-in and terms pages MUST always be Portalab's own,
  without pack content.

**Hardened looks (028)**

- **FR-008**: A look's stylesheet MUST NOT be able to draw outside its element's box or above other content;
  analysis MUST block fixed or sticky positioning, unbounded stacking and escaping dimensions or transforms;
  the browser-side guard MUST neutralise them again; parts of a booster scene meant to extend beyond the pack
  MUST stay within their declared stage.
- **FR-009**: A look MUST NOT inject literal text; analysis MUST block it; empty decorations and Portalab's
  own values stay allowed.
- **FR-010**: Pack files, sandboxes and complete interfaces MUST be served from an origin separate from
  Portalab's own, so they run apart from Portalab's pages — by default a second port of the same server
  (Portalab's port + 1), or a host name the administrator configures.

**Complete interfaces**

- **FR-011**: A pack MAY bring a complete-interface element: an application drawn in a confined frame of the
  separate origin, covering the screen below the trust layer, without session, cookies, storage of
  Portalab's, network access, forms, popups or navigation of the page.
- **FR-012**: A complete interface MAY use any drawing capability of the browser (2D, 3D and GPU drawing,
  compiled code, background workers, packaged video, audio and fonts) but MUST NOT reach the network or
  device sensors (camera, microphone, location).
- **FR-013**: A complete interface MUST declare its operations, its forms (phone, tablet, desktop), the
  equivalents it offers to Portalab's pages, and its light version; the Admin MUST accept its operations at
  Review (028) before publication, and decide there, as for any 028 element, whether it is sold (price,
  rarity), offered to everyone (the default) or a reward.
- **FR-014**: Members MUST be able to choose a published complete interface in their appearance settings,
  seeing its name, preview, forms and what it reads of their data; their choice MUST be kept per member and
  per device form.
- **FR-015**: A complete interface MUST receive the member's preferences that matter to drawing (language,
  reduced motion, text size, colour scheme, device form) and be told when they change.
- **FR-016**: When a complete interface fails to start, stops responding, crashes or exceeds its budget,
  Portalab's interface MUST come back within a few seconds and the failure MUST be counted on its pack.

**Broker and exposure catalog**

- **FR-017**: A complete interface MUST read and act only through Portalab's broker, which performs each
  operation with exactly the member's rights; the server MUST check every operation as it does for
  Portalab's own interface.
- **FR-018**: Every operation of Portalab MUST carry a label: read, simple action, committing action or
  forbidden; an operation without a label MUST be treated as forbidden.
- **FR-019**: Committing actions MUST always go through the trust layer's confirmation (FR-001, FR-002)
  before they happen.
- **FR-020**: Operations of administration, security, account, authentication and sensitive settings MUST
  be labelled forbidden; an interface asking for them MUST be refused at analysis and at run time.
- **FR-021**: At run time, an operation the interface did not declare, or that the Admin did not accept,
  MUST be refused without being performed.
- **FR-022**: Images and files MUST be handed to an interface as their content, never as addresses carrying
  a session or a token; live updates (notifications, progression) MUST be delivered through the broker.
- **FR-023**: Operations performed through a complete interface MUST be attributed to it in the audit log
  and limited in rate per interface; an interface exceeding its limits MUST be slowed, then stopped.

**Host components**

- **FR-024**: A complete interface MAY place Portalab's own components — in the first version the media
  player, the book reader, the framed avatar and the booster stage; others are added later, each labelled like
  an operation — in a region it designates; Portalab MUST draw them with the
  member's session and rights, follow the region's moves, and keep them visible above the interface.
- **FR-025**: Stream addresses, reading tokens and draw results MUST never pass through a complete interface
  before Portalab has shown them.

**Budgets and fallbacks**

- **FR-026**: Every pack visual (complete interface, HD look, scene, widget) MUST run within a budget of
  frames per second, processor time and memory adapted to the device; above it, Portalab MUST lower its
  quality, then fall back to its light version or Portalab's own, tell the member discreetly and count it
  for the administrators.
- **FR-027**: Portalab's trust layer and exit control MUST stay responsive whatever pack content runs.

**Authoring and review**

- **FR-028**: Pack authors MUST have an SDK listing every operation an interface may use with its contents,
  a simulated broker with sample data, and a project template; the offline analysis tool MUST check complete
  interfaces as the Admin's analysis does.
- **FR-029**: The Test step (028) MUST measure a complete interface's load time, frames per second and memory
  on a desktop and a phone profile, run automatic visual probes (nothing covers the trust layer's controls,
  the texts the pack generates are listed) and keep the results with the version.
- **FR-030**: An example pack with a totally different interface MUST be provided and pass analysis with no
  blocking finding.

**Compatibility**

- **FR-031**: Portalab's interface MUST remain the built-in default and the fallback of every failure.
- **FR-032**: Everything spec 028 delivered — interface definitions, navigations of their own, looks, booster
  scenes, widgets, palettes, the built-in packs, packs of format 1 — MUST keep working without change for
  members; looks that FR-008/FR-009 now refuse MUST be listed for the Admin with what to change, and keep
  showing (neutralised) until replaced.
- **FR-033**: Members' choices (interfaces, looks, preferences) MUST be kept through this change.

### Key Entities *(include if feature involves data)*

- **Complete interface**: an element of a pack (028) — its application files, forms, declared operations,
  equivalents of Portalab's pages, light version, preview; reviewed and published like any element, sold,
  offered (default) or a reward as decided at review.
- **Operation label**: for each operation of Portalab, its group (read, simple action, committing action,
  forbidden), its plain-words description and what a confirmation shows for it.
- **Accepted operations**: per interface version, the operations the Admin accepted at review.
- **Seal**: per member, a symbol (among 48), a colour (among 12) and an optional word (≤ 16 characters)
  shown on genuine confirmations; assigned at random until chosen; never exposed to packs.
- **Interface choice**: per member and device form, the complete interface chosen (or Portalab's), and the
  safe-mode state.
- **Host component placement**: a region an interface designates and the Portalab component drawn in it.
- **Visual budget**: per kind of visual and device, its limits; and the record of a visual's failures.
- **Test measures and probe results**: per version, load time, frames per second, memory per profile, and
  each probe's outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In an isolation campaign of probe packs (imitating a confirmation, covering the trust layer,
  reading a session, reaching the network, reading the seal, calling an undeclared or forbidden operation,
  injecting text into a look, escaping a look's box), 100% of attempts are refused or neutralised.
- **SC-002**: Every committing action performed from any interface shows a Portalab confirmation with the
  member's seal before it happens, in 100% of the actions of the e2e journeys.
- **SC-003**: From any screen of any interface, a member gets back to Portalab's interface in one action, in
  under 1 second.
- **SC-004**: A failing or frozen complete interface gives way to Portalab's interface within 5 seconds.
- **SC-005**: While any pack content runs, the trust layer and the exit control answer a member's action in
  under 0.1 second.
- **SC-006**: The example complete interface shows its first screen in under 3 seconds on the reference
  phone profile and keeps at least 30 frames per second while browsing.
- **SC-007**: A visual exceeding its budget lowers its quality within 3 seconds and falls back within 10.
- **SC-008**: 100% of the existing automated tests and example packs of specs up to 028 pass unchanged;
  members' choices are identical before and after.
- **SC-009**: A complete interface never shows a member data they could not see in Portalab's interface (0
  differences on the e2e comparison of reads).
- **SC-010**: A pack author builds the example interface from the template and runs it offline in under 30
  minutes, guided by the SDK alone.

## Assumptions

- Browsers members use support confined frames of another origin, a top layer for dialogs and background
  drawing; members on browsers that do not are kept on Portalab's interface.
- The separate origin is served by Portalab itself: a second port of the same server by default (Portalab's
  port + 1), or a host name the administrator configures; it works on a local network without DNS changes.
- Labelling Portalab's operations is done once for the existing API, then for each new operation as part of
  its spec; unlabelled operations stay forbidden meanwhile.
- The administrator of the server remains trusted; this spec protects members from extensions, not from the
  operator.
- Complete interfaces are client-side only; anything needing new server behaviour belongs to spec 030.
- Pack size limits of 028 are raised for complete interfaces to a value set at planning, still bounded.
