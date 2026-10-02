# Contracts — Design System & UI preferences

## Frontend contracts
- `ThemeProvider` applies `ThemeDefinition` tokens then user a11y overrides; exposes `useTheme()`, `usePreferences()`.
- `FunctionalState` component (from 001) now reads `state_map`; props: `state`, `asOf?`, `onRetry?`; always renders icon + text + color.
- `Announce` live-region utility (polite/assertive) used by notifications and async results.
- `KeyboardShortcuts` registry (consumed by Command Palette in 004/008).
- Component catalog (Card, Panel, Button, Badge, Status, Progress, Table, List, Timeline, Calendar, Chart, Form, Modal, Drawer, Tabs, Avatar, Media/Service/User/Achievement/Project Card, Notification) each documented with states, a11y notes and RTL behaviour.

## Backend HTTP (`/api/v1`)
| Path | Permission |
|---|---|
| GET `/ui/themes` | authenticated (enabled & allowed themes only) |
| POST `/admin/ui/themes` (register admin theme), PATCH enable/disable | `appearance.manage` (sensitive for enabling external themes; floor check mandatory) |
| GET `/admin/ui/themes/{id}/floor-report` | `appearance.manage` |
| GET/PUT `/me/preferences` (ui.* keys) | `users.self.manage` (via 020) |
Problem codes: `theme.invalid_definition`, `theme.floor_violation`.

## Extension point (023)
Plugins contribute UI only through design-system components and token roles; Marketplace themes register through `POST /admin/ui/themes`-equivalent service call (same validation).

## Implementation notes (2026-10-03)
- `GET /ui/themes` requires `users.self.manage` (every signed-in user) and returns `{themes, policy}`; the
  `high-contrast` theme is always offered (accessibility). Extra routes: `GET /admin/ui/themes`,
  `POST /admin/ui/themes/check` (dry run with floor report).
- Notification appearance primitives (`NotificationArea`, `useNotify`), `AnnounceProvider`, `ShortcutRegistry`,
  `DirectionProvider`, `SoundService` and the dev gallery (`/dev/gallery`, development builds only) are exported
  from `design-system/index.ts`.
