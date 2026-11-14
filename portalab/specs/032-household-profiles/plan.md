# Implementation Plan: Household Profiles

**Branch**: `032-household-profiles` | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md) | **Issue**: #418
**Input**: Feature specification from `/specs/032-household-profiles/spec.md`

## Summary

A household is owned by Identity (`002`): a profile is an `identity.users` row **without a login**, tied to its
master by `identity.household_members` (kind, colour, order, Argon2 PIN, community visibility, restrictions).
The master's session remembers which member it acts as (`sessions.acting_user_id`, `profile_chosen`); the
session resolver then returns `Principal(user_id=<profile>, profile_of=<master>)`, so every module keyed by
`user_id` (dashboard, recommendations, quests, notifications, preferences…) serves the profile unchanged.
Other modules learn about households through one capability, `identity.household` (`owner_of`,
`restrictions_of`, `grants`, `granted`, `hidden`):

- **Economy** — `LedgerWriter.record`, the single write path, records the same XP/Contribution/Coins amount
  once more for a profile's master in the same transaction (`transactions.profile_id`, key derived from the
  profile row's); a debit the household cannot cover refuses a spend or a reservation; the copy publishes
  no reward event.
- **Authorization** — the engine withholds the permissions of a profile's kept-out features after the grant
  decision (`_evaluate`, `visible`, `effective_permissions`).
- **Media** — `TitleGate` computes, per restricted profile (cached 30 s), the films and series rated above its
  age (TMDB `certification` → age) minus its approved requests, plus their seasons and episodes; the catalog
  query excludes them in SQL, the title page and the player answer `household.restricted`, shelves, taste
  cards, « My feed », collections and person pages drop them, media widgets and the media search provider
  are wrapped (`GatedWidget`, `GatedSearch`).
- **Community** — `identity.members` leaves out hidden profiles (members directory and leaderboards).
- **App** — `enforce_terms` refuses the account's own routes to profiles (`household.owner_only`) and checks
  the master's terms acceptance.

## Technical Context

**Language/Version**: Python 3.12 · TypeScript 5.9 (Node 22)
**Primary Dependencies**: existing only (FastAPI, Pydantic 2, SQLAlchemy 2 async, argon2-cffi, React 19,
TanStack Query, Radix). **No new dependency.**
**Storage**: PostgreSQL — migrations `identity_0006` (households, access requests, session columns) and
`gamification_0013` (`transactions.profile_id`).
**Testing**: pytest (integration on PostgreSQL), Vitest + axe.
**Constraints**: nothing changes for accounts without profiles; nothing is sent to connected services.

## Constitution Check

- Module boundaries: households in Identity; other modules use the `identity.household` capability only
  (import-linter contracts kept).
- Deny by default: restrictions withdraw permissions server-side; the client only reflects them.
- Privacy: profile tables classified (`pii`/`not_personal`), tombstoned with their user; a profile's data
  follows the account deletion saga.
- Security: PIN hashed with the portal's Argon2 parameters, wrong PINs throttled in their own transaction;
  IDOR checks on every household route; the account's security routes closed to profiles.
- i18n: namespace `household` (en, fr); accessibility: axe-tested picker, PIN pad, page and editor.

## Project Structure

```text
backend/src/portalab/capabilities/household.py            # contract, Restrictions, age_of
backend/src/portalab/modules/identity/household/          # rules.py, service.py
backend/src/portalab/modules/identity/api/household.py    # /api/v1/household/*
backend/src/portalab/modules/media/restrictions.py        # TitleGate, GatedWidget, GatedSearch
backend/migrations/identity/versions/20261114_1200_identity_0006_households.py
backend/migrations/gamification/versions/20261114_1200_gamification_0013_household_mirror.py
backend/locales/{en,fr}/household.json
frontend/src/features/household/                          # api, ProfilePicker (gate, PIN pad), HouseholdPage,
                                                          # ProfileEditor, LockedTitle, household.css
```

## Known limits

Titles are rated only when TMDB enriched them (films and series); seasons and episodes inherit their series'.
Surfaces not filtered by age yet: statistics pages (server-wide tops), upcoming releases and the calendar,
« since your last visit », the AI assistant's recommendations tool, Mediacards and games sources,
newsletters, request discovery (TMDB titles outside the library — the child preset keeps requests out).
