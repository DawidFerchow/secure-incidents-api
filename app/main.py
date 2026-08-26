from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.status import HTTP_413_CONTENT_TOO_LARGE

from app.api.routes import router
from app.core.logging import configure_logging, request_id_context
from app.core.settings import Settings
from app.store import IncidentStore

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_MAX_CONTENT_LENGTH = 1_048_576


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or Settings.from_env()
    configure_logging(active_settings.log_level)
    logger = logging.getLogger("app.http")

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        store = IncidentStore()
        store.seed(active_settings.seed_records)
        application.state.store = store
        logger.info(
            "application_started",
            extra={"seed_records": active_settings.seed_records},
        )
        yield
        logger.info("application_stopped")

    application = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        description="In-memory CRUD API delivered with a complete DevSecOps workflow.",
        lifespan=lifespan,
    )
    application.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(active_settings.allowed_hosts)
    )

    @application.middleware("http")
    async def request_observability(request: Request, call_next):  # type: ignore[no-untyped-def]
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_CONTENT_LENGTH:
            return JSONResponse(
                status_code=HTTP_413_CONTENT_TOO_LARGE,
                content={"detail": "Request body is too large"},
            )

        supplied_request_id = request.headers.get("x-request-id", "")
        request_id = (
            supplied_request_id
            if _REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else str(uuid.uuid4())
        )
        token = request_id_context.set(request_id)
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - started_at) * 1_000, 2)
            logger.info(
                "request_completed",
                extra={
                    "http_method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - started_at) * 1_000, 2)
            logger.exception(
                "request_failed",
                extra={
                    "http_method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            request_id_context.reset(token)

    @application.get("/", tags=["system"])
    def root() -> dict[str, str]:
        return {
            "name": active_settings.app_name,
            "documentation": "/docs",
            "health": "/health/ready",
        }

    @application.get("/health/live", tags=["system"])
    def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/ready", tags=["system"])
    def readiness(request: Request) -> dict[str, str | int]:
        store: IncidentStore = request.app.state.store
        return {"status": "ready", "records": len(store)}

    application.include_router(router)
    return application


app = create_app()
