# Research: Trusted Interfaces (029)

Grounded in spec 028 as built on `impl/028-visual-packs` (POC worktree): `modules/visuals` (manifest, analysis,
store, sandbox.py bootstrap + CSP, registry epoch, `/visuals/live/{epoch}`), `design-system/visuals`
(`registry.ts`, `cssGuard.ts` with `lookSelectorOk`/`shieldSelector`, `sandbox.ts`, `gpu.ts`, `vocabulary.ts`),
`design-system/motion/budget.ts`, `shell/AppShell.tsx` (`PROTECTED_PAGES`), the isolation campaign
(`frontend/tests/e2e/visual-packs/isolation.spec.ts`). Every decision below was taken with the recommended
option, the user having asked to chain autonomously.

## R1 — The separate origin serves documents only, pack bytes travel as data

**Decision**: `portalab serve` listens on a second port (bootstrap setting `PACK_ORIGIN_PORT`, default
`BIND_PORT + 1`; public address `PACK_ORIGIN_URL`, default the request's host on that port) with a tiny ASGI
app (`app/pack_origin.py`) serving **only** the static sandbox documents (`/sandbox/script`, `/sandbox/app`) —
no API, no session, no pack file. Every byte of a pack reaches a sandbox as **data** handed by the host
(`run` with the module's text, `asset` with its bytes), as 028 already does. Documents carry
`Origin-Agent-Cluster: ?1`, `Cross-Origin-Resource-Policy: cross-origin` (framing) and
`frame-ancestors <main origin>`; frames keep `sandbox="allow-scripts"` (opaque origin). The main CSP gains
`frame-src <pack origin>`. Looks' CSS/GLSL text stays fetched by the host from `/visuals/live/{epoch}` (data
turned into guarded constructed stylesheets — never a document).
**Rationale**: what runs pack code lives apart from Portalab's origin (FR-010) while the pack origin holds
nothing worth taking (no session, no files, no API): a sandbox escape lands nowhere. Cookies are scoped by
host, not port — so the pack origin must not *need* them, and it does not.
**Alternatives**: a second host name (needs DNS on a LAN; kept as an option via `PACK_ORIGIN_URL`); serving
pack files from the pack origin with signed tickets (more moving parts, nothing gained since bytes are handed
as data); a separate container (operational weight).

**Measured on the POC (2026-10-17)**: a frame of the pack origin on the same host and the next port (same
*site*), sandboxed (`allow-scripts` only), hung in a busy loop: with the browser's site isolation on (the
default of desktop browsers) the frame runs in a process of its own and Portalab's page keeps running (its
heartbeat sees the silence, Portalab is back < 5 s); Playwright's Chromium starts without site isolation (the
e2e of a hung interface passes `--site-per-process`). A pack origin on another host name (`PACK_ORIGIN_URL`)
stays the strongest setting.

## R2 — A complete interface is a sandboxed application module in « app » mode

**Decision**: new element type `interface_app` (render kind `app`): an ES module (any framework, bundled by
the author) whose default export receives `(root, api)` like 028 scripts, run full-screen in a frame from
`/sandbox/app`. The app document's policy adds `'wasm-unsafe-eval'` to `script-src`, `worker-src blob:`,
`media-src blob: data:`, `font-src blob: data:`; `connect-src 'none'`, `form-action 'none'`, no
`allow-same-origin`/`allow-forms`/`allow-popups`/`allow-top-navigation`; the frame's `allow` attribute is empty
(no camera, microphone, geolocation, sensors, fullscreen, payment) (FR-011, FR-012).
**Rationale**: reuses 028's proven bootstrap and isolation campaign; any drawing capability works (Canvas,
WebGL/WebGPU, wasm, workers from blobs); nothing reaches the network.
**Alternatives**: an HTML entry document from the pack (needs its files served by URL — R1 rejects); a
Web Components host in Portalab's document (no isolation).

## R3 — The broker lives in Portalab's page and speaks the sandbox protocol

