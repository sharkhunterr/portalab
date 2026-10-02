# Contracts — Portal Core Shell

## Backend capability: `core.navigation`
- `register_contribution(contribution: NavigationContribution)` — called at module load (modules) or plugin activation (023). Validates schema; rejects duplicates deterministically.
- `NavigationAssembler.build(principal) -> NavigationView` — merges contributions, filters by enablement + `authorize()` (batched), applies layout policy and user order, resolves conflicts by documented precedence.

## HTTP (`/api/v1`)
| Path | Permission | Notes |
|---|---|---|
| GET `/me/navigation` | authenticated | ETag/If-None-Match; returns `NavigationView` |
| GET `/me/stream` (SSE) | authenticated | emits `navigation.changed` (no payload beyond version), heartbeat |
| GET/PUT `/admin/shell/layout` | `shell.manage` (audited) | admin navigation policy; validated against known keys |
| GET `/admin/shell/contribution-errors` | `shell.manage` | diagnostics |
User ordering and shortcuts use `/me/preferences` (020).
Problem codes: `navigation.contribution_invalid`, `route.unavailable`, `route.unauthorized`.

## Frontend contracts
- `registerRoutes(manifestRoutes)`; `RouteHandle = { crumb, related?, existenceSensitive?, requiredPermission? }`.
- `<AppShell>` slots: `Header`, `PrimaryNav`, `SearchEntry`, `AiEntry`, `NotificationEntry`, `IdentityMenu`, `Outlet`, `GlobalStatusBanner`.
- `CommandRegistry`: `register(command)`, `useCommands(query)`; commands carry `id,label_key,keywords,permission,run|route`.
- `RouteBoundary` renders `FunctionalState` (022) for `loading|error|unavailable|unauthorized|not-available`.
- Search/AI entry contracts: `SearchProvider.open(query?)`, `AiProvider.open(context?)` — implemented by 008/018; shell renders a degraded placeholder when absent.

## Extension point (023)
Plugins call `core.navigation.register_contribution` only through the plugin host; enrichment of existing modules requires the target to declare an `extension_slot`.

## Implementation notes (2026-10-03)
- Live updates use the kernel stream `GET /api/v1/stream` (topic `navigation.changed`, payload `{version}`)
  instead of a second `/me/stream` endpoint. `GET /me/navigation` requires `users.self.manage` (every account).
- New capabilities used by the shell: `admin.extension_state` (module/plugin enablement) and
  `admin.config_writer` (audited admin layout change), both provided by Administration (020).
- Frontend slot contracts: `ShellSlotsProvider` with `search`, `ai`, `notifications`, `help` (`HelpResolver`, 011).
