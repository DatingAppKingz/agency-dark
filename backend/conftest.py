"""
Global pytest configuration and fixtures
"""
import pytest
import asyncio
from typing import Generator, AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import os
from pathlib import Path
import sys

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import settings and base
from core.config import Settings
from core.database import Base

# Override database URL for tests
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/agencydark_test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,  # Disable pooling for tests
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="session")
def test_settings():
    """Get test settings."""
    settings = Settings()
    settings.TESTING = True
    settings.DATABASE_URL = TEST_DATABASE_URL
    return settings

@pytest.fixture
def mock_redis(monkeypatch):
    """Mock Redis client for tests."""
    class MockRedis:
        def __init__(self):
            self.data = {}
            self.expires = {}
        
        def get(self, key):
            return self.data.get(key)
        
        def set(self, key, value, ex=None):
            self.data[key] = value
            if ex:
                self.expires[key] = ex
            return True
        
        def delete(self, key):
            self.data.pop(key, None)
            self.expires.pop(key, None)
            return 1
        
        def exists(self, key):
            return key in self.data
        
        def incr(self, key):
            val = int(self.data.get(key, 0)) + 1
            self.data[key] = str(val)
            return val
        
        def expire(self, key, seconds):
            if key in self.data:
                self.expires[key] = seconds
                return True
            return False
        
        def pipeline(self):
            return self
        
        def execute(self):
            return []
        
        def zremrangebyscore(self, key, min_score, max_score):
            return 0
        
        def zadd(self, key, mapping):
            return len(mapping)
        
        def zcard(self, key):
            return 0
    
    mock = MockRedis()
    monkeypatch.setattr("redis.Redis", lambda **kwargs: mock)
    return mock