**Decision**: the host page (trusted code) brokers every call: `{type:"call", id, operation, params}` →
check (declared ∧ accepted at review ∧ label not forbidden) → for a committing operation, the trust layer's
confirmation (R6) → `fetch` with the member's session and the header
`X-Portalab-Interface: <pack>@<sha16>/<element>` → the answer scrubbed (R11) → `{type:"result", id, ok,
data | problem}`. Live updates: `{type:"subscribe", topics}` → the host's shared stream (`connectStream`)
forwards only topics the interface declared and that read operations cover. Errors are problem documents
with the same codes Portalab gives anywhere (FR-017, FR-021, US4-4).
**Rationale**: the pack never holds a session or a token; the server sees ordinary requests from the member's
own session and checks them as always.
**Alternatives**: a server-side proxy per interface (duplicates authorization); handing the pack a scoped
token (a token in a pack is a token outside).

## R4 — The exposure catalog: labels declared by modules, unlabelled = forbidden

**Decision**: `capabilities/exposure.py` defines `Exposure = read | action | committing | forbidden`, an
`OperationLabel(method, path, exposure, words{en,fr}, confirm{en,fr} | None)` and a registry; each module
declares its labels in `modules/<m>/exposure.py` (data only); rule-based **forbidden** prefixes win over any
declaration (`/api/v1/admin`, `/auth`, `/users`, `/roles`, `/groups`, `/permissions`, `/grants`, `/audit`,
`/maintenance`, `/privacy`, `/me/security`, `/me/sessions`, `/me/seal`, `/me/account`…). A route without a
label is forbidden. `GET /api/v1/exposure` (members) lists the non-forbidden operations with their words —
the SDK's source. v1 labels the member-facing reads and actions an interface needs (media, community
reads, dashboard, marketplace catalog/purchases, progression, notifications, news, wiki, calendar, search)
— about 120 of the 607 operations; everything else stays forbidden until labelled.
**Rationale**: default deny (Constitution VI); labels sit with the module that owns the route; one table
drives analysis, review, run-time checks, SDK and docs.
**Alternatives**: labels in `openapi_extra` (scattered, hard to audit); one central table (couples all modules).

## R5 — The server checks interface requests again

**Decision**: middleware `app/interfaces.py`: a request carrying `X-Portalab-Interface` must name a live,
published `interface_app` element whose accepted operations include the request's (method, path template)
and whose label is not forbidden — else `403 ui.interface_operation_refused` before any route runs. It rate
limits per (member, interface) — 20 requests/s, burst 60; committing 1 per 2 s — answering `429` and, after
three refusals in a minute, an event `visuals.interface.misbehaved` (counted on the element, FR-016). Every
committing operation through an interface is audited (`interface.operation`: member, interface, operation,
outcome) (FR-023).
**Rationale**: defence in depth: even a broker bug cannot widen what an interface does.

## R6 — The trust layer: a shadow root in the browser's top layer

**Decision**: a custom element `<portalab-trust>` attached once to `document.body`, with a shadow
root holding its own constructed stylesheet (fixed colours, not theme tokens); confirmations are a
`<dialog>` opened with `showModal()` (top layer: above every frame, every look, every other dialog opened
before), the exit control a `popover="manual"` element re-shown on top after any dialog closes. React renders
into the shadow root through a portal. Pack CSS (adopted on the document) never crosses a shadow boundary;
the confirmation shows: the operation's words, the exact content (amounts, product, target, free text in
full), and the member's seal (R7). Portalab's own committing flows use the same `confirmTrusted()` (purchase,
booster opening, media request, deletion, publication) (FR-001, FR-002, FR-004, SC-002).
**Rationale**: the top layer cannot be covered by page content; shadow DOM cannot be styled from outside
(an *open* root: closing it would only hide it from the page's own scripts — Portalab's, since no pack runs
in the page — and from the e2e tests); one component for every interface keeps the seal meaningful.

## R7 — The seal

