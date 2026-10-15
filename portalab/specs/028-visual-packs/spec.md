# Feature Specification: Visual Packs (Every Look as a Pack, Visual Import Workflow, Pack Navigations, Booster Scenes, Widgets, Minimal Public Surface)

**Feature Branch**: `028-visual-packs`
**Created**: 2026-10-15
**Status**: Draft
**Input**: User description: "Visual packs — every visual element of Portalab delivered as packs (built on the POC of issue #1, branch poc/visual-packs; issues #1, #134, #135). Built-in content as packs (an always-on « Portalab — socle » pack plus optional sub-packs per universe, season, HD collection and a « base collection » for loose elements), enabled or disabled by the administrator, owners keeping what they own; an import workflow redesigned and more visual (import → analysis → security → test → review → validation, versions, rollback, switch off, a registry kept by the portal); maximal security (pack scripts sandboxed, CSS confined, interface vocabulary limited, pack files served inert, audit, an intrusion guard blocking a malicious member, and a minimal public surface: without a session only sign-in and the single sign-on return answer); navigations of their own brought by packs; boosters as modular elements (the whole booster scene customizable, or only a booster's composition); widgets (restyled, or new widgets fed by Portalab through declared data contracts). Out of scope: a public pack marketplace, pack signing beyond fingerprints, multi-factor authentication."

## Role of This Document

This is a **detailed feature specification** for **visual packs**: the way every customizable look of the
portal — interfaces, palettes, animated backgrounds, avatar frames, banners, profile backgrounds, name
styles and their fonts, level badges, badges, titles, level-up moments, celebrations, notification styles
and animations, navigations, booster scenes, widget styles and widgets, product packs, theme packs and
boosters — is delivered, reviewed, published, worn and withdrawn. It turns the proof of concept of issue #1
(branch `poc/visual-packs`) into the product, and it refines Personalization & Themes (`022`), the Visual
Experience (`027`, layout-capable themes, the navigation variants), the Marketplace (`015`, products, packs,
boosters, ownership), Gamification (`013`, level rewards), the Dashboard (`009`, widgets), Extensibility
(`023`, packages, review, quarantine), Roles & Permissions (`003`), Administration (`020`) and Privacy (`021`),
under the project Constitution (`.specify/memory/constitution.md`).

**Why this spec exists**: the portal's looks are written in its code — every new look means editing about a
dozen places, and an administrator cannot add, remove or replace one without a new release. The proof of
concept showed that each look can live in its own files, be drawn by the portal's renderers and be
reviewed and published by an administrator, with the risks of outside content contained. This spec makes
that the only way looks exist — the built-in ones included — and adds what the proof of concept did not
cover: the built-in catalog as packs, a guided import workflow, booster scenes and widgets from packs, and
a portal that answers nobody without a session but for signing in.

Scope boundary: this spec **owns** the pack format and its contracts, the pack registry and lifecycle, the
import workflow, the review and publication of pack elements, the isolation of pack content at run time,
the packaging of the built-in catalog, the minimal public surface of the portal and the intrusion guard. It
does **not** change what a member may do or see beyond looks (permissions, economy rules, privacy), nor the
meaning of products, ownership, refunds and boosters (`015`), nor the functional behavior of widgets'
underlying data (`009` and the owning modules). It chooses no technology.

### Principles (normative)

- **Everything visual is a pack element**: a look exists only as an element of an enabled pack — the
  built-in ones included; the portal's code holds renderers and contracts, not looks.
- **Ownership is never lost**: a member keeps every product they own whatever happens to its pack; a look
  that cannot be shown falls back to a default, and comes back when its pack does.
- **Outside content can never act as a member**: whatever a pack holds — trusted source or not — it cannot
  read or change a member's data, reach the network, move the page or touch a protected surface.
- **Nobody is answered without a session but to sign in**.
- **Nothing is published unseen**: every version is analysed, shown and validated by an administrator
  before any member sees it; nothing updates on its own.

## Clarifications

### Session 2026-10-15

- Q: Which public exposure is targeted? → A: Portalab itself reduces its public surface to the minimum
  (signing in and the single sign-on return); no requirement on an upstream proxy or VPN.
- Q: How is the built-in content split? → A: one always-on « Portalab — socle » pack plus optional sub-packs
  (per universe, season, HD collection) and a « base collection » for elements belonging to no pack today.
