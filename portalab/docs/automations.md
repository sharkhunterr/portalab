# Automations (spec 019)

A bounded rules engine: **WHEN** a trigger **IF** a closed condition tree **THEN** up to
`automations.maxSteps` (10) actions in order. No branching, loops, scripts or cron strings. Authoring is
Admin-only in v1 (`automations.allowUserAuthoring = false`).

## Model

```json
{
  "name": "Announce campaigns",
  "trigger": {"kind": "event", "event_type": "campaign.started",
              "filter": [{"field": "campaign", "op": "eq", "value": "halloween"}]},
  "conditions": {"all_of": [
    {"leaf": "time_window", "params": {"start": "08:00", "end": "22:00", "timezone": "Europe/Paris"}},
    {"not": {"leaf": "campaign_active", "params": {"campaign": "maintenance-week"}}}]},
  "steps": [
    {"id": "draft", "action": "ai.invoke", "params": {"instruction": "One friendly line about ${event.campaign}"}},
    {"id": "send", "action": "communication.produce", "params": {
       "category": "campaigns.announcement", "template_key": "campaigns:notify.announcement",
       "audience": {"type": "all"}, "dedup_key": "campaign:${event.campaign}:${event.occurrence}",
       "params": {"campaign": "${event.campaign}", "message": "${steps.draft.text}"}}}],
  "limits": {"cooldown_s": 0, "dedup_key": "${event.campaign}", "dedup_window_s": 86400,
             "batchable": false, "rate_per_min": 60},
  "identity": {"kind": "author"}
}
```

* **Triggers**: any event type flagged `automatable` in the 007 registry (including plugin and system
  events and the internal `automation.triggered`), a field filter over its declared attributes, plus
  `at` (one time), `relative` (an event's datetime attribute ± `offset_minutes`) and `recurring`
  (`daily | weekly | monthly` at `HH:MM` in a time zone; DST: a missing time moves forward, a repeated one
  is the earlier).
* **Conditions**: `all_of`, `any_of`, `not` (depth ≤ 3) over closed leaves — `user_is`, `role_in`,
  `level_at_least`, `service_state_in`, `media_kind`, `genre`, `title_contains`, `campaign_active`,
  `time_window`, `permission_held` (informational, never grants), `event_field`. Every leaf is evaluated
  and traced; an unknown leaf (provider down, missing attribute) counts as false.
* **Substitution**: `${event.<declared field>}`, `${event.id|occurred_at}`, `${subject.id|type}`,
  `${actor.id}`, `${automation.key}`, `${steps.<earlier step>.<key>}` — nothing else.

## Safety controls

| Control | Behavior |
|---|---|
| Identity | runs as `Principal(channel="automation", acting_for=author)`; a *system* identity is the author's rights restricted to declared scopes (never beyond the publisher) |
| Permissions | re-checked before every action; a suspended/deactivated author or a missing right ⇒ `refused` + `needs_review` |
| Approvals | *destructive* actions (or permissions requiring confirmation) wait for an approver (`automation.approve`) per execution; *sensitive* ones need a standing approval attested at publish (confirmation) |
| AI boundary | `ai.invoke` output may only feed non-sensitive actions declaring `ai_output_allowed`; never a condition (conditions take no substitution) and never approvals |
| Loops | events emitted by actions carry `correlation_id = chain_id` and `provenance.automation {id, execution_id, depth, path}`; an automation already in the path, or a depth ≥ `maxChainDepth` (3), is `prevented` |
| Repeats | one execution per `(automation, version, trigger event)`; `dedup_key` per window; `cooldown_s` |
| Timeouts | per action (`actionTimeoutSeconds`) within the execution deadline (`executionTimeoutSeconds`) ⇒ `timeout` |
| Storms | beyond `rate_per_min`: `batchable` automations add to the latest execution's `batch_count`, others record `throttled` — never silent |
| Suspension | ≥ `suspendAfterFailures` consecutive failures or > `suspendFailureRate` over 20 runs ⇒ `suspended`, event and notification; executions while suspended are recorded; explicit re-enable |

Execution statuses: `success`, `no_op`, `refused`, `prevented`, `timeout`, `suspended`, `failed`,
`throttled`, `awaiting_approval`. History keeps references only (trigger ref, condition trace, step outcomes
with short scalar results) — never payload bodies or secrets; retention `executionRetentionDays` (90).

## Authoring

`/admin/automations`: builder (catalog-driven), dry-run (conditions + planned steps, no side effects),
publish, pause/resume/archive/re-enable, manual run (confirmation, same safety controls), executions,
approvals inbox and templates (`campaign-start-announcement`, `campaign-ending-soon`,
`welcome-on-verification`, `critical-service-incident-draft`, `weekly-community-digest-news`,
`new-ticket-notify-support`). Every save is a new append-only version; the published version runs.

## Registering actions and conditions (owners)

```python
from portalab.capabilities.automations import ActionType, register_action_type

register_action_type(ActionType(
    key="media.request", description="Request a title", permission="media.request",
    idempotency="one request per (user, title) — the service dedups",
    run=handler,                       # async (params, principal) -> result refs
    owner="module:media", params_schema={"title_id": "string", "note": "string?"},
    sensitivity="normal",              # normal | sensitive | destructive
    ai_output_allowed=False,
))
```

Handlers act **as the given principal** through the same domain services as the API; events they publish
automatically carry the chain id and `provenance.automation`. `current_action()` exposes the running step.
Condition leaves are a closed catalog: only core modules register them (`register_condition_leaf`);
plugins contribute event attributes, never operators. All registries support `unregister(owner)`.

## Follow-ups applied with this spec

* 007: `automatable` on `user.verified`; the event publisher merges `provenance_scope()` (new core context)
  into event provenance.
* 010: `communication.produce` declares all its parameters (`params`, `action_url`, `rule`) and required
  ones, and accepts AI-drafted text.
* 018: `ai.invoke` registered as an action (read-only assist).
* 013 (`award.*`, `reward.unlock`), 016 (`ticket.create`, `incident.create`), 011 (`content.publish`) and
  005 (`connector.sync|action`) already register their actions; their permissions decide sensitivity.

## Recorded deviations (T037)

* Executions run inline in the trigger consumer / scheduler job (no separate `automations_run` job); the
  unique execution key keeps them idempotent on redelivery.
* `automations.pending_fires` (not in the data model) stores scheduled `relative` fires.
* Chain depth and loops use the event provenance `path` (ancestry) rather than every execution sharing the
  chain id, so sibling automations of one event do not count against each other.
* The identity guard also requires the author's account to be active (identity directory).
