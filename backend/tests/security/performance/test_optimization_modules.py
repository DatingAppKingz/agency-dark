"""
Tests for performance optimization modules.

Tests caching strategies, query optimization, and permission evaluation
performance improvements.
"""
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import json
from typing import List

import numpy as np

from models.user import User, UserRole
from models.feature_permission import (
    FeaturePermission, FeatureType, AnalyticsScope, DataSensitivity
)
from core.security.cache_strategies import (
    LRUCache, MultiLayerCache, CacheInvalidator,
    CacheWarmer, CacheSynchronizer
)
from core.security.query_optimization import (
    QueryOptimizationStrategies, QueryResultCache,
    QueryPerformanceAnalyzer, BulkOperationOptimizer
)
from core.security.permission_optimizer import (
    OptimizedPermissionEvaluator, PermissionEvaluationStrategy,
    PermissionIndexer, PermissionDecision
)


class TestLRUCache:
    """Test LRU cache implementation."""
    
    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """Test basic cache operations."""
        cache = LRUCache(max_size=3)
        
        # Test set and get
        await cache.set("key1", "value1", ttl_seconds=60)
        assert await cache.get("key1") == "value1"
        
        # Test miss
        assert await cache.get("nonexistent") is None
        
        # Test stats
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
    
    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test LRU eviction policy."""
        cache = LRUCache(max_size=3)
        
        # Fill cache
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        # Access key1 to make it recently used
        await cache.get("key1")
        
        # Add new key, should evict key2 (least recently used)
        await cache.set("key4", "value4")
        
        assert await cache.get("key1") == "value1"  # Still there
        assert await cache.get("key2") is None  # Evicted
        assert await cache.get("key3") == "value3"  # Still there
        assert await cache.get("key4") == "value4"  # New entry
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Test TTL expiration."""
        cache = LRUCache(max_size=10)
        
        # Set with short TTL
        await cache.set("key1", "value1", ttl_seconds=0.1)
        
        # Should exist immediately
        assert await cache.get("key1") == "value1"
        
        # Wait for expiration
        await asyncio.sleep(0.2)
        
        # Should be expired
        assert await cache.get("key1") is None


class TestMultiLayerCache:
    """Test multi-layer caching system."""
    
    @pytest.mark.asyncio
    async def test_cache_hierarchy(self):
        """Test L1 and L2 cache interaction."""
        cache = MultiLayerCache(l1_max_size=10, l2_ttl_seconds=300)
        
        # Mock Redis for L2
        with patch('core.redis.redis_client') as mock_redis:
            mock_redis.get.return_value = None
            mock_redis.setex.return_value = True
            
            # Set value
            await cache.set("test_key", {"data": "test_value"})
            
            # Get should hit L1
            value = await cache.get("test_key")
            assert value == {"data": "test_value"}
            assert cache.metrics["l1_hits"] == 1
            
            # Clear L1 cache
            await cache.l1_cache.clear()
            
            # Mock L2 hit
            mock_redis.get.return_value = json.dumps({"data": "test_value"})
            
            # Get should hit L2 and populate L1
            value = await cache.get("test_key")
            assert value == {"data": "test_value"}
            assert cache.metrics["l2_hits"] == 1
            
            # Next get should hit L1
            value = await cache.get("test_key")
            assert cache.metrics["l1_hits"] == 2
    
    @pytest.mark.asyncio
    async def test_compression(self):
        """Test data compression in L2 cache."""
        cache = MultiLayerCache(enable_compression=True)
        
        # Large data that benefits from compression
        large_data = {
            "permissions": [
                {"id": str(uuid.uuid4()), "action": "view_report"}
                for _ in range(100)
            ]
        }
        
        with patch('core.redis.redis_client') as mock_redis:
            mock_redis.setex = AsyncMock()
            
            await cache.set("large_key", large_data)
            
            # Verify compression was used (msgpack)
            call_args = mock_redis.setex.call_args[0]
            compressed_data = call_args[2]
            
            # Compressed data should be smaller than JSON
            json_size = len(json.dumps(large_data))
            assert len(compressed_data) < json_size


