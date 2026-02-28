# Event Ingestion API — Project Memory

## Project state
Full production-ready REST API. All core features implemented, tested, and running.
GitHub repo exists. CI passing.

## Stack
- Python 3.12 (Docker) / 3.14 (local)
- FastAPI + SQLAlchemy 2.0 async + asyncpg + PostgreSQL 16
- structlog JSON logging, pydantic-settings, alembic, slowapi (rate limiting)
- pytest + pytest-asyncio + testcontainers (Postgres via Docker, auto-managed)

## Key files
- app/config.py — pydantic BaseSettings, reads from .env
- app/database.py — async engine, AsyncSessionLocal, get_db, get_session_factory
- app/models.py — Event ORM model, composite index (event_type, timestamp)
- app/schemas.py — EventCreate, EventResponse, EventListResponse, health schemas
- app/routers/health.py — split liveness (/healthz/live) and readiness (/healthz/ready)
- app/routers/events.py — POST /events, GET /events (cursor pagination), GET /events/{id}
- app/main.py — lifespan, structlog config, global exception handlers
- app/limiter.py — Limiter(key_func=get_remote_address), headers_enabled NOT set (incompatible with Starlette 0.52 BaseHTTPMiddleware)
- tests/conftest.py — Postgres via testcontainers, reset_rate_limiter autouse fixture
- tests/test_events.py — 14 tests including cursor sort direction validation
- tests/test_rate_limit.py — monkeypatches settings limits to "3/minute", resets limiter storage between tests
- alembic/env.py — async migration setup with run_sync bridge
- .github/workflows/ci.yml — runs pytest on push/PR to main

## Architecture decisions
- Cursor-based pagination: base64 JSON {ts, id, dir} encoded cursor, sort direction in cursor
- Concurrent count+data queries via asyncio.gather with two separate sessions
- get_session_factory() dependency so list_events sessions are overridable in tests
- Split liveness/readiness: liveness never touches DB (avoids pool exhaustion from health pings)
- Rate limiting: slowapi, IP-based via get_remote_address, limits in config (ingest/bulk/list/get), custom 429 handler with Retry-After: 60 header
- Global exception handlers: RateLimitExceeded→429, OperationalError→503, IntegrityError→409, Exception→500
- expire_on_commit=False on session factory (avoids extra SELECTs after commit in async)
- Alembic migrations, NOT create_all on startup (race conditions, slow migrations)
- Python 3.12 annotation quirk: use "EventCreate" (quoted) in model_validator return type

## User preferences
- User types files themselves (learning approach) — explain before they type
- User wants production-scale reasoning, not just interview-scale
- User is preparing for DigitalOcean 3-hour live build interview

## Common gotchas encountered
- slowapi headers_enabled=True crashes on Starlette 0.52: call_next returns a streaming wrapper, not a plain Response — _inject_headers raises. Fix: leave headers_enabled at default (False) and set Retry-After manually in the custom handler.
- slowapi rate limit testing: use monkeypatch.setattr(config.settings, "ingest_rate_limit", "3/minute") + lambda: settings.X on the decorator so the limit is dynamic. Reset limiter._limiter.storage between tests via autouse fixture.
- add_logger_name processor incompatible with PrintLoggerFactory (use PrintLoggerFactory without it)
- AsyncSessionLocal bypass: list_events uses session_factory dependency, not get_db
- session_factory() needs () call — async with session_factory() not async with session_factory
- Alembic init alembic must run from project root with venv activated
- .github/workflows/ci.yml path required (not .github/ci.yml)
