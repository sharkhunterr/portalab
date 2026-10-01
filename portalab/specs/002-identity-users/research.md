# Research — Identity & Users (spec 002)

Baseline stack is fixed by `specs/001-portal-global-spec/research.md` (Python 3.12/FastAPI, PostgreSQL, React/TS). Decisions below are specific to identity.

| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| R1 | **Server-side sessions** in PostgreSQL: opaque 256-bit token, stored as SHA-256 hash, delivered in a `__Host-` HttpOnly Secure SameSite=Lax cookie; absolute + idle expiry from config | Suspension/deletion must revoke sessions immediately (OQ-10 default); permissions are evaluated per request so no stale claims | JWT access tokens (cannot be revoked without a denylist, claims go stale) |
| R2 | **Password hashing: Argon2id** (`argon2-cffi`), per-hash salt, parameters in config, rehash-on-login when parameters change | Current OWASP recommendation, memory-hard | bcrypt (acceptable but weaker), PBKDF2 |
| R3 | **Authentication behind an `AuthProvider` port**; baseline provider = local credentials. OIDC/MFA are *not* in spec 002 and are future providers | Keeps product scope; the port avoids a rewrite later | Building OIDC now (invented scope) |
| R4 | **Non-enumerating login**: identical response and constant-time work for unknown identifier / wrong password / inactive state; state-specific message only after valid credentials | FR-006/008, SC-002 | Distinct errors (enumeration) |
| R5 | **Throttling, not lockout**: progressive delay per (identifier, IP) stored in PostgreSQL | Hard lockout would let anyone lock the sole Admin out | Permanent lock after N failures |
| R6 | **CSRF**: SameSite=Lax cookie + required `X-CSRF-Token` (double-submit) on unsafe methods | Cookie auth requires it | Token-only auth for browser |
| R7 | **Display-name uniqueness** via a normalized key (NFKC + casefold) with a unique index; key nulled on deletion (name released, OQ-8 default) | FR-001/010/026 | Case-sensitive unique (homoglyph/case collisions) |
| R8 | **Account lifecycle = explicit state machine** with a guard table; each transition = one transaction writing state, history row, outbox event, audit record | FR-003, invariants | Ad-hoc flag columns |
| R9 | **Single-Admin invariant lives in `authz`** (partial unique index + transactional transfer); Identity orchestrates transfer through the `authz.admin_authority` capability | CD-001; avoids two owners of roles | Duplicating role logic in identity |
| R10 | **Preferences are NOT stored by identity**: user-tier settings belong to the Administration configuration system (CD-011); identity only declares keys and exposes `/me` facade once Configuration (step 4) lands | Prevents a second config store | A `user_preferences` table here |
| R11 | **Deletion & export use participant capabilities** (`privacy.erasure_participant`, `privacy.export_contributor`): every module that stores user data registers one; identity runs the saga/bundle | One generic mechanism, extensible by plugins, no table-name knowledge | Hard-coded deletion list |
| R12 | **Avatar storage via `core.blobstore` port** (filesystem baseline, S3-compatible later); uploads validated, decoded and re-encoded (Pillow) to strip metadata; served only through an authenticated, visibility-checked route | FR-011 no dangling public reference | Direct static serving |
| R13 | **Bootstrap Admin** through a single `IdentityBootstrap` service, exposed first as CLI `portalab admin bootstrap` (refuses if an Admin exists); the Administration first-run wizard (020) later calls the same service | OQ-6 default, one code path | Seeding via SQL |
| R14 | **Event publishing via a kernel `EventPublisher` port** whose envelope mirrors `architecture/EVENT_MODEL.md` (id, type, occurred_at, received_at, source, actor, object, metadata, version); 007 later owns/extends it | Events needed now, model owned by 007 | Private event format |

Resolved: no `NEEDS CLARIFICATION` remains. Product gaps surfaced as risks in plan §14 (registration policy, verification channel, Privacy sequencing).