**Decision**: table `identity.seals(user_id PK, symbol smallint 0–47, colour smallint 0–11, word text ≤ 16,
chosen bool, updated_at)`, created on first need with a random symbol and colour; `GET/PUT /api/v1/me/seal`
(forbidden to interfaces), shown and chosen on the account page (a Portalab page), included in the privacy
export and deleted with the account. 48 symbols from the icon set (drawn as inline SVG inside the shadow
root), 12 fixed colours chosen for contrast on light and dark. The seal is read by the trust layer only;
never in any manifest, context or answer handed to a sandbox (FR-003).

## R8 — Exit control, shortcut, safe mode

**Decision**: the exit control is drawn by the trust layer whenever an `interface_app` (or a pack navigation
covering the screen) is active; the shortcut is **Alt+Shift+P** — caught by the host and, inside frames, by
the sandbox bootstrap's capture-phase listener registered before the pack's code runs, which posts `exit`
through the reference to `postMessage` it took first. Safe mode: `?safe=1` on any address or the settings
toggle stores `portalab.safe=1` (localStorage, sessionStorage fallback); while on, no `ExternalVisualsLoader`,
no interface app, no palette or look of a pack — only the socle — with a Portalab banner « Safe mode · Leave »
(FR-005, FR-006, SC-003).

## R9 — Protected pages carry no pack content at all

**Decision**: on `PROTECTED_PAGES` (`/admin`, `/account`, `/privacy`, plus sign-in and terms outside the shell)
the registry withdraws every pack stylesheet from `document.adoptedStyleSheets` (a scope flag) and the
interface app is suspended (Portalab's shell shows); leaving them restores both (FR-007).

## R10 — Hardened looks: analysis rules and run-time confinement

**Decision**: analysis (and the browser guard) refuse in a look's stylesheet: `position: fixed|sticky`;
`z-index` outside −1…10; viewport units (`vw`, `vh`, `vmin`, `vmax`, `dvh`, `svh`, `lvh`) in sizes and
offsets; `content:` strings containing a letter or a digit (`\p{L}|\p{N}`) — symbols, punctuation, emoji and
`attr()`/`counter()` stay allowed (FR-008, FR-009). At run time, every look hook element gets confinement
from Portalab's base CSS: `isolation: isolate` (its stacking cannot rise above others) and, for the small
hooks (avatar frame, level badge, name, title, badge, notification, widget frame, card face/back),
`overflow: clip; overflow-clip-margin: 24px` (a bounded halo, nothing further). Stage-like hooks (level-up,
celebration, ambient, booster stage) are already full-screen layers under the trust layer. Looks of
published versions that the new rules refuse are listed for the Admin (finding « to update ») and keep
showing neutralised (declarations dropped by the guard) (FR-032). The built-in packs are adapted to pass.

## R11 — Portalab's words stay Portalab's

**Decision**: texts stating a price, a rarity, a draw result, an amount, the member's identity or security
carry `data-protected`; the CSS guard now applies `shieldSelector` to **look** sheets too (028 shielded only
interfaces), so no look reaches them; answers handed to interfaces have image addresses replaced by bytes
(the host fetches `/api/v1/media/…` images with the session and transfers `ArrayBuffer`s; fields named
`*_url` pointing to Portalab are rewritten to asset handles) (FR-004, FR-022).

## R12 — Budgets and fallbacks

**Decision**: extend `motion/budget.ts` with a `VisualBudget` per device form (phone: 30 fps target, 192 MB;
tablet: 40 fps, 256 MB; desktop: 50 fps, 384 MB). Sandboxes report every 2 s `{type:"health", fps, memory}`
(the bootstrap measures its own `requestAnimationFrame` cadence and `performance.memory` when present); GPU
looks are timed by `badgeFx` per frame. Under target for 3 s → `{type:"quality", level:"low"}` (GPU looks
halve their resolution); still under at 10 s, or a missed heartbeat (028: 5 s), or memory over → fallback
(the element's light version, else Portalab's own), a discreet notice, a report (`/visuals/reports`, reason
`budget`) counted on the element (FR-026, SC-007). The trust layer and exit control live in the host's main
thread outside any frame — a frame's busy thread (another process per R1/R2) cannot block them (FR-027,
SC-005).

## R13 — Host components

