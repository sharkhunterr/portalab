# Marketplace (spec 015)

Marketplace owns two things: the **community funding lifecycle** (slice A, roadmap step 25) and the
**catalog** of products bought with Coins (slice B, step 26). It never holds Coins: they stay in the
Gamification ledger (013), where Marketplace *reserves*, *releases* and *consumes* them.

## Community projects (slice A)

Community (012) owns proposals and votes; Marketplace owns each project's **state** and **funding**.

```
idea → proposal → open → validation → development → beta → released
  └──────────────┴──────┴────────────┴→ rejected        (and → abandoned from any non-final state)
```

* Community registers one project per `project` proposal through `ProjectLifecycle.register` (idempotent)
  and reads `state`, `accepts_votes` (idea, proposal, open) and `funding_summary` (public aggregates).
* Transitions need `projects.manage` (Admin; sensitive, audited). Approving at validation, rejecting,
  abandoning and releasing move members' Coins, so they also need a confirmation
  (`authz.confirmation_required` → retry with `confirmation`). Every change appends to
  `project_state_history` (append-only), emits `project.status_changed` (dedup `(project, seq)`) and may
  carry a public note. Validation is the Admin's gate — informed by votes and funding, never bound to them.
* Funders are notified of status changes (`marketplace.project`, 010).

### Funding rules — frozen when the project opens

```json
{"consume_at": "released", "min_funding": 1, "max_funding_per_user": 1000, "goal_amount": 5000}
{"consume_at": [{"state": "beta", "percent": 40}, {"state": "released", "percent": 60}]}
```

`refund_on_reject` and `refund_on_abandon` are 100 % (see deviations). Defaults come from
`marketplace.funding.defaultRules`; `marketplace.funding.minAmount|maxPerUser` bound every project.

### Funding

`POST /api/v1/projects/{id}/fund {amount, acknowledged: true}` (`marketplace.purchase`, active account,
`Idempotency-Key` header) — only while `open`; the member must acknowledge that **funding does not
guarantee implementation** (`project.acknowledgement_required`). The amount is split into one 013
reservation per consumption tranche, atomically with the funding row; insufficient Coins are refused and
the balance never goes negative. Voting and funding are independent: neither requires nor creates the
other. `project.funding_added` is emitted once per request.

### Resolution

* rejected / abandoned → every still-reserved tranche is **released** (a new ledger transaction;
  `project.funding_released`);
* reaching a milestone (or release) → the tranches due are **consumed** (`project.funding_consumed`);
* everything happens in the transition's transaction and is idempotent; an hourly job reconciles each
  tranche with its 013 reservation (drift reported to Observability, component `marketplace`).

### Account deletion (R6)

At final deletion every funding still holding reserved Coins becomes `destroyed_on_deletion` whatever
the project state; the 013 participant releases then destroys the reservations with the account's
remaining Coins — never a refund, never a transfer to the project. Project totals (computed live) drop.

### API (slice A)

| Path | Access |
|---|---|
| `GET /api/v1/projects?state` · `GET /api/v1/projects/{id}` | `marketplace.read` (state, rules, public totals, history, notes) |
| `POST /api/v1/projects/{id}/fund` | `marketplace.purchase` + active account + acknowledgement |
| `GET /api/v1/me/fundings` | self |
| `POST /api/v1/admin/projects/{id}/promote|open|validate|transition|abandon|reject` | `projects.manage` |
| `GET /api/v1/admin/projects/{id}/fundings` | `projects.manage` (per funder, Admin only) |

Problem codes: `project.funding_closed`, `project.acknowledgement_required`, `project.funding_limits`,
`project.rules_frozen`, `project.invalid_rules`, `project.invalid_transition`, `project.version_conflict`,
`economy.insufficient_coins`.

## Recorded deviations

* Project reads use `marketplace.read` (granted to users) instead of the contract's `community.read`, which
  belongs to the Community module.
* Refunds on reject/abandon are fixed at 100 %: a partial refund would require the 013 ledger to split a
  reservation. Milestone consumption is supported by splitting each funding into one reservation per
  tranche at funding time.
* Fundings have no retention target: they reference ledger reservations (integrity) and are anonymized at
  deletion (R6).
* 013 follow-ups delivered with 015: `EconomyService.refund(..., amount=)` (partial refunds) and
  `EconomyService.reservations(ids)` (reconciliation).
