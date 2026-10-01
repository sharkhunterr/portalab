# Contracts — Identity & Users

## Exposed capabilities / ports (consumed by other specs)
- **`identity.directory`**: `get_user_summary(user_id)`, `is_active_account(user_id) -> bool` (only state `active`; used by voting, rewards), `exists(user_id)`. Tombstoned users return an anonymized summary.
- **`identity.principal`**: `Principal{user_id, session_id, state, roles_ref}` resolved per request by the auth middleware; the only way modules, AI, automations and plugins learn *who* acts (CD-003).
- **`AuthProvider` port**: `authenticate(credentials) -> AuthResult | Denied`; baseline = local. Future OIDC/MFA providers implement it.
- **`privacy.erasure_participant`** (declared here, consumed by every data-owning module): `erase(user_id, mode)` idempotent; **`privacy.export_contributor`**: `export(user_id) -> Iterable[ExportRecord]` (no secrets, no other users' private data).
- **`IdentityBootstrap`**: `create_first_admin(login, password)`; refuses when an Admin exists.

## Consumed
`authz.authorize()` + `authz.admin_authority` (003) · kernel `EventPublisher`, jobs, secrets, blobstore, settings declaration (001) · `AuditSink` (003).

## HTTP API (`/api/v1`, conventions per 001 contracts/api-conventions.md)
| Method & path | Permission | Notes |
|---|---|---|
| POST `/auth/register` | public (policy-gated) | creates `pending_verification`; non-enumerating |
| POST `/auth/verify` | public (token) | → `active`, starts onboarding |
| POST `/auth/login` | public | throttled; sets session cookie + CSRF token |
| POST `/auth/logout` | session | revokes current session |
| GET `/me` · PATCH `/me/profile` | `users.self.manage` | display name uniqueness, field visibility preference |
| PUT/DELETE `/me/avatar` | `users.self.manage` | validated, re-encoded |
| GET `/users/{id}/profile` | `users.read` | fields filtered by visibility (021) |
| POST `/me/export` · GET `/me/export/{id}` | `users.self.manage` | async job, expiring download |
| POST `/me/deletion` · DELETE `/me/deletion` | `users.self.manage` | request / cancel within grace; re-auth required |
| GET `/users` · POST `/users/{id}/suspend|reactivate|deletion` | `users.manage` | audited, confirmation |
| POST `/admin/transfer` | `users.admin.transfer` | step-up re-authentication; atomic |
Error codes (problem+json `code`): `auth.invalid_credentials` (single code for all unauthenticated failures), `auth.account_unavailable`, `user.display_name_taken`, `user.state_transition_forbidden`, `admin.sole_admin_protected`.
