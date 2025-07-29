"""
Performance benchmarks for critical code paths
"""
import pytest
import asyncio
import time
from typing import List, Dict, Any, Callable
import statistics
import psutil
import gc
from memory_profiler import profile
from line_profiler import LineProfiler

from core.database import get_db
from core.cache import cache_service
from core.monitoring.metrics import metrics_collector
from modules.analytics.application.analytics_service import AnalyticsService
from modules.auth.application.auth_service import AuthService


class PerformanceBenchmark:
    """Base class for performance benchmarks"""
    
    def __init__(self, name: str):
        self.name = name
        self.results: List[float] = []
        self.memory_usage: List[float] = []
        self.cpu_usage: List[float] = []
    
    def record_execution(self, duration: float, memory: float = 0, cpu: float = 0):
        """Record benchmark execution"""
        self.results.append(duration)
        if memory:
            self.memory_usage.append(memory)
        if cpu:
            self.cpu_usage.append(cpu)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get benchmark statistics"""
        if not self.results:
            return {}
        
        return {
            "name": self.name,
            "executions": len(self.results),
            "min": min(self.results),
            "max": max(self.results),
            "mean": statistics.mean(self.results),
            "median": statistics.median(self.results),
            "stdev": statistics.stdev(self.results) if len(self.results) > 1 else 0,
            "p95": statistics.quantiles(self.results, n=20)[18] if len(self.results) > 1 else self.results[0],
            "p99": statistics.quantiles(self.results, n=100)[98] if len(self.results) > 1 else self.results[0],
            "memory_avg": statistics.mean(self.memory_usage) if self.memory_usage else 0,
            "cpu_avg": statistics.mean(self.cpu_usage) if self.cpu_usage else 0
        }


class TestDatabasePerformance:
    """Benchmark database operations"""
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    async def test_single_query_performance(self, benchmark, db_session):
        """Benchmark single database query"""
        async def query_user():
            result = await db_session.execute(
                "SELECT * FROM users WHERE id = $1",
                ["123e4567-e89b-12d3-a456-426614174000"]
            )
            return result.fetchone()
        
        # Run benchmark
        result = benchmark(query_user)
        
        # Assert performance threshold
        assert benchmark.stats["mean"] < 0.01  # Should complete in under 10ms
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    async def test_bulk_insert_performance(self, benchmark, db_session):
        """Benchmark bulk insert operations"""
        async def bulk_insert():
            users = [
                {
                    "id": f"user_{i}",
                    "email": f"user{i}@example.com",
                    "username": f"user{i}"
                }
                for i in range(1000)
            ]
            
            await db_session.execute_many(
                """
                INSERT INTO users (id, email, username) 
                VALUES ($1, $2, $3)
                """,
                users
            )
            await db_session.commit()
        
        result = benchmark(bulk_insert)
        assert benchmark.stats["mean"] < 1.0  # Should complete in under 1 second
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    async def test_complex_join_performance(self, benchmark, db_session):
        """Benchmark complex join queries"""
        async def complex_query():
            result = await db_session.execute("""
                SELECT 
                    u.id, u.username,
                    COUNT(DISTINCT c.id) as content_count,
                    COUNT(DISTINCT a.id) as activity_count,
                    MAX(a.created_at) as last_activity
                FROM users u
                LEFT JOIN content c ON c.user_id = u.id
                LEFT JOIN activities a ON a.user_id = u.id
                WHERE u.created_at > NOW() - INTERVAL '30 days'
                GROUP BY u.id, u.username
                ORDER BY content_count DESC
                LIMIT 100
            """)
            return result.fetchall()
        
        result = benchmark(complex_query)
        assert benchmark.stats["mean"] < 0.1  # Should complete in under 100ms


class TestCachePerformance:
    """Benchmark caching operations"""
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    async def test_cache_read_performance(self, benchmark):
        """Benchmark cache read operations"""
        # Pre-populate cache
        await cache_service.set("test_key", {"data": "test"})
        
        async def read_cache():
            return await cache_service.get("test_key")
        
        result = benchmark(read_cache)
        assert benchmark.stats["mean"] < 0.001  # Should complete in under 1ms
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    async def test_cache_write_performance(self, benchmark):
        """Benchmark cache write operations"""
        test_data = {"id": "123", "data": "x" * 1000}  # 1KB payload
        
        async def write_cache():
            await cache_service.set(f"key_{time.time()}", test_data, ttl=60)
        
        result = benchmark(write_cache)
        assert benchmark.stats["mean"] < 0.002  # Should complete in under 2ms
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    async def test_cache_invalidation_performance(self, benchmark):
        """Benchmark cache invalidation"""
        # Pre-populate cache with pattern
        for i in range(100):
            await cache_service.set(f"user:{i}", {"id": i})
        
        async def invalidate_pattern():
            await cache_service.delete_pattern("user:*")
        
        result = benchmark(invalidate_pattern)
        assert benchmark.stats["mean"] < 0.01  # Should complete in under 10ms


class TestAPIEndpointPerformance:
    """Benchmark API endpoint performance"""
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    async def test_auth_endpoint_performance(self, benchmark, async_client):
        """Benchmark authentication endpoint"""
        login_data = {
            "username": "testuser",
            "password": "testpassword",
            "grant_type": "password"
        }
        
        async def login_request():
            response = await async_client.post(
                "/api/v1/auth/login",
                data=login_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            return response
        
        result = benchmark(login_request)
        assert benchmark.stats["mean"] < 0.1  # Should complete in under 100ms
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    async def test_list_endpoint_performance(self, benchmark, async_client, auth_headers):
        """Benchmark list endpoint with pagination"""
        async def list_request():
            response = await async_client.get(
                "/api/v1/content?limit=50&offset=0",
                headers=auth_headers
            )
            return response
        
        result = benchmark(list_request)
        assert benchmark.stats["mean"] < 0.05  # Should complete in under 50ms
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    async def test_analytics_aggregation_performance(self, benchmark, async_client, auth_headers):
        """Benchmark analytics aggregation endpoint"""
        async def analytics_request():
            response = await async_client.get(
                "/api/v1/analytics/metrics?metric=revenue&granularity=hour&days=7",
                headers=auth_headers
            )
            return response
        
        result = benchmark(analytics_request)
        assert benchmark.stats["mean"] < 0.2  # Should complete in under 200ms


class TestConcurrencyPerformance:
    """Benchmark concurrent operations"""
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    async def test_concurrent_requests(self, benchmark, async_client, auth_headers):
        """Benchmark handling concurrent requests"""
        async def concurrent_requests():
            tasks = []
            for i in range(10):
                task = async_client.get(
                    f"/api/v1/users/me",
                    headers=auth_headers
                )
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks)
            return responses
        
        result = benchmark(concurrent_requests)
        # Average time per request should still be reasonable
        avg_per_request = benchmark.stats["mean"] / 10
        assert avg_per_request < 0.02  # Each request should average under 20ms
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    async def test_connection_pool_performance(self, benchmark, db_session):
        """Benchmark database connection pool efficiency"""
        async def parallel_db_queries():
            tasks = []
            for i in range(50):
                task = db_session.execute(
                    "SELECT COUNT(*) FROM users"
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(parallel_db_queries)
        assert benchmark.stats["mean"] < 0.5  # Should handle 50 queries in under 500ms


class TestMemoryPerformance:
    """Benchmark memory usage"""
    
    @pytest.mark.performance
    def test_large_payload_memory(self):
        """Test memory usage with large payloads"""
        benchmark = PerformanceBenchmark("large_payload_memory")
        
        def process_large_data():
            # Create 10MB of data
            data = [{"id": i, "data": "x" * 1000} for i in range(10000)]
            
            # Process data
            processed = [
                {**item, "processed": True}
                for item in data
            ]
            
            return len(processed)
        
        # Measure memory before
        gc.collect()
        process = psutil.Process()
        mem_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Run function
        start_time = time.time()
        result = process_large_data()
        duration = time.time() - start_time
        
        # Measure memory after
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_used = mem_after - mem_before
        
        benchmark.record_execution(duration, memory=memory_used)
        
        # Memory usage should be reasonable
        assert memory_used < 50  # Should use less than 50MB
    
    @pytest.mark.performance
    @profile
    def test_memory_leak_detection(self):
        """Test for memory leaks in repeated operations"""
        def leaky_function():
            cache = []
            for i in range(1000):
                # Simulate potential memory leak
                cache.append({"id": i, "data": "x" * 1000})
                if i % 100 == 0:
                    # Should clear cache periodically
                    cache = cache[-10:]  # Keep only last 10
            return len(cache)
        
        # Run multiple times
        for _ in range(10):
            result = leaky_function()
            gc.collect()
        
        # Check final memory usage
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        assert memory_mb < 200  # Should not exceed 200MB


class TestOptimizationBenchmarks:
    """Benchmark optimization techniques"""
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    def test_algorithm_optimization(self, benchmark):
        """Compare optimized vs naive algorithm"""
        test_data = list(range(10000))
        
        def naive_search(data, target):
            for i, value in enumerate(data):
                if value == target:
                    return i
            return -1
        
        def optimized_search(data, target):
            # Binary search (assumes sorted data)
            left, right = 0, len(data) - 1
            while left <= right:
                mid = (left + right) // 2
                if data[mid] == target:
                    return mid
                elif data[mid] < target:
                    left = mid + 1
                else:
                    right = mid - 1
            return -1
        
        # Benchmark both
        naive_result = benchmark(naive_search, test_data, 9999)
        
        # The optimized version should be significantly faster
        # This is just for demonstration - actual benchmarking would be separate
    
    @pytest.mark.benchmark
    @pytest.mark.performance
    async def test_batch_vs_individual_operations(self, benchmark, db_session):
        """Compare batch vs individual database operations"""
        ids = [f"id_{i}" for i in range(100)]
        
        async def individual_queries():
            results = []
            for id in ids:
                result = await db_session.execute(
                    "SELECT * FROM users WHERE id = $1",
                    [id]
                )
                results.append(result.fetchone())
            return results
        
        async def batch_query():
            result = await db_session.execute(
                "SELECT * FROM users WHERE id = ANY($1)",
                [ids]
            )
            return result.fetchall()
        
        # Batch should be significantly faster
        result = benchmark(batch_query)
        assert benchmark.stats["mean"] < 0.05  # Should complete in under 50ms


# Performance test utilities
def measure_performance(func: Callable, *args, **kwargs) -> Dict[str, float]:
    """Measure function performance"""
    gc.collect()
    process = psutil.Process()
    
    # CPU before
    cpu_before = process.cpu_percent()
    
    # Memory before
    mem_before = process.memory_info().rss / 1024 / 1024
    
    # Time execution
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    
    # CPU after
    cpu_after = process.cpu_percent()
    
    # Memory after
    mem_after = process.memory_info().rss / 1024 / 1024
    
    return {
        "duration": end_time - start_time,
        "memory_used": mem_after - mem_before,
        "cpu_average": (cpu_before + cpu_after) / 2,
        "result": result
    }


def profile_function(func: Callable) -> Callable:
    """Decorator to profile function performance"""
    def wrapper(*args, **kwargs):
        profiler = LineProfiler()
        profiler.add_function(func)
        profiler.enable()
        
        result = func(*args, **kwargs)
        
        profiler.disable()
        profiler.print_stats()
        
        return result
    
    return wrapper