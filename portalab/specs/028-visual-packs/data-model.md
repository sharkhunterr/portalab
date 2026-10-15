# Data Model: Visual Packs (028)

PostgreSQL, schema `visuals` (new module, migration `visuals_0001`), plus `identity.security_blocks`
(migration `identity_security_blocks`), new settings, and a data migration of `ui.themes` sources. UUIDv7
ids, `timestamptz` UTC. Pack files stay on disk (`DATA_DIR/visuals/store/<pack>/<sha256>/`), immutable.

## visuals.packs

| column | type | rules |
|---|---|---|
| `id` | `text` PK | `^[a-z][a-z0-9-]{1,40}$`; built-in ids (`portalab-*`) reserved to `builtin` packs |
| `builtin` | `bool` | true for packs synced from `/app/packs/builtin` (R5) |
| `socle` | `bool` | exactly one row true (`portalab-socle`); partial unique index |
| `source` | `jsonb` | `{kind: builtin\|inbox\|upload\|github, path?, url?}` |
| `state` | `text` | `enabled` \| `disabled` \| `archived` \| `removed`; socle ⇒ always `enabled` (check) |
| `current_version_id` | `uuid` NULL → `pack_versions.id` | the published version (NULL until one is) |
| `remote` | `jsonb` NULL | GitHub offer `{version, ref, release, checked_at}` |
| `names` | `jsonb` | `{fr, en}` from the current (or latest) manifest |
| `created_at`, `updated_at` | `timestamptz` | |

State transitions (FR-007, FR-012, FR-013a):

```text
(none) --import--> disabled (no current version)
disabled --publish version--> enabled
enabled --switch off--> disabled --switch on--> enabled
enabled|disabled --remove, owners > 0--> archived --enable--> enabled
enabled|disabled|archived --remove, owners = 0--> removed (files deleted, row kept as tombstone)
socle: enabled only (switch off / archive / remove refused)
builtin new in a release: disabled (FR-008a); first migration: enabled when its products already exist (R7)
```

## visuals.pack_versions

| column | type | rules |
|---|---|---|
| `id` | `uuid` PK | |
| `pack_id` | `text` → `packs.id` | |
| `version` | `text` | semver-like (`version_key` ordering of the POC); unique `(pack_id, version)` |
| `sha256` | `char(64)` | fingerprint of the normalized file set; same version + other sha ⇒ refused when published (FR-010) |
| `folder` | `text` | relative to the store root |
| `step` | `text` | `imported`, `analysed`, `tested`, `reviewed`, `published`, `refused`, `superseded`, `purged` |
| `outcomes` | `jsonb` | per step `{analysis, security, test, review}` → `done\|warning\|blocking` |
| `report` | `jsonb` | analysis: pack manifest, elements, findings `[{level, code, element, file, params}]`, summary |
| `measures` | `jsonb` NULL | Test step: `[{element, compiled, fps, ready_ms, errors[]}]`, `at`, `by` |
| `draft` | `jsonb` NULL | Review in progress: economy per product, scene bindings, confirmations |
| `decision` | `jsonb` NULL | `{by, at, economy{product: {price, rarity, level, supply, collection}}, confirmations{scripts, replaces[], contracts[]}, bindings{}, reason?}` |
| `changes` | `jsonb` NULL | built-in « what changed » vs the previous version: `{added[], removed[], changed[]}` (R6) |
| `detected_at`, `published_at` | `timestamptz` | |

```text
imported → analysed → tested → reviewed → published → superseded (a newer one published)
any step before published → refused (reason) ; never published → purged (files deleted)
blocking analysis/security outcome: stays at analysed (validation refused)
built-in: imported → analysed → published directly (R6)
rollback: a superseded version that was published becomes published again (its decision reused)
```

## visuals.elements

| column | type | rules |
|---|---|---|
| `id` | `uuid` PK | |
| `version_id` | `uuid` → `pack_versions.id` | |
| `folder` | `text` | element folder in the pack |
| `type` | `text` | FR-002 vocabulary: `theme` (interface), `navigation`, `palette`, `ambient`, `profile_background`, `avatar_frame`, `profile_banner`, `name_style`, `level_badge`, `badge`, `title`, `level_up`, `effect` (celebration), `notification_style`, `notification_animation`, `booster_scene`, `booster_look`, `booster_opening`, `card_reveal`, `card_face`, `card_back`, `booster`, `widget_style`, `widget`, `bundle` (product pack), `theme_pack` |
| `family` | `text` NULL | claim family (R3); NULL for data-only elements without a look |
| `look` | `text` NULL | `^[a-z0-9][a-z0-9-]{0,47}$` |
| `product_key` | `text` NULL | shop product; NULL for elements never sold (`navigation`, scene parts, `widget` code is sold through its `widget` product only when priced) |
| `kind` | `text` | `css`, `glsl`, `js`, `theme`, `data`, `renderer` (R9) |
| `render` | `jsonb` | `{file, css[], stage, shape, radius, reveal, duration, nav{position,size,expands}, renderer, params, rarity}` |
| `names`, `descriptions` | `jsonb` | `{fr, en}` |
| `proposed` | `jsonb` | economy proposed by the pack `{price, rarity, level, supply, collection, icon, repeatable, season}` |
| `payload` | `jsonb` | bundle `products[]`; booster `pool, packs, cards, odds, guarantee`; badge/title `label, icon, style`; scene `parts{}`; widget `contracts[], sizes[], refresh` |
| `replaces` | `bool` | declares taking over a look of the same key |

