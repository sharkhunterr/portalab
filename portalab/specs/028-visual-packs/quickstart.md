# Quickstart: Visual Packs (028)

How to verify the feature end to end. Commands from `portalab/` (see the project `CLAUDE.md` for the test
database).

## 1. Migration keeps everything (US2, SC-001)

```bash
cd backend
uv run pytest tests/migrations/test_visuals_0001.py tests/integration/visuals/test_builtin_sync.py
```

- Seeds a portal with the pre-migration catalog, ownerships, equipped looks and preferences, runs
  `visuals_0001` + the built-in sync, and asserts: every key of `tests/fixtures/builtin-looks-before.json`
  is held by exactly one built-in element; ownerships, equipped flags, preferences and product economy are
  unchanged; every built-in pack whose products existed is `enabled`.
- `portalab visuals builtin sync --dry-run` on an up-to-date portal prints « nothing to change ».

## 2. Import workflow (US1, SC-002)

1. Copy `examples/visual-packs/nordlys/` into `DATA_DIR/visuals/inbox/`.
2. Administration → Appearance → Packs → *Read the inbox*: Nordlys appears at **Analysis**.
3. Walk the steps: Security (confirm scripts), Test (each element drawn; measures saved), Review (change one
   price), Validation → *Publish*.
4. The shop shows Nordlys products with the decided price; the audit log has every step.
5. Import `tests/fixtures/visual-packs/blocking/` → stops at Analysis; *Publish* is refused.

Automated: `tests/integration/visuals/test_workflow.py`, `frontend/tests/e2e/visual-packs/workflow.spec.ts`.

## 3. Malicious member and public surface (US3, SC-005, SC-006)

```bash
uv run pytest tests/security/test_anonymous_surface.py tests/integration/identity/test_guard.py
```

- Anonymous sweep: only the allow-list answers; everything else returns the identical generic 401.
- As a member, request admin routes until blocked: sessions revoked, sign-in again refused, alert to
  `security.manage` holders within 1 min; restart `serve` → still blocked.
- `portalab security blocks list` / `lift --all` from the server console lifts it (the Admin's too).

## 4. Pack navigation (US4, SC-007)

Publish Abysses, choose its interface: the sonar navigation reaches every section on 390/820/1280 px and with
the keyboard; make its script fail (test fixture) → built-in navigation within 5 s; on `/admin/*` the
built-in navigation shows. Automated: `frontend/tests/e2e/visual-packs/navigation.spec.ts`.

## 5. Booster scene (US5, SC-008)

Publish `examples/visual-packs/booster-scene/` and bind its scene to one booster: opening it plays the pack's
look/opening and the legendary reveal only; cards and rarities equal the API's draw (asserted on 50
openings); another booster opens with the default scene; reduced motion reveals without animation.
Automated: `frontend/tests/e2e/visual-packs/booster-scene.spec.ts`.

## 6. Widgets (US6, SC-009)

Publish `examples/visual-packs/widgets/`: its widget style applies to an existing widget; its new widget
(contract `me.progression`) shows the member's own level; a widget with an undeclared request receives
nothing; a contract the member may not read shows the empty state.
Automated: `frontend/tests/unit/visuals/widget-contracts.test.ts`, `…/e2e/visual-packs/widgets.spec.ts`.

## 7. Lifecycle (US7, SC-010)

v1 → v2 (one element removed) → publish: the element leaves the shop, owners keep it; roll back to v1;
switch off → within 1 min members see defaults and the pack's files answer 404; remove with owners →
archived; remove a pack nobody owns → removed. Automated: `tests/integration/visuals/test_lifecycle.py`.

## 8. Authoring (US8)

```bash
uv run portalab visuals analyse ../examples/visual-packs/abysses   # exit 0
uv run portalab visuals analyse tests/fixtures/visual-packs/blocking  # exit 1
```

## 9. Isolation campaign (SC-004)

`npx playwright test tests/e2e/visual-packs/isolation.spec.ts` — every probe reports « refused »;
`uv run pytest tests/security/visuals` — malformed archives store nothing.

## Full gates

```bash
cd backend && uv run pytest -n auto --dist loadfile && uv run ruff check . && uv run mypy && uv run lint-imports --config importlinter.ini
cd frontend && npm run lint && npm run typecheck && npm test && npm run build && npm run check:api-drift
```
