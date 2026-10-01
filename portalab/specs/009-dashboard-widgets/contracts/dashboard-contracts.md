# Contracts — Dashboard & Widgets

## Python capability `capabilities/dashboard`
- `WidgetDefinition{key, owner, title_key, description_key, icon, required_permission, config_schema, config_defaults, size{default,min,max}, multiple, refresh{mode, interval_s, events[]}, stale_after_s, conditions[], template|component_id, schema_version}`.
- `WidgetDataProvider.load(principal, config, ctx: LocaleContext) -> WidgetPayload` (provider authorizes and applies visibility; raise `Unavailable`/`Partial` helpers).
- `ChangeSummaryProvider.changes_since(principal, since, limit, ctx) -> list[ChangeItem{kind, title_key|text, occurred_at, ref, priority}]`.
- `register_widget(defn, provider)` / `unregister_widget(key)`; `ConditionEvaluator` closed set (`role_in`, `permission`, `service_state`, `campaign_active`, `module_enabled`, `data_present`).

## HTTP (`/api/v1`)
| Path | Permission | Notes |
|---|---|---|
| GET `/dashboard` | authenticated | effective dashboard: instances + resolved policy flags (`locked`,`mandatory`,`removable`,`hideable`), `layout_version` |
| GET `/dashboard/catalog` | authenticated | widgets the user may add (permitted, enabled, not disabled by policy) |
| POST `/dashboard/widgets` · PATCH `/dashboard/widgets/{id}` (position/size/status/config) · DELETE `/dashboard/widgets/{id}` | `users.self.manage` | policy-validated; `If-Match: layout_version`; problem codes `dashboard.policy_locked`, `dashboard.widget_unavailable`, `dashboard.config_invalid`, `dashboard.version_conflict` |
| PUT `/dashboard/layout` | `users.self.manage` | batch reorder/resize atomically |
| GET `/widgets/{key}/data` | widget's `required_permission` (+provider rules) | `WidgetPayload` with timeout budget; never throws 5xx for provider failure (returns state) |
| GET `/dashboard/since-last-login` · POST `/dashboard/since-last-login/seen` | authenticated | scoped by providers; `seen` advances boundary |
| GET/PUT `/admin/dashboard/policies`, `/admin/dashboard/starter` | `dashboard.manage` (audited) | via 020 settings, validated against registered keys |
SSE (004 stream): message `widget.invalidate {key}`.

## Frontend
`<DashboardPage>` (grid, edit mode with keyboard move/resize, catalog drawer, `PolicyField` badges), `<WidgetFrame>` (boundary + `FunctionalState`), `registerWidgetComponent(key, Component)` and the declarative templates `stat|list|chart|timeline|status`, `<SinceLastLogin>` card.

## Extension point (015/023)
Marketplace/plugin widgets call `register_widget` through the plugin host with a declarative template; removal on deactivation drops instances to a graceful "widget no longer available" placeholder (config retained for reactivation).
