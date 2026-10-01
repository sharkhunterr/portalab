# Data Model — Marketplace (schema `marketplace`)

FKs only intra-module or to `identity.users(id)`; Community proposal, extension package, economy reservation and transaction ids are opaque references.

## Slice A — community funding lifecycle
- **marketplace.projects**: `id` UUIDv7 · `proposal_ref` (Community proposal id) unique · `title` (snapshot) · `state` (`idea|proposal|open|validation|development|beta|released|rejected|abandoned`) · `funding_rules` jsonb null (frozen at `open`) · `rules_frozen_at` null · `goal_amount` null (display only) · `validated_by` FK null · `validated_at` null · `version` int · `created_at` · `updated_at`.
- **marketplace.project_state_history** (append-only): `project_id` FK · `seq` · `from_state` · `to_state` · `actor_user_id` FK null · `reason` · `created_at`.
- **marketplace.project_fundings**: `id` · `project_id` FK · `user_id` FK · `amount` bigint · `reservation_ref` (013) · `status` (`reserved|released|consumed|destroyed_on_deletion`) · `acknowledged_at` (non-guarantee notice, required) · `created_at` · `resolved_at` null · `resolution_tx_refs` jsonb. Index `(project_id, status)`.
- **marketplace.project_notes**: `project_id` · `author_id` · `state` · `public_note` — milestone/status notes shown to funders.

## Slice B — catalog, ownership, quota
- **marketplace.categories**: `id` · `key` · `label_key` · `position`.
- **marketplace.products**: `id` · `key` unique · `type` (registered ProductType) · `category_id` FK · `state` (`draft|available|unavailable|archived`) · `current_version` · `repeatable` bool · `extension_ref` null (023) · `created_by` FK · `created_at`.
- **marketplace.product_versions** (append-only): `product_id` FK · `version` · `price_coins` null · `conditions` jsonb (closed set, AND) · `refund_policy` jsonb · `names` jsonb · `descriptions` jsonb · `config_required` bool · `effective_from` · `changed_by` FK · PK `(product_id, version)`.
- **marketplace.ownerships**: `id` · `user_id` FK · `product_id` FK · `origin` (`purchase|grant`) · `product_version` · `price_paid` · `conditions_snapshot` jsonb · `purchase_tx_ref` null · `state` (`active|needs_configuration|activation_failed|revoked|refunded|expired`) · `acquired_at` · `expires_at` null · `revoked_at` null · `revoke_ground` null · `revoke_reason` null. Unique partial index `(user_id, product_id) WHERE state NOT IN ('revoked','refunded','expired') AND NOT repeatable`.
- **marketplace.refunds** (append-only): `id` · `ownership_id` FK · `refund_tx_ref` · `percent` · `reason` · `actor_user_id` FK · `created_at`.
- Quota balances are **not stored here**: a quota product's activation credits units in 024 (`media.request_quota_units`); the ownership row records the purchase.
- **marketplace.audit_refs**: none (audit lives in `AuditSink`).

## Settings (declared into 020)
`marketplace.refundDefaults.<type>`, `marketplace.access.allowedPermissions` (Admin-approved list for `access` products), `marketplace.funding.minAmount|maxPerUser`, `marketplace.funding.defaultRules`, `marketplace.quota.kinds`, `marketplace.activationRetryMinutes`.

## Events (via 007; ids/amounts, no PII)
Produced: `marketplace.purchase` (dedup `(user, product, acquisition_seq)`), `marketplace.unlock`, `marketplace.refund`, `marketplace.grant`, `marketplace.revocation`, `marketplace.product_published|archived`, `project.status_changed` (dedup `(project, seq)`), `project.funding_added|funding_released|funding_consumed`. Consumed: `project.created` (Community → register lifecycle), `user` deletion saga participant calls, `campaign.*` (condition caches), extension activation results (023).

## Privacy / retention
Ownerships and fundings = personal data (`activity`); anonymized/tombstoned per 021 and R6; purchase history visible to the owner and `marketplace.manage`; ledger references are ids only.