- Q: What may packs do with widgets? → A: restyle existing widgets and bring new widgets, fed by Portalab
  through declared data contracts (never calling the portal themselves).
- Q: Method? → A: full Spec Kit (specify, clarify, plan, tasks), the proof of concept as the starting point.
- Q: When a new release of Portalab changes its built-in packs, what happens? → A: existing built-in packs
  are updated with the release (a « what changed » note in the administration); a new built-in pack arrives
  disabled and the administrator enables it if they want.
- Q: Which permission manages packs (import, test, validate, switch off, remove)? → A: a permission reserved
  to the Admin, never delegated to a role, since packs may hold code.
- Q: What does the intrusion guard do when a session of the Admin crosses the threshold? → A: the Admin is
  blocked like anyone else; an intervention on the server's own console lifts any block easily (the Admin's
  included).
- Q: Can a pack (and its files) be removed for good? → A: a pack some member owns a product of is only
  archived (switched off, its files and versions kept, can be enabled again); it can be removed for good only
  once no member owns any of its products; versions never published can be purged at any time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The Admin imports a pack through a guided, visual workflow (Priority: P1)

The Admin (the only one allowed to manage packs, FR-014a) receives a pack (a folder dropped in the portal's inbox, a file uploaded from the
administration, or the address of a repository). The portal walks them through six visible steps —
**Import** (the pack read, its files stored apart under their fingerprint), **Analysis** (what it holds, its
format, its looks and their conflicts, its economy), **Security** (what its stylesheets and scripts would try
and what the portal will refuse, explained in plain words), **Test** (every element drawn for real in a
sandbox, tried on oneself, measured in the browser), **Review** (the price, rarity, level and copies each
element proposes, changed if wanted) and **Validation** (published, or refused with a reason). Each step
shows its state (done, warning, blocking) and what to do next.

**Why this priority**: it is the door every look goes through — the built-in ones included — and the place
where the administrator's trust is earned.

**Independent Test**: import the example pack from the inbox; each step shows its result; validate with one
price changed; the elements appear in the shop with that price; a version with a blocking problem cannot
pass the Security or Analysis step.

**Acceptance Scenarios**:

1. **Given** a valid pack in the inbox, **When** the administrator reads the inbox, **Then** the pack appears
   at the Analysis step with its elements, their kinds and a summary (blocking / warning / info counts).
2. **Given** a version with a blocking finding, **When** the administrator tries to validate it, **Then** the
   validation is refused and the finding is shown with the element and file it concerns.
3. **Given** a version holding scripts, **When** it reaches Security, **Then** the administrator sees what the
   scripts may and may not do and must confirm explicitly before validating.
4. **Given** the Test step, **When** the administrator opens it, **Then** every element is drawn as members
   would see it (shop, profile, moment), can be tried on oneself, and the browser's measures (compiled or
   not, frames per second) are recorded with the version.
5. **Given** the Review step, **When** the administrator changes an element's price and validates, **Then**
   the published product carries the decided price and the decision is kept with the version.
6. **Given** a published version, **When** a new version of the same pack arrives, **Then** it waits at
   Analysis; nothing members see changes until it is validated.

---

### User Story 2 - The built-in catalog is delivered as packs the administrator enables or disables (Priority: P1)

Every look the portal offers today is an element of a pack: the « Portalab — socle » pack (always on: the
default interface, the free looks, what the portal needs to look right), sub-packs per universe, per season
and per HD collection, and a « base collection » for elements that belong to no pack today. The
administrator sees them in the same list as imported packs, enables or disables each sub-pack, and a member
keeps what they bought from a disabled pack.

**Why this priority**: it is what makes « everything visual is a pack » true — and lets an administrator
offer a small, focused catalog instead of everything.

**Independent Test**: after migration, every product, look and interface available before is available
again with the same key and the same owners; disabling a universe pack takes its products off sale and its
looks fall back to defaults for those who wear them; enabling it brings everything back.

**Acceptance Scenarios**:

1. **Given** an existing portal with owned products, **When** the built-in catalog becomes packs, **Then**
   every product keeps its key, its owners, its equipped state and its price, and members notice no change.
2. **Given** an element that belongs to no universe, season or collection today, **When** the catalog is
   packaged, **Then** it belongs to the « base collection » (never to no pack).
