# Contracts — Marketplace

## Ports provided
- **`ProjectLifecycle`** (to Community 012): `register(proposal_ref, proposer) -> ProjectRef`, `state(project_ref)`, `accepts_votes(project_ref)`, `funding_summary(project_ref)`.
- **`EntitlementReader`** (to 009 widgets, 022 themes, 017 `product_owned`, Community cosmetics, 003 access checks): `owns(user, product_key) -> bool`, `owned_by_type(user, type)`, `state(user, product_key)`.
- Quota products call Media's **`RequestQuotaService.add_units/remove_units`** (024) — Marketplace never measures or consumes quota and never influences ordering/priority.
- `ProductType` registry + `ActivationHandler` Protocol (`activate(ownership) -> ActivationResult{active|needs_configuration|failed|incompatible}`, `deactivate`), `register_product_type(...)`.
## Ports consumed
`EconomyService.reserve|release|consume|spend|refund` (013; **follow-up: reservations + unit-of-work**) · `ProgressionReader`, `CampaignReader`, authz roles/`authorize` · `ExtensionActivation` (023, stub until step 27) · `notifications.send` (010) · `AuditSink`/`ConfirmationService` (003) · `SearchProvider` SDK (008) · `ContentLocalizer` (026).

## HTTP (`/api/v1`) — Slice A (funding lifecycle)
| Path | Permission |
|---|---|
| GET `/projects?state` · GET `/projects/{id}` (state, rules, funding totals, history notes) | `community.read` |
| POST `/projects/{id}/fund` `{amount, acknowledged: true}` | active account; state `open`; `ConfirmationService` not required, acknowledgement mandatory |
| GET `/me/fundings` | self |
| POST `/admin/projects/{id}/promote|open` (`open` sets frozen rules) · `/validate` (approve/reject + reason) · `/transition` (development/beta/released) · `/abandon` · `/reject` | `projects.manage` (Admin; sensitive, audited, confirmation on validate/reject/abandon/release) |
| GET `/admin/projects/{id}/fundings` (aggregate + per funder for Admin) | `projects.manage` |
## Slice B (marketplace)
| Path | Permission |
|---|---|
| GET `/marketplace/categories` · GET `/marketplace/products?category&type&q&cursor` · GET `/marketplace/products/{key}` (type, price, conditions, **eligibility with named unmet conditions**, ownership, refund policy) | `marketplace.read` (default grant) |
| POST `/marketplace/products/{key}/acquire` (`Idempotency-Key`) | `marketplace.purchase` (default grant; active accounts) |
| GET `/me/marketplace/purchases` · GET `/me/marketplace/owned` · POST `/me/marketplace/owned/{id}/configure` (needs-configuration) · POST `/me/marketplace/owned/{id}/refund` | self |
| GET/POST/PUT `/admin/marketplace/products[/{key}]` · POST `…/publish|archive|unavailable` | `marketplace.manage` (sensitive for publish/price/condition changes, audited) |
| POST `/admin/marketplace/grants` · POST `/admin/marketplace/ownerships/{id}/revoke` `{ground, reason}` · POST `…/refund` | `marketplace.grant` / `marketplace.revoke` / `marketplace.refund` (sensitive, audited, confirmation) |
| GET `/admin/marketplace/audit?…` | `marketplace.audit` |
Problem codes: `marketplace.conditions_unmet` (lists names), `marketplace.already_owned`, `marketplace.not_available`, `marketplace.insufficient_coins`, `marketplace.not_refundable`, `project.funding_closed`, `project.rules_frozen`, `project.acknowledgement_required`.

## Frontend
Catalog (categories, filters, product cards with ownership/eligibility), product detail (conditions checklist, price, refund policy before purchase), purchase flow with confirmation, owned/history pages, needs-configuration flow; project pages (state timeline, rules, funding with non-guarantee notice, my fundings); admin consoles (products, grants/revocations, project validation/transitions, audit).
