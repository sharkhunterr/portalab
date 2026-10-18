# Quickstart: Confined Extensions — validation scenarios

Each scenario names the success criterion it proves and the suite that automates it. Run from `backend/` and
`frontend/` as in the repository's CLAUDE.md (integration tests need the disposable PostgreSQL).

## 1. The kernel confines a plugin (SC-001)

```bash
uv run portalab plugin runtime          # landlock_abi ≥ 4, seccomp yes, ok yes
uv run pytest tests/security/plugins/test_confinement.py
```

The probe plugin (`tests/fixtures/plugins/probe`) is enabled with storage only; the test asks it, one by one,
to: read a core table, leave its role, open a socket, reach the database port, reach an unlisted host and a
private address, read the application key file and `/proc/1/environ`, read another plugin's scratch folder,
write its own code, fork, exec, signal its parent, exceed its memory, exceed its time, flood its live topic
and its storage. **Expected**: every attempt fails, one `plugins.attempts` row each, nothing outside the
plugin changed (core row counts and files hashed before/after), quarantine after the threshold.

## 2. The portal keeps working while a plugin misbehaves (SC-002)

`tests/integration/plugins/test_containment.py` runs the API journeys (sign-in, media, wiki, shop list,
notifications) while the probe crashes in a loop, hangs every call and floods; all pass; the probe ends
quarantined; the Admin is notified.

## 3. Forum end to end (SC-003)

```bash
uv run portalab plugin validate examples/plugins/forum     # capabilities listed, no blocking finding
```

Admin: install `forum`, open its review (capabilities in plain words), accept, enable. Member A: Forum in the
navigation → new topic → Portalab's dialog shows the exact title and first lines → confirm. Member B (follows
the forum): notified; finds the topic in the portal search. A asks for their privacy export: the posts are
in it. Admin disables Forum: entry, pages, search results gone; re-enables: posts back.
Automated: `tests/integration/plugins/test_forum.py`, `frontend/tests/e2e/plugins/forum.spec.ts`.

## 4. Chat live (SC-004)

`tests/integration/plugins/test_chat_live.py`: 50 simulated members subscribed to a room; 200 messages; p95
delivery ≤ 1 s; a member who blocked the author receives none of theirs; a moderator removes a message
(removed for all); a flood beyond 20/s is slowed (`plugin.rate_limited`), the portal's health stays green.

## 5. Plugin operation overhead (SC-005)

`tests/integration/plugins/test_overhead.py`: the same « list 50 rows » done by a core route and by a
confined plugin route; p95 difference ≤ 50 ms over 500 calls.

## 6. 023 keeps working (SC-006)

`uv run pytest tests -k "plugins and not confined"` (023's suites unchanged) and
`tests/migrations/test_plugins_runtime_upgrade.py`: an install with `hello` (in-process) upgrades →
`allowUnconfined` true, `hello` still runs, warning shown; on a fresh install `hello` v1 with code is
`held_unconfined`; `hello` 2.0.0 (`runtime = "confined"`) keeps 100% of its rows.

## 7. Product type never loses coins (SC-007)

`tests/integration/plugins/test_commission.py`: buy « Avatar commission » → coins debited, ownership
recorded, activation creates the request in the plugin; fault injection (activation raises, times out,
child killed mid-call) → each purchase ends refunded or pending per the shop's rule; the plugin's attempt
to call a balance operation is `denied`.

## 8. Secrets never reach the plugin (SC-008)

`tests/security/plugins/test_secrets.py`: a secret setting is set; the plugin calls its listed host (a local
test server listed `private = true`) and the server sees the injected header; the secret's value is
searched in the plugin's storage, scratch folder, every message the child received, the logs and every
page/slot response: 0 occurrences.

## 9. Moments in the player (SC-009)

`frontend/tests/e2e/plugins/moments.spec.ts` (API stubbed): a moment at 42 s on a title is shown by the
player between 42 s and 47 s (±1 s), the « Add a moment » button opens Portalab's form; the member hides the
contribution → gone for them; extension removed → no overlay, no button, no settings panel.

## 10. Slots cost little (SC-010)

`frontend/tests/unit/plugins/slots-performance.test.tsx` and `tests/integration/plugins/test_slots.py`:
slot contributions are fetched once per page view in parallel with the page's own data; p95 added time ≤
100 ms against the stubbed API.

## 11. Deployment hardening (FR-023–026)

`portalab doctor` reports user, writable code folders, egress allow-list, module roles, audit sink;
`tests/integration/security/test_egress.py` (an unlisted host refused when on), `tests/integration/
security/test_module_roles.py` (with `security.moduleRoles` on, a module's unit of work cannot read another
schema; the whole suite run once with it on in CI), `tests/integration/audit/test_offsite.py` (each audit
entry reaches the syslog test server and the file).

## 12. Authoring (US7)

```bash
uv run portalab plugin new demo --path /tmp/demo
uv run portalab plugin simulate /tmp/demo --database "$PORTALAB_TEST_DATABASE_URL"
uv run portalab plugin validate /tmp/demo
```
