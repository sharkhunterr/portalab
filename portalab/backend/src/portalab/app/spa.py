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
            return response
        if path in ("", ".", "index.html"):
            response.headers.update(NO_STORE)
        return response


def spa_directory(candidate: Path) -> Path | None:
    return candidate if (candidate / "index.html").is_file() else None