**Decision**: `{type:"place", id, component, props, rect}` / `{type:"move", id, rect}` / `{type:"unplace",
id}`; the host renders the Portalab component in a fixed-position layer above the interface frame at `rect`
(clamped to the viewport), with the member's session: `media.player` (`VideoPlayer`, props `{item}`),
`media.reader` (`ReaderPage`'s reader, `{item}`), `community.avatar` (framed avatar, `{member}`),
`marketplace.booster` (`StageHost`, `{booster}`; the result is posted to the interface only once revealed:
`{type:"event", name:"booster.revealed", cards}`). Components are labelled in the exposure catalog like
operations (`component:<name>`) and declared/accepted the same way (FR-024, FR-025).

## R14 — The member's choice

**Decision**: setting `ui.interfaceApp` (user scope) `{desktop, tablet, phone}` each `"<look>" | null`; the
vocabulary gains type `interface_app`; a sold interface needs its product like a theme; the appearance page
lists published interfaces with preview, forms, what they read (their read operations' words); a form the
interface does not support falls back to Portalab's there (FR-014). The interface gets `context`:
`{form, language, reducedMotion, textScale, colorScheme, page, equivalents}` and `{type:"context"}` on change
(FR-015).

## R15 — Element format

**Decision**: `interface_app` element: `render: {kind: "app", file: "<entry>.js"}`, `app: {forms: [...],
operations: ["GET /api/v1/media", …], components: ["media.player", …], topics: [...],
equivalents: {"/media": "library", "/marketplace": "shop", …}, light: "<another interface_app look>" | null}`,
`preview`, economy as any 028 element (default offered). Pack limits for a pack holding an `interface_app`:
60 MB total, 20 MB per file (028: 20 MB / 5 MB) (FR-013).

## R16 — Analysis of complete interfaces

**Decision**: blocking if an operation or component is unknown, forbidden or unlabelled; if a form is
unknown; if `light` names no `interface_app` of the pack; warning if the interface supports no phone form
(members on phones stay on Portalab's), if it declares no equivalent for `/` . The Review step lists each
operation with its words grouped read/action/committing and requires each to be accepted (stored in the
draft's `operations`) (US4).

## R17 — SDK and example

**Decision**: `sdk/interface/` in the repository: `portalab-interface.d.ts` generated by
`npm run gen:interface-sdk` from `GET /exposure` + `backend/openapi.json`, `simulator.js` (a broker answering
every labelled read with sample data and recording actions), `template/` (pack.json, element.json, an entry
module, a page to run it with the simulator); the offline tool `portalab visuals analyse` checks
`interface_app` (FR-028). Example pack `examples/visual-packs/teletext/`: a full Teletext-style interface
(numbered pages: 100 index, 200 library, 300 progression, 400 shop, 500 notifications), reading media,
progression, notifications, the shop; requesting a title (committing → trust layer); placing the media
player; a light version (FR-030).

## R18 — Test step: measures and probes

**Decision**: for an `interface_app`, the Test step runs it in two frames (1280×800 desktop, 390×844 phone)
with the simulated broker: time to `ready`, fps over 5 s of scripted scrolling, memory when reported; probes:
(1) the exit control's hit-test at its place returns the control, (2) the texts the interface wrote
(collected by the bootstrap's text walker, `{type:"texts"}`) are listed, (3) every call it attempted outside
its declaration is listed. Results stored with the version through the existing measures endpoint
(FR-029).

## R19 — Interfaces and Portalab's addresses

**Decision**: the host keeps Portalab's address bar: the interface's `navigate(key)` to an equivalent sets the
matching Portalab path (history), the back button sends `{type:"context", page}`; a Portalab address the
interface has no equivalent for shows Portalab's own page (the interface suspended) with the exit/return
control (edge case « deep link »).

## R20 — Compatibility and migration

**Decision**: format 1 packs unchanged; no data migration beyond `identity.seals` and the new setting;
published 028 versions are re-analysed at start for the new look rules (findings « to update », never
blocking for what is published); the built-in packs are fixed to pass. 028's navigations and widgets keep
their script mode (`/sandbox/script` now on the pack origin).
