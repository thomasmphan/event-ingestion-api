# Event Ingestion API

A production-ready REST API for ingesting and querying events, built with FastAPI, SQLAlchemy 2.0 async, and PostgreSQL.

## Stack

- **FastAPI** — async web framework with auto-generated OpenAPI docs
- **SQLAlchemy 2.0** — async ORM with connection pooling
- **PostgreSQL 16** — primary data store
- **structlog** — structured JSON logging
- **pytest + pytest-asyncio + testcontainers** — async test suite (Postgres via Docker, spun up automatically)

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/events` | Ingest a single event |
| `POST` | `/events/bulk` | Ingest up to 1000 events in one request |
| `GET` | `/events` | List events with filtering and cursor pagination |
| `GET` | `/events/{id}` | Fetch a single event |
| `GET` | `/healthz/live` | Liveness probe (no DB) |
| `GET` | `/healthz/ready` | Readiness probe (checks DB) |

### Query parameters for `GET /events`

| Param | Type | Description |
|-------|------|-------------|
| `event_type` | string | Filter by event type |
| `source` | string | Filter by source |
| `start_time` | ISO8601 | Filter events at or after this time |
| `end_time` | ISO8601 | Filter events at or before this time |
| `limit` | int (1–1000) | Page size, default 100 |
| `sort` | `asc` or `desc` | Sort order by timestamp, default `desc` |
| `cursor` | string | Opaque cursor from previous response for pagination |

## Local Development

```bash
# Install dependencies
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt

# Run tests (requires Docker Desktop running)
pytest -v

# Start with Docker
docker compose up --build
```

Interactive docs available at `http://localhost:8000/docs` once running.

## Database Migrations

Schema changes are managed with Alembic. The database is **not** auto-migrated on startup — migrations must be run explicitly.

**First-time setup** (after `docker compose up`):

```bash
alembic upgrade head
```

**When you change a model** (`app/models.py`):

```bash
# 1. Generate the migration (review the file before applying)
alembic revision --autogenerate -m "describe your change"

# 2. Apply it to the database
alembic upgrade head
```

Commit the generated migration file in `alembic/versions/` alongside the model change. CI/CD applies migrations before starting new containers.

## Environment Variables

Copy `.env.example` to `.env` and adjust values:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/events` | Async Postgres connection string |
| `DEBUG` | `false` | Enables SQLAlchemy query logging |
| `LOG_LEVEL` | `INFO` | structlog log level |