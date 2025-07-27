"""
Integration tests for cache system.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import (
    cache,
    ModelCache,
    monitor,
    manager
)
from core.cache.model_cache import FanCache
from modules.analytics.cache.analytics_cache import AnalyticsCache
from modules.financial.cache.financial_cache import FinancialCache
from core.domain.models import ModelProfile, User, Agency, UserRole
from modules.financial.domain.models import FinancialTransaction, TransactionType


class TestCacheIntegration:
    
    @pytest.mark.asyncio
    async def test_model_cache_integration(
        self,
        db_session: AsyncSession,
        test_model_profile: ModelProfile
    ):
        """Test model cache with database integration."""
        # Cache model profile
        profile_data = {
            'id': str(test_model_profile.id),
            'agency_id': str(test_model_profile.agency_id),
            'onlyfans_username': test_model_profile.onlyfans_username,
            'display_name': test_model_profile.display_name,
            'total_earnings': float(test_model_profile.total_earnings)
        }
        
        await ModelCache.set_model_profile(
            str(test_model_profile.id),
            profile_data
        )
        
        # Retrieve from cache
        cached = await ModelCache.get_model_profile(str(test_model_profile.id))
        assert cached is not None
        assert cached['id'] == str(test_model_profile.id)
        assert cached['onlyfans_username'] == test_model_profile.onlyfans_username
        
        # Test username lookup
        model_id = await cache.get(
            f"model:username:{test_model_profile.onlyfans_username.lower()}"
        )
        assert model_id == str(test_model_profile.id)
    
    @pytest.mark.asyncio
    async def test_financial_cache_integration(
        self,
        db_session: AsyncSession,
        test_model_profile: ModelProfile
    ):
        """Test financial cache integration."""
        # Set balance
        balance = Decimal("1500.00")
        await FinancialCache.set_balance(
            "model",
            str(test_model_profile.id),
            balance
        )
        
        # Get balance
        cached_balance = await FinancialCache.get_balance(
            "model",
            str(test_model_profile.id)
        )
        assert cached_balance == balance
        
        # Test commission rate caching
        rate = Decimal("0.20")
        await FinancialCache.cache_commission_rate(
            str(test_model_profile.id),
            "subscription",
            rate
        )
        
        cached_rate = await FinancialCache.get_commission_rate(
            str(test_model_profile.id),
            "subscription"
        )
        assert cached_rate == rate
    
    @pytest.mark.asyncio
    async def test_analytics_cache_integration(
        self,
        test_model_profile: ModelProfile
    ):
        """Test analytics cache integration."""
        # Cache model metrics
        metrics = {
            'revenue_today': 250.00,
            'new_subscribers': 5,
            'messages_sent': 45,
            'engagement_rate': 0.75
        }
        
        await AnalyticsCache.set_model_metrics(
            str(test_model_profile.id),
            datetime.utcnow(),
            metrics
        )
        
        # Retrieve metrics
        cached_metrics = await AnalyticsCache.get_model_metrics(
            str(test_model_profile.id),
            datetime.utcnow()
        )
        assert cached_metrics == metrics
        
        # Test cache invalidation
        await AnalyticsCache.invalidate_model_cache(str(test_model_profile.id))
        
        # Should be gone
        cached_metrics = await AnalyticsCache.get_model_metrics(
            str(test_model_profile.id),
            datetime.utcnow()
        )
        assert cached_metrics is None
    
    @pytest.mark.asyncio
    async def test_batch_operations(
        self,
        db_session: AsyncSession,
        test_agency: Agency
    ):
        """Test batch cache operations."""
        # Create multiple models
        model_ids = []
        for i in range(5):
            model = ModelProfile(
                id=uuid4(),
                agency_id=test_agency.id,
                onlyfans_username=f"model_{i}",
                display_name=f"Model {i}"
            )
            db_session.add(model)
            model_ids.append(str(model.id))
        
        await db_session.commit()
        
        # Cache all models
        for model_id in model_ids:
            await ModelCache.set_model_profile(
                model_id,
                {'id': model_id, 'cached': True}
            )
        
        # Batch get
        results = await ModelCache.batch_get_models(model_ids)
        assert len(results) == 5
        assert all(r['cached'] for r in results.values())
        
        # Cache agency model list
        await ModelCache.cache_agency_models(
            str(test_agency.id),
            model_ids
        )
        
        # Retrieve list
        cached_list = await ModelCache.get_agency_models(str(test_agency.id))
        assert set(cached_list) == set(model_ids)
    
    @pytest.mark.asyncio
    async def test_cache_monitoring(self):
        """Test cache monitoring functionality."""
        # Clear stats
        await cache.clear_stats()
        
        # Generate some cache activity
        for i in range(10):
            await cache.set(f"test:monitor:{i}", f"value_{i}")
        
        for i in range(15):
            await cache.get(f"test:monitor:{i}")  # 10 hits, 5 misses
        
        # Check stats
        stats = cache.get_stats()
        assert stats['hits'] == 10
        assert stats['misses'] == 5
        assert stats['sets'] == 10
        assert stats['hit_rate'] == 66.67  # 10/15 * 100
        
        # Test monitor health check
        health = await monitor.get_health_status()
        assert health['status'] in ['healthy', 'degraded']
        assert health['redis_connected'] is True
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_patterns(
        self,
        test_model_profile: ModelProfile
    ):
        """Test cache invalidation patterns."""
        model_id = str(test_model_profile.id)
        
        # Set various cache entries
        await cache.set(f"analytics:model:metrics:{model_id}:2024-01-01", "metrics")
        await cache.set(f"analytics:revenue:summary:{model_id}:today", "revenue")
        await cache.set(f"financial:balance:model:{model_id}", "1000")
        
        # Invalidate analytics cache for model
        await AnalyticsCache.invalidate_model_cache(model_id)
        
        # Analytics keys should be gone
        assert await cache.get(f"analytics:model:metrics:{model_id}:2024-01-01") is None
        assert await cache.get(f"analytics:revenue:summary:{model_id}:today") is None
        
        # Financial keys should remain
        assert await cache.get(f"financial:balance:model:{model_id}") == "1000"
    
    @pytest.mark.asyncio
    async def test_ttl_behavior(self):
        """Test TTL behavior with different cache types."""
        # Short TTL for real-time data
        await cache.set(
            "test:realtime:value",
            "current",
            ttl=timedelta(seconds=1)
        )
        
        # Longer TTL for historical data
        await cache.set(
            "test:historical:value",
            "archived",
            ttl=timedelta(minutes=5)
        )
        
        # Verify both exist
        assert await cache.get("test:realtime:value") == "current"
        assert await cache.get("test:historical:value") == "archived"
        
        # Wait for short TTL to expire
        await asyncio.sleep(1.5)
        
        # Real-time should be gone, historical should remain
        assert await cache.get("test:realtime:value") is None
        assert await cache.get("test:historical:value") == "archived"
    
    @pytest.mark.asyncio
    async def test_cache_key_patterns(self):
        """Test cache key pattern analysis."""
        # Create various key patterns
        patterns = [
            ("model:profile:", 10),
            ("analytics:revenue:", 15),
            ("financial:balance:", 8),
            ("user:permissions:", 12)
        ]
        
        for pattern, count in patterns:
            for i in range(count):
                await cache.set(f"{pattern}{i}", "value")
        
        # Analyze patterns
        key_patterns = await monitor.get_key_patterns()
        
        # Should identify the patterns
        assert "model:profile" in key_patterns
        assert "analytics:revenue" in key_patterns
        assert "financial:balance" in key_patterns
        assert "user:permissions" in key_patterns
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self):
        """Test concurrent cache access."""
        key = "test:concurrent"
        
        async def increment_counter():
            for _ in range(100):
                await cache.increment(key)
        
        # Run multiple concurrent incrementers
        tasks = [increment_counter() for _ in range(10)]
        await asyncio.gather(*tasks)
        
        # Should have correct total
        final_value = await cache.get(key)
        assert int(final_value) == 1000  # 10 tasks * 100 increments
    
    @pytest.mark.asyncio
    async def test_cache_warmup(
        self,
        db_session: AsyncSession,
        test_model_profile: ModelProfile
    ):
        """Test cache warming strategies."""
        # Simulate cache warming for a model
        model_id = str(test_model_profile.id)
        
        # Warm frequently accessed data
        warm_data = {
            f"model:profile:{model_id}": {
                'id': model_id,
                'warmed': True
            },
            f"financial:balance:model:{model_id}": "5000.00",
            f"analytics:revenue:summary:{model_id}:today": {
                'total': 250.00,
                'transactions': 15
            }
        }
        
        # Batch set for warming
        await cache.set_many(warm_data, ttl=timedelta(minutes=30))
        
        # Verify all warmed data is available
        for key in warm_data:
            assert await cache.get(key) is not None
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test cache error handling."""
        # Test with invalid data that might cause serialization issues
        class NonSerializable:
            def __init__(self):
                self.file = open(__file__, 'r')
        
        # Should handle gracefully
        try:
            obj = NonSerializable()
            result = await cache.set("test:error", obj)
            # Close file
            obj.file.close()
        except:
            # Might fail, but should not crash
            pass
        
        # Cache should still be functional
        await cache.set("test:after_error", "works")
        assert await cache.get("test:after_error") == "works"
    
    @pytest.fixture(autouse=True)
    async def cleanup_cache(self):
        """Clean up cache after each test."""
        yield
        # Clean test keys
        await cache.delete_pattern("test:*")
        await cache.delete_pattern("model:*")
        await cache.delete_pattern("analytics:*")
        await cache.delete_pattern("financial:*")
        await cache.delete_pattern("user:*")