class TestCacheInvalidation:
    """Test cache invalidation strategies."""
    
    @pytest.mark.asyncio
    async def test_pattern_invalidation(self):
        """Test pattern-based cache invalidation."""
        cache = MultiLayerCache()
        invalidator = CacheInvalidator(cache)
        
        # Set up test data
        await cache.set("perm:user123:reports:view", True)
        await cache.set("perm:user123:reports:export", True)
        await cache.set("perm:user456:reports:view", True)
        
        # Invalidate user123's permissions
        await invalidator.invalidate_user_permissions("user123")
        
        # User123's permissions should be gone
        assert await cache.get("perm:user123:reports:view") is None
        assert await cache.get("perm:user123:reports:export") is None
        
        # User456's permissions should remain
        assert await cache.get("perm:user456:reports:view") is True
    
    @pytest.mark.asyncio
    async def test_dependency_invalidation(self):
        """Test dependency-based invalidation."""
        cache = MultiLayerCache()
        invalidator = CacheInvalidator(cache)
        
        # Register dependencies
        invalidator.register_dependency(
            "derived:*",
            ["source:data1", "source:data2"]
        )
        
        # Set cache values
        await cache.set("source:data1", "value1")
        await cache.set("derived:calc1", "derived_value")
        
        # Invalidate source data
        await invalidator.invalidate("source:data1")
        
        # Derived data should also be invalidated
        assert await cache.get("derived:calc1") is None


class TestQueryOptimization:
    """Test query optimization strategies."""
    
    @pytest.mark.asyncio
    async def test_batch_permission_loading(self):
        """Test batch loading of permissions."""
        mock_db = AsyncMock()
        
        # Create test users
        users = [
            User(id=uuid.uuid4(), email=f"user{i}@test.com")
            for i in range(10)
        ]
        
        # Mock permissions
        all_permissions = []
        for user in users[:5]:  # Only first 5 users have permissions
            for j in range(3):
                perm = FeaturePermission(
                    id=uuid.uuid4(),
                    feature_type=FeatureType.REPORTS,
                    user_id=user.id,
                    allowed_actions=["view_report"]
                )
                all_permissions.append(perm)
        
        # Mock query execution
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = all_permissions
        mock_db.execute.return_value = mock_result
        
        # Batch load permissions
        result = await QueryOptimizationStrategies.batch_load_permissions(
            mock_db, users, FeatureType.REPORTS
        )
        
        # Verify results
        assert len(result) == 10  # All users in result
        
        # First 5 users should have permissions
        for i, user in enumerate(users[:5]):
            assert len(result[str(user.id)]) == 3
        
        # Last 5 users should have no permissions
        for user in users[5:]:
            assert len(result[str(user.id)]) == 0
        
        # Only one query should be executed
        assert mock_db.execute.call_count == 1
    
    @pytest.mark.asyncio
    async def test_query_result_caching(self):
        """Test query result caching."""
        cache = QueryResultCache(ttl_seconds=60)
        mock_db = AsyncMock()
        
        # Mock query and result
        query = MagicMock()
        query.compile.return_value = "SELECT * FROM permissions"
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["perm1", "perm2"]
        mock_db.execute.return_value = mock_result
        
        # First execution - cache miss
        result1 = await cache.get_or_execute(mock_db, query, {"user_id": "123"})
        assert result1 == ["perm1", "perm2"]
        assert mock_db.execute.call_count == 1
        
        # Second execution - cache hit
        result2 = await cache.get_or_execute(mock_db, query, {"user_id": "123"})
        assert result2 == ["perm1", "perm2"]
        assert mock_db.execute.call_count == 1  # No additional query
    
    def test_query_performance_analysis(self):
        """Test query performance analyzer."""
        analyzer = QueryPerformanceAnalyzer()
        
        # Record some query times
        analyzer._record_stats("get_user_permissions", 0.010)  # 10ms
        analyzer._record_stats("get_user_permissions", 0.015)  # 15ms
        analyzer._record_stats("get_user_permissions", 0.150)  # 150ms - slow
        
        # Get stats
        stats = analyzer.query_stats["get_user_permissions"]
        assert stats["count"] == 3
        assert stats["min_time"] == 0.010
        assert stats["max_time"] == 0.150
        assert abs(stats["avg_time"] - 0.058) < 0.001  # ~58ms average
        
        # Check recommendations
        report = analyzer.get_performance_report()
        recommendations = report["recommendations"]
        assert any("get_user_permissions" in r for r in recommendations)


