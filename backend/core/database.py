from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import MetaData, event, text, create_engine
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from backend.core.config import settings
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=naming_convention)
Base = declarative_base(metadata=metadata)

if settings.ENVIRONMENT == "test":
    engine = create_async_engine(
        DATABASE_URL,
        echo=settings.DEBUG,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    # Import all models to ensure they're registered with Base
    from .domain.models import *  # noqa: F401
    from backend.modules.analytics.domain.models import *  # noqa: F401
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
        
    logger.info("Database tables created successfully")


async def set_tenant_id(session: AsyncSession, tenant_id: str):
    await session.execute(f"SET app.current_tenant = '{tenant_id}'")


# Sync database for middleware
SYNC_DATABASE_URL = settings.DATABASE_URL
sync_engine = create_engine(SYNC_DATABASE_URL, echo=settings.DEBUG)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


@contextmanager
def get_db_sync():
    """Get sync database session for middleware."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()