3. **Given** a sub-pack, **When** the administrator disables it, **Then** its products leave the shop, members
   wearing its looks see the default instead, and their ownership remains.
4. **Given** the socle pack, **When** the administrator looks at it, **Then** it cannot be disabled (only its
   optional elements may be taken off sale).
5. **Given** a disabled sub-pack, **When** it is enabled again, **Then** members see their worn looks again.

---

### User Story 3 - A malicious member cannot reach what is forbidden, and is blocked (Priority: P1)

A member probes what they may not open: administration pages and data, other members' objects, addresses
leaving their folder, settings they may not change. Every attempt is refused; past a threshold within a
short time, all their sessions are signed out and their account is blocked for a while — signing in again
changes nothing — and the administrators are alerted, see the block and may lift it. A visitor without a
session reaches nothing but the sign-in.

**Why this priority**: the portal is meant to be exposed to the internet; looks from outside must not open
new doors, and a member trying the doors must be stopped.

**Independent Test**: as a member, request administration routes, another member's objects and
attack-shaped addresses until blocked; the account stays blocked after signing in again; an administrator
is alerted and lifts the block; as a visitor, every route but the sign-in answers that a session is needed.

**Acceptance Scenarios**:

1. **Given** a visitor without a session, **When** they request any portal address other than signing in,
   the single sign-on return or the pages and files the sign-in page itself needs, **Then** nothing of the
   portal is revealed.
2. **Given** a member, **When** they repeatedly request what they may not open, **Then** after the threshold
   every session of theirs is signed out, their account is refused for the block's duration, the event is in
   the audit log and the holders of the security permission are alerted.
3. **Given** a blocked member, **When** they sign in again, **Then** their new session is refused too until
   the block ends or an administrator lifts it.
4. **Given** members sharing a network address with a blocked visitor, **When** they are signed in, **Then**
   they are not affected.
5. **Given** the administration overview, **When** a member requests it, **Then** it shows them no
   operational information (server errors, slowness, required actions).

---

### User Story 4 - A pack brings a navigation of its own (Priority: P2)

A pack's interface may bring a navigation never seen before (a sonar, a star chart, a ship's deck), drawn by
the pack itself. Members using that interface move through the portal with it on every device; it knows
only the sections and pages the member may open, and opens them by asking the portal. If it fails, a
built-in navigation takes over; the administration always keeps its own.

**Why this priority**: it is what lets a pack change the portal's principle and not only its colours.

**Independent Test**: publish a pack whose interface has its own navigation; a member choosing it navigates
every section; a failing navigation is replaced by a built-in one within seconds; on administration pages
the built-in navigation shows.

**Acceptance Scenarios**:

1. **Given** an interface with its own navigation, **When** a member uses it, **Then** they can reach every
   section and page they may open, on phone, tablet and desktop, with the keyboard too.
2. **Given** a navigation asking to open a page it was not given, **When** it asks, **Then** nothing happens.
3. **Given** a navigation that does not start or fails, **When** the page shows, **Then** a built-in navigation
   is shown instead, without the member losing their page.
4. **Given** any administration page, **When** an interface with its own navigation is in use, **Then** the
   built-in navigation shows there.

---

### User Story 5 - Packs customize the booster scene, or only a booster's composition (Priority: P2)

Opening a booster is a scene: the sealed booster, its opening, each card revealed with an effect according
to its rarity, the cards' faces and backs. Today's scene is the built-in default. A pack may bring any part
of it — a booster's look, an opening animation, a reveal effect per rarity, card faces and backs per rarity
— or a whole scene; a pack may also bring only a booster's composition (what it draws from, its odds), which
administrators can still create from the administration without any pack.

**Why this priority**: boosters are the most shown moment of the shop; letting packs dress them extends
universes to their richest scene.

**Independent Test**: publish a pack with a booster scene for one booster and a reveal effect for the
legendary rarity only; opening that booster plays the pack's scene; other parts use the default; a
booster created from the administration opens with the default scene.

**Acceptance Scenarios**:

1. **Given** a booster with a pack scene, **When** a member opens it, **Then** the pack's booster look,
   opening and reveal effects play, and the cards drawn and their rarities are exactly the portal's draw.
2. **Given** a scene bringing only some parts, **When** it plays, **Then** the missing parts use the default.
3. **Given** a pack bringing only a booster composition, **When** it is validated, **Then** the booster is on
   sale with the decided price and its composition, and opens with the default scene (or the scene chosen).