class TestPermissionOptimizer:
    """Test permission evaluation optimization."""
    
    @pytest.mark.asyncio
    async def test_first_match_strategy(self):
        """Test first match evaluation strategy."""
        evaluator = OptimizedPermissionEvaluator(
            strategy=PermissionEvaluationStrategy.FIRST_MATCH
        )
        
        user = User(id=uuid.uuid4(), role=UserRole.MANAGER)
        
        # Create permissions with different priorities
        permissions = [
            FeaturePermission(
                id=uuid.uuid4(),
                priority=10,
                allowed_actions=["view_report"],
                denied_actions=[]
            ),
            FeaturePermission(
                id=uuid.uuid4(),
                priority=5,
                allowed_actions=["*"],  # Wildcard
                denied_actions=[]
            )
        ]
        
        # Should match first permission (higher priority)
        decision = await evaluator.evaluate_permissions(
            user, permissions, "view_report", None
        )
        
        assert decision.allowed is True
        assert decision.permission_id == str(permissions[0].id)
        assert decision.evaluation_time_ms < 10  # Should be fast
    
    @pytest.mark.asyncio
    async def test_most_permissive_strategy(self):
        """Test most permissive evaluation strategy."""
        evaluator = OptimizedPermissionEvaluator(
            strategy=PermissionEvaluationStrategy.MOST_PERMISSIVE
        )
        
        user = User(id=uuid.uuid4(), role=UserRole.MANAGER)
        
        # Create permissions with different permissiveness
        permissions = [
            FeaturePermission(
                id=uuid.uuid4(),
                allowed_actions=["view_report"],
                max_export_rows=1000,
                analytics_scope=AnalyticsScope.OWN
            ),
            FeaturePermission(
                id=uuid.uuid4(),
                allowed_actions=["view_report", "export_report"],
                max_export_rows=10000,
                analytics_scope=AnalyticsScope.AGENCY  # More permissive
            )
        ]
        
        decision = await evaluator.evaluate_permissions(
            user, permissions, "view_report", None
        )
        
        assert decision.allowed is True
        assert decision.permission_id == str(permissions[1].id)  # More permissive one
    
    @pytest.mark.asyncio
    async def test_weighted_strategy(self):
        """Test weighted evaluation strategy."""
        evaluator = OptimizedPermissionEvaluator(
            strategy=PermissionEvaluationStrategy.WEIGHTED
        )
        
        user = User(id=uuid.uuid4(), role=UserRole.MANAGER)
        
        permissions = [
            FeaturePermission(
                id=uuid.uuid4(),
                priority=100,
                allowed_actions=["view_report"],
                denied_actions=[]
            ),
            FeaturePermission(
                id=uuid.uuid4(),
                priority=50,
                allowed_actions=["*"],
                denied_actions=["delete_report"]
            )
        ]
        
        decision = await evaluator.evaluate_permissions(
            user, permissions, "view_report", None
        )
        
        assert decision.allowed is True
        assert "score" in decision.metadata
        assert decision.metadata["score"] > 0
    
    @pytest.mark.asyncio
    async def test_permission_caching(self):
        """Test permission decision caching."""
        evaluator = OptimizedPermissionEvaluator()
        
        user = User(id=uuid.uuid4(), role=UserRole.MANAGER)
        permissions = [
            FeaturePermission(
                id=uuid.uuid4(),
                allowed_actions=["view_report"]
            )
        ]
        
        # First evaluation
        start = time.time()
        decision1 = await evaluator.evaluate_permissions(
            user, permissions, "view_report", None
        )
        first_time = time.time() - start
        
        # Second evaluation (should hit cache)
        start = time.time()
        decision2 = await evaluator.evaluate_permissions(
            user, permissions, "view_report", None
        )
        second_time = time.time() - start
        
        assert decision1.allowed == decision2.allowed
        assert second_time < first_time / 2  # Cache hit should be much faster
        
        # Check metrics
        metrics = evaluator.get_evaluation_metrics()
        assert metrics["cache_hits"] == 1
        assert metrics["cache_hit_rate"] == 0.5


