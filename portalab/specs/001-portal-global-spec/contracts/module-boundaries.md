# Contract — Module Boundaries

Mechanically enforced in CI (import-linter + boundary tests). Violations fail the build.

## Layers (a layer may import only layers to its left)

```
core  ←  capabilities  ←  modules / connectors  ←  app
```
`plugins_runtime` sits beside `app`; **plugin packages** live outside the core tree and import only
`capabilities` and published module SDKs.

## Rules

1. `core` imports nothing from `capabilities`, `modules`, `connectors`, `plugins*`, `app`.
2. A **module never imports another module's internals**. Allowed interactions: call a **capability contract**,
   or publish/consume a **Domain Event** (envelope owned by spec 007).
3. A **connector** depends only on `core` + `capabilities`; it implements capability Protocols. It never imports a
   module, and no module imports a connector (resolution is via the registry).
4. **No cross-schema SQL**: no joins and no foreign keys across module schemas, except to `identity.users(id)`.
5. `app` is the only composition root allowed to import everything.
6. The core has **no import path** to any plugin (a missing/disabled plugin must never break startup).

## Ownership checks (one owner per mechanism — CANONICAL_DECISIONS §1)

A boundary test asserts that each of these exists in exactly one package and nowhere else: configuration store
(`administration`), WHEN/IF/THEN engine (`automations`), event model & dedup (`events`), ledger (`gamification`),
funding lifecycle (`marketplace`), incident lifecycle (`support`), visibility engine (`privacy`),
self-observation (`observability`), localization (`i18n`).

## Allowed vs forbidden (examples)

| Allowed | Forbidden |
|---|---|
| `modules.media` resolves capability `media.library` | `modules.media` imports `connectors.plex` |
| `modules.statistics` subscribes to `media.playback_finished` | `modules.statistics` imports `modules.media.models` |
| connector `plex` implements `media.library` Protocol | connector `plex` writes to the `media` schema directly |
| notifications registers a *communication action* in Automations | notifications defines its own WHEN/IF/THEN engine |
