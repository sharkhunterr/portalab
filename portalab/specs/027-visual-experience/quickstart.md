# Quickstart: Visual Experience (027) — validation scenarios

Prerequisites: backend + worker running against a migrated database (`dashboard_0002`, `ui` theme v2
seed), frontend built or `npm run dev`; users `admin` (Admin) and `ursula` (User) with avatar, level 3,
120 Coins (seed via `uv run portalab admin bootstrap` + gamification manual credit in tests).

## Automated

```bash
cd backend && uv run pytest tests/integration/shell tests/integration/dashboard tests/integration/gamification/test_live_progression.py tests/integration/ui tests/migrations -n 6 --dist loadfile
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
cd frontend && npx playwright test tests/e2e/visual-experience tests/a11y
```

## Scenarios (map to spec)

1. **Header everywhere (US1, SC-001)** — at 390 × 844, 820 × 1180 and 1440 × 900: open `/`, `/media`,
   `/support/tickets`, `/admin`; header shows avatar, `Lv 3` + XP bar, `120` Coins, bell with count,
   search, menu. Stop gamification (`PATCH /admin/modules/gamification` disable) → level/Coins disappear,
   the rest stays.
2. **Live reward (US1 #3/#4, SC-010)** — credit 40 XP to `ursula` from an admin session; within a few
   seconds her header XP animates; a level-crossing credit shows one celebration; with reduced motion on:
   no animation, static toast; with sounds off: silent.
3. **Sections (US2, SC-002/003)** — as `admin`: ≤ 9 top-level sections, Administration grouped by topics;
   as `ursula`: no Administration, ≤ 8 sections; every route from the old flat navigation is reachable
   (Playwright iterates the 004 route table).
4. **Plugin section fallback (US2 #6)** — install/enable the `hello` example plugin with `group: "nope"`:
   its page appears under its default/`more` section; a diagnostic is listed in
   `/admin/shell/contribution-errors`.
5. **Phone layout (US3, SC-004)** — 320 px and 390 px: bottom bar (Home, Search, Notifications, Menu), no
   empty column, no horizontal scroll on every page of the route table.
6. **Rotation (US3 #4)** — type in a ticket form on a tablet portrait, rotate to landscape → text kept, same
   page, scroll kept.
7. **Page kit (US4, SC-007/008)** — `npm run lint` includes `check-page-header` (every routed page renders
   `PageHeader`); empty lists show `EmptyState` with an action; slow API (Playwright route delay) shows
   skeletons.
8. **Dashboard editing (US6, SC-011)** — desktop: Edit → drag "News" next to "Services", resize "Progress"
   to 6 × 2, add "Leaderboard" from the gallery, Save → reload → identical; repeat with keyboard only
   (Enter, arrows, Shift+arrows, Enter to save); Cancel restores; locked widget shows its reason.
9. **Derived views (FR-045/046)** — same account on phone: same reading order, single column; Edit offers
   add/hide/remove/reorder only.
10. **Migration (SC-012)** — `tests/migrations/test_dashboard_0002.py` upgrades a database seeded with
    ordered layouts and asserts identical widget sets, sizes and configs, no overlaps.
11. **Themes with layouts (US5, SC-006)** — switch `portalab-dark` → `portalab-light` → a test theme with
    `nav.desktop: topbar`, `cards: flat`, `motion.profile: playful`: arrangement changes < 1 s, no reload,
    open dialog and typed text kept; header elements all present; axe passes on each.
12. **Theme validation (US5 #4)** — `POST /admin/ui/themes/check` with `layout.nav.desktop: "floating"` →
    422 `theme.invalid` at `layout.nav.desktop`.
13. **Sign-in & welcome (US7)** — sign out → branded sign-in card on phone and desktop; new user first
    visit → WelcomeCard; dismiss → absent on another browser.

## Manual (hallway tests)

- SC-005: 10 participants, tasks "open a support ticket", "see the leaderboard", "check my Coins" — record
  time to first correct click (target ≤ 10 s for 9/10).
- SC-011: 10 participants move, resize and add a widget (target ≤ 30 s for 9/10).
