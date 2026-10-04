# UI Contracts: Visual Experience (027)

Contracts between the shell, the design system, feature modules and plugins (frontend). Plugins see them
through the design-system `index.ts` export surface only.

## Shell frame (`frontend/src/shell/`)

| Element | Contract |
|---------|----------|
| `AppHeader` | Always renders: menu control, brand, search (bar ≥ tablet, button on phone), assistant, notifications (unread count), `ProgressChip` (level + XP bar, hidden when gamification is off), `CoinBadge`, avatar → `PersonalMenu`. Each data element is wrapped in its own `RegionBoundary` + query; failure ⇒ neutral chip, never hides search/menu/notifications/sign-out. Arrangement from `layout.header` (`full`, `compact`, `centered`). |
| `PersonalMenu` | Radix dropdown: profile, progression, the `personal` navigation entries (account, appearance, language, notification preferences, privacy, linked accounts), sign out. |
| `NavFrame` | Chooses `Sidebar` / `TopBar` / `Rail` / `Drawer` / `BottomBar` from `layout.nav[deviceClass]`; all variants consume the same `sections` view. The outlet is a sibling and is never remounted when the variant changes. |
| `SectionNav` | Collapsible sections (`aria-expanded`), section icon + label, `direct` sections as plain links, admin topics as sub-headings; current entry `aria-current="page"`; expanded state persisted (`shell.navigation.expanded`). |
| `BottomBar` (phone) | Home, Search, Notifications (badge), Menu (opens `Drawer` with `SectionNav`). Safe-area aware. |
| `PageFrame` | `Breadcrumbs (section → page)`, outlet, related links; content width from `layout.content`. |

## Design-system kit (`frontend/src/design-system/components/`)

| Component | Props (essential) | Notes |
|-----------|-------------------|-------|
| `PageHeader` | `title`, `context?`, `primary?: Action`, `secondary?: Action[]`, `artwork?` | Required on every routed page (lint `check-page-header`). |
| `Card` | `title?`, `actions?`, `variant?` (defaults to theme `layout.cards`) | Glass variant degrades to solid (R9). |
| `Tile` / `TileGrid` | `image?`, `title`, `subtitle?`, `badges?`, `href|onSelect` | Artwork-forward; image fallback = gradient + icon; responsive columns. |
| `ListItem` | `leading: Avatar|Icon`, `title`, `meta?`, `trailing?` | |
| `Avatar` | `userId`, `name`, `src?`, `size` | Initials fallback with hue derived from `userId`. |
| `LevelBadge` / `ProgressChip` / `ProgressBar` | `level`, `value`, `floor`, `next` | XP bar animation respects reduced motion. |
| `CoinBadge` | `amount` | Compact notation ≥ 10 000 with exact value in accessible name/tooltip. |
| `StatFigure` | `label`, `value`, `trend?` | |
| `Skeleton` | `shape: text|card|tile|list|figure`, `count?` | `aria-busy` on the region, no announcements spam. |
| `EmptyState` | `icon|illustration`, `title`, `message`, `action` (**required**) | Enforces "no dead end". |
| `Icon` | `name`, `label?` | lucide mapping by stable name; unknown ⇒ dot. |
| `Celebration` | via `useCelebrate()` → `celebrate({kind: "reward"|"level", value})` | Queue of 1, coalescing; `motion.celebration`; reduced motion ⇒ static toast; plays `reward`/`levelUp` sound through `SoundService`. |
| `AuthLayout` | `title`, `children` | Sign-in, registration, recovery, first run. |
| `WelcomeCard` | `onDismiss` | Dashboard first visit. |

## Dashboard editor (`frontend/src/features/dashboard/`)

| Unit | Contract |
|------|----------|
| `grid/engine.ts` | Pure functions: `place(items, moved, to)`, `resize(items, id, w, h, limits)`, `compact(items)`, `firstFree(items, w, h)`, `derive(items, columns)`, `readingOrder(items)`. Deterministic; same algorithm as `modules/dashboard/arrangement.py` (shared fixtures in `tests/fixtures/dashboard-arrangements.json`). |
| `grid/DashboardGrid.tsx` | CSS grid with explicit `grid-column/grid-row` from `x,y,w,h` on desktop; derived columns on tablet/phone; DOM order = reading order. |
| `edit/EditSession` | `enter() / move / resize / add / hide / remove / save() / cancel()`; snapshot + optimistic local state; one `PUT /dashboard/arrangement` on save. |
| `edit/DragLayer` | Pointer-events drag & resize with ghost placeholder, snapping, edge auto-scroll; desktop width only. |
| `edit/KeyboardArrange` | Enter selects, arrows move, Shift+arrows resize, Escape cancels; each step announced. |
| `edit/WidgetGallery` | Catalog with preview, description, size options; disabled entries show the policy reason. |

## Theme application (`frontend/src/design-system/themes/`)

`applyTheme(definition, prefs)` sets on `<html>`: CSS variables (colors, radii, motion durations, fonts) and
attributes `data-nav-desktop|tablet|phone`, `data-header`, `data-cards`, `data-content`, `data-corners`,
`data-widget-frame`, `data-motion`, `data-celebration`, `data-color-scheme`. Accessibility overrides are
applied last (`data-reduced-motion`, `data-contrast`, text scale) and always win.
