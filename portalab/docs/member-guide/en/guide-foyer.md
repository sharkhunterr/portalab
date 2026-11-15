---
slug: guide-foyer
title: My household and its profiles
position: 17
help_keys: [household.page, household.picker]
tags: [guide, account, household, profiles, screen time]
---
Do you share your account with your family? Give everyone **a profile of their own**: their own home, recommendations, quests and progress, without mixing up everybody's tastes. Your account stays the **master account**: you make the household, manage the profiles, set their rules and decide how they earn.

## Making a household

You make a household whenever you want:

- **In the new members' welcome**: after your profile and your media accounts, the **« A household? »** screen asks whether other people share your account. **« Make my household »** takes you through three screens: **« How your household earns »**, **« Your family »** (one first name per person, each one becomes a profile) and **« Each profile's rules »**. **« No profiles »** skips this part.
- **From your account page**: the **« Make a household »** card replays just that part of the welcome, at any time.

Until you have a household, nothing about it shows: no « Who's there? », no **« My household »**. Changed your mind before adding anyone? **« I don't want a household »** removes it.

Then, in **« My household »**, **« Add a profile »**:

- **Name** and **colour**: this is what shows on the « Who's there? » screen.
- **Kind**: **Standard** (no restrictions), **Child** (up to age 12, unrated titles hidden, horror kept out, no shop, no requests, no assistant, no community participation) or **Custom** (you choose everything). The kind only sets the starting settings: you can adjust them afterwards.
- **PIN (optional)**: 4 to 6 digits, asked when someone enters this profile.

A profile has no username and no password: it is used from your account. The first time it is opened, it gets **its own welcome**: its language, its text size, its look, and **its own PIN** if it wants one. A profile never has to set up e-mails: your account receives them. Its settings only show what concerns it: the password, two-factor authentication, linked media accounts, privacy and data stay yours.

## « Who's there? »

![The « Who's there? » screen: the account master and the household's profiles, a padlock on the protected profile](shot:foyer-qui)

After you sign in, if your account has profiles, Portalab asks **« Who's there? »**: tap your tile or a profile's. To switch later, tap **« Switch profile »**: to the right of your name in the drawer on a phone, at the top of the avatar menu on a computer. The whole portal reloads for the chosen profile.

- Entering a protected profile always asks for its PIN, even from the master account.
- **Coming back to your account** from a profile asks for **your** PIN if you have one. « My household » reminds you as long as you don't: without it, any profile can come back to yours, and to its tools.
- Too many wrong PINs in a row: you have to wait a little before trying again.

> [!NOTE]
> Account security (password, two-factor authentication, sessions, deletion, export) can only be reached from the master account.

## The « My household » page

It has four tabs: **« Overview »**, **« Profiles »**, **« Schedule »** and **« Requests »**. A profile sees **« My schedule »** instead.

