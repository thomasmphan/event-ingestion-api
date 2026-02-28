from app.config import settings
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,        # max persistent connections
    max_overflow=20,     # extra connections allowed under burst load
    pool_timeout=30,     # seconds to wait for a connection before erroring
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return AsyncSessionLocal
