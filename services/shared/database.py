"""
AdsGen 2.0 - Database Connection Module
Async SQLAlchemy setup with PostgreSQL
"""

from functools import lru_cache

from sqlalchemy import create_engine, Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


settings = get_settings()


@lru_cache
def get_sync_engine() -> Engine:
    """
    Get sync engine for Celery workers.
    Cached to avoid creating multiple engine instances.
    """
    sync_url = settings.database_url.replace(
        "+asyncpg", ""
    ).replace(
        "postgresql+asyncpg", "postgresql+psycopg2"
    )
    return create_engine(
        sync_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def get_session() -> AsyncSession:
    """Dependency for FastAPI to get database session."""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    # Import models to ensure they are registered with Base.metadata
    # items are imported locally to avoid circular imports
    from .models.vacancy import Vacancy
    from .models.import_batch import ImportBatch

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
