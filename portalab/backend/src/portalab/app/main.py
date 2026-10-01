"""ASGI application factory — the composition root (plan §1, contracts/api-conventions.md)."""

import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

import portalab
from portalab.app.composition import BACKEND_DIR
from portalab.app.health import router as health_router
from portalab.app.migrations import expected_heads
from portalab.app.security import AnonymousResolver, PrincipalResolver, enforce_default_deny
from portalab.app.spa import SPAStaticFiles, spa_directory
from portalab.app.stream import StreamOptions
from portalab.app.stream import router as stream_router
from portalab.core.authz_port import Authorizer, DenyAllAuthorizer
from portalab.core.db import Database
from portalab.core.errors import (
    PROBLEM_CONTENT_TYPE,
    BadRequest,
    Forbidden,
    NotFound,
    PortalError,
    ValidationFailed,
    internal_error_problem,
    to_problem,
)
from portalab.core.logging import correlation_scope, get_correlation_id, get_logger
from portalab.core.settings import BootstrapSettings

CORRELATION_HEADER = "X-Correlation-Id"
_CORRELATION_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")
API_PREFIX = "/api/v1"
DEFAULT_STATIC_DIR = BACKEND_DIR / "static"

log = get_logger("portalab.app")


def _problem_response(problem: dict[str, Any]) -> JSONResponse:
    return JSONResponse(problem, status_code=int(problem["status"]), media_type=PROBLEM_CONTENT_TYPE)


def create_app(
    settings: BootstrapSettings | None = None,
    *,
    database: Database | None = None,
    authorizer: Authorizer | None = None,
    principal_resolver: PrincipalResolver | None = None,
    migration_heads: set[str] | None = None,
    stream_options: StreamOptions | None = None,
    static_dir: Path | None = DEFAULT_STATIC_DIR,
) -> FastAPI:
    """Build the API. Dependencies are injectable so tests can wire fakes; production wires real ones."""

    owns_database = database is None and settings is not None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if owns_database and settings is not None:
            app.state.database = Database.from_url(settings.database_url.reveal())
        try:
            yield
        finally:
            if owns_database and app.state.database is not None:
                await app.state.database.dispose()

    app = FastAPI(
        title="Portalab API",
        version=portalab.__version__,
        lifespan=lifespan,
        dependencies=[Depends(enforce_default_deny)],
        docs_url=None,
        redoc_url=None,
        openapi_url=None,  # schema exported by `portalab openapi`; the portal is authenticated-only (CD-025)
    )
    app.state.database = database
    app.state.authorizer = authorizer or DenyAllAuthorizer()
    app.state.principal_resolver = principal_resolver or AnonymousResolver()
    app.state.stream_options = stream_options or StreamOptions()
    if migration_heads is None:
        url = settings.database_url.reveal() if settings else "postgresql+asyncpg://unused/unused"
        migration_heads = expected_heads(url)
    app.state.migration_heads = migration_heads

    @app.middleware("http")
    async def correlation_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(CORRELATION_HEADER)
        valid = incoming if incoming and _CORRELATION_RE.fullmatch(incoming) else None
        started = time.perf_counter()
        with correlation_scope(valid) as correlation_id:
            try:
                response = await call_next(request)
            except Exception as exc:  # last-resort guard: never leak internals
                log.exception("unhandled error", extra={"fields": {"path": request.url.path}})
                response = _problem_response(
                    internal_error_problem(exc, correlation_id=correlation_id, instance=request.url.path)
                )
            response.headers[CORRELATION_HEADER] = correlation_id
            log.info(
                "request",
                extra={
                    "fields": {
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                },
            )
            return response

    @app.exception_handler(PortalError)
    async def portal_error_handler(request: Request, exc: PortalError) -> JSONResponse:
        return _problem_response(
            to_problem(exc, correlation_id=get_correlation_id(), instance=request.url.path)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(err.get("loc", ())), "type": err.get("type")} for err in exc.errors()]
        error = ValidationFailed("The request is invalid.", extensions={"errors": errors})
        return _problem_response(
            to_problem(error, correlation_id=get_correlation_id(), instance=request.url.path)
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        mapped: PortalError
        if exc.status_code == 404:
            mapped = NotFound()
        elif exc.status_code == 403:
            mapped = Forbidden()
        elif exc.status_code == 405:
            mapped = BadRequest("Method not allowed.", code="method_not_allowed")
        else:
            mapped = BadRequest()
        problem = to_problem(mapped, correlation_id=get_correlation_id(), instance=request.url.path)
        problem["status"] = exc.status_code
        return _problem_response(problem)

    app.include_router(health_router)
    app.include_router(stream_router)
    spa = spa_directory(static_dir) if static_dir else None
    if spa is not None:
        app.mount("/", SPAStaticFiles(directory=spa, html=True), name="spa")
    return app
