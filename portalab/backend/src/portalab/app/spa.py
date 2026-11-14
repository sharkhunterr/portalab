"""Serve the built SPA from the backend (single image, research R14).

Unknown client-side routes fall back to ``index.html``; ``/api/*``, ``/healthz`` and ``/readyz`` never do, so
API 404s stay problem documents — nor do the bundle's own files (``/assets/*``): a page left open across a
deployment asking for a file of the previous build gets a 404 it can recover from (it reloads), never an HTML
page taken for code. ``index.html`` is never cached, so a reload always finds the current build.
The SPA bundle is public (the sign-in surface needs it, CD-025); every API
call it makes is still default-deny on the server.

#21: the book reader (``/media/<id>/read``) is a page of its own, entered by a full load: the EPUB it shows
is laid out in frames that carry their own styles and fonts, so its document allows inline styles, fonts and
frames from ``blob:`` — and still no script but the portal's own (the book's frames are sandboxed besides).

Issue 419: the retro play page (``/media/<id>/play``) is one too: the library's emulator (EmulatorJS, relayed
by the portal from the same origin) compiles its WebAssembly cores, runs them in workers and scripts made from
``blob:`` (the Emscripten glue of its cores evaluates strings), and the cores that need threads share memory —
so its document allows ``'unsafe-eval'``, ``'wasm-unsafe-eval'`` and ``blob:`` scripts and workers, still only
from the portal itself, and is isolated from every other origin (COOP + COEP: nothing of another site loads in
it, nor may it reach one — EmulatorJS's own update check included).
"""

import re
from pathlib import Path

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

NEVER_FALLBACK = ("/api/", "/healthz", "/readyz", "/assets/")
NO_STORE = {"Cache-Control": "no-cache, no-store, must-revalidate"}
READER = re.compile(r"^/media/[0-9a-fA-F-]{36}/read/?$")
READER_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' blob:; "
    "img-src 'self' data: blob:; font-src 'self' data: blob:; connect-src 'self'; media-src 'self' blob:; "
    "frame-src 'self' blob:; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)

RETRO = re.compile(r"^/media/[0-9a-fA-F-]{36}/play/?$")
RETRO_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval' blob:; "
        "style-src 'self' 'unsafe-inline' blob:; "
        "img-src 'self' data: blob:; font-src 'self' data: blob:; connect-src 'self' blob: data:; "
        "media-src 'self' blob:; worker-src 'self' blob:; frame-src 'none'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Embedder-Policy": "require-corp",
}


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            request_path = str(scope.get("path", ""))
            if exc.status_code != 404 or request_path.startswith(NEVER_FALLBACK):
                raise
            response = await super().get_response("index.html", scope)
            response.headers.update(NO_STORE)
            if READER.match(request_path):
                response.headers["Content-Security-Policy"] = READER_CSP
            elif RETRO.match(request_path):
                response.headers.update(RETRO_HEADERS)
            return response
        if path in ("", ".", "index.html"):
            response.headers.update(NO_STORE)
        return response


def spa_directory(candidate: Path) -> Path | None:
    return candidate if (candidate / "index.html").is_file() else None
