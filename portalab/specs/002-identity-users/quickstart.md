# Quickstart — Identity & Users (target behaviour)

1. `uv run portalab migrate` creates schema `identity`.
2. `uv run portalab admin bootstrap --login <login> [--password-file <file>]` creates the sole Admin (second run refuses; needs the authorization module of spec 003 to be installed, otherwise it fails closed).
3. Register → verify → login via the API; `GET /me` returns the principal; logout revokes the session.
4. Suspend a user as Admin: their session stops working on the next request; an audit record exists.
5. Request deletion, cancel within the grace period → state restored; let `due_at` pass → worker tombstones the user, ledger/history rows remain referencing the same `id`.
6. Run the security suite: enumeration, timing, CSRF, cookie flags, throttling, session fixation, sole-Admin concurrency.
