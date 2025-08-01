"""Synchronous database helpers for Celery tasks."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager

from core.config import settings


# Create async engine for Celery tasks
celery_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,  # Don't use connection pooling in Celery workers
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    celery_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_db_sync() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for use in Celery tasks."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_celery_db():
    """Initialize database for Celery tasks."""
    # Test connection
    async with celery_engine.begin() as conn:
        await conn.execute("SELECT 1")


async def close_celery_db():
    """Close database connections for Celery tasks."""
    await celery_engine.dispose()