4. **Given** reduced motion, **When** a booster opens, **Then** cards are revealed without animation.

---

### User Story 6 - Packs restyle widgets and bring new ones (Priority: P3)

A pack may give existing dashboard widgets a style of its own, and may bring new widgets. A new widget is
drawn by the pack and fed by the portal: it declares which data it needs among contracts the portal offers
(the member's progression, what they are watching, what was recently added…), the administrator sees and
accepts those needs at review, and the widget only ever receives that data, for the member looking at it.

**Why this priority**: widgets are the dashboard's building blocks; packs extend them once the safer
elements are in place.

**Independent Test**: publish a pack with a widget style and a new widget needing the member's progression;
the style applies to the existing widget; the new widget shows the member's own progression and nothing
else; a widget asking for a contract the member may not read shows its empty state.

**Acceptance Scenarios**:

1. **Given** a new widget declaring data contracts, **When** the administrator reviews it, **Then** the
   contracts and what they reveal are listed and must be accepted.
2. **Given** a member placing that widget, **When** it shows, **Then** it receives only the declared data for
   that member, within what the member may see.
3. **Given** a widget asking for data it did not declare, **When** it asks, **Then** it receives nothing.

---

### User Story 7 - Packs evolve: updates, versions, rollback, switch off (Priority: P2)

A pack from a repository offers a new version: the administrator sees it is available, imports it, goes
through the workflow and publishes it; an element the new version no longer holds leaves the shop (owners
keep it); a version can be rolled back to; a whole pack can be switched off at once and on again.

**Why this priority**: a catalog lives; safe updates and an emergency stop are part of trusting it.

**Independent Test**: publish version 1, offer version 2 removing an element, publish it; the removed element
leaves the shop and its owners keep it; roll back to version 1; switch the pack off then on.

**Acceptance Scenarios**:

1. **Given** a pack from a repository, **When** the administrator checks for updates, **Then** they see the
   version offered and whether it is newer, and nothing is installed without them.
2. **Given** a published version, **When** the same version number arrives with other content, **Then** it is
   refused (a new number is required).
3. **Given** a pack switched off, **When** members use the portal, **Then** none of its files are served, its
   products are off sale and their looks fall back to defaults.

---

### User Story 8 - A pack author knows what to write (Priority: P3)

A pack author finds the format, every element type's contract (what it receives, what it must produce, what
it may not do), examples covering each kind of element, and gets the same analysis the portal runs before
sending their pack.

**Why this priority**: outside packs only exist if writing one is clear.

**Independent Test**: following the documentation only, write a pack with one element of each kind; the
analysis reports no blocking finding; it imports and publishes.

**Acceptance Scenarios**:

1. **Given** the documentation, **When** an author writes an element of any type, **Then** its contract
   (inputs, outputs, limits) is described with an example.
2. **Given** a pack, **When** the author runs the portal's analysis on it, **Then** they get the same findings
   the administrator would see.

### Edge Cases

- The administrator asks to remove a pack some member owns a product of: it is archived instead (switched
  off, files and versions kept), the number of owners shown; the product stays theirs, shown with its name,
  its look falling back to a default; enabling the pack again gives the looks back.
- Two packs bring the same look key: the second is blocked at Analysis unless the administrator explicitly
  decides it replaces the first (never silently).
- A pack replaces a built-in look (declared `replaces`): validated only with an explicit decision; rolling
  back restores the built-in look.
- An interface names a navigation, an animation or an ambient its pack does not hold and no enabled pack
  provides: refused at Analysis; if that pack is later disabled, the interface falls back to defaults.
- A pack's script never answers, loops or is too slow: the moment or navigation is replaced by its default
  within a bounded time, and the element is reported to the administrators.
- A pack is switched off while members are on a page drawn by it: the next page uses the defaults; nothing
  is cut mid-purchase.
- The member's language is not in the pack's texts: the other language provided is shown, else the key.
- Reduced motion: every pack moment shows its still frame or none, never an animation.
- A pack archive lies about its sizes, holds paths leaving its folder, links or files of forbidden kinds: it
  is refused before anything is stored.
