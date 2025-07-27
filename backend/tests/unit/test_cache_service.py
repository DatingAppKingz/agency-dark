"""
Unit tests for cache service.
"""
import pytest
import asyncio
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel

from core.cache.cache_service import (
    CacheService,
    CacheKey,
    CacheSerializer,
    cached,
    cache_invalidate
)


class TestModel(BaseModel):
    """Test model for serialization."""
    id: str
    name: str
    value: Decimal


class TestCacheService:
    
    @pytest.fixture
    async def cache_service(self, redis_client):
        """Create cache service instance."""
        service = CacheService(redis_client)
        yield service
        # Clean up
        await redis_client.flushdb()
    
    @pytest.mark.asyncio
    async def test_set_and_get_string(self, cache_service):
        """Test setting and getting string values."""
        key = "test:string"
        value = "test_value"
        
        # Set value
        result = await cache_service.set(key, value)
        assert result is True
        
        # Get value
        retrieved = await cache_service.get(key)
        assert retrieved == value
    
    @pytest.mark.asyncio
    async def test_set_and_get_dict(self, cache_service):
        """Test setting and getting dictionary values."""
        key = "test:dict"
        value = {"name": "test", "count": 42, "active": True}
        
        # Set value
        result = await cache_service.set(key, value)
        assert result is True
        
        # Get value
        retrieved = await cache_service.get(key)
        assert retrieved == value
    
    @pytest.mark.asyncio
    async def test_set_and_get_model(self, cache_service):
        """Test setting and getting Pydantic model."""
        key = "test:model"
        value = TestModel(
            id=str(uuid4()),
            name="Test Model",
            value=Decimal("123.45")
        )
        
        # Set value
        result = await cache_service.set(key, value)
        assert result is True
        
        # Get value with model class
        retrieved = await cache_service.get(key, TestModel)
        assert isinstance(retrieved, TestModel)
        assert retrieved.id == value.id
        assert retrieved.name == value.name
        assert retrieved.value == value.value
    
    @pytest.mark.asyncio
    async def test_ttl(self, cache_service):
        """Test TTL functionality."""
        key = "test:ttl"
        value = "expires_soon"
        
        # Set with 1 second TTL
        await cache_service.set(key, value, ttl=1)
        
        # Should exist immediately
        retrieved = await cache_service.get(key)
        assert retrieved == value
        
        # Wait for expiry
        await asyncio.sleep(1.5)
        
        # Should be gone
        retrieved = await cache_service.get(key)
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_delete(self, cache_service):
        """Test delete functionality."""
        key = "test:delete"
        await cache_service.set(key, "value")
        
        # Verify it exists
        assert await cache_service.get(key) == "value"
        
        # Delete it
        deleted = await cache_service.delete(key)
        assert deleted == 1
        
        # Verify it's gone
        assert await cache_service.get(key) is None
    
    @pytest.mark.asyncio
    async def test_delete_multiple(self, cache_service):
        """Test deleting multiple keys."""
        keys = ["test:del1", "test:del2", "test:del3"]
        for key in keys:
            await cache_service.set(key, "value")
        
        # Delete all
        deleted = await cache_service.delete(keys)
        assert deleted == 3
        
        # Verify all are gone
        for key in keys:
            assert await cache_service.get(key) is None
    
    @pytest.mark.asyncio
    async def test_delete_pattern(self, cache_service):
        """Test pattern-based deletion."""
        # Set multiple keys
        await cache_service.set("test:pattern:1", "value1")
        await cache_service.set("test:pattern:2", "value2")
        await cache_service.set("test:other:1", "value3")
        
        # Delete by pattern
        deleted = await cache_service.delete_pattern("test:pattern:*")
        assert deleted == 2
        
        # Verify correct keys deleted
        assert await cache_service.get("test:pattern:1") is None
        assert await cache_service.get("test:pattern:2") is None
        assert await cache_service.get("test:other:1") == "value3"
    
    @pytest.mark.asyncio
    async def test_get_many(self, cache_service):
        """Test getting multiple values."""
        # Set multiple values
        data = {
            "test:many:1": "value1",
            "test:many:2": "value2",
            "test:many:3": "value3"
        }
        
        for key, value in data.items():
            await cache_service.set(key, value)
        
        # Get all at once
        keys = list(data.keys())
        result = await cache_service.get_many(keys)
        
        assert result == data
    
    @pytest.mark.asyncio
    async def test_set_many(self, cache_service):
        """Test setting multiple values."""
        data = {
            "test:setmany:1": "value1",
            "test:setmany:2": {"nested": "data"},
            "test:setmany:3": 42
        }
        
        # Set all at once
        result = await cache_service.set_many(data, ttl=60)
        assert result is True
        
        # Verify all were set
        for key, expected in data.items():
            value = await cache_service.get(key)
            assert value == expected
    
    @pytest.mark.asyncio
    async def test_increment(self, cache_service):
        """Test increment functionality."""
        key = "test:counter"
        
        # First increment creates key
        result = await cache_service.increment(key)
        assert result == 1
        
        # Subsequent increments
        result = await cache_service.increment(key, 5)
        assert result == 6
        
        result = await cache_service.increment(key, -2)
        assert result == 4
    
    @pytest.mark.asyncio
    async def test_get_or_set(self, cache_service):
        """Test get_or_set functionality."""
        key = "test:get_or_set"
        call_count = 0
        
        async def factory():
            nonlocal call_count
            call_count += 1
            return f"computed_value_{call_count}"
        
        # First call should compute
        result = await cache_service.get_or_set(key, factory, ttl=60)
        assert result == "computed_value_1"
        assert call_count == 1
        
        # Second call should use cache
        result = await cache_service.get_or_set(key, factory, ttl=60)
        assert result == "computed_value_1"
        assert call_count == 1  # Factory not called again
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, cache_service):
        """Test cache statistics."""
        # Clear stats first
        await cache_service.clear_stats()
        
        # Generate some activity
        await cache_service.set("test:stats:1", "value")
        await cache_service.get("test:stats:1")  # Hit
        await cache_service.get("test:stats:2")  # Miss
        await cache_service.delete("test:stats:1")
        
        # Check stats
        stats = cache_service.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['sets'] == 1
        assert stats['deletes'] == 1
        assert stats['total_requests'] == 2
        assert stats['hit_rate'] == 50.0


