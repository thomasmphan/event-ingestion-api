import logging
import structlog

from app.config import settings
from app.database import Base, engine
from app.routers import events, health
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger = structlog.get_logger()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