- A repository address redirects elsewhere or answers too much: the import stops, nothing is stored.
- The Admin is the one crossing the threshold (or a stolen Admin session): the Admin is blocked like anyone
  else (sessions signed out, account refused); the block ends by itself or is lifted from the server's console
  (FR-040a) — never left without a way back.
- Many members share one network address: an address is only blocked for requests without a session.
- The intrusion guard restarts: blocks in force must survive a restart of the portal.

## Requirements *(mandatory)*

### Functional Requirements

**Pack format and elements**

- **FR-001**: A pack MUST be a folder or an archive holding a manifest (identity, version, names and
  descriptions in each supported language, author, licence) and one folder per element with its own
  manifest and files.
- **FR-002**: Each element MUST declare its type among: interface, navigation, palette, animated background,
  profile background, avatar frame, profile banner, name style, level badge, badge, title, level-up moment,
  celebration, notification style, notification animation, booster scene (or one of its parts: booster look,
  opening, reveal effect per rarity, card face, card back, per rarity), booster, widget style, widget, product
  pack, theme pack.
- **FR-003**: Each element MUST declare how it is drawn (stylesheets, a graphics-chip fragment, a script, a
  definition, or data only), its key (look) where it has one, its texts, the economy it proposes (price,
  rarity, level, copies, collection) and, where relevant, its place (navigations) and its timings (moments).
- **FR-004**: The portal MUST document, for each type, the contract it offers: what the element receives,
  what it must produce, what it may not do, with an example (see US8).

**Built-in catalog as packs**

- **FR-005**: Every look the portal offers at the time of migration MUST become an element of a pack: the
  « Portalab — socle » pack, sub-packs per universe, per season and per HD collection, and a « base
  collection » for elements belonging to none of them.
- **FR-006**: The migration MUST keep every product key, every owner, every equipped look, every preference
  naming a look and every price, rarity, level and availability; members MUST notice no change.
- **FR-007**: The socle pack MUST always be enabled; the administrator MUST be able to enable or disable each
  other built-in pack like an imported one.
- **FR-008**: The portal's code MUST NOT hold looks outside these packs once migrated (renderers and contracts
  only), so that adding, changing or removing a look never requires a release.
