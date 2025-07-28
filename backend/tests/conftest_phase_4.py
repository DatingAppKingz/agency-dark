"""
Pytest configuration and fixtures for Phase 4 tests.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
import redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.redis import redis_client


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def test_db(test_engine):
    """Create a test database session."""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.setex = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.exists = AsyncMock(return_value=0)
    mock_client.expire = AsyncMock(return_value=True)
    mock_client.zadd = AsyncMock(return_value=1)
    mock_client.zrange = AsyncMock(return_value=[])
    mock_client.zrem = AsyncMock(return_value=1)
    
    return mock_client


@pytest.fixture
def sample_agency():
    """Create a sample agency for testing."""
    return MagicMock(
        id=uuid4(),
        name="Test Agency",
        subscription_tier="premium",
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return MagicMock(
        id=uuid4(),
        email="test@example.com",
        display_name="Test User",
        is_active=True,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_model():
    """Create a sample model for testing."""
    return MagicMock(
        id=uuid4(),
        username="test_model",
        display_name="Test Model",
        platform="onlyfans",
        is_active=True,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_fan():
    """Create a sample fan for testing."""
    return MagicMock(
        id=uuid4(),
        username="test_fan",
        display_name="Test Fan",
        subscription_status="active",
        total_spent=100.0,
        message_count=10,
        platform_data={"onlyfans": {"user_id": "123456"}},
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_bulk_message():
    """Create a sample bulk message for testing."""
    return {
        "campaign_name": "Test Campaign",
        "message_template": "Hello {{display_name}}!",
        "recipient_filters": {
            "subscription_status": ["active"],
            "spent_min": 50
        },
        "platform": "onlyfans"
    }


@pytest.fixture
def sample_report_template():
    """Create a sample report template for testing."""
    return {
        "name": "Test Report",
        "description": "Test report template",
        "report_type": "revenue",
        "layout": {"columns": 2, "rows": 2},
        "widgets": [
            {
                "type": "metric",
                "title": "Total Revenue",
                "config": {"metric_type": "revenue"},
                "position": 0,
                "size": "medium"
            },
            {
                "type": "chart",
                "title": "Revenue Trend",
                "config": {"chart_type": "line", "data_source": "revenue"},
                "position": 1,
                "size": "large"
            }
        ]
    }


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    return {
        "choices": [{
            "message": {
                "content": json.dumps([
                    {
                        "response": "Thanks for your message!",
                        "tone": "friendly",
                        "intent": "acknowledgment"
                    },
                    {
                        "response": "I appreciate your support!",
                        "tone": "grateful",
                        "intent": "appreciation"
                    }
                ])
            }
        }]
    }


@pytest.fixture
def mock_platform_api():
    """Mock platform API client."""
    mock_api = MagicMock()
    mock_api.send_message = AsyncMock(return_value={"success": True, "message_id": "123"})
    mock_api.get_fans = AsyncMock(return_value=[])
    mock_api.get_messages = AsyncMock(return_value=[])
    return mock_api


# Cleanup fixtures
@pytest.fixture(autouse=True)
async def cleanup_redis(mock_redis):
    """Cleanup Redis after each test."""
    yield
    # Clear any test data
    await mock_redis.flushdb()


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    # Reset any singleton services if needed
    yield


# Test data generators
def generate_fans(count: int, **kwargs):
    """Generate test fan data."""
    fans = []
    for i in range(count):
        fan = {
            "id": uuid4(),
            "username": f"fan_{i}",
            "display_name": f"Fan {i}",
            "subscription_status": kwargs.get("subscription_status", "active"),
            "total_spent": kwargs.get("base_spent", 100) + (i * 10),
            "message_count": i * 2,
            "created_at": datetime.utcnow() - timedelta(days=i)
        }
        fans.append(fan)
    return fans


def generate_transactions(count: int, **kwargs):
    """Generate test transaction data."""
    transactions = []
    for i in range(count):
        transaction = {
            "id": uuid4(),
            "amount": kwargs.get("base_amount", 50) + (i * 5),
            "type": kwargs.get("type", "tip"),
            "status": "completed",
            "created_at": datetime.utcnow() - timedelta(days=i)
        }
        transactions.append(transaction)
    return transactions


def generate_messages(count: int, **kwargs):
    """Generate test message data."""
    messages = []
    for i in range(count):
        message = {
            "id": uuid4(),
            "content": f"Test message {i}",
            "sender_type": kwargs.get("sender_type", "fan"),
            "created_at": datetime.utcnow() - timedelta(hours=i)
        }
        messages.append(message)
    return messages


# Async helpers
async def create_test_data(db: AsyncSession, data_type: str, count: int):
    """Create test data in the database."""
    if data_type == "fans":
        data = generate_fans(count)
    elif data_type == "transactions":
        data = generate_transactions(count)
    elif data_type == "messages":
        data = generate_messages(count)
    else:
        raise ValueError(f"Unknown data type: {data_type}")
    
    # Add to database
    for item in data:
        db.add(item)
    
    await db.commit()
    return data


# Performance testing helpers
class PerformanceTimer:
    """Context manager for timing operations."""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.utcnow()
        duration = (self.end_time - self.start_time).total_seconds()
        print(f"\n{self.name} took {duration:.3f} seconds")
    
    @property
    def duration(self):
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


# Mock external services
@pytest.fixture
def mock_external_services(mock_redis, mock_platform_api, mock_openai_response):
    """Mock all external services."""
    with patch('core.redis.redis_client', mock_redis):
        with patch('modules.messaging.infrastructure.platform_api', mock_platform_api):
            with patch('openai.ChatCompletion.create', return_value=mock_openai_response):
                yield