# Contracts — Automations

## Python capability `capabilities/automations`
- `register_action_type(ActionType{key, owner, label_key, params_schema, required_permission, sensitivity: normal|sensitive|destructive, handler(principal, params, ctx) -> ActionResult, idempotency(params, trigger) -> str, ai_output_allowed: bool})` — implemented by owning domains (010 `communication.produce` already shaped this way).
- `ActionContext{execution_id, chain_id, depth, trigger_ref, principal, deadline}`; handlers MUST propagate `provenance.automation` into emitted events.
- `register_condition_leaf(...)` — closed catalog extensible only by core modules (plugins may add *event attributes*, not operators).
- `TriggerRegistry`: derived from 007 registry (`automatable` event types) + schedule kinds.
- `ApprovalProvider`: `request(execution, step, summary, params_hash)`; decisions via API.
- Ports consumed: `ProgressionReader` (013), `CampaignReader`/`ActivityAttributeProvider` (014), `health.service_state` (006), authz `authorize`, 026 time helpers, `ConfirmationService`.

## HTTP (`/api/v1`)
| Path | Permission |
|---|---|
| GET `/admin/automations` · GET `/admin/automations/{id}` (+versions) | `automations.read` |
| POST `/admin/automations` (draft) · PUT `/admin/automations/{id}` · POST `…/publish` | `automations.manage` (sensitive when critical actions; `ConfirmationService`; audited) |
| POST `/admin/automations/{id}/pause|resume|archive` · POST `…/reenable` (after suspension) | `automations.manage` (audited) |
| POST `/admin/automations/{id}/dry-run` `{sample_event|event_id}` | `automations.manage` (no side effects) |
| POST `/admin/automations/{id}/run` (manual run for schedule/test, real, confirmation) | `automations.manage` (sensitive) |
| GET `/admin/automations/{id}/executions?status&cursor` · GET `/admin/automations/executions/{id}` | `automations.read` |
| GET `/admin/automations/approvals?status` · POST `/admin/automations/approvals/{id}/approve|reject` | `automations.approve` (audited; approver ≠ unauthorized) |
| GET `/admin/automations/catalog` (triggers, condition leaves, action types incl. sensitivity) | `automations.read` |
| GET `/admin/automations/templates` · POST `…/templates/{key}/instantiate` | `automations.manage` |
Problem codes: `automation.invalid_definition`, `automation.action_forbidden`, `automation.loop_prevented`, `automation.suspended`, `automation.approval_required`.

## Frontend
Admin automation builder (trigger picker → condition builder → step list with schema-driven forms → validation panel → dry-run result), versions diff, execution history with condition trace and per-step outcomes, approvals inbox, suspended banner/re-enable, templates gallery.

## Preset templates (shipped)
`campaign-start-announcement`, `campaign-ending-soon`, `welcome-on-verification`, `critical-service-incident-draft` (approval-gated), `weekly-community-digest-news`, `new-ticket-notify-support`.
