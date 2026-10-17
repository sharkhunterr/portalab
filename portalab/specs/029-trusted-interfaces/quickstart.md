# Quickstart: Trusted Interfaces (029)

Run on the POC instance (https://127.0.0.1:8444, pack origin :8445) with the demo seeded.

## 1. The seal and the trust layer (US1, SC-002)

1. Account → « Your seal »: choose a symbol, a colour and a word.
2. Shop → buy a product: the confirmation is Portalab's (top layer) with the exact price and the seal.
3. Open a paid booster, request a title, delete a comment: each confirmed the same way.

Automated: `frontend/tests/unit/trust/*.test.tsx`, `frontend/tests/e2e/trust/confirmations.spec.ts`
(every committing action of the journeys shows the seal), `backend/tests/integration/identity/test_seal.py`.

## 2. Exit and safe mode (US1, SC-003)

- With the Teletext interface on: the exit control and Alt+Shift+P bring back Portalab's interface < 1 s.
- `/?safe=1`: no pack stylesheet, script, frame or palette loads; « Leave safe mode » restores them.

Automated: `frontend/tests/e2e/trust/exit-and-safe-mode.spec.ts`.

## 3. Hardened looks (US2, SC-001)

`uv run pytest tests/unit/visuals/test_hardening.py` — fixed/sticky, z-index, viewport units, literal text
blocked; symbols allowed; built-in packs and examples pass. `npx vitest run tests/unit/visuals/css-guard`
— the guard drops them at run time; looks no longer reach `[data-protected]`.

## 4. A complete interface (US3, SC-004, SC-006, SC-009)

1. Import `examples/visual-packs/teletext/`, review (accept its operations), publish.
2. Appearance → Complete interfaces → Teletext « on this kind of device ».
3. Pages 100–500: library, progression, shop, notifications — the same data as Portalab's pages.
4. Request a title from page 200: the trust layer confirms with the seal.
5. Freeze it (Test step's « stall » probe): Portalab's interface is back within 5 s, the failure counted.

Automated: `frontend/tests/e2e/interfaces/teletext.spec.ts` (with the comparison of reads),
`backend/tests/integration/visuals/test_interfaces.py`.

## 5. Operations review and server check (US4)

- An interface declaring `GET /api/v1/admin/visuals` is blocked at analysis; one calling an undeclared
  operation gets `ui.interface_operation_refused` from the broker and from the server.

Automated: `backend/tests/unit/test_exposure_catalog.py` (every route resolved; forbidden prefixes never
exposed), `backend/tests/security/test_interface_requests.py`.

## 6. Host components (US5)

The Teletext player page places `media.player`: the video plays; the frame never receives a stream address
(`frontend/tests/e2e/interfaces/host-components.spec.ts`).

## 7. Budgets (US6, SC-005, SC-007)

The `heavy` probe pack lowers quality within 3 s and falls back within 10 s; the exit control answers in
< 100 ms meanwhile (`frontend/tests/e2e/interfaces/budget.spec.ts`).

## 8. Authoring (US7, SC-010)

```bash
cd sdk/interface/template && npx serve .   # run with the simulated broker
cd backend && uv run portalab visuals analyse ../examples/visual-packs/teletext   # exit 0
```

## 9. Isolation campaign (SC-001)

`npx playwright test tests/e2e/visual-packs/isolation.spec.ts tests/e2e/interfaces/isolation.spec.ts` —
028's probes plus: imitate a confirmation (no seal), read the seal, call undeclared/forbidden operations,
cover the exit control, escape a look's box, inject text — all refused or neutralised.

## Full gates

```bash
cd backend && uv run pytest -n 4 --dist loadfile && uv run ruff check . && uv run mypy && uv run lint-imports --config importlinter.ini
cd frontend && npm run lint && npm run typecheck && npm test && npm run build && npm run check:api-drift
```

## Results on the POC (2026-10-17, branch impl/029-trusted-interfaces)

Live on https://127.0.0.1:8444 with the pack origin on :8445 (`poc.sh serve` runs both through `serve_both`),
a demo member, no committing action ever confirmed (every confirmation cancelled: no Coins spent, nothing
sent to the request service):

| scenario | result |
|---|---|
| 4.1 Teletext imported, analysed (publishable), publication refused until each operation is accepted, then published | pass |
| 4.2 offered to members, chosen for the desktop, drawn full screen from `https://…:8445/sandbox/app` | pass |
| 5 server check: an accepted operation answered (200), a forbidden one and an undeclared one refused (403) | pass |
| 4.3 page 200 reads the library (empty on the POC: no media server) and Portalab's address follows (`/media`), page 300 the progression | pass |
| 4.4 a request through Teletext | no request service on the POC — covered by `e2e/interfaces/teletext.spec.ts` |
| 2 the exit control brings Portalab back (45–69 ms); `?safe=1` loads no pack (0 requests), its banner leaves it | pass |
| a deep link without a view of the interface (`/marketplace/products/…`) shows Portalab's own page (R19) | pass (fixed during the run: equivalents are exact, `/*` for a subtree) |
| 1 a committing action of Portalab's own confirmed with the seal | no open proposal and no affordable product for the member — covered by `e2e/trust/confirmations.spec.ts` |

Found and fixed during the run: the server check did not recognise the routes of included routers (every
interface request was refused) — fixed and tested with an included router; equivalents matched by prefix
(a product's page showed the interface's shop) — now exact.

Gates: backend 2118 passed (pytest -n 4), ruff, mypy, lint-imports clean; frontend lint, typecheck, 1785
unit tests, build, API drift clean; e2e trust, interfaces, visual packs: all pass.