Index: `(version_id)`, `(family, look)`, `(product_key)`.

## visuals.look_claims

| column | type | rules |
|---|---|---|
| `family`, `look` | `text` | PK `(family, look)` |
| `pack_id` | `text` | claiming pack |
| `element_id` | `uuid` | |
| `replaced_from` | `text` NULL | pack that held it before a `replaces` decision (restored on rollback/switch off) |

Written inside the publish / switch / rollback / archive transaction; analysis reads it for conflicts (R3).

## visuals.scene_bindings

| column | type | rules |
|---|---|---|
| `booster_key` | `text` PK | a booster product key, or `*` (default scene for every booster) |
| `element_id` | `uuid` | a live `booster_scene` element |
| `bound_by`, `bound_at` | | |

Missing binding ⇒ the built-in default scene; a part missing in the scene ⇒ the default part (FR-030).

## visuals.registry_epoch

Single row `epoch bigint`, incremented in every transaction that changes what is live (R4).

## identity.security_blocks

| column | type | rules |
|---|---|---|
| `id` | `uuid` PK | |
| `kind` | `text` | `account` \| `session` \| `address` |
| `subject` | `text` | user id, session id hash, or IP/CIDR |
| `label` | `text` NULL | login or address, for display |
| `reason` | `text` | weighing reason (`refused`, `refused on the administration`, `attack-shaped address`, …) |
| `points` | `int` | |
| `paths` | `jsonb` | last ≤ 8 paths (truncated to 200 chars) |
| `started_at`, `until` | `timestamptz` | |
| `lifted_at`, `lifted_by` | NULL | `lifted_by`: user id or `console:<os user>` (FR-040a) |

Active block = `lifted_at IS NULL AND until > now()`; partial index on `(kind, subject)` where active.

## Settings (Administration config, CD-011)

| key | tier | default | rule |
|---|---|---|---|
| `security.guard.session_limit` | global | 20 | 5–200 |
| `security.guard.address_limit` | global | 60 | 10–1000 |
| `security.guard.window_s` | global | 600 | 60–3600 |
| `security.guard.block_s` | global | 900 | 60–86400 |
| `observability.health.networks` | global | `["127.0.0.0/8", "::1/128"]` | CIDR list |
| `server.trusted_proxies` | bootstrap (env) | `[]` | CIDR list (R28) |
| `visuals.github.enabled` | global | true | |
| `visuals.limits` | global | `{archive_mb: 20, files: 400, file_mb: 5}` | |

## Capabilities (`capabilities/visuals.py`)

- `external_looks` → renamed `live_looks`: the open vocabulary per family, built from `look_claims` (built-in
  lists of `capabilities/themes.py` removed once the extraction is done, R8).
- `CatalogWriter` (Marketplace): `publish(actor, product) -> str`, `withdraw(actor, key)`, **new**
  `owners(keys) -> int` (live ownerships across those products), `retire(actor, key)` (off sale for good).
- `WIDGET_CONTRACTS`: `{key: {permission, refresh_s, fields[]}}` — `me.progression`, `me.watching`,
  `media.recently_added`, `me.statistics` (R26).

## Events (outbox, 007)

| event | payload | consumers |
|---|---|---|
| `visuals.changed` | `{epoch}` | every process (cache), live stream (clients refetch `active`) |
| `visuals.pack.published` / `.switched` / `.rolled_back` / `.archived` / `.removed` / `.purged` | `{pack, version, by}` | audit (also written directly), notifications (none by default) |
| `visuals.element.failed` | `{pack, element, reason, count}` | administration (element health) |
| `security.block.started` | `{kind, label, reason, until}` | notifications to `security.manage` holders (R31) |
| `security.blocks.changed` | `{}` | every process (block cache) |

## Data migrations

1. `visuals_0001`: schema and tables above; imports the POC's `DATA_DIR/visuals/state.json` when present
   (packs, versions, decisions) then renames it `state.json.migrated`.
2. Built-in sync, first run (R7): creates built-in packs/versions/elements, adopts existing products' economy,
   claims looks, enables packs whose products exist; marks `ui.themes` rows of built-in interfaces with
   `source = "visuals:<pack>"`.
3. `identity_security_blocks`: table above (no data).

Validation invariants (tests): every product key that existed before is held by exactly one element of a
built-in pack (`builtin-looks-before.json`); every look key per family is claimed by exactly one live element
after migration; ownerships, equipped flags and preferences are byte-identical before/after.
