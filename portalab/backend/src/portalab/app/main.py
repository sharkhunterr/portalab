"""ASGI application factory — the composition root (plan §1, contracts/api-conventions.md)."""

import asyncio
import contextlib
import re
import secrets
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
from portalab.app.security import PrincipalResolver, SecurityMiddleware, enforce_default_deny
from portalab.app.spa import SPAStaticFiles, spa_directory
from portalab.app.stream import StreamOptions
from portalab.app.stream import router as stream_router
from portalab.app.wiring import DeferredAuthorizer, wire_identity, wire_platform
from portalab.capabilities.catalog import new_registry
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authorization import authorization_scope
from portalab.core.authz_port import Authorizer
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
from portalab.core.metrics import default_metrics, phase_scope, record_request
from portalab.core.settings import BootstrapSettings
from portalab.modules.administration.api import routers as admin_routers
from portalab.modules.administration.module import AdministrationModule
from portalab.modules.ai.api import routers as ai_routers
from portalab.modules.ai.module import AiModule
from portalab.modules.authz.api import routers as authz_routers
from portalab.modules.authz.module import AuthzModule
from portalab.modules.automations.api import routers as automations_routers
from portalab.modules.automations.module import AutomationsModule
from portalab.modules.calendar.api import routers as calendar_routers
from portalab.modules.calendar.module import CalendarModule
from portalab.modules.campaigns.api import routers as campaigns_routers
from portalab.modules.campaigns.module import CampaignsModule
from portalab.modules.community.api import routers as community_routers
from portalab.modules.community.module import CommunityModule
from portalab.modules.connectors.api import routers as connectors_routers
from portalab.modules.connectors.module import ConnectorsModule
from portalab.modules.content.api import routers as content_routers
from portalab.modules.content.module import ContentModule
from portalab.modules.dashboard.api import routers as dashboard_routers
from portalab.modules.dashboard.module import DashboardModule
from portalab.modules.events.api import routers as events_routers
from portalab.modules.events.module import EventsModule
from portalab.modules.gamification.api import routers as gamification_routers
from portalab.modules.gamification.module import GamificationModule
from portalab.modules.health.api import routers as health_routers
from portalab.modules.health.module import HealthModule
from portalab.modules.i18n.api import routers as i18n_routers
from portalab.modules.i18n.module import I18nModule
from portalab.modules.identity.api import routers as identity_routers
from portalab.modules.identity.api.middleware import SessionPrincipalResolver
from portalab.modules.identity.context import IdentityContext
from portalab.modules.marketplace.api import routers as marketplace_routers
from portalab.modules.marketplace.module import MarketplaceModule
from portalab.modules.media.api import routers as media_routers
from portalab.modules.media.module import MediaModule
from portalab.modules.news.api import routers as news_routers
from portalab.modules.news.module import NewsModule
from portalab.modules.notifications.api import routers as notifications_routers
from portalab.modules.notifications.module import NotificationsModule
from portalab.modules.observability.api import routers as observability_routers
from portalab.modules.observability.module import ObservabilityModule
from portalab.modules.privacy.api import routers as privacy_routers
from portalab.modules.privacy.module import PrivacyModule
from portalab.modules.privacy.settings import SecurityConfig
from portalab.modules.search.api import routers as search_routers
from portalab.modules.search.module import SearchModule
from portalab.modules.shell.api import routers as shell_routers
from portalab.modules.shell.module import ShellModule
from portalab.modules.statistics.api import routers as statistics_routers
from portalab.modules.statistics.module import StatisticsModule
from portalab.modules.support.api import routers as support_routers
from portalab.modules.support.module import SupportModule
from portalab.modules.ui.api import routers as ui_routers
from portalab.modules.ui.module import UiModule
from portalab.modules.wiki.api import routers as wiki_routers
from portalab.modules.wiki.module import WikiModule

CORRELATION_HEADER = "X-Correlation-Id"
_CORRELATION_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")
API_PREFIX = "/api/v1"
_EPHEMERAL_KEY = secrets.token_bytes(32)  # only when no bootstrap settings (tests, `portalab openapi`)
DEFAULT_STATIC_DIR = BACKEND_DIR / "static"

log = get_logger("portalab.app")