* The Marketplace audit view reads the 003 audit through a new `audit.query` capability (action family
  `marketplace.`).
* Media (024) has no request ordering function; the "no paid priority" guarantee is enforced by the
  schema guard and a structural test (no priority-like column in Media requests or Marketplace tables).

## Catalog (slice B)

Products are bought with **Coins only** — there is no payment, currency or card anywhere (guarded by
`tests/security/marketplace/test_no_real_money.py`); Coins come from earning.

### Product types

`register_product_type(ProductType(key, owner, handler, refundable_by_default, payload_fields))` — the
registry is owner-tagged (`unregister(owner)`; plugin types are namespaced `plugin:<key>.<type>`). Built-in
types and their activation:

| Type | Payload | Activation |
|---|---|---|
| `widget` | `widget` | ownership read by 009 (`marketplace.entitlements`); unknown widget ⇒ incompatible |
| `theme` | `theme` | must exist in the 022 catalog |
| `statistic` | `statistic` | read by 017 `product_owned` unlocks |
| `badge`, `title`, `effect` | `label`, `icon` / `effect` | shown in the `cosmetics` profile section (012) |
| `feature`, `plugin` | `extension`, `config_required` | `needs_configuration` until the owner configures; portal-level code is installed by the Admin when publishing (023 activation later) |
| `access` | `permission` | a per-user grant (003), only for permissions in `marketplace.access.allowedPermissions` and never Admin-reserved; removed on revoke |
| `quota` | `kind`, `units` | units credited through Media's `RequestQuotaService` (024); Marketplace never measures or consumes quota |

Nothing can buy priority: any priority-like key (`priority`, `queue`, `boost`, `skip`, `rank`…) in a
product definition is rejected (`marketplace.priority_forbidden`).

### Versions and states

```json
{"key": "night_owl", "type": "badge", "category": "cosmetics", "repeatable": false,
 "version": {"price_coins": 50, "conditions": [{"kind": "min_level", "level": 3}],
             "refund_policy": {"refundable": true, "window_days": 7, "percent": 100},
             "names": {"en": "Night owl", "fr": "Oiseau de nuit"}, "payload": {"label": "Night owl"}}}
```

Every change of price, conditions, refund policy, texts or payload is a **new version** (append-only); an
ownership keeps its snapshot (version, price paid, conditions). States `draft → available ⇄ unavailable →
archived`: archived products are hidden from new purchases and stay with their owners. Publishing and
revising a published product are sensitive (confirmation) and audited. Refund defaults per type come from
`marketplace.refundDefaults`; otherwise plugins, access and quota are non-refundable, the rest
refundable for 7 days at 100 %.

### Conditions and acquisition

Conditions form a closed set combined with **AND**: `min_level`, `achievement`, `campaign_active`, `role`
(plus the Coins price). The product page lists each one by name, met or not; an unavailable port fails
closed (`unavailable`). `POST /api/v1/marketplace/products/{key}/acquire` (`Idempotency-Key`) runs in one
unit of work: eligibility, the once-only check for permanent products (`repeatable` opt-in), the 013 spend
and the ownership row with its snapshot, then `marketplace.purchase`. Activation runs after the commit
and never undoes the ownership (`needs_configuration`, or `activation_failed` retried every
`marketplace.activationRetryMinutes`).

### Refunds, grants and revocation

* Refund within the policy (owner) or by an administrator (`marketplace.refund`, any time, confirmed): a
  new `refund` ledger transaction reversing the purchase (partial percentages supported), an append-only
  refund row, the ownership `refunded` and deactivated. Quota units already used make it non-refundable.
* Grants (`marketplace.grant`, confirmed, audited): `origin=grant`, optional expiry (a job expires them).
* Revocation (`marketplace.revoke`, confirmed, audited): ground `abuse | grant_expired | refund |
  withdrawn_for_cause` and a reason; a Coins purchase is refunded per its policy unless the ground is
  `abuse`; the member is notified; history is never rewritten.
* `GET /api/v1/admin/marketplace/audit` (`marketplace.audit`) lists the marketplace audit trail.

### Integrations

`marketplace.entitlements` (`owns`, `owned_by_type`), search kind `product`, dashboard widget
`marketplace.featured`, AI tool `marketplace.catalog` (read-only), statistics pack `marketplace`
(`marketplace.coins_spent`, `marketplace.purchases`), notifications `marketplace.purchase|refund|
revocation`, profile section `cosmetics`.