- **FR-008a**: When a release of the portal changes its built-in packs, the existing ones MUST be updated with
  the release (keys, owners and the administrator's enable/disable choices kept) and the administration MUST
  show what changed; a built-in pack new in that release MUST arrive disabled.

**Registry and lifecycle**

- **FR-009**: The portal MUST keep a registry of packs and of their versions (source, fingerprint, analysis,
  test measures, decisions, state) that survives restarts and is shared by every process of the portal.
- **FR-010**: A pack version MUST be stored apart under its fingerprint and never changed in place; the same
  version number with other content MUST be refused.
- **FR-011**: Packs MUST be importable from the inbox folder, from an upload in the administration and from a
  repository address; a repository MUST only be reached at its own hosts, with bounded sizes and redirects
  checked; updates MUST be offered, never installed on their own.
- **FR-012**: A published pack MUST be switchable off at once (its files no longer served, its products off
  sale, owners keeping them, looks falling back) and on again, and rollable back to a version validated before
  with the economy decided then.
- **FR-013**: An element a newer version no longer holds MUST leave the shop when that version is published;
  its owners MUST keep it.
- **FR-013a**: Removing a pack some member owns a product of MUST archive it instead (switched off, its files
  and versions kept, enabled again at will); a pack MUST be removable for good (files and versions deleted)
  only once no member owns any of its products; a version never published MUST be purgeable at any time; the
  socle MUST be neither archived nor removed.
- **FR-014**: Every action on a pack (import, analysis, test, decision, publication, refusal, switch, rollback,
  archiving, removal, purge) MUST be recorded in the audit log with who did it.
- **FR-014a**: Managing packs — importing, testing, reviewing, validating, refusing, enabling or disabling
  (built-in packs included), switching off, rolling back, removing — MUST require a permission reserved to the
  Admin that can never be granted to a role; every other member, administrators of other areas included, MUST
  be refused.

**Import workflow**

- **FR-015**: The administration MUST present each pack version through the steps Import, Analysis,
  Security, Test, Review and Validation, each showing its state (done, warning, blocking), its findings in
  plain words and the next action.
- **FR-016**: The Analysis MUST report the format, every element, look-key conflicts (with built-in looks and
  other packs), texts missing per language, file kinds and sizes, the economy proposed against the portal's
  own rules, and pack and booster contents.
- **FR-017**: The Security step MUST report, per element, what its stylesheets and scripts would try (rules
  outside their scope, outside addresses, network, storage, dynamic code) and what the portal will refuse;
  any blocking finding MUST prevent validation; scripts MUST require an explicit confirmation.
- **FR-018**: The Test step MUST draw every element as members would see it, let the administrator try it on
  themselves without changing their saved choices, and record the browser's measures with the version.
- **FR-019**: The Review step MUST let the administrator change price, rarity, level, copies and collection
  per element, and MUST list the data contracts new widgets ask for, which must be accepted.
- **FR-020**: Validation MUST publish the version's elements as shop products through the same path as any
  product, and MUST keep the decision (who, when, economy, confirmations) with the version.

**Isolation and security of pack content**

- **FR-021**: A pack script MUST always run isolated from the portal: no access to the member's session or
  data, to the portal's storage, to the network, to the page around it; it MUST only receive what its
  contract hands it and only ask what its contract allows.
- **FR-022**: A look's stylesheet MUST only style its own element; an interface's stylesheet MUST style the
  interface under its own key and MUST never style a protected surface (administration, purchases,
  confirmations, security dialogs); this MUST be enforced when the stylesheet is applied, whatever the analysis
  said.
- **FR-023**: An interface MUST only rename navigation entries, page titles and value names; what a member
  confirms MUST stay in the portal's words.
- **FR-024**: Pack files MUST be served so that opening one directly runs nothing and reaches nothing, and
  MUST not be readable by another site; files of a version not yet validated MUST only be served to
  administrators.
- **FR-025**: An element too slow for the device (a moment, a background, a navigation) MUST be stopped and
  replaced by its default within a bounded time.

**Navigations from packs**

- **FR-026**: An interface MUST be able to name a navigation brought by its pack; that navigation MUST know
  the member's sections and pages only by keys (never addresses), the current page, the interface's colours
  and words and the member's counters, and MUST only ask the portal to open one of those keys.
- **FR-027**: A pack navigation MUST declare its place (an edge of the screen, a floating control, its size,
  whether it may cover the screen while open) so the page keeps its room before it starts.
- **FR-028**: When a pack navigation fails, does not start within a bounded time or is not available, a
  built-in navigation MUST be shown; administration pages MUST always show the built-in navigation.
- **FR-029**: The portal MUST keep the navigation landmark, its accessible name and the skip link whatever the
  navigation drawing it.

**Booster scenes**

- **FR-030**: The booster scene MUST be made of parts — booster look, opening, reveal effect per rarity, card
  face and back per rarity — each provided by the default scene or by a pack; a scene MAY be bound to one
  booster or offered as the default for every booster.
- **FR-031**: The cards drawn, their rarities, refunds of duplicates and limits MUST be the portal's draw
  whatever scene plays; a scene only shows them.
- **FR-032**: A pack MAY bring only a booster's composition; administrators MUST still be able to create and
  edit a booster from the administration without any pack.

**Widgets**

- **FR-033**: A pack MUST be able to restyle existing widgets with styles members choose like any widget look.
- **FR-034**: A pack MAY bring new widgets; a new widget MUST declare the data contracts it needs among those
  the portal offers, MUST only receive that data, for the member viewing it, within what that member may see,
  and MUST never request the portal itself.
- **FR-035**: The portal MUST describe each data contract it offers (what it contains, which permission it
  requires, how often it refreshes).

**Public surface and intrusion guard**

- **FR-036**: Without a session, the portal MUST answer only: signing in and out, the single sign-on start and
  return, the pages and files the sign-in page needs, and the single-purpose links sent by e-mail or to a
  device (account verification, deletion cancel, a casting device's stream) — each refused unless its
  feature is enabled; every other address MUST reveal nothing.
- **FR-037**: Health and readiness checks MUST only answer the local machine and the networks the
  administrator declares; the first-run status MUST stop answering once the portal is set up; the terms of use
  MUST be shown after signing in.
- **FR-038**: The administration overview and every administration read MUST show a member only what their
  permissions allow; a provider of required actions declaring no permission MUST show nothing (#134).
- **FR-039**: The portal MUST weigh every refused or attack-shaped request per session and per network
  address; past a threshold within a window, every session of the member MUST be signed out, their account
  refused for a block duration (signing in again changing nothing), and a network address MUST be refused
  for requests without a session only.
- **FR-040**: Blocks MUST be recorded in the audit log, MUST alert the holders of the security permission,
  MUST be listed with their reason and remaining time in the administration, MUST be liftable by those
  holders, and MUST survive a restart.
- **FR-040a**: Anyone with access to the server's own console MUST be able to list and lift any block — the
  Admin's included — with a single local command, without signing in to the portal; the command MUST be
  recorded in the audit log.
- **FR-041**: Thresholds, window and block duration MUST have safe defaults and be adjustable by the
  administrator.

**Authoring**

- **FR-042**: The portal MUST provide the documentation of the format and contracts, example packs covering
  every kind of element, and a way for an author to run the same analysis outside the portal.

### Key Entities *(include if feature involves data)*

- **Pack**: an identity, its source (built-in, inbox, upload, repository), whether it is the socle, its state
  (enabled, switched off, archived), its current version, the version a repository offers.
- **Pack version**: a version number, a fingerprint, its stored files, its analysis findings, its test
  measures, its state (pending, published, refused, superseded) and the decision made (who, when, economy,
  confirmations).
- **Element**: belongs to a version; a type, a look key (when it has one), how it is drawn, its texts, its
  proposed and decided economy, its place or timings, its declared data contracts; published as a shop
  product (except navigations, scene parts and widget code, worn through their interface, booster or widget).
- **Finding**: a level (blocking, warning, info), a code, the element and file it concerns, its parameters.
- **Booster scene**: parts (booster look, opening, reveal effect per rarity, card face and back per rarity),
  each from the default or a pack element; bound to a booster or default for all.
- **Data contract**: a named set of data the portal offers widgets, its contents, required permission and
  refresh.
- **Block**: what is blocked (an account, a session, a network address), why, since when, until when, by how
  many points; liftable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After migration, 100% of the products, looks, interfaces and owners that existed before are
  available with the same keys; members report no lost item.
- **SC-002**: An administrator imports, tests, reviews and publishes a pack of a dozen elements in under 10
  minutes, guided by the steps alone.
- **SC-003**: Adding, replacing or removing a look requires no release of the portal (0 code changes).
- **SC-004**: In a security campaign covering every kind of element, 0 pack script reaches a member's data,
  the network or the page around it, and 0 pack stylesheet changes a protected surface.
- **SC-005**: A visitor without a session gets a meaningful answer from 0 addresses other than those listed
  in FR-036.
- **SC-006**: A member probing forbidden addresses is blocked within 20 attempts, cannot use the portal for
  the block's duration even after signing in again, and an administrator is alerted within 1 minute.
- **SC-007**: A pack navigation lets a member reach 100% of the sections and pages they may open, on phone,
  tablet and desktop, keyboard included; a failing one is replaced within 5 seconds.
- **SC-008**: A booster opened with a pack scene shows exactly the cards and rarities drawn by the portal in
  100% of openings.
- **SC-009**: A new widget receives only the data contracts it declared, for the member viewing it, in 100% of
  displays.
- **SC-010**: Switching a pack off takes effect for members within 1 minute; rolling back restores the
  previous version's looks and economy.

## Assumptions

- The proof of concept of issue #1 (branch `poc/visual-packs`) is the starting point: its format, analysis,
  sandbox, CSS guard, navigations and intrusion guard are kept and completed; its shortcuts (a registry in a
  file, built-in looks in the code, blocks kept in memory) are replaced.
- Pack sources are chosen by administrators; the portal still assumes any pack may be hostile (defence in
  depth), never trusting its content.
- The economy (prices, rarities, levels, the spread of levels over the curve) keeps the portal's own rules;
  the analysis reports deviations as warnings, the administrator decides.
- Built-in packs are maintained with the portal: shipped with each release and updated with it (FR-008a),
  unlike imported packs, which change only through the import workflow.
- Self-registration stays as configured today: when closed, its route answers nothing; when open, it is one
  of the single-purpose routes of FR-036.
- Fingerprints identify versions; signing packs is out of scope, as are a public pack marketplace and
  multi-factor authentication (separate issue).
- Data contracts for widgets start with a small set (the member's progression, what they are watching or
  reading, what was recently added, their statistics), each reusing data the dashboard already shows; more
  may be added by later specs.