async def _flush_loop(observability: ObservabilityModule, interval: float = 30.0) -> None:
    """Drain this process's observability hooks periodically (the worker flushes its own, R4)."""
    while True:
        await asyncio.sleep(interval)
        with contextlib.suppress(Exception):
            await observability.collector.flush()


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
    identity: IdentityContext | None = None,
    capabilities: CapabilityRegistry | None = None,
    authz: AuthzModule | None = None,
    privacy: PrivacyModule | None = None,
    administration: AdministrationModule | None = None,
    events: EventsModule | None = None,
    connectors: ConnectorsModule | None = None,
    health: HealthModule | None = None,
    observability: ObservabilityModule | None = None,
    ui: UiModule | None = None,
    shell: ShellModule | None = None,
    i18n: I18nModule | None = None,
    search: SearchModule | None = None,
    dashboard: DashboardModule | None = None,
    support: SupportModule | None = None,
    statistics: StatisticsModule | None = None,
    notifications: NotificationsModule | None = None,
    media: MediaModule | None = None,
    content: ContentModule | None = None,
    wiki: WikiModule | None = None,
    news: NewsModule | None = None,
    calendar: CalendarModule | None = None,
    ai: AiModule | None = None,
    gamification: GamificationModule | None = None,
    campaigns: CampaignsModule | None = None,
    automations: AutomationsModule | None = None,
    community: CommunityModule | None = None,
    marketplace: MarketplaceModule | None = None,
    security_config: SecurityConfig | None = None,
) -> FastAPI:
    """Build the API. Dependencies are injectable so tests can wire fakes; production wires real ones."""

    owns_database = database is None and settings is not None

    def wire_modules(app: FastAPI, db: Database) -> None:
        if identity is not None:  # tests wire their own identity context (and optionally an authz module)
            app.state.identity_module = wire_identity(identity)
            return
        platform = wire_platform(
            db,
            data_dir=settings.data_dir if settings else Path("/var/lib/portalab"),
            capabilities=app.state.capabilities,
            secret_key=settings.secret_key if settings else _EPHEMERAL_KEY,
        )
        app.state.platform = platform
        app.state.administration_module = platform.administration
        app.state.events_module = platform.events
        app.state.connectors_module = platform.connectors
        app.state.health_module = platform.health
        app.state.observability_module = platform.observability
        app.state.ui_module = platform.ui
        app.state.shell_module = platform.shell
        app.state.i18n_module = platform.i18n
        app.state.search_module = platform.search
        app.state.dashboard_module = platform.dashboard
        app.state.support_module = platform.support
        app.state.statistics_module = platform.statistics
        app.state.notifications_module = platform.notifications
        app.state.media_module = platform.media
        app.state.content_module = platform.content
        app.state.wiki_module = platform.wiki
        app.state.news_module = platform.news
        app.state.calendar_module = platform.calendar
        app.state.ai_module = platform.ai
        app.state.gamification_module = platform.gamification
        app.state.campaigns_module = platform.campaigns
        app.state.automations_module = platform.automations
        app.state.community_module = platform.community
        app.state.marketplace_module = platform.marketplace
        app.state.authz_module = platform.authz
        app.state.privacy_module = platform.privacy
        app.state.identity_module = platform.identity
        if isinstance(app.state.authorizer, DeferredAuthorizer):
            app.state.authorizer.target = platform.authz.engine

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if owns_database and settings is not None:
            app.state.database = Database.from_url(settings.database_url.reveal())
            wire_modules(app, app.state.database)
        if app.state.platform is not None:
            await app.state.platform.refresh_config()
            await app.state.platform.start_services()
        flusher = (
            asyncio.create_task(_flush_loop(app.state.platform.observability))
            if app.state.platform is not None
            else None
        )
        try:
            yield
        finally:
            if flusher is not None:
                flusher.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await flusher
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
    if authorizer is None:
        authorizer = authz.engine if authz else identity.authorizer if identity else DeferredAuthorizer()
    app.state.authorizer = authorizer
    app.state.capabilities = identity.capabilities if identity else (capabilities or new_registry())
    app.state.authz_module = authz
    app.state.privacy_module = privacy
    app.state.administration_module = administration
    app.state.events_module = events
    app.state.connectors_module = connectors
    app.state.health_module = health
    app.state.observability_module = observability
    app.state.ui_module = ui
    app.state.shell_module = shell
    app.state.i18n_module = i18n
    app.state.search_module = search
    app.state.dashboard_module = dashboard
    app.state.support_module = support
    app.state.statistics_module = statistics
    app.state.notifications_module = notifications
    app.state.media_module = media
    app.state.content_module = content
    app.state.wiki_module = wiki
    app.state.news_module = news
    app.state.calendar_module = calendar
    app.state.ai_module = ai
    app.state.gamification_module = gamification
    app.state.campaigns_module = campaigns
    app.state.automations_module = automations
    app.state.community_module = community
    app.state.marketplace_module = marketplace
    app.state.platform = None
    app.state.principal_resolver = principal_resolver or SessionPrincipalResolver()
    app.state.identity_module = None
    if database is not None:
        wire_modules(app, database)
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
        with correlation_scope(valid) as correlation_id, authorization_scope(), phase_scope() as phases:
            try:
                response = await call_next(request)
            except Exception as exc:  # last-resort guard: never leak internals
                default_metrics.error(
                    "portal", "unhandled_request_error", exc, context={"method": request.method}
                )
                log.exception("unhandled error", extra={"fields": {"path": request.url.path}})
                response = _problem_response(
                    internal_error_problem(exc, correlation_id=correlation_id, instance=request.url.path)
                )
            response.headers[CORRELATION_HEADER] = correlation_id
            route = getattr(request.scope.get("route"), "path", "unmatched")
            record_request(
                "portal",
                "http.request",
                time.perf_counter() - started,
                phases,
                {"route": route, "method": request.method, "status": response.status_code // 100 * 100},
                timed_out=response.status_code == 504,
            )
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

    security = security_config or SecurityConfig()
    app.add_middleware(
        SecurityMiddleware,
        max_body_bytes=security.max_body_bytes,
        per_ip_per_minute=security.rate_limit_per_ip_per_minute,
        per_user_per_minute=security.rate_limit_per_user_per_minute,
    )
    app.include_router(health_router)
    app.include_router(stream_router)
    for router in [
        *identity_routers(),
        *authz_routers(),
        *privacy_routers(),
        *admin_routers(),
        *events_routers(),
        *health_routers(),  # before connectors: /services/health must not match /services/{id}
        *connectors_routers(),
        *observability_routers(),
        *ui_routers(),
        *shell_routers(),
        *i18n_routers(),
        *search_routers(),
        *dashboard_routers(),
        *support_routers(),
        *statistics_routers(),
        *notifications_routers(),
        *media_routers(),
        *content_routers(),
        *wiki_routers(),
        *news_routers(),
        *calendar_routers(),
        *ai_routers(),
        *gamification_routers(),
        *campaigns_routers(),
        *automations_routers(),
        *community_routers(),
        *marketplace_routers(),
    ]:
        app.include_router(router)
    spa = spa_directory(static_dir) if static_dir else None
    if spa is not None:
        app.mount("/", SPAStaticFiles(directory=spa, html=True), name="spa")
    return app
