import pytest
import pytest_asyncio
import subprocess
import time

from app.database import Base, get_db, get_session_factory
from app.main import app
from collections.abc import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.core.container import DockerContainer


@pytest.fixture(scope="session", autouse=True)
def ensure_docker() -> None:
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        result = None

    if result is None or result.returncode != 0:
        pytest.exit("Docker is not running. Start Docker Desktop before running tests.", returncode=1)


@pytest.fixture(scope="session")
def postgres_url(ensure_docker: None) -> Generator[str, None, None]:
    with (
        DockerContainer("postgres:16")
        .with_env("POSTGRES_USER", "postgres")
        .with_env("POSTGRES_PASSWORD", "postgres")
        .with_env("POSTGRES_DB", "events")
        .with_exposed_ports(5432)
    ) as pg:
        for _ in range(30):
            result = pg.exec(["pg_isready", "-U", "postgres"])
            if result.exit_code == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Postgres container did not become ready")

        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        yield f"postgresql+asyncpg://postgres:postgres@{host}:{port}/events"


@pytest_asyncio.fixture
async def client(postgres_url: str) -> AsyncGenerator[AsyncClient, None]:
    engine = create_async_engine(postgres_url, connect_args={"ssl": False})
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_factory] = lambda: session_factory

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
