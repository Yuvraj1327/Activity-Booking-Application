"""FastAPI application factory.

Run from the backend/ directory:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8008
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_app_settings, get_database
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import REQUEST_ID_HEADER, register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.core.security import build_jwt_verifier
from app.database.health import check_database
from app.database.session import Database
from app.gateways.fcm import FcmSender
from app.gateways.razorpay import RazorpayGateway
from app.gateways.resend import ResendSender
from app.schemas.common import DatabaseStatus, ErrorResponse, HealthResponse
from app.services.dispatch import sweep_loop
from app.services.storage import SupabaseStorageGateway

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.db = Database(settings)  # lazy: does not connect
        app.state.jwt_verifier = build_jwt_verifier(settings)
        if not hasattr(app.state, "storage"):  # tests may inject a fake before startup
            app.state.storage = SupabaseStorageGateway(settings)
        # Payment / push / email providers; tests inject fakes before startup.
        if not hasattr(app.state, "payment_gateway"):
            app.state.payment_gateway = RazorpayGateway(settings)
        if not hasattr(app.state, "push_sender"):
            app.state.push_sender = FcmSender(settings)
        if not hasattr(app.state, "email_sender"):
            app.state.email_sender = ResendSender(settings)
        sweeper = None
        if settings.background_sweep_seconds and app.state.db.configured:
            sweeper = asyncio.create_task(sweep_loop(app, settings.background_sweep_seconds))
        logger.info(
            "startup",
            extra={
                "environment": settings.environment,
                "database_configured": app.state.db.configured,
                "auth_configured": app.state.jwt_verifier.configured,
            },
        )
        try:
            yield
        finally:
            if sweeper is not None:
                sweeper.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await sweeper
            await app.state.db.dispose()
            logger.info("shutdown")

    docs = settings.docs_are_enabled
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="ZURUV backend API. Discover. Book. Play.",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
        responses={
            401: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    # Expose settings/db early so tests using TestClient without lifespan still work.
    app.state.settings = settings
    app.state.storage = SupabaseStorageGateway(settings)
    app.state.payment_gateway = RazorpayGateway(settings)
    app.state.push_sender = FcmSender(settings)
    app.state.email_sender = ResendSender(settings)

    register_exception_handlers(app)

    # Added last = outermost: request id is set before CORS/handlers run.
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key", REQUEST_ID_HEADER],
            expose_headers=[REQUEST_ID_HEADER],
        )
    app.add_middleware(RequestContextMiddleware)

    @app.get("/health", response_model=HealthResponse, tags=["health"], summary="Liveness and DB check")
    async def health(
        cfg: Annotated[Settings, Depends(get_app_settings)],
        db: Annotated[Database, Depends(get_database)],
    ) -> HealthResponse:
        result = await check_database(db, cfg.db_health_timeout)
        return HealthResponse(
            status="ok" if result.status == "ok" else "degraded",
            app=cfg.app_name,
            version=cfg.app_version,
            environment=cfg.environment,
            database=DatabaseStatus(**result.model_dump()),
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
