# Scope revision (2026-10-17): spec 029 reduced

After building the complete version on the POC (branch `impl/029-trusted-interfaces`, kept for reference,
not merged), the owner judged it too complex for what it adds over spec 028. The specification below is
kept as written for its reasoning; **only the following is delivered** (branch `impl/029-interfaces-catalog`,
from `impl/028-visual-packs`):

| Delivered | What it is |
|-----------|------------|
| Exposure catalog | Every API operation labelled read / action / committing action / forbidden, unlabelled = forbidden (FR on the catalog, `capabilities/exposure.py`, `GET /api/v1/exposure`); spec 030 scopes what an extension's code may call with it |
| One « Interfaces » gallery | What 028 called themes is presented as *interfaces* (appearance gallery, shop department and group) |
| Safe mode | Portalab's own interface without anything brought by a pack, in this browser, from the appearance settings or any address with `?safe=1` (left with `?safe=0` or its banner); the page reloads on entering and leaving |
| Fixes found on the way | A script navigation asked during the 400 ms pause is opened when it ends (never dropped); rate limit raised in the default-deny integration test |

| Dropped (owner's decision) | Why |
|----------------------------|-----|
| Complete interfaces (interface app, broker, host components, server interface guard, SDK, Teletext and Swipe examples) | Too complex for the value added over 028's themes, looks and navigations |
| Trust layer and personal seal | The administrator is responsible for the packs offered; a fallback seal brings little |
| Hardened looks (no escape, no literal text) | Not useful enough given 028's sandbox and review |
| Separate pack origin (second port) | 028's opaque-origin sandbox already isolates pack scripts |

| Postponed | |
|-----------|--|
| Budget per visual (frames per second, memory, fallback) | « on verra plus tard » — issue 143 reopened |

Security of the reduced scope: issue 149, a dedicated security review pass (malicious member, malicious
administrator towards members).
