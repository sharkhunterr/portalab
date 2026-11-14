# Feature Specification: Household Profiles (Several People Behind One Account)

**Feature Branch**: `032-household-profiles`
**Created**: 2026-11-14
**Status**: Draft
**Issue**: #418
**Input**: User description: "A profile system built into Portalab: one account can create as many profiles as
it wants (always at least the master profile) — simple, child or other restricted profiles. The master profile
sees what its profiles did and can allow access to some content (a child profile asks for a film its
restrictions do not allow). Profiles may have PIN codes. Each profile has its dashboard, its
recommendations… like a new user, but tied to the master account." Refined the same day: "Profile management
and restriction in Portalab only — never in Plex or Jellyfin. My users have a Plex account (their e-mail) in
my Plex Home, and at home several people use that same account. The goal is to offer that account, in
Portalab, profiles that are purely theirs. XP and Coins are pooled on the master account: every XP, Coin,
Contribution… a profile earns also goes to the master account, whatever the profile; each profile keeps its own
XP/Coins/Contribution (the same amount simply also goes to the master). Every profile can see the household's
money (each profile's) and XP/Contribution. The master decides whether its profiles appear in the community."

## Role of This Document

This spec adds **households** to Identity (`002`): a member account (the **master**) holds **profiles** for the
people sharing it. It works with Roles & Permissions (`003`), the Dashboard (`009`), Notifications (`010`),
Community (`012`), Economy & Progression (`013`), Marketplace (`015`), Privacy (`021`) and Media (`024`). It
changes nothing in any connected service: Plex, Jellyfin, Tautulli and the request services are never told
about profiles.

### Principles (normative)

- **A profile is a member of its own**: its dashboard, recommendations, quests, achievements, streaks,
  notifications, preferences and appearance are its own, exactly as for any member.
- **The master stays the account**: one sign-in (password, MFA, single sign-on) opens the household; account
  security, deletion and export belong to the master only; the media services' accounts stay linked to the
  master, so plays read from them go to the master.
- **The household shares one wallet**: whatever a profile earns or spends is mirrored on the master account,
  so the master's balances are the household's; each profile keeps its own figures.
- **Restrictions are enforced by Portalab**: a restricted profile cannot reach, through Portalab, what its
  restrictions forbid — never a client-side hiding only.
- **Nothing changes for an account without profiles.**

## Clarifications

### Session 2026-11-14

- Q: Where are restrictions applied? → A (owner): in Portalab only, never in Plex or Jellyfin.
- Q: To whom go the plays of a shared media account? → A (owner): to the master account (the account linked to
  the service), as today.
- Q: How do XP, Coins and Contribution work? → A (owner): each profile has its own; every amount a profile
  earns is also credited to the master. Decided by default: what a profile *spends* is debited from both (the
  master's balance is the household wallet, so a profile cannot spend what the household no longer has);
  corrections and refunds follow the same mirror.
- Q: Who sees the household's figures? → A (owner): every profile sees the household — the master's totals and
  each profile's XP, Coins and Contribution.
- Q: Do profiles appear in the community? → A (owner): the master chooses, profile by profile. Decided by
  default: a child profile starts hidden, a standard profile starts shown.
- Q: How are PINs used? → A (owner, revised the same day): a 4–6 digit PIN per profile (optional); entering a
  protected profile always asks its PIN, from the master too. Coming back to the master from a profile asks
  the master's PIN when it has one; right after signing in, the master is free (the password was just given).
  Wrong PINs slow down progressively, like sign-in attempts. Switching is « Switch profile » beside the name (the
  picker opens); « My household » is a section of the main navigation; a profile's first welcome leaves out the media accounts and the community presence.
- Q: Which restrictions exist? → Decided by default: a maximum age rating (all, 6+, 10+, 12+, 14+, 16+, 18+),
  whether unrated titles are allowed, and features kept out (shop, requests, AI assistant, community
  participation, games, support). Kinds are presets: *standard* (no restriction), *child* (12+, unrated
  hidden, shop/requests/AI/community kept out, hidden from the community), *custom* (the master's choice).
- Q: Session 2 (owner feedback) — a profile must play with its master's linked account; its plays through the
  portal count for it while the master's figures stay the household's cumul (every member sees them); a
  child's age comes from its birth date (updated at each birthday); the master chooses hidden or locked
  titles and whether access requests are allowed; a profile's settings drop what is its master's. → Built.
- Q: Where is « My household »? → A (owner): a section of its own in the main navigation, like Games or
  Statistics — amending 027 FR-008 (at most nine top-level sections) to ten.
- Q: Session 3 (owner feedback): a child profile could start horror films — France rates many of them 12. →
  A title's age is now the strictest of TMDB's FR/US/GB/DE ratings and the media server's (Plex, Jellyfin),
  shown on its page; genres (horror, thriller, crime, war) may be kept out whatever their rating; the child
  preset keeps horror out.
- Q: How does a child get a title above its rating? → A: the locked title offers « Ask for access »; the master
  is notified, approves (for good or for a number of days) or refuses; the profile is told.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The family shares one account, each with a profile of their own (Priority: P1)

A member signs in on the family TV or laptop. Portalab asks « Who's there? » and shows the master and every
profile as large tiles; the child picks theirs (entering their PIN when it has one) and lands on their own
dashboard, with their own recommendations and quests. Later the parent opens the header menu, « Switch
profile », and comes back to theirs with their PIN.

**Independent Test**: create two profiles, switch between them, check that `/me`, the dashboard and the
notifications follow the active profile and that the master's PIN is required to come back.

**Acceptance Scenarios**:

1. **Given** an account with profiles, **When** it signs in, **Then** the profile picker is shown before the
   portal, listing the master first, then its profiles in order.
2. **Given** a profile with a PIN, **When** anyone (the master included) picks it with a wrong PIN, **Then** it stays closed, and
   repeated failures are slowed down.
3. **Given** a child profile is active, **When** it switches to the master, **Then** the master's PIN is asked
   when the master has one.
4. **Given** a profile is active, **When** it opens account security, deletion or export, **Then** Portalab
   refuses (those belong to the master).
5. **Given** an account without profiles, **When** it signs in, **Then** nothing changes.

### User Story 2 - The household's economy is pooled (Priority: P1)

The child completes a daily quest worth 20 XP and 5 Coins: their profile shows +20 XP and +5 Coins, and the
master's balances also grow by 20 XP and 5 Coins. On « My household », every profile sees the household wallet
(the master's balances) and each member's level, XP, Coins and Contribution.

**Independent Test**: grant a profile XP and Coins, spend Coins from it, and check both ledgers and the
household page.

**Acceptance Scenarios**:

1. **Given** a profile earns an amount of a value, **When** it is recorded, **Then** the same amount is recorded
   on the master, once (replays never double it).
2. **Given** a profile spends Coins, **When** the purchase succeeds, **Then** both balances are debited; **When**
   the household wallet cannot cover it, **Then** the purchase is refused and nothing is recorded.
3. **Given** any household member, **When** they open « My household », **Then** they see the household totals
   and every member's figures.

### User Story 3 - A child profile is restricted and asks for access (Priority: P1)

The parent sets their child's profile to « 12+ », hides unrated titles and keeps the shop out. The child does not
see 16+ films in the library, the discovery pages, the recommendations or the search; opening one by its link
shows it locked with « Ask for access ». The parent is notified, approves for 2 days, and the child can open it.

**Independent Test**: set a maximum rating on a profile, list the catalog as that profile, ask and approve an
access request, list again.

**Acceptance Scenarios**:

1. **Given** a profile limited to 12+, **When** it browses or searches, **Then** titles rated above 12 are not
   listed, and opening one answers « restricted » with the possibility to ask.
2. **Given** a pending request, **When** the master approves it, **Then** the title becomes available to that
   profile (until the chosen end), and the profile is notified; **When** refused, the profile is notified too.
3. **Given** a feature kept out (e.g. the shop), **When** the profile tries it, **Then** Portalab refuses it and
   the feature's entries are not offered.

### User Story 4 - The master supervises and manages (Priority: P2)

On « My household » the master adds, renames, recolours and deletes profiles, sets their kind, restrictions,
PIN and community visibility, reads each profile's recent activity (what it earned and spent, its requests)
and handles access requests.

**Acceptance Scenarios**:

1. **Given** the master, **When** they create a profile, **Then** it appears in the picker and on the household
   page; a profile cannot manage the household.
2. **Given** a profile hidden from the community, **When** any member opens the members directory or the
   leaderboards, **Then** that profile is not listed.
3. **Given** the master deletes a profile, **Then** sessions using it are closed and its data follows the
   normal deletion of an account.

### Edge Cases

- The master account is suspended or deleted: its profiles can no longer be used; deleting the master deletes
  its profiles.
- A profile is deleted while it is active on a device: that device is signed out.
- A profile's display name may be the same as another member's (it is not unique across the portal).
- Profiles never sign in by themselves and are never made inactive for dormancy: they live by their master.
- A profile mirrored debit that the household wallet cannot cover: a spend or a reservation is refused; an
  administrator's correction is applied to the profile and mirrored up to what the master holds.
- The number of profiles per account is bounded (administrators choose; 8 by default).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: An active member account MUST be able to create profiles (up to the configured maximum), each
  a member of its own tied to that account; the account is the household's master.
- **FR-002**: Every request made while a profile is active MUST act as that profile; the session stays the
  master's (one sign-in, one sign-out).
- **FR-003**: Profiles MUST NOT manage account security, sessions, deletion, export or the household itself.
- **FR-004**: Profiles MAY have a 4–6 digit PIN, stored like a secret; wrong PINs MUST be throttled.
- **FR-005**: After sign-in, an account with profiles MUST be offered the profile picker before the portal.
- **FR-006**: Every XP, Coins and Contribution amount recorded for a profile MUST be recorded once more for its
  master, idempotently, in the same transaction; mirrored records MUST NOT trigger rewards again.
- **FR-007**: Every household member MUST be able to see the household totals and each member's figures.
- **FR-008**: The master MUST choose, per profile, whether it appears in the community (directory,
  leaderboards).
- **FR-009**: A profile MUST be restrictable by maximum age rating, unrated titles and kept-out features;
  restrictions MUST be enforced by the server.
- **FR-010**: A restricted profile MUST be able to ask for access to a locked title; the master MUST be
  notified and be able to approve (optionally for a number of days) or refuse; the profile MUST be notified.
- **FR-011**: The master MUST see each profile's recent activity (economy history, requests).
- **FR-012**: Administrators MUST be able to turn households off and set the maximum number of profiles.
- **FR-013**: Nothing MUST change in connected services, nor for accounts without profiles.

### Key Entities

- **Household member**: a user that belongs to a household — the master (owner) or a profile — with its kind,
  colour, order, optional PIN, community visibility and restrictions.
- **Profile session state**: which household member a signed-in session currently acts as, and whether the
  choice was made.
- **Access request**: a profile's request for one title, its decision and its optional end.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Switching profile takes two taps (or two taps and a PIN) and reloads the portal as that profile.
- **SC-002**: 100% of the amounts recorded for a profile appear once on its master (replay-tested).
- **SC-003**: A profile limited to an age never receives a title rated above it from any listing, search or
  detail route covered by the test suite.
- **SC-004**: An access request reaches the master's notifications within the delivery delay of any
  notification.
- **SC-005**: The existing test suites pass unchanged for accounts without profiles.

## Assumptions

- Age ratings come from the media metadata already stored (`certification`); ratings of the main systems
  (US, FR, DE, UK, the bare ages) are mapped to an age; an unmapped rating counts as unrated.
- The plays of a shared media-service account go to the master; a profile with its own media-service
  account may link it as any member does.
- The master's leaderboard figures include its profiles' (the household's), as asked.
