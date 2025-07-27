"""
Pytest configuration for financial module tests.
"""
import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from core.database import Base
from core.domain.models import User, Agency, ModelProfile
from modules.financial.domain.models import (
    BillingCycle,
    CryptoWallet,
    CryptoNetwork,
    CommissionRule,
    CommissionTier
)


@pytest.fixture(scope="function")
async def async_engine():
    """Create async test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=NullPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(async_engine):
    """Create async database session for tests."""
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_agency(db_session):
    """Create a test agency."""
    agency = Agency(
        id=uuid4(),
        name="Test Agency",
        domain="test.agency.com",
        settings={},
        created_at=datetime.utcnow()
    )
    db_session.add(agency)
    await db_session.commit()
    return agency


@pytest.fixture
async def test_user(db_session, test_agency):
    """Create a test user."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        role="agency_owner",
        agency_id=test_agency.id,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def test_model_user(db_session, test_agency):
    """Create a test model user."""
    user = User(
        id=uuid4(),
        email="model@example.com",
        username="testmodel",
        full_name="Test Model",
        role="model",
        agency_id=test_agency.id,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def test_model_profile(db_session, test_model_user, test_agency):
    """Create a test model profile."""
    profile = ModelProfile(
        id=uuid4(),
        user_id=test_model_user.id,
        agency_id=test_agency.id,
        display_name="Test Model",
        bio="Test bio",
        created_at=datetime.utcnow()
    )
    db_session.add(profile)
    await db_session.commit()
    return profile


@pytest.fixture
async def test_billing_cycle(db_session, test_agency):
    """Create a test billing cycle."""
    cycle = BillingCycle(
        id=uuid4(),
        agency_id=test_agency.id,
        cycle_start=datetime.utcnow(),
        cycle_end=datetime.utcnow(),
        is_closed=False,
        total_revenue=Decimal("0.00"),
        total_commission=Decimal("0.00"),
        created_at=datetime.utcnow()
    )
    db_session.add(cycle)
    await db_session.commit()
    return cycle


@pytest.fixture
async def test_crypto_wallet(db_session, test_model_user):
    """Create a test crypto wallet."""
    wallet = CryptoWallet(
        id=uuid4(),
        user_id=test_model_user.id,
        network=CryptoNetwork.ETHEREUM,
        address="0x1234567890123456789012345678901234567890",
        label="Test Wallet",
        is_verified=True,
        is_active=True,
        is_default=True,
        created_at=datetime.utcnow()
    )
    db_session.add(wallet)
    await db_session.commit()
    return wallet


@pytest.fixture
async def test_commission_rule(db_session, test_agency):
    """Create a test commission rule."""
    rule = CommissionRule(
        id=uuid4(),
        agency_id=test_agency.id,
        tier=CommissionTier.TIER_1,
        rate=Decimal("70.00"),
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(rule)
    await db_session.commit()
    return rule