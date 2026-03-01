import logging
import structlog

from app.config import settings
from app.database import engine
from app.limiter import limiter
from app.metrics import rate_limit_exceeded_total
from app.middleware import RequestIDMiddleware
from app.routers import events, health
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.exc import IntegrityError, OperationalError


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger = structlog.get_logger()
    logger.info("startup_complete", app=settings.app_name, debug=settings.debug)
    yield
    await engine.dispose()
    logger.info("shutdown_complete", app=settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="Event ingestion and query API",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestIDMiddleware)


Instrumentator(
    excluded_handlers=["/metrics", "/healthz/live", "/healthz/ready"],
    should_group_status_codes=False,
).instrument(app).expose(app, include_in_schema=False)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    rate_limit_exceeded_total.labels(path=request.url.path).inc()
    return JSONResponse(
        {"detail": f"Rate limit exceeded: {exc.detail}"},
        status_code=429,
        headers={"Retry-After": "60"},
    )


@app.exception_handler(OperationalError)
async def db_connection_error(request: Request, exc: OperationalError) -> JSONResponse:
    structlog.get_logger().error("db_unavailable", error=str(exc), path=str(request.url))
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


@app.exception_handler(IntegrityError)
async def db_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    structlog.get_logger().error("db_integrity_error", error=str(exc), path=str(request.url))
    return JSONResponse(status_code=409, content={"detail": "Conflict: constraint violation"})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    structlog.get_logger().error("unhandled_exception", error=str(exc), path=str(request.url))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router)
app.include_router(events.router)
