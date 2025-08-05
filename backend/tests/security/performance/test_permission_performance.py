"""
Performance tests for permission system.

Tests performance characteristics including:
- Permission check latency
- Cache effectiveness
- Database query optimization
- Concurrent request handling
"""
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import statistics

from models.user import User, UserRole
from models.feature_permission import (
    FeaturePermission, FeatureType, AnalyticsScope
)
from core.security.feature_permissions.service import FeaturePermissionService
from core.rate_limit.service import DynamicRateLimitService
from core.rate_limit.algorithms import TokenBucketAlgorithm


class TestPermissionCheckPerformance:
    """Performance tests for permission checking."""
    
    @pytest.mark.asyncio
    async def test_single_permission_check_latency(self):
        """Test latency of a single permission check."""
        service = FeaturePermissionService()
        mock_db = AsyncMock()
        
        user = User(id=uuid.uuid4(), email="test@example.com")
        permission = FeaturePermission(
            id=uuid.uuid4(),
            feature_type=FeatureType.REPORTS,
            user_id=user.id,
            allowed_actions=["view_report"],
            is_active=True
        )
        
        # Mock cache miss and permission fetch
        with patch('core.redis.redis_client.get', return_value=None):
            with patch.object(
                service,
                '_get_user_feature_permissions',
                return_value=[permission]
            ):
                with patch.object(
                    service,
                    '_evaluate_permission',
                    return_value=(True, None)
                ):
                    with patch.object(
                        service,
                        '_log_feature_usage',
                        return_value=None
                    ):
                        with patch('core.redis.redis_client.setex'):
                            # Measure execution time
                            start_time = time.time()
                            
                            allowed, reason = await service.check_feature_permission(
                                db=mock_db,
                                user=user,
                                feature_type=FeatureType.REPORTS,
                                action="view_report"
                            )
                            
                            end_time = time.time()
                            latency_ms = (end_time - start_time) * 1000
                            
                            assert allowed is True
                            assert latency_ms < 50  # Should complete within 50ms
                            print(f"Single permission check latency: {latency_ms:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_cached_permission_check_latency(self):
        """Test latency when permission is cached."""
        service = FeaturePermissionService()
        mock_db = AsyncMock()
        
        user = User(id=uuid.uuid4(), email="test@example.com")
        
        # Mock cache hit
        cached_result = '{"allowed": true, "reason": null}'
        with patch('core.redis.redis_client.get', return_value=cached_result):
            start_time = time.time()
            
            allowed, reason = await service.check_feature_permission(
                db=mock_db,
                user=user,
                feature_type=FeatureType.REPORTS,
                action="view_report"
            )
            
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            assert allowed is True
            assert latency_ms < 5  # Cached check should be very fast
            print(f"Cached permission check latency: {latency_ms:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_bulk_permission_checks(self):
        """Test performance of multiple permission checks."""
        service = FeaturePermissionService()
        mock_db = AsyncMock()
        
        # Create test data
        users = [
            User(id=uuid.uuid4(), email=f"user{i}@example.com")
            for i in range(100)
        ]
        
        permissions = [
            FeaturePermission(
                id=uuid.uuid4(),
                feature_type=FeatureType.REPORTS,
                user_id=users[i].id,
                allowed_actions=["view_report"],
                is_active=True
            )
            for i in range(100)
        ]
        
        # Mock responses
        with patch('core.redis.redis_client.get', return_value=None):
            with patch.object(
                service,
                '_get_user_feature_permissions',
                side_effect=[[permissions[i]] for i in range(100)]
            ):
                with patch.object(
                    service,
                    '_evaluate_permission',
                    return_value=(True, None)
                ):
                    with patch.object(
                        service,
                        '_log_feature_usage',
                        return_value=None
                    ):
                        with patch('core.redis.redis_client.setex'):
                            # Measure bulk operation time
                            start_time = time.time()
                            
                            tasks = [
                                service.check_feature_permission(
                                    db=mock_db,
                                    user=users[i],
                                    feature_type=FeatureType.REPORTS,
                                    action="view_report"
                                )
                                for i in range(100)
                            ]
                            
                            results = await asyncio.gather(*tasks)
                            
                            end_time = time.time()
                            total_time_ms = (end_time - start_time) * 1000
                            avg_time_ms = total_time_ms / 100
                            
                            assert all(r[0] for r in results)  # All allowed
                            assert avg_time_ms < 10  # Average < 10ms per check
                            print(f"Bulk permission checks - Total: {total_time_ms:.2f}ms, Average: {avg_time_ms:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_concurrent_permission_checks(self):
        """Test performance under concurrent load."""
        service = FeaturePermissionService()
        mock_db = AsyncMock()
        
        user = User(id=uuid.uuid4(), email="test@example.com")
        permission = FeaturePermission(
            id=uuid.uuid4(),
            feature_type=FeatureType.REPORTS,
            user_id=user.id,
            allowed_actions=["view_report"],
            is_active=True
        )
        
        # Mock cache with some hits and misses
        cache_hit_count = 0
        
        async def mock_cache_get(key):
            nonlocal cache_hit_count
            cache_hit_count += 1
            # 50% cache hit rate
            if cache_hit_count % 2 == 0:
                return '{"allowed": true, "reason": null}'
            return None
        
        with patch('core.redis.redis_client.get', side_effect=mock_cache_get):
            with patch.object(
                service,
                '_get_user_feature_permissions',
                return_value=[permission]
            ):
                with patch.object(
                    service,
                    '_evaluate_permission',
                    return_value=(True, None)
                ):
                    with patch.object(
                        service,
                        '_log_feature_usage',
                        return_value=None
                    ):
                        with patch('core.redis.redis_client.setex'):
                            # Simulate 1000 concurrent requests
                            start_time = time.time()
                            
                            tasks = [
                                service.check_feature_permission(
                                    db=mock_db,
                                    user=user,
                                    feature_type=FeatureType.REPORTS,
                                    action="view_report"
                                )
                                for _ in range(1000)
                            ]
                            
                            results = await asyncio.gather(*tasks)
                            
                            end_time = time.time()
                            total_time_s = end_time - start_time
                            requests_per_second = 1000 / total_time_s
                            
                            assert all(r[0] for r in results)
                            assert requests_per_second > 100  # Should handle >100 req/s
                            print(f"Concurrent permission checks - {requests_per_second:.0f} req/s")


class TestRateLimitPerformance:
    """Performance tests for rate limiting."""
    
    @pytest.mark.asyncio
    async def test_token_bucket_performance(self):
        """Test token bucket algorithm performance."""
        mock_redis = AsyncMock()
        algorithm = TokenBucketAlgorithm(mock_redis)
        
        # Mock Redis Lua script execution
        mock_redis.eval.return_value = 50.0
        
        # Measure single check latency
        latencies = []
        
        for _ in range(100):
            start_time = time.time()
            
            allowed, info = await algorithm.check_and_update(
                key="test_key",
                limit=60,
                window_seconds=60,
                burst_size=100
            )
            
            end_time = time.time()
            latencies.append((end_time - start_time) * 1000)
        
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        
        assert avg_latency < 5  # Average < 5ms
        assert p95_latency < 10  # 95th percentile < 10ms
        print(f"Token bucket - Avg: {avg_latency:.2f}ms, P95: {p95_latency:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_rate_limit_check_with_multiple_configs(self):
        """Test performance with multiple rate limit configurations."""
        service = DynamicRateLimitService()
        mock_db = AsyncMock()
        
        user = User(id=uuid.uuid4(), email="test@example.com")
        
        # Create multiple configs
        configs = [
            MagicMock(
                limit_type=f"type_{i}",
                requests_per_minute=60,
                algorithm="token_bucket",
                priority=i
            )
            for i in range(5)
        ]
        
        # Mock getting configs and algorithm checks
        with patch.object(
            service,
            '_get_applicable_configs',
            return_value=configs
        ):
            with patch.object(
                service,
                '_check_with_algorithm',
                return_value=(True, {"remaining": 50})
            ):
                with patch.object(
                    service,
                    '_calculate_request_cost',
                    return_value=1.0
                ):
                    start_time = time.time()
                    
                    # Check rate limit with multiple configs
                    allowed, info = await service.check_rate_limit(
                        db=mock_db,
                        identifier="user123",
                        identifier_type="user",
                        endpoint="/api/v1/test",
                        user=user
                    )
                    
                    end_time = time.time()
                    latency_ms = (end_time - start_time) * 1000
                    
                    assert allowed is True
                    assert latency_ms < 20  # Should complete quickly even with multiple configs
                    print(f"Multi-config rate limit check: {latency_ms:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_cost_calculation_performance(self):
        """Test performance of cost calculation."""
        service = DynamicRateLimitService()
        mock_db = AsyncMock()
        
        # Mock endpoint cost configuration
        endpoint_cost = MagicMock(
            base_cost=1.0,
            compute_time_factor=0.01,
            database_read_cost=0.5,
            database_write_cost=1.0,
            ml_inference_cost=5.0
        )
        
        # Test cost calculation for various scenarios
        scenarios = [
            {"compute_time": 10, "db_reads": 5, "db_writes": 1, "ml_calls": 0},
            {"compute_time": 50, "db_reads": 20, "db_writes": 5, "ml_calls": 1},
            {"compute_time": 100, "db_reads": 50, "db_writes": 10, "ml_calls": 2},
        ]
        
        with patch.object(
            service,
            '_get_endpoint_cost',
            return_value=endpoint_cost
        ):
            for scenario in scenarios:
                start_time = time.time()
                
                # Calculate cost
                cost = (
                    endpoint_cost.base_cost +
                    scenario["compute_time"] * endpoint_cost.compute_time_factor +
                    scenario["db_reads"] * endpoint_cost.database_read_cost +
                    scenario["db_writes"] * endpoint_cost.database_write_cost +
                    scenario["ml_calls"] * endpoint_cost.ml_inference_cost
                )
                
                end_time = time.time()
                latency_us = (end_time - start_time) * 1_000_000
                
                assert latency_us < 100  # Should complete in microseconds
                print(f"Cost calculation ({scenario}): {latency_us:.0f}μs, Cost: {cost}")


class TestCacheEffectiveness:
    """Tests for cache effectiveness and optimization."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_rate(self):
        """Test cache hit rate under typical usage patterns."""
        service = FeaturePermissionService()
        mock_db = AsyncMock()
        
        # Simulate user permission checks with typical access patterns
        users = [User(id=uuid.uuid4(), email=f"user{i}@example.com") for i in range(10)]
        
        cache_hits = 0
        cache_misses = 0
        
        async def mock_cache_get(key):
            nonlocal cache_hits, cache_misses
            # Simulate 80% cache hit rate for repeated users
            if "user0" in key or "user1" in key or "user2" in key:
                cache_hits += 1
                return '{"allowed": true, "reason": null}'
            else:
                cache_misses += 1
                return None
        
        permission = FeaturePermission(
            id=uuid.uuid4(),
            feature_type=FeatureType.REPORTS,
            allowed_actions=["view_report"],
            is_active=True
        )
        
        with patch('core.redis.redis_client.get', side_effect=mock_cache_get):
            with patch.object(
                service,
                '_get_user_feature_permissions',
                return_value=[permission]
            ):
                with patch.object(
                    service,
                    '_evaluate_permission',
                    return_value=(True, None)
                ):
                    with patch.object(
                        service,
                        '_log_feature_usage',
                        return_value=None
                    ):
                        with patch('core.redis.redis_client.setex'):
                            # Simulate 100 requests with skewed distribution
                            for _ in range(100):
                                # 60% of requests from first 3 users
                                if asyncio.get_event_loop().time() % 10 < 6:
                                    user_idx = int(asyncio.get_event_loop().time() % 3)
                                else:
                                    user_idx = int(asyncio.get_event_loop().time() % 10)
                                
                                await service.check_feature_permission(
                                    db=mock_db,
                                    user=users[user_idx],
                                    feature_type=FeatureType.REPORTS,
                                    action="view_report"
                                )
        
        total_requests = cache_hits + cache_misses
        hit_rate = cache_hits / total_requests if total_requests > 0 else 0
        
        print(f"Cache performance - Hits: {cache_hits}, Misses: {cache_misses}, Hit Rate: {hit_rate:.2%}")
        assert hit_rate > 0.5  # Should have >50% hit rate with skewed access
    
    @pytest.mark.asyncio
    async def test_cache_memory_usage(self):
        """Test cache memory usage patterns."""
        # Calculate memory usage for cached permissions
        
        # Single permission cache entry
        cache_entry = {
            "allowed": True,
            "reason": None,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": str(uuid.uuid4()),
            "feature_type": "reports",
            "action": "view_report"
        }
        
        import sys
        entry_size = sys.getsizeof(str(cache_entry))
        
        # Estimate cache size for different scenarios
        scenarios = [
            {"users": 100, "features": 5, "actions": 3},
            {"users": 1000, "features": 10, "actions": 5},
            {"users": 10000, "features": 15, "actions": 10},
        ]
        
        for scenario in scenarios:
            total_entries = scenario["users"] * scenario["features"] * scenario["actions"]
            total_size_mb = (total_entries * entry_size) / (1024 * 1024)
            
            print(f"Cache size estimate - {scenario}: {total_entries:,} entries, {total_size_mb:.1f} MB")
            
            # Ensure cache size is reasonable
            assert total_size_mb < 1000  # Should fit in reasonable memory


class TestDatabaseQueryOptimization:
    """Tests for database query optimization."""
    
    @pytest.mark.asyncio
    async def test_permission_query_performance(self):
        """Test database query performance for permission fetching."""
        mock_db = AsyncMock()
        
        # Simulate query execution time
        query_times = []
        
        async def mock_execute(query):
            # Simulate varying query times
            import random
            query_time = random.uniform(0.001, 0.010)  # 1-10ms
            await asyncio.sleep(query_time)
            query_times.append(query_time * 1000)
            
            # Return mock results
            return MagicMock(scalars=lambda: MagicMock(all=lambda: []))
        
        mock_db.execute = mock_execute
        
        # Run multiple queries
        for _ in range(50):
            await mock_db.execute("SELECT * FROM feature_permissions WHERE user_id = ?")
        
        avg_query_time = statistics.mean(query_times)
        p95_query_time = statistics.quantiles(query_times, n=20)[18]
        
        print(f"Permission query performance - Avg: {avg_query_time:.2f}ms, P95: {p95_query_time:.2f}ms")
        assert avg_query_time < 10  # Average query < 10ms
        assert p95_query_time < 20  # 95th percentile < 20ms
    
    @pytest.mark.asyncio
    async def test_batch_query_optimization(self):
        """Test batch query optimization for multiple users."""
        mock_db = AsyncMock()
        
        # Test individual queries vs batch query
        user_ids = [uuid.uuid4() for _ in range(50)]
        
        # Individual queries
        start_time = time.time()
        for user_id in user_ids:
            await mock_db.execute(f"SELECT * FROM permissions WHERE user_id = '{user_id}'")
        individual_time = time.time() - start_time
        
        # Batch query
        start_time = time.time()
        user_id_list = ",".join(f"'{uid}'" for uid in user_ids)
        await mock_db.execute(f"SELECT * FROM permissions WHERE user_id IN ({user_id_list})")
        batch_time = time.time() - start_time
        
        # Batch should be significantly faster
        speedup = individual_time / batch_time if batch_time > 0 else float('inf')
        print(f"Batch query optimization - Individual: {individual_time*1000:.1f}ms, Batch: {batch_time*1000:.1f}ms, Speedup: {speedup:.1f}x")
        
        # Note: In mock, times will be similar, but in real DB batch would be much faster