class TestCacheKey:
    
    def test_simple_key_generation(self):
        """Test simple cache key generation."""
        key = CacheKey.generate("test", "user", "123")
        assert "test" in key
        assert "user" in key
        assert "123" in key
    
    def test_key_with_kwargs(self):
        """Test key generation with keyword arguments."""
        key = CacheKey.generate(
            "test",
            "prefix",
            user_id="123",
            role="admin"
        )
        assert "test" in key
        assert "prefix" in key
        assert "user_id:123" in key
        assert "role:admin" in key
    
    def test_key_with_model(self):
        """Test key generation with Pydantic model."""
        model = TestModel(
            id="test_id",
            name="Test",
            value=Decimal("100")
        )
        
        key = CacheKey.generate("test", model)
        # Should contain JSON representation
        assert "test_id" in key
    
    def test_long_key_hashing(self):
        """Test that long keys are hashed."""
        # Create a very long key
        long_arg = "x" * 1000
        key = CacheKey.generate("test", long_arg)
        
        # Should be shortened with hash
        assert len(key) < 200


class TestCacheSerializer:
    
    def test_serialize_string(self):
        """Test string serialization."""
        value = "test_string"
        serialized = CacheSerializer.serialize(value)
        assert isinstance(serialized, bytes)
        
        deserialized = CacheSerializer.deserialize(serialized)
        assert deserialized == value
    
    def test_serialize_dict(self):
        """Test dictionary serialization."""
        value = {"key": "value", "number": 42}
        serialized = CacheSerializer.serialize(value)
        
        deserialized = CacheSerializer.deserialize(serialized)
        assert deserialized == value
    
    def test_serialize_model(self):
        """Test Pydantic model serialization."""
        value = TestModel(
            id="123",
            name="Test",
            value=Decimal("99.99")
        )
        serialized = CacheSerializer.serialize(value)
        
        deserialized = CacheSerializer.deserialize(serialized, TestModel)
        assert isinstance(deserialized, TestModel)
        assert deserialized.id == value.id
        assert deserialized.value == value.value


class TestCacheDecorators:
    
    @pytest.mark.asyncio
    async def test_cached_decorator(self, redis_client):
        """Test @cached decorator."""
        call_count = 0
        
        @cached(prefix="test", ttl=60)
        async def expensive_function(x: int, y: int) -> int:
            nonlocal call_count
            call_count += 1
            return x + y
        
        # First call computes
        result = await expensive_function(2, 3)
        assert result == 5
        assert call_count == 1
        
        # Second call uses cache
        result = await expensive_function(2, 3)
        assert result == 5
        assert call_count == 1
        
        # Different args compute again
        result = await expensive_function(3, 4)
        assert result == 7
        assert call_count == 2
        
        # Clean up
        await redis_client.flushdb()
    
    @pytest.mark.asyncio
    async def test_cache_invalidate_decorator(self, redis_client):
        """Test @cache_invalidate decorator."""
        # Set some cache values
        cache = CacheService(redis_client)
        await cache.set("test:invalidate:1", "value1")
        await cache.set("test:invalidate:2", "value2")
        await cache.set("test:other:1", "value3")
        
        @cache_invalidate(prefix="test:invalidate", 
                         key_func=lambda: "test:invalidate:*")
        async def update_function():
            return "updated"
        
        # Call function
        result = await update_function()
        assert result == "updated"
        
        # Check cache was invalidated
        assert await cache.get("test:invalidate:1") is None
        assert await cache.get("test:invalidate:2") is None
        assert await cache.get("test:other:1") == "value3"
        
        # Clean up
        await redis_client.flushdb()


@pytest.fixture
async def redis_client():
    """Create test Redis client."""
    from redis.asyncio import Redis
    from core.config import settings
    
    # Use a test database
    client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        db=15  # Use separate DB for tests
    )
    
    yield client
    
    # Clean up
    await client.flushdb()
    await client.close()