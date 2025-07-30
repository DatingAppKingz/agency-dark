from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import MetaData, event, text, create_engine
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from core.config import settings
from core.database_pool import DatabasePoolConfig, pool_manager
import logging
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)

# Use the DATABASE_URL directly from settings
DATABASE_URL = settings.DATABASE_URL

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=naming_convention)
Base = declarative_base(metadata=metadata)

# Use optimized pool configuration for async engine
engine = create_async_engine(
    DATABASE_URL,
    **DatabasePoolConfig.get_async_pool_config()
)

# Initialize pool manager for advanced use cases
# NOTE: This needs to be done inside an async context, not at module level
# import asyncio
# asyncio.create_task(pool_manager.initialize(DATABASE_URL))

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """Get database session for general use"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_read_db() -> AsyncSession:
    """Get database session optimized for read operations"""
    read_engine = pool_manager.get_engine("read")
    async_session = async_sessionmaker(
        read_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_analytics_db() -> AsyncSession:
    """Get database session optimized for analytics queries"""
    analytics_engine = pool_manager.get_engine("analytics")
    async_session = async_sessionmaker(
        analytics_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables():
    # Import all models to ensure they're registered with Base
    from core.domain import models as auth_models  # noqa: F401
    # from modules.models.domain import models as model_models  # noqa: F401
    # from modules.fans.domain import models as fan_models  # noqa: F401
    from modules.analytics.domain import models as analytics_models  # noqa: F401
    from modules.financial.domain import models as financial_models  # noqa: F401
    from modules.whitelabel.domain import models as whitelabel_models  # noqa: F401
    
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