# Portalab against OWASP ASVS 5.0, Level 2

## Scope and how to read this

This review measures Portalab against the [OWASP Application Security Verification Standard 5.0](https://owasp.org/www-project-application-security-verification-standard/), Level 2. It was done on 2026-11-13 by reading the code, the tests, the deployment files and the CI pipeline. It is not a penetration test, and nothing was run against a live portal for it.

What is covered: the FastAPI backend, the React frontend, the Docker image and Compose file, and the CI pipeline. What is not covered: the reverse proxy you put in front of Portalab, your identity provider (Authentik or other), the services Portalab connects to (Plex, Jellyfin, the *arr stack...), and the host.

Each table groups related ASVS requirements under their section number (for example 6.2 for password security). Individual requirement numbers are given only where the mapping is unambiguous. Statuses:

- **Met**: the code does what the requirements in that group ask, and the evidence column says where.
- **Partly met**: some of it is done, or it is done but with a default or an exception that matters. The note says what is missing.
- **Not met**: the control does not exist.
- **Not applicable**: the feature the requirement is about does not exist in Portalab.

Paths are relative to the repository root. `src/` stands for `portalab/backend/src/portalab/`, `tests/` for `portalab/backend/tests/`, `web/` for `portalab/frontend/src/`.

A short list of the gaps, in priority order, is at the end of this file.

## V1 Encoding and Sanitization

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 1.1 Architecture: one place decodes and sanitizes user content | Met | `src/capabilities/content/render.py` is the single renderer: Markdown rendered server-side with raw HTML disabled, then sanitized by `nh3` with an allow-list. Terms of use go through the same renderer (`src/modules/privacy/terms/service.py`). | |
| 1.2 Injection prevention: SQL | Met | SQLAlchemy ORM and bound parameters throughout. The few `text(f"...")` statements build DDL from identifiers checked by `_ident` (`src/modules/plugins/db/plugin_db.py`) or from integers. Ruff S608, Bandit B608 and Semgrep run in CI (`.gitlab-ci.yml`, `validate:sast`). Crafted backup manifests with SQL in them are refused (`tests/security/admin/test_crafted_backup.py`). | Keep the identifier checks next to every new DDL statement; they are the only barrier there. |
| 1.2 Injection prevention: OS commands | Met | Only argument lists, never a shell: `asyncio.create_subprocess_exec` in `src/connectors/plex/frames.py` (ffmpeg) and `src/modules/plugins/confined/host.py`; `subprocess.run(list(...))` in `src/app/operations.py`. No `shell=True` in the code base. | |
| 1.2 Injection prevention: HTML/JS in the browser | Met | React escapes by default. The only `dangerouslySetInnerHTML` uses (`web/features/content/SafeHtml.tsx`, `web/features/terms/TermsGate.tsx`, `web/features/auth/LoginForm.tsx`) insert HTML that the server sanitizer produced. Newsletter HTML escapes every text (`src/modules/news/editions/render.py`) and is served with its own restrictive CSP and `sandbox` (`src/modules/news/api/editions.py`). Tests: `tests/security/content/test_markdown_xss_corpus.py`, `tests/security/ui/test_theme_inert.py`. | |
| 1.3 Sanitization: links, images, Mermaid | Met | Link schemes limited to http(s), mailto, relative and `portalab://`; external images blocked unless allowed; Mermaid rendered client-side in strict mode (`render.py`, `SafeHtml.tsx`). | |
| 1.3 Sanitization: SSRF on user-supplied URLs | Met | News sources: http(s) only, every resolved address must be public unless the admin allows the LAN, redirects re-checked, the connection goes to the checked address (no DNS rebinding), size and time limits (`src/modules/news/sources/fetch.py`, `tests/security/news/test_fetch_rebinding.py`). Confined plugins: listed hosts only, same pinned-address approach, no redirects (`src/modules/plugins/confined/network.py`, `tests/integration/plugins/confined/test_network.py`). | Admin-configured service URLs (connectors, AI providers, SMTP) are trusted and may point at the LAN by design. See V13 for the egress allow-list. |
| 1.4 Memory and unmanaged code | Not applicable | Python and TypeScript. Native code is limited to well-known libraries (Pillow, argon2-cffi, cryptography, nh3). | Image decoding is bounded (see V5). |
| 1.5 Safe deserialization | Met | No `pickle`, `yaml.load` or `eval` on untrusted data. XML (RSS, Atom, OPML) is parsed with `defusedxml` (`src/modules/news/sources/parse.py`, `opml.py`). `SecretValue` and `SecretBox` refuse to be pickled (`src/core/secrets.py`). JSON request bodies are parsed by Pydantic models, most with `extra="forbid"`. | |
| Log injection | Met | Logs are one JSON object per line (`src/core/logging.py`); control characters in values are escaped by the encoder. | |

## V2 Validation and Business Logic

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 2.1 Documentation of validation rules and limits | Partly met | Limits are declared as settings with descriptions (`src/modules/identity/settings.py`, `src/modules/privacy/settings.py`, `src/modules/plugins/settings.py`) and visible in the admin configuration. | There is no single document listing the business limits (rates, sizes, quotas, economy bounds). This file is a start. |
| 2.2 Input validation | Met | Pydantic models with bounded lengths and `extra="forbid"` on request schemas (about 216 strict models; for example `src/modules/identity/api/schemas.py`). Validation errors become a generic RFC 9457 problem that lists only field locations and error types (`src/app/main.py`, `validation_handler`). API fuzzing from the OpenAPI contract with Schemathesis (`tests/fuzz/`, CI job `test:api-fuzz`). | Not every model is strict; a few response-only or internal models are not, which is fine. |
| 2.3 Business logic: sequential steps, limits, integrity | Met | Account state machine (`src/modules/identity/domain/state_machine.py`); single-use confirmation tokens bound to principal, permission, resource and payload hash for sensitive AI and automation actions (`src/modules/authz/confirmation/service.py`); append-only economy ledger with `portalab economy verify` (`src/core/append_only.py`, `src/app/cli.py`); no real-money surface (`tests/security/marketplace/test_no_real_money.py`); automations bounded by the owner's permissions (`tests/security/automations/test_permission_bounds.py`). | |
| 2.3 Concurrency in business flows | Met | Row locks (`with_for_update`) on throttle, OIDC state and account rows; one sign-in attempt at a time per key (`src/modules/identity/services/auth.py`, `tests/security/identity/test_throttle.py::test_a_burst_sent_at_once_is_throttled_like_one_after_the_other`). | |
| 2.4 Anti-automation | Met | Per-IP, per-session and per-address sign-in rate limits, a separate budget for images (`src/app/security.py`, `SecurityMiddleware`); intrusion guard that blocks sessions, accounts and addresses that probe forbidden or attack-shaped paths (`src/modules/identity/guard/guard.py`). Tests: `tests/security/test_headers_limits.py`, `tests/unit/identity/test_intrusion_guard.py`, `tests/integration/identity/test_guard_http.py`. | Limiters live in process memory (single node). Guard blocks are stored in the database and shared. |

## V3 Web Frontend Security

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 3.2 Unintended content interpretation | Met | `X-Content-Type-Options: nosniff` on every response (`src/app/security.py`, `SECURITY_HEADERS`); user files are served with their sniffed type and non-images as `Content-Disposition: attachment` (`src/modules/support/attachments/service.py`). | |
| 3.3 Cookie setup | Partly met | Session cookie `__Host-portalab_session`: `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/` (`src/modules/identity/api/middleware.py`). CSRF cookie `__Host-portalab_csrf` is readable by scripts by design. Test: `tests/security/identity/test_session_cookie_csrf.py::test_cookie_flags`. | Deliberate exception: a portal reached in plain HTTP from a private address gets `portalab_session` without `Secure` and without the prefix (#395). That cookie is ignored over HTTPS (`test_a_plain_cookie_never_counts_over_https`). It is a reasonable trade-off for a LAN, but it means session cookies travel in clear there. |
| 3.4 Browser security headers | Met | CSP with `default-src 'self'`, no `unsafe-inline` or `unsafe-eval` for scripts or styles, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, `frame-ancestors 'none'`; HSTS one year with `includeSubDomains`; `X-Frame-Options: DENY`; `Referrer-Policy: no-referrer`; `Permissions-Policy` denying camera, microphone, geolocation, payment; COOP `same-origin`; CORP `same-origin` on JSON answers (`src/app/security.py`). Tests: `test_security_headers_on_every_response`, `test_an_answer_in_json_cannot_be_embedded_by_another_site`. | CSP has no reporting endpoint, so violations go unnoticed. HSTS has no `preload` (fine for self-hosting). |
| 3.5 Browser origin separation (CSRF, CORS) | Met | Double-submit CSRF token derived from the session token, checked on every unsafe method of a cookie-authenticated request (`middleware.py`, `check_csrf`; `sessions.py`, `csrf_token_for`). No CORS middleware, so no cross-origin read is allowed. Login takes a JSON body, which a cross-site form cannot send without a preflight. Test: `test_unsafe_methods_need_the_csrf_header`. | No `Sec-Fetch-Site` / `Sec-Fetch-Mode` checks as a second layer. |
| 3.5 Isolation of third-party code in the page | Met | Plugin views, visual packs and pack navigation run in `sandbox="allow-scripts"` iframes without `allow-same-origin`, so they get an opaque origin with no cookies and no access to the portal (`web/features/plugins/views/PluginView.tsx`, `web/features/dashboard/widgets/pack/PackFrame.tsx`, `web/shell/nav/PackNav.tsx`); messages are accepted only from the frame's own window. Tests: `tests/security/plugins/test_ui_bounds.py`, `tests/integration/plugins/confined/test_views.py`. | |
| 3.6 External resource integrity | Partly met | Everything is served from the portal itself except the Google Cast SDK (`web/features/media/player/cast.ts`), limited to three gstatic folders in the CSP. | The Cast loader cannot carry Subresource Integrity (Google changes it). It is a trusted third-party script running with the portal's origin. Worth a sentence in the deployment docs. |
| 3.7 Other: open redirects, external links | Met | The OIDC `next` target is restricted to local paths (`src/modules/identity/services/oidc.py`, `safe_next`). External links get `rel="noopener noreferrer nofollow"`. Source maps are not shipped (`portalab/frontend/vite.config.ts`). | |

## V4 API and Web Service

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 4.1 Generic web service security | Met | All errors are RFC 9457 `application/problem+json` with a correlation id (`src/core/errors.py`). Unknown methods answer 405. `X-Forwarded-For` / `X-Forwarded-Proto` are believed only from `TRUSTED_PROXIES` (`src/app/cli.py`, uvicorn `forwarded_allow_ips`; `src/app/security.py`, `behind_untrusted_proxy`). OpenAPI and docs endpoints are disabled in the running app (`src/app/main.py`). | HTTP to HTTPS redirection is left to the reverse proxy (documented in `portalab/docs/internet-exposure.md`). |
| 4.1 Default deny on routes | Met | An app-wide dependency refuses any route that declares neither `public` nor a permission (`src/app/security.py`, `enforce_default_deny`); without a session only a short allow-list answers (`ANONYMOUS_PATHS`). Tests: `tests/security/authz/test_permission_matrix.py::test_every_route_is_protected_or_allow_listed`, `tests/security/shell/test_no_enumeration.py`. | |
| 4.2 HTTP message structure | Partly met | Request body cap (10 MiB default, 413), checked both on `Content-Length` and while streaming (`SecurityMiddleware`); test `test_body_size_cap`. Uvicorn with h11 parses requests. | Request smuggling protection depends on the reverse proxy and uvicorn; nothing Portalab-specific. The first-run import route accepts up to 200 GiB, but only before setup and only from setup networks. |
| 4.3 GraphQL | Not applicable | No GraphQL. | |
| 4.4 WebSocket | Not applicable | Live updates use Server-Sent Events over the normal authenticated HTTP stack (`src/app/stream.py`). | |

## V5 File Handling

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 5.1 Documentation of accepted files | Partly met | Types and sizes are in code (`src/core/uploads.py`: image and document allow-lists, 10 MiB default, 40 Mpx; avatars 2 MiB in `src/modules/identity/api/profile.py`). | Not written down for administrators. |
| 5.2 Upload content checks | Met | Type from magic bytes, never from the client; allow-listed types only; images decoded with an allow-listed set of decoders, re-encoded (EXIF/GPS stripped), decompression bombs refused (`src/core/uploads.py`). Used by content, support attachments, avatars, site images, news images. Tests: `tests/unit/identity/test_avatar_validation.py`. | |
| 5.2 Archives (plugins, visual packs, backups) | Met | Plugin zips: file count and total size caps, absolute paths and `..` refused, SHA-256 of the content verified on every load (`src/modules/plugins/store/package.py`). Visual packs and backups have their own crafted-archive tests (`tests/security/visuals/test_archives.py`, `tests/security/plugins/test_package_archives.py`, `tests/security/admin/test_crafted_backup.py`). | The scrypt cost parameters of a backup archive are read from the archive header without an upper bound (`src/modules/administration/backup/crypto.py`); a crafted file can ask for a very expensive key derivation. |
| 5.2 Malware scanning | Not met | No antivirus scan of uploaded documents (PDF or text attachments in support tickets). | Low risk for a small community; can be delegated to a ClamAV sidecar if needed. |
| 5.3 File storage | Met | Blobs are content-addressed (`<namespace>/<sha256>`, strict regex), stored outside the web root and never served statically, only through authenticated routes (`src/core/blobstore.py`). File names are sanitized (`sanitize_filename`). | |
| 5.4 File download | Met | `Content-Disposition: attachment` for non-image files, `nosniff` on file responses (`src/modules/support/attachments/service.py`, `src/modules/media/api/books.py`, `src/modules/authz/api/audit.py`). | |

## V6 Authentication

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 6.1 Documentation | Partly met | Throttle and guard behaviour are described in the module docstrings and the settings descriptions. `portalab/docs/internet-exposure.md` covers proxies and setup networks. | No document listing the authentication pathways (local password, OIDC, verification tokens, casting tickets) and the controls on each. |
| 6.2 Password length and handling | Met | Minimum 12, maximum 256 characters by default (bounded 8-128 / 16-1024), no composition rules, no truncation, blank passwords refused (`src/modules/identity/services/credentials.py`, `src/modules/identity/settings.py`). Password managers and paste work (`autocomplete` attributes in `web/features/auth/LoginForm.tsx`, `AccountPage.tsx`). Change requires the current password (`src/modules/identity/services/password.py`). | |
| 6.2 Common and breached password checks | Not met | `check_password_policy` checks length only. | No check against a list of common passwords and no breached-password check (for example a local k-anonymity list or the HIBP range API). Both are ASVS Level 1 and Level 2 requirements respectively. |
| 6.3 Brute force and enumeration | Partly met | Progressive delay per (normalized login, /24 or /48 prefix), capped at 15 minutes, never a hard lockout (`src/modules/identity/services/throttle.py`); 30 sign-in POSTs per minute per address (`src/app/security.py`); identical answers and identical Argon2 work for unknown login, wrong password and any account state (`src/modules/identity/services/auth.py`, `credentials.py`). Tests: `tests/security/identity/test_login_enumeration.py`, `test_throttle.py`. | The throttle key includes the client network, so an attacker spread over many networks is throttled per network, not per account. There is no account-wide ceiling. |
| 6.3 Multi-factor authentication (6.3.3) | Not met | No TOTP, WebAuthn or other second factor for local accounts. The `AuthProvider` port mentions MFA as future work (`auth.py`). | Members who sign in through OIDC get whatever MFA the identity provider enforces. Local accounts, including the Admin, have a password only. |
| 6.3 Default accounts | Met | No default account. The first Admin is created by the arrival wizard, answered only before setup and only from setup networks (`src/app/security.py`, `SETUP_PATHS`), or by `portalab admin bootstrap`. | See V13 about how "local network" is judged behind Docker. |
| 6.3 Notification of authentication changes | Not met | Only administrators are notified, and only of intrusion-guard blocks (`src/app/main.py`, `security_alert`). | A member is not told when their password is changed (by themselves or by an administrator), when their account is blocked, when sign-in is throttled, or when an SSO identity is linked to their account. |
| 6.4 Factor lifecycle and recovery | Met | Verification tokens are 256-bit, stored hashed, single use, expire after 72 hours, and travel in the URL fragment (`src/modules/identity/services/registration.py`, `src/modules/notifications/channels/email.py`). No security questions or hints. There is no self-service reset: an administrator sets a new password after re-entering their own, and every session of the member ends (`password.py`, `set_for`). | |
| 6.5 to 6.7 MFA, out-of-band, cryptographic authenticators | Not applicable | None implemented (see 6.3). | |
| 6.8 Identity provider | Partly met | Users are keyed by (issuer, subject) (`src/modules/identity/services/oidc.py`, `ExternalIdentity`). ID token signature, issuer, audience, expiry and nonce are checked. | Account linking by e-mail treats a missing `email_verified` claim as verified for non-Admin accounts. If the provider lets users set an unverified e-mail and omits the claim, a provider user can take over the portal account with that e-mail. The Admin is protected (the claim must be `true`). No check of `acr` / `amr`, so Portalab cannot require that the provider used MFA. |

## V7 Session Management

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 7.1 Documentation | Partly met | Timeouts are declared settings (`identity.sessionIdleMinutes`, `identity.sessionAbsoluteHours`). | The rationale for the defaults is not written down. |
| 7.2 Fundamental session security | Met | Opaque 256-bit token from `secrets.token_urlsafe`, only its SHA-256 stored, checked server-side on every request; account must be Active (`src/modules/identity/services/sessions.py`, `middleware.py`). A new token on every sign-in and any presented session is revoked ("rotated") (`auth.py`, `open_session`). Database unreachable fails closed with 503. Tests: `test_login_rotates_any_presented_session`, `test_garbage_cookie_is_anonymous`. | |
| 7.3 Session timeout | Partly met | Sliding idle timeout and absolute lifetime, both enforced server-side (`sessions.py`, `_expiry`). | Defaults are long: 7 days idle, 30 days absolute, the same for the Admin as for members. Consider shorter defaults, or a shorter limit for holders of administrative permissions. |
| 7.4 Session termination | Met | Logout revokes server-side and clears cookies (`auth.py`, `sign_out`; `test_logout_revokes_and_clears_cookies`). Suspension, deletion, guard blocks and admin password resets revoke every session; a password change revokes the other sessions (`admin_ops.py`, `deletion.py`, `password.py`, `src/app/main.py`). | Logout does not end the identity provider session (no RP-initiated or back-channel logout). |
| 7.5 Defenses against session abuse | Partly met | Re-authentication with the password before account deletion, cancelling deletion, Admin transfer, an administrator setting a member's password, and system reset (`src/modules/identity/api/lifecycle.py`, `admin.py`, `src/modules/administration/api/backups.py`). | Members cannot see their active sessions or end one remotely. Several sensitive admin actions do not ask for re-authentication: granting roles and permissions, changing the OIDC client secret, allowing unconfined plugins, switching the egress allow-list off, suspending a member. |
| 7.6 Federated re-authentication | Not met | `reauthenticate` checks a local password. | Members who only sign in through OIDC have no local password, so they cannot pass the step-up check at all (for example to delete their account). No `prompt=login` / `max_age` round trip to the provider. |
| Media and casting tickets | Partly met | HMAC-signed, time-limited tickets for streams; player tickets are bound to the member (`src/modules/media/player/tickets.py`). | Remote (casting) tickets are bearer URLs valid 8 hours and player tickets 12 hours; neither is revoked when the member signs out or is suspended. |

## V8 Authorization

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 8.1 Documentation | Met | Permission catalog with descriptions per module (`src/modules/*/permissions.py`), role and grant model documented for administrators (`docs/admin/members-and-roles.md`). | |
| 8.2 General design: default deny, server-side, per request | Met | Engine decides deny by default: unknown or disabled permissions never grant, explicit deny wins over everything including the Admin, reserved permissions are Admin-only, delegated channels (AI, automation, plugin) act with at most the user's rights (`src/modules/authz/engine/engine.py`). Decisions read the current database state on every request; the only cache is a per-request memo (`src/core/authorization.py`), so revoked rights take effect immediately. | |
| 8.2 Object and field level (IDOR, BOLA, BOPLA) | Met | `require(..., resource=...)` with optional `hide_existence` (404 instead of 403); visibility applied after authorization (`src/core/authorization.py`, `src/core/visibility_port.py`). Tests per module: `tests/security/content/test_authz_idor.py`, `tests/security/community/test_profile_visibility.py`, `tests/security/search/test_no_leak.py`, `tests/security/marketplace/test_projects_authz.py`, `tests/security/authz/test_visible_matches_decisions.py`. | |
| 8.3 Operation-level authorization and permission matrix | Met | Matrix tests for anonymous, plain user and privileged callers on every route (`tests/security/authz/test_permission_matrix.py`, `tests/security/identity/test_permission_matrix.py`, `tests/security/connectors/test_permission_matrix.py`, `tests/security/events/test_permission_matrix_and_logs.py`); escalation and reserved permissions (`tests/security/authz/test_reserved_and_escalation.py`). | |
| 8.3 Audit of sensitive decisions | Met | Sensitive permissions audit both allow and deny, and fail closed when the audit cannot be written (`engine.py`, `_audit`; `src/modules/authz/audit/store.py`). | |
| 8.4 Administrative interfaces | Partly met | Admin routes go through the same engine; probing them counts double in the intrusion guard; sole-Admin protections (`tests/security/admin/test_single_admin_sensitive.py`). | Only some admin actions require re-authentication (see 7.5). Multi-tenancy is not applicable. |

## V9 Self-contained Tokens

Portalab does not use JWTs for its own sessions. Self-contained tokens appear in two places: the ID token received from the OIDC provider, and the HMAC-signed media tickets Portalab issues.

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 9.1 Source and integrity: ID tokens | Met | Signature checked against the provider's JWKS, key chosen by `kid`, algorithms limited to RS256, ES256, PS256 (never `none` or HMAC) (`src/modules/identity/services/oidc.py`, `_claims`). Test: `tests/integration/identity/test_oidc.py::test_a_state_is_used_once_and_a_forged_token_refused`. | |
| 9.1 Source and integrity: media tickets | Met | HMAC-SHA256 checked with a constant-time comparison before the payload is parsed; keys derived per purpose from `SECRET_KEY` (player, remote, statistics) (`src/modules/media/player/tickets.py`, `src/app/wiring.py`). | |
| 9.2 Token content: expiry, audience, purpose | Partly met | ID token: `exp`, `iat`, `sub` required, issuer and audience checked, 60 s leeway, nonce checked. Tickets: expiry checked, player tickets bound to the member, remote tickets use a separate key. | Ticket payloads are readable base64 JSON (member id, service id, item) in URLs, so they end up in proxy logs. Remote tickets have no audience other than "whoever holds the URL". |

## V10 OAuth and OIDC

Portalab is an OIDC relying party (a confidential OAuth client). It is not an authorization server, a resource server or an OpenID provider.

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 10.1 Generic: tokens kept server-side | Met | The code exchange happens server-side with client authentication; the access token and ID token are never sent to the browser or stored; only (issuer, subject) is kept (`oidc.py`). | |
| 10.2 OAuth client: PKCE, state, browser binding | Met | Authorization code flow with PKCE S256, 256-bit `state` and `nonce`, stored server-side for 10 minutes and used once; the callback is accepted only in the browser that started it (cookie `__Host-portalab_sso` holding a hash of the state) (`oidc.py`, `src/modules/identity/api/auth.py`). Tests: `test_the_way_back_is_refused_in_another_browser`. | Single provider, so authorization server mix-up does not apply. |
| 10.2 Redirect URI and discovery | Partly met | `redirect_uri` is built from the request (`request.url_for`). | The redirect URI depends on the `Host` header; the provider's registered redirect list is what keeps it safe. The discovery document's `issuer` is not compared with the configured issuer, and `https` is not required for the issuer, token endpoint or JWKS URI. |
| 10.3, 10.4, 10.6, 10.7 Resource server, authorization server, OpenID provider, consent | Not applicable | | |
| 10.5 OIDC client | Partly met | Nonce, audience, issuer and expiry are verified; users identified by issuer and `sub`. | E-mail linking accepts a missing `email_verified` (see 6.8). `azp` is not checked when `aud` holds several values. No back-channel logout. |

## V11 Cryptography

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 11.1 Inventory and key management | Partly met | One application key (`SECRET_KEY_FILE`, at least 32 bytes, refused inline) from which purpose-specific keys are derived with HKDF or HMAC (`src/core/settings.py`, `src/core/secrets.py`, `src/app/wiring.py`). After a restore, stored secrets are re-encrypted with the new portal's key (`src/modules/administration/config/rekey.py`, `src/modules/connectors/services/rekey.py`, `src/modules/plugins/rekey.py`). | No written crypto inventory or key management policy. I found no operator command to rotate `SECRET_KEY` in place on a running portal. |
| 11.2 Implementation | Met | Only vetted libraries: `cryptography` (AES-GCM, HKDF, scrypt), `argon2-cffi`, `PyJWT`, `hmac.compare_digest` for every token comparison. No home-made primitives. | |
| 11.3 Encryption algorithms | Met | Secrets at rest: AES-256-GCM, random 96-bit nonce per record, context bound as associated data so a ciphertext cannot be moved to another record (`src/core/secrets.py`; `tests/unit/test_secretbox.py`). Backups: scrypt-derived AES-256-GCM, chunked with counter and last-chunk flag in the nonce, header authenticated (`src/modules/administration/backup/crypto.py`; `tests/unit/admin/test_backup_crypto.py`). | The operator command `portalab backup` writes a plain `pg_dump` plus a tarball (`src/app/operations.py`); only `portalab archive` and the admin UI backups are encrypted. |
| 11.4 Hashing and password storage | Met | Argon2id, t=3, m=64 MiB, p=4 by default, per-hash salt, rehash on parameter change, at most four hashes at once (`credentials.py`). Session and verification tokens stored as SHA-256 (they are 256-bit random, so a fast hash is appropriate). | |
| 11.5 Random values | Met | `secrets` and `os.urandom` for every token, nonce and key. The only `random.random()` is retry jitter (`src/capabilities/isolation.py`). | |
| 11.6, 11.7 Public key crypto, in-use data | Not applicable | Public keys only verify ID tokens (V9). | |

## V12 Secure Communication

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 12.1, 12.2 TLS for browsers | Partly met | Portalab serves HTTP on port 8080 and expects a reverse proxy to terminate TLS; this is documented with concrete proxy settings (`docs/configuration.md`, `portalab/docs/internet-exposure.md`). HSTS is sent. | TLS configuration (versions, ciphers) is entirely the proxy's job. Plain HTTP is accepted from private addresses on purpose (#395). |
| 12.3 Service to service | Partly met | Outbound HTTP uses `httpx` with certificate verification on by default; per-connector `verify_tls` can be turned off by an administrator (`src/capabilities/connector_http.py`, `src/modules/connectors/http/client.py`). The database stays on the Compose network, not published. | SMTP TLS is off by default (`src/modules/notifications/settings.py`, `smtp_tls = False`). The off-site audit copy over syslog uses plain TCP (`src/modules/authz/audit/offsite.py`). The OIDC issuer may be `http://`. |

## V13 Configuration

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 13.1 Configuration documentation | Met | Bootstrap settings, proxies, health and setup networks documented (`docs/configuration.md`, `portalab/docs/internet-exposure.md`, `SECURITY.md`). | |
| 13.2 Backend communication and least privilege | Partly met | Containers run read-only, `cap_drop: ALL`, `no-new-privileges`, non-root UID 10001 (`portalab/deploy/docker-compose.yml`, `portalab/deploy/Dockerfile`). Plugins get their own PostgreSQL role with no rights on core schemas and a statement timeout (`src/modules/plugins/db/plugin_db.py`, `tests/security/plugins/test_role_isolation.py`). | The default Compose file creates the database with `POSTGRES_USER: portalab`, which makes the application's role a PostgreSQL superuser. Plugin roles need `CREATEROLE` and restore needs superuser (`src/modules/administration/backup/archive.py`), but day-to-day serving does not. A flaw that reaches SQL would get superuser rights (including `COPY ... TO PROGRAM` in the database container). |
| 13.2 Outbound allow-list | Partly met | Every `httpx` client passes the egress hook (`src/core/egress.py`; `tests/unit/security/test_egress.py`). | The allow-list is off by default (`src/modules/privacy/settings.py`, `egress_enabled = False`). News sources add their own host to the declared list when fetched (`src/modules/news/sources/fetch.py`, `EGRESS.allow`), so an editor-supplied feed URL is never refused by it (the public-address check still applies). |
| 13.3 Secret management | Met | Secrets come from files (`*_FILE`), are never accepted inline for the key, are wrapped in `SecretValue` and registered for log redaction (`src/core/settings.py`, `src/core/secrets.py`). Sensitive settings are encrypted with the application key and never returned by the API (`src/modules/administration/config/service.py`). The init container creates secrets with mode 600 and refuses file systems that cannot keep permissions. gitleaks in CI. | |
| 13.4 Unintended information leakage | Partly met | No API docs in production, no source maps, generic 500 answers with a correlation id (`src/core/errors.py`, `internal_error_problem`), `/metrics`, `/healthz`, `/readyz` answer only to health networks (`src/app/security.py`). Anonymous callers get the same 401 everywhere (`tests/security/shell/test_no_enumeration.py`). | Uvicorn sends `server: uvicorn` (`src/app/cli.py` does not pass `server_header=False`). "Local network" is judged by source address: with Docker's userland proxy, internet clients can appear as a private gateway address, which would open the arrival wizard (before setup) and the plain-HTTP cookie fallback to them. |

## V14 Data Protection

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 14.1 Data classification | Met | Columns holding personal data declare their class (`src/core/privacy_registry.py`); a CI test fails on unclassified columns named like personal data (`tests/unit/test_pii_registry.py`). | |
| 14.2 General data protection: minimization, retention, erasure | Met | IP addresses truncated to /24 or /48 and user agents summarized on sessions (`sessions.py`); retention engine applies configured windows per target (`src/modules/privacy/retention/engine.py`; `tests/integration/privacy/test_retention.py`); export and deletion with a grace period (`src/modules/identity/services/export.py`, `deletion.py`, `src/modules/identity/jobs/finalize_deletion.py`). Personal data kept out of logs and metrics (`tests/security/privacy/test_no_pii_in_logs.py`, `tests/security/observability/test_permissions_privacy.py`). | |
| 14.2 Sensitive data in URLs | Partly met | Session tokens never travel in URLs; verification tokens use the URL fragment. | Casting tickets and newsletter picture tokens are in URL paths by design (devices and mail clients have no session). |
| 14.2 / 14.3 Caching of authenticated responses | Partly met | Many sensitive routes set `Cache-Control: no-store` or `private` (player, books, AI, games, stream, SPA shell). | There is no default `Cache-Control: no-store` on API JSON responses (`src/app/security.py`, `SECURITY_HEADERS`). |
| 14.3 Client-side data | Partly met | No token in `localStorage` or `sessionStorage`; browser storage holds preferences, reading positions and cached translations only. | Nothing is cleared at logout (no `Clear-Site-Data`), so the next user of a shared browser sees the previous member's reading positions and preferences. |

## V15 Secure Coding and Architecture

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 15.1 Documentation, remediation policy | Partly met | `SECURITY.md` lists the checks and the reporting channel; Renovate applies security fixes without delay and other updates after 7 days (`renovate.json`). | No stated time frame for fixing vulnerable dependencies by severity. |
| 15.2 Dependencies and supply chain | Partly met | `uv.lock` and `package-lock.json` installed frozen; pip-audit, npm audit, Trivy (config and image), Hadolint, gitleaks in CI; CycloneDX SBOM per release; image signing with cosign when a key is set (`.gitlab-ci.yml`, `portalab/deploy/ci/sign-image.sh`). | `portalab/deploy/Dockerfile` uses tags, not digests (`node:22-alpine`, `python:3.12-slim`, `uv:0.9`), even though `renovate.json` asks for digest pinning. Image signing "never blocks the release". The Compose file defaults to the `latest` tag. |
| 15.2 Module boundaries | Met | import-linter contracts in CI keep modules talking through capabilities (`validate:import-linter`). | |
| 15.2 Third-party code: plugins | Partly met | Confined plugins run in a separate process with an empty environment, Landlock (files and TCP) and seccomp, resource limits, no sockets, network only through the portal to admin-approved hosts, their own database role, and views in an opaque-origin iframe (`src/core/confinement.py`, `src/modules/plugins/confined/host.py`, `tests/unit/plugins/confined/test_kernel.py`, `tests/integration/plugins/confined/`). Installing requires the Admin's review by default. A static import scanner checks plugin code (`tests/security/plugins/test_import_scanner.py`). | No publisher signature: integrity is a SHA-256 taken at install time. `plugins.unconfined` defaults to `existing`, so plugins installed before confinement keep running inside the portal process. `allowWeakConfinement` lets plugins run where the kernel cannot confine them (off by default). |
| 15.3 Defensive coding | Met | Typed code (mypy strict in CI), Bandit, Semgrep (OWASP Top 10 rules), Ruff security rules; bounded regexes (a ReDoS in the log redactor was fixed, see `src/core/logging.py`); AI prompt-injection corpus (`tests/security/ai/test_injection_corpus.py`). | |
| 15.4 Safe concurrency | Met | Row locks and per-key async locks for throttling, OIDC state, confirmations; bounded Argon2 concurrency; per-request authorization memo instead of a shared cache (`src/core/authorization.py`). | |
| Dynamic testing | Met | OWASP ZAP baseline signed in as the Admin against the built image (`portalab/deploy/ci/dast.sh`, `zap-rules.conf`); Schemathesis fuzzing (`tests/fuzz/`). | |

## V16 Security Logging and Error Handling

| Area | Status | Evidence | Gap / note |
| --- | --- | --- | --- |
| 16.1 Logging documentation | Partly met | Log format and redaction described in `src/core/logging.py`; audit retention is a setting (`privacy.retention.auditMonths`). | No document listing which security events are logged where (application log, audit log, domain events). |
| 16.2 General logging | Met | Structured JSON, UTC timestamps, a correlation id per request echoed in `X-Correlation-Id` and in error answers (`src/app/main.py`, `src/core/logging.py`). | |
| 16.2 Secrets and personal data kept out of logs | Met | Redaction of secret-looking keys, URL credentials, bearer tokens and every registered secret value (`src/core/logging.py`); failed sign-ins logged with a hashed identifier and network prefix (`auth.py`). Tests: `tests/unit/test_logging.py`, `tests/security/identity/test_no_secrets_in_logs.py`, `tests/security/ai/test_secrets_audit.py`, `tests/security/automations/test_secrets_privacy.py`. | |
| 16.3 Security events | Partly met | Audited: failed sign-ins, sign-outs, password changes and admin resets, sensitive authorization decisions (allow and deny), intrusion-guard blocks, account lifecycle. Logged and counted: egress refusals (`src/core/egress.py`), untrusted proxy warning. | Successful sign-ins are domain events (`user.signed_in`), not audit entries. Failed OIDC callbacks are swallowed without a log line or audit entry (`src/modules/identity/api/auth.py`, `oidc_callback`). CSRF failures and validation failures are not logged as security events (they only add guard points). |
| 16.4 Log protection | Met | Audit entries are append-only with hash-chained checkpoints and `portalab audit verify` (`src/modules/authz/audit/checkpoints.py`, `verify.py`; `tests/integration/audit/test_checkpoints_verify.py`); optional off-site copy to a file or syslog (`offsite.py`); audit read access is a permission (`tests/security/audit/test_audit_query.py`). | Syslog copy is plain TCP (see V12). |
| 16.5 Error handling | Met | Expected errors become RFC 9457 problems with stable codes; unexpected ones a generic 500 with a correlation id and nothing about the exception (`src/core/errors.py`, `src/app/main.py`). Fails closed: database unavailable during authentication gives 503, a sensitive action whose audit write fails is refused (`middleware.py`, `engine.py`). | |

## V17 WebRTC

Not applicable. Portalab has no WebRTC, TURN or media signaling. The `Permissions-Policy` header denies camera and microphone. Casting uses the Google Cast SDK and HTTP streams.

## Gaps, by priority

Priorities weigh impact against how a typical Portalab is deployed: a small community, often on a LAN or behind a reverse proxy with an identity provider.

### High

1. **No second factor for local accounts.** The Admin and every local member sign in with a password only. Add TOTP and preferably WebAuthn behind the existing `AuthProvider` port, and offer to require it for holders of administrative permissions. Files: `src/modules/identity/services/auth.py`, `src/modules/identity/api/auth.py`, `src/modules/identity/models/`.
2. **No common or breached password check.** Add a bundled list of common passwords (at least the top 10,000) and an optional breached-password check (local k-anonymity list, or the HIBP range API through the egress allow-list). File: `src/modules/identity/services/credentials.py` (`check_password_policy`).
3. **The application connects to PostgreSQL as a superuser in the default Compose file.** Create a runtime role without `SUPERUSER` (with `CREATEROLE` only if plugins need it), and use the superuser only for `migrate` and restore. Files: `portalab/deploy/docker-compose.yml`, `src/modules/plugins/db/plugin_db.py`, `src/modules/administration/backup/archive.py`, `docs/configuration.md`.
4. **OIDC e-mail linking accepts a missing `email_verified`.** Link an existing non-Admin account by e-mail only when the claim is `true`, or make the lenient behaviour an explicit setting for providers known to omit it. Also compare the discovery `issuer` with the configured issuer and require `https` for the issuer and its endpoints. File: `src/modules/identity/services/oidc.py` (`_member`, `_metadata`, `_claims`).

### Medium

5. **Members are not told about security changes to their account.** Notify on password change, password set by an administrator, account blocked by the intrusion guard, sign-in throttled, and a new SSO identity linked. Files: `src/modules/identity/services/password.py`, `src/app/main.py` (`security_alert`), `src/modules/identity/services/oidc.py`, notification templates.
6. **No view of active sessions.** Let members list their sessions (created, last seen, network prefix, user agent summary are already stored) and end one or all others. Files: `src/modules/identity/services/sessions.py`, `src/modules/identity/api/profile.py`, `web/features/auth/AccountPage.tsx`.
7. **Step-up re-authentication is incomplete.** OIDC-only members cannot pass it at all; add a provider round trip with `prompt=login` and `max_age`. Require it for granting roles and permissions, changing the OIDC client secret, allowing unconfined or weakly confined plugins, and disabling the egress allow-list. Files: `src/modules/identity/services/auth.py` (`reauthenticate`), `src/modules/authz/api/routes.py`, `src/modules/administration/api/routes.py`, `src/modules/plugins/api/admin.py`.
8. **Long default session lifetimes.** 7 days idle and 30 days absolute for everyone. Consider shorter defaults, a shorter limit for administrative sessions, and write the rationale down. File: `src/modules/identity/settings.py`.
9. **Security event logging gaps.** Audit successful sign-ins; log and audit failed OIDC callbacks with a reason (the `SignOnFailed.reason` already exists); log CSRF failures. Files: `src/modules/identity/services/auth.py`, `src/modules/identity/api/auth.py`.
10. **Plain-text transports by default.** Turn SMTP TLS on by default (or warn in the admin UI when it is off), add TLS to the syslog off-site copy, refuse an `http://` OIDC issuer outside private addresses. Files: `src/modules/notifications/settings.py`, `src/modules/authz/audit/offsite.py`, `src/modules/identity/services/oidc.py`.
11. **No caching and client-storage hygiene on logout.** Send `Cache-Control: no-store` by default on API JSON responses, and `Clear-Site-Data: "storage"` (or a targeted client-side cleanup) on logout. Files: `src/app/security.py`, `src/modules/identity/api/auth.py` (`logout`), `web/shell/preferences.ts`.
12. **Credential stuffing across networks.** Add an account-wide ceiling (for example a slower delay once failures from several networks add up) on top of the per-network throttle, and notify the member (item 5). File: `src/modules/identity/services/throttle.py`.
13. **Egress allow-list is weaker than it looks.** It is off by default, and news sources add their own hosts to it. Either keep feed hosts out of the declared set when the allow-list is on, or document that news sources bypass it. Files: `src/core/egress.py`, `src/modules/news/sources/fetch.py`, `src/modules/privacy/settings.py`.
14. **Media tickets outlive the session.** Shorten remote ticket lifetimes, or keep a revocation list (per member, checked on each request) filled at logout and suspension. File: `src/modules/media/player/tickets.py`.

### Low

15. **Base images not pinned by digest.** Pin `node`, `python` and `uv` in the Dockerfile (Renovate will keep them current), stop defaulting to `latest` in Compose, and decide whether an unsigned image may be released. Files: `portalab/deploy/Dockerfile`, `portalab/deploy/docker-compose.yml`, `.gitlab-ci.yml`.
16. **Unbounded scrypt parameters in backup headers.** Refuse `n`, `r`, `p` above what Portalab itself writes (or a fixed ceiling) before deriving the key. File: `src/modules/administration/backup/crypto.py`.
17. **Operator backups are not encrypted.** `portalab backup` writes a plain dump and tarball. Encrypt it like `portalab archive`, or document that it must be stored encrypted. File: `src/app/operations.py`.
18. **Plugins have no publisher signature, and legacy in-process plugins keep running.** Consider signed packages, and move the `plugins.unconfined` default from `existing` to `refuse` in a future major release. Files: `src/modules/plugins/store/package.py`, `src/modules/plugins/settings.py`.
19. **"Local network" is judged by source address.** Behind Docker's userland proxy every client may look private. Document it next to `SETUP_NETWORKS` and the plain-HTTP fallback, and suggest checking the `portalab doctor` output after deployment. Files: `src/modules/identity/api/middleware.py` (`plain_http`), `src/app/security.py`, `portalab/docs/internet-exposure.md`.
20. **Host header not validated.** The OIDC `redirect_uri` is built from the request. Add a configured public URL or Starlette's `TrustedHostMiddleware`. Files: `src/app/main.py`, `src/modules/identity/api/auth.py`.
21. **Small hardening items.** Disable the uvicorn `server` header (`src/app/cli.py`, `server_header=False`); add a CSP reporting endpoint; check `Sec-Fetch-Site` on unsafe methods as a second CSRF layer (`src/app/security.py`); mention the Cast SDK as the one third-party script in the deployment docs.
22. **No malware scan of uploaded documents.** Optional ClamAV hook for support attachments. File: `src/modules/support/attachments/service.py`.
23. **Missing documentation.** A crypto inventory and key rotation procedure (including an in-place `SECRET_KEY` rotation command, which I did not find), the list of authentication pathways and their controls, the list of security events and where they are recorded, and a remediation time frame per severity in `SECURITY.md`. This file can serve as the starting point.
