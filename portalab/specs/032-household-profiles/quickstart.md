# Quickstart: Household Profiles

1. Sign in, open « My household » (avatar menu), add « Léa » (Child, PIN 1234) and « Tom » (Standard).
2. Sign out and in: « Who's there? » lists you, Léa, Tom. Pick Léa (no PIN asked: you are the master).
3. As Léa: a 16+ film is absent from the library; its link shows « Locked for your profile » → « Ask for
   access ». The shop and the assistant are not offered.
4. « Switch profile » → you (your PIN if set): « My household » → Requests → « Allow for 1 day »; Léa can
   now open it.
5. Grant Léa XP (a quest): her card and the household wallet both grow by the same amount.
6. Suites: `tests/integration/identity/test_household.py`, `tests/integration/gamification/test_household_economy.py`,
   `tests/integration/media/test_household_titles.py`, `tests/unit/identity/test_household_rules.py`,
   `frontend/tests/unit/household/`, `frontend/tests/a11y/household.test.tsx`.
