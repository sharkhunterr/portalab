# Data Model: Visual Experience (027)

027 adds **no new business data**. It extends four existing structures (navigation contributions, theme
documents, dashboard instances, user-tier settings) and one live-event topic. Ownership stays with the
modules that already own them.

## 1. NavigationSection (new, `capabilities.navigation`, in-memory registry)

| Field | Type | Rules |
|-------|------|-------|
| `key` | str | `^[a-z][a-z0-9_-]{0,47}$`; unique; built-ins: `home, media, content, services, support, community, marketplace, admin, me, more` |
| `owner` | str | `module:<id>` or `plugin:<key>`; plugin sections must be namespaced `plugin-<key>` |
| `label_key` | str | i18n key (026), e.g. `nav.section.support` |
| `icon` | str | design-system icon name (R15) |
| `order_hint` | int | 0–10 000; admin `group_order` wins |
| `audience` | `everyone` \| `administration` \| `personal` | `administration` sections render in the Administration area; `personal` (`me`) renders in the avatar menu only |
| `topics` | list[{key, label_key, order_hint}] | optional sub-groups (used by `admin`: `access, services, content, economy, system, extensions`) |
| `default_for` | list[str] | owners whose contributions fall back to this section when they declare none/unknown |

Validation: closed schema (extra = forbid); duplicate key ⇒ first wins + rejection diagnostic (same as 004
contributions); withdrawal of an owner removes its sections (023 sweep).

## 2. NavigationContribution (extended, schema_version stays 1)

| Field | Change |
|-------|--------|
| `group` | meaning clarified: **section key**; unknown ⇒ owner default section ⇒ `more` (never dropped, diagnostic `navigation.section_unknown`) |
| `topic` | **new**, optional str; must be one of the section's topics, else ignored with diagnostic |

## 3. Navigation view (response of `GET /me/navigation`, extended)

```
{ version, degraded,
  sections: [ { key, label_key, icon, audience, direct: bool,
                topics: [ { key, label_key, entries: [Entry] } ],   # only when the section has topics
                entries: [Entry] } ],                               # entries without topic
  personal: [Entry],                                                # section `me` (avatar menu)
  commands, related, ...                                            # unchanged
  groups: [...] }                                                   # deprecated alias (one release)
```

Rules: a section with zero permitted entries is omitted; `direct = true` when exactly one permitted entry
and no topics; ordering = admin layout (`group_order`, `order`, `pinned`, `groups_of`) > user order >
`order_hint` (unchanged 004 R5).

## 4. User-tier settings (Administration, declared by `shell`)

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `shell.navigation.expanded` | list[str] (section keys) | `[]` (current section auto-expanded) | FR-015 |
| `shell.welcome.dismissedAt` | datetime \| null | null | FR-029 |
| `ui.colorMode` (declared by `ui`) | `dark` \| `light` \| `system` | `dark` | R8, clarification Q3 |

Global setting changes: `ui.defaultTheme` default becomes `portalab-dark` (data migration keeps an
explicitly configured value).

## 5. ThemeDefinition v2 (extended, `modules/ui` + `frontend/src/design-system/themes/schema.ts`)

New/changed blocks (all optional; v1 documents are upgraded on read with the defaults in brackets):

| Block | Fields |
|-------|--------|
| `schemaVersion` | `2` |
| `family` | str `^[a-z][a-z0-9-]{1,47}$` [none] |
| `layout.nav` | `desktop: sidebar\|topbar\|rail\|orbit` [sidebar], `tablet: rail\|topbar\|drawer\|orbit` [rail], `phone: bottom-bar\|drawer\|orbit` [bottom-bar] |
| `layout.header` | `full\|compact\|centered` [full] |
| `layout.headerPosition` | `top\|bottom` [top] — `bottom` turns the header into a footer bar (all header elements kept) |
| `layout.cards` | `elevated\|flat\|outlined\|glass` [elevated] |
| `layout.content` | `narrow\|wide\|full` [wide] |
| `layout.corners` | `square\|soft\|round` [soft] |
| `layout.widgetFrame` | `card\|plain\|glass` [card] |
| `motion.profile` | `none\|subtle\|lively\|playful` [subtle] (existing `fastMs/normalMs` kept) |
| `motion.celebration` | `none\|sparkle\|confetti\|glow` [sparkle] |
| `sounds` | keys `notification, alert, success, reward, levelUp, ui` (bundled `asset:` only) |
| `colors` | + optional `accentAlt` (gamification accent), `rarity` {common, rare, epic, legendary} (badge colors; floor-checked against `surfaceRaised`) |

Invariants: no field can hide a critical element (header search/notifications/menu/identity/sign-out are
always rendered by every layout variant); the floor report checks glass surfaces with their solid fallback
(`surfaceRaised`), and every theme × device class.

Built-in documents: `portalab-dark` (default, family `portalab`), `portalab-light` (family `portalab`),
`light`, `dark`, `high-contrast` (upgraded to v2).

## 6. Dashboard WidgetInstance (extended, `dashboard.widget_instances`)

| Column | Change |
|--------|--------|
| `x` | **new** int, 0–11, NOT NULL after back-fill |
| `y` | **new** int, ≥ 0, NOT NULL after back-fill |
| `w`, `h` | unchanged (1–12), bounded by the widget's `SizeLimits` |
| `position` | kept; **derived** reading order = rank by `(y, x, id)`; recomputed on every arrangement write |

Constraints: `CHECK (x >= 0 AND x + w <= 12 AND y >= 0)`; no overlap among `active` instances of a user
(validated by the service, not a DB constraint); hidden instances keep their last `x,y,w,h`.
Index: `(user_id, y, x)` replaces `(user_id, position)` usage for reads.

**DashboardArrangement** (value object, API): `{ layout_version, items: [{id | widget_key, x, y, w, h}] }`;
derived views (tablet 6 columns, phone 1–2 columns) are computed, never stored (FR-045).

Migration `dashboard_0002` (R14): add nullable `x,y` → back-fill per user by flowing `position` order into
12 columns with the engine algorithm → set NOT NULL + check. Starter layout items accept optional `x,y`.

## 7. Live event `progression.changed` (new topic, published by `gamification`)

| Field | Type |
|-------|------|
| audience | the user whose XP/Coins changed (`audience_user_id`) |
| `xp`, `level`, `level_floor`, `next_level_at`, `coins`, `reserved_coins` | ints (post-transaction values) |
| `delta_xp`, `delta_coins` | ints |
| `level_up` | bool |

Published inside the ledger transaction (outbox); no other user's data; consumers dedup by stream `seq`.

## State transitions

- **Dashboard edit session (client)**: `view → editing (snapshot) → saving → view`; `editing → view` on
  cancel restores the snapshot; `saving → editing` on 409 conflict (reload latest, re-apply not attempted —
  user informed).
- **Celebration queue (client)**: `idle → playing → idle`; events arriving while `playing` are coalesced
  into one pending (max 1); `reducedMotion` ⇒ celebrations replaced by a static toast.