class TestPermissionIndexer:
    """Test permission indexing."""
    
    def test_permission_indexing(self):
        """Test building permission indexes."""
        indexer = PermissionIndexer()
        
        # Create test permissions
        permissions = []
        for i in range(100):
            perm = FeaturePermission(
                id=uuid.uuid4(),
                feature_type=FeatureType.REPORTS if i % 2 == 0 else FeatureType.ANALYTICS,
                allowed_actions=["view", "export"] if i < 50 else ["view"],
                user_id=uuid.uuid4() if i % 3 == 0 else None,
                is_active=i % 10 != 0  # 90% active
            )
            permissions.append(perm)
        
        # Index permissions
        indexer.index_permissions(permissions)
        
        # Test action index
        view_perms = indexer.find_permissions_for_action("view")
        assert len(view_perms) == 90  # All active permissions have "view"
        
        export_perms = indexer.find_permissions_for_action("export")
        assert len(export_perms) == 45  # Half of active permissions have "export"
        
        # Test feature type filtering
        report_export_perms = indexer.find_permissions_for_action(
            "export", feature_type=FeatureType.REPORTS
        )
        assert all(p.feature_type == FeatureType.REPORTS for p in report_export_perms)


class TestPerformanceComparison:
    """Compare optimized vs non-optimized performance."""
    
    @pytest.mark.asyncio
    async def test_evaluation_performance_comparison(self):
        """Compare evaluation performance with different strategies."""
        user = User(id=uuid.uuid4(), role=UserRole.MANAGER)
        
        # Create many permissions
        permissions = []
        for i in range(1000):
            perm = FeaturePermission(
                id=uuid.uuid4(),
                priority=i,
                allowed_actions=["action1", "action2", "action3"],
                denied_actions=["denied1"] if i % 10 == 0 else [],
                requires_mfa=i % 5 == 0
            )
            permissions.append(perm)
        
        # Test different strategies
        strategies = [
            PermissionEvaluationStrategy.FIRST_MATCH,
            PermissionEvaluationStrategy.MOST_PERMISSIVE,
            PermissionEvaluationStrategy.WEIGHTED
        ]
        
        results = {}
        
        for strategy in strategies:
            evaluator = OptimizedPermissionEvaluator(strategy=strategy)
            
            # Warm up
            await evaluator.evaluate_permissions(user, permissions[:10], "action1")
            
            # Time evaluation
            start = time.time()
            for _ in range(100):
                await evaluator.evaluate_permissions(
                    user, permissions, "action2", {"mfa_verified": True}
                )
            duration = time.time() - start
            
            results[strategy.value] = duration
        
        # First match should be fastest
        assert results["first_match"] < results["most_permissive"]
        assert results["first_match"] < results["weighted"]
        
        print(f"Performance results: {results}")


class TestCacheWarming:
    """Test cache warming strategies."""
    
    @pytest.mark.asyncio
    async def test_cache_warmer(self):
        """Test proactive cache warming."""
        cache = MultiLayerCache()
        warmer = CacheWarmer(cache, warm_interval_seconds=0.1)
        
        # Mock active users
        with patch('core.redis.redis_client.smembers') as mock_smembers:
            mock_smembers.return_value = [
                "user123", "user456", "user789"
            ]
            
            # Start warmer
            await warmer.start()
            
            # Let it run one cycle
            await asyncio.sleep(0.2)
            
            # Stop warmer
            await warmer.stop()
            
            # Should have called to get active users
            assert mock_smembers.called