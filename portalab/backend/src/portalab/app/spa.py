"""Serve the built SPA from the backend (single image, research R14).

Unknown client-side routes fall back to ``index.html``; ``/api/*``, ``/healthz`` and ``/readyz`` never do, so
API 404s stay problem documents. The SPA bundle is public (the sign-in surface needs it, CD-025); every API
call it makes is still default-deny on the server.
"""

from pathlib import Path

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

NEVER_FALLBACK = ("/api/", "/healthz", "/readyz")


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            request_path = str(scope.get("path", ""))
            if exc.status_code != 404 or request_path.startswith(NEVER_FALLBACK):
                raise
            return await super().get_response("index.html", scope)


def spa_directory(candidate: Path) -> Path | None:
    return candidate if (candidate / "index.html").is_file() else None
