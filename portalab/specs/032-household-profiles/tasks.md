# Tasks: Household Profiles

**Input**: spec.md, plan.md, data-model.md, contracts/household-api.md · **Tests**: requested (quickstart.md)

## Phase 1: Foundation

- [X] T001 Contract `backend/src/portalab/capabilities/household.py` (Household, Restrictions, FEATURE_PERMISSIONS, age_of) registered in `capabilities/catalog.py`
- [X] T002 Migrations `identity_0006` and `gamification_0013`; models in `modules/identity/models` and `modules/gamification/models`
- [X] T003 `Principal.profile_of` in `core/authz_port.py`; `create_user(login=None, unique_name=False)`

## Phase 2: US1 — profiles, picker, PIN (P1)

- [X] T004 [US1] Tests `tests/integration/identity/test_household.py` (switch, PINs, throttle, account routes, limit)
- [X] T005 [US1] `modules/identity/household/{rules,service}.py`, router `api/household.py`, session resolver, `/me` fields
- [X] T006 [US1] Account routes closed to profiles and master's terms in `app/security.py`; dormancy skips profiles
- [X] T007 [US1] Frontend `features/household/ProfilePicker.tsx` (gate, picker, PIN pad), header « Switch profile »

## Phase 3: US2 — pooled economy (P1)

- [X] T008 [US2] Tests `tests/integration/gamification/test_household_economy.py`
- [X] T009 [US2] Mirror in `modules/gamification/ledger/writer.py`; household overview with every member's figures

## Phase 4: US3 — restrictions and access requests (P1)

- [X] T010 [US3] Tests `tests/integration/media/test_household_titles.py`, `tests/unit/identity/test_household_rules.py`
- [X] T011 [US3] Feature withholding in `modules/authz/engine/engine.py`
- [X] T012 [US3] `modules/media/restrictions.py` and its use in catalog, title page, player, shelves, taste, feed, collections, people, widgets, search
- [X] T013 [US3] Access requests (ask, decide, notify) and `features/household/LockedTitle.tsx` on the title page

## Phase 5: US4 — supervision and management (P2)

- [X] T014 [US4] « My household » page, editor, activity, requests; hidden profiles out of `identity.members`; deletion cascade
- [X] T015 [US4] Admin settings `identity.household.enabled|maxProfiles` with labels and meta

## Phase 6: Polish

- [X] T016 Locales `household` (en, fr), docs (`docs/members/households.md`, admin section, member guide `guide-foyer`)
- [X] T017 Vitest + axe tests; Bandit, Semgrep; full backend and frontend suites
