"""
Pytest configuration and fixtures.
"""
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from httpx import AsyncClient
import uuid
from datetime import datetime

from backend.core.database import Base
from backend.core.config import settings
from backend.main import app
from backend.core.dependencies import get_db
from backend.modules.auth.domain.models import User, Agency, UserRole
from backend.modules.auth.application.auth_service import AuthService
from backend.core.security import get_password_hash


# Test database URL
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace("/agencydark", "/agencydark_test")


# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_agency(db_session: AsyncSession) -> Agency:
    """Create a test agency."""
    agency = Agency(
        id=uuid.uuid4(),
        name="Test Agency",
        domain="test-agency",
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(agency)
    await db_session.commit()
    await db_session.refresh(agency)
    return agency


@pytest.fixture
async def test_user(db_session: AsyncSession, test_agency: Agency) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("testpassword"),
        agency_id=test_agency.id,
        role=UserRole.AGENCY_ADMIN,
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict:
    """Get authentication headers for test user."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def super_admin_user(db_session: AsyncSession, test_agency: Agency) -> User:
    """Create a super admin user."""
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        username="admin",
        hashed_password=get_password_hash("adminpassword"),
        agency_id=test_agency.id,
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def model_user(db_session: AsyncSession, test_agency: Agency) -> User:
    """Create a model user."""
    user = User(
        id=uuid.uuid4(),
        email="model@example.com",
        username="modeluser",
        hashed_password=get_password_hash("modelpassword"),
        agency_id=test_agency.id,
        role=UserRole.MODEL,
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def chatter_user(db_session: AsyncSession, test_agency: Agency) -> User:
    """Create a chatter user."""
    user = User(
        id=uuid.uuid4(),
        email="chatter@example.com",
        username="chatteruser",
        hashed_password=get_password_hash("chatterpassword"),
        agency_id=test_agency.id,
        role=UserRole.CHATTER,
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user