![The family dashboard: each member's time, sittings, finished titles and streak](shot:foyer-famille)

The **family dashboard** shows the household's kitty (with a common pot) and, over 7 or 30 days, for each member: their time, their sittings, their finished titles, the kinds of media, their last title and their play streak. **« The household's detailed statistics »** opens **Statistics › My household**.

## The household's economy

In the **« Profiles »** tab, you choose how your profiles' XP, Coins, Contribution and rewards count:

![The household's economy (common pot or separate profiles), then each profile's card: its figures, its age, its PIN and the screen time buttons](shot:foyer-economie)

- **Common pot** (the default): each profile keeps its own figures, **privately**. Everything it earns (XP, Coins, Contribution, **boosters and rewards**) is also added to your account, which **stands for the household in the community**. When a profile spends Coins, they leave its balance **and** the pot: a profile cannot spend what the household no longer has.
- **Separate profiles**: each profile has **its own wallet** and appears in the community, **publicly** (with its name) or **anonymously** (no name and no avatar in the leaderboards), as you set in its **« Edit »** form. Nothing is added to your account.

**Switching moves what they already earned**: switching to the common pot rebuilds it from the profiles' balances; switching to separate profiles gives each one its share back.

Each profile has **its own play streak**; with a common pot, what a profile plays also keeps the pot's streak going. Whatever the economy, **profiles never take part in community projects**: proposing, voting and funding are kept for the account master.

## Restricting a profile

You, the account master, set each profile's policy: **« My household » → « Edit »**. A profile cannot change any of it. Everything is set with switches.

- **Age**: a **birth date** (the age follows the profile, one year more at each birthday, no limit from 18) or a fixed **maximum age**. Titles above it are **hidden**, **shown locked** (blurred, with a padlock) or **shown** (their page opens, but they don't start). Two switches: **unrated titles** allowed or not, and **access requests** possible or not.
- **Allowed content**: Films, Series, Books, Audiobooks, Music, Video games. Turn a kind off and it disappears for this profile.
- **Genres kept out**: Horror, Thriller, Crime, War, or **any genre of the catalog** (« Animation », « Science Fiction »…), whatever their age rating.
- **Titles kept out**: on a title's page, **« Household restrictions »** lets you keep it out profile by profile. The list is in the profile's form, with **« Allow again »**.
- **Allowed features**: shop, requests, AI assistant, community participation, portal mini-games, support. And **« Open titles in their services »**: when it is off, the « Watch on Plex », « Read on Grimmory », « Play on RomM »… buttons disappear; the profile only uses the portal's player and reader, where its screen time and every rule apply (off by default for a child profile).
- **Shown in the community** (separate profiles only): publicly or anonymously.

### Age ratings

Every title shows its **age rating** (films, series, books, games), and the library filters by « What I may watch ». A title's age is **its rating in the portal's country**, which the administrator sets with the system language: in France, a film rated « Tous publics » (all audiences) is open to everyone. **Without a rating for that country, the strictest of the others counts**: those of the United States, the United Kingdom, Germany (from TMDB) and the one from your Plex or Jellyfin server. Each title's page shows that age and its sources.

A game follows its age rating (PEGI, ESRB… from IGDB, through RomM) when it has one; an unrated game stays open, since most retro games are older than the rating boards. Books and music carry no rating.

## Screen time

The **« Schedule »** tab sets, for each profile, **when** it may watch and **for how long**, like a calendar:

![A profile's schedule: what counts, the week in spans, the time left right now](shot:foyer-horaires)

- **What counts**: **« Media only »** (what it watches, reads, listens to and plays, in the portal or in its services) or **« All of Portalab »** (every minute on the portal, media included; once the time is up, the portal locks behind a screen that says when it opens again).
- **Spans**: tap or drag on a day to add a span; drag it to move it, drag its bottom edge to make it longer; tap it to give it **its own time** or leave it **open from start to end**. Outside the spans, the screen is closed. **A day without spans is open all day.** **« Copy Monday »** copies Monday **to Tuesday through Friday** or **to the whole week**.
- **A maximum per day**, above each day's column.
- **Right now**: the profile's time left, the current span or the next one.
- **In two taps**, on the profile's card or in the schedule: **« More time today »** (+15, +30, +60 or +120 min), **« No limits for… »** 1 hour, 2 hours or the rest of the day, and **« Limits back »**.

Plays on a TV through the Plex or Jellyfin app are not counted. Once the time is up, a film, a book or a [game played in the portal](portalab://wiki/guide-retro) in progress stops.

## Access requests

A profile that opens a title above its age sees **« Locked for your profile »**, with **« Ask for access »** (and a note for you, if it wants). You are notified, in the portal and by e-mail; in **« My household » → « Requests »**, choose **« Allow »**, **« Allow for 1 day »** or **« Decline »**. The profile is told your answer, and the title opens for that profile alone.

## What a profile watches

Plays from your shared Plex or Jellyfin account (the living-room TV, for example) go to the master account. A profile watches in Portalab with that same account, with nothing to link: **whatever a profile watches, reads, listens to or plays in the portal is its own**: its XP, its streak, its statistics and its **« Continue »** row, never the account master's.

In **Statistics**, the **« My household »** tab shows the household's figures, each profile's included. **« Me »** shows what the profile itself did in the portal.

## Following and deleting a profile

**« …'s activity »** on a profile's card shows what it earned and spent lately, and its access requests.

**« Edit »** → **« Delete this profile »**: its progress, preferences and history are erased, the devices that used it are signed out, and it **leaves no trace**: it disappears from leaderboards, charts and requests, the administration's included. Deleting the master account deletes its profiles too.
