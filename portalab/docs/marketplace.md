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

## Recorded deviations (slice A)

* Project reads use `marketplace.read` (granted to users) instead of the contract's `community.read`, which
  belongs to the Community module.
* Refunds on reject/abandon are fixed at 100 %: a partial refund would require the 013 ledger to split a
  reservation. Milestone consumption is supported by splitting each funding into one reservation per
  tranche at funding time.
* Fundings have no retention target: they reference ledger reservations (integrity) and are anonymized at
  deletion (R6).

## Catalog (slice B)

Delivered at roadmap step 26.
