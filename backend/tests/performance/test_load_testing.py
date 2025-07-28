"""
Load testing and performance benchmarks for AgencyDark API.
"""
import pytest
import asyncio
import aiohttp
import time
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import json
from uuid import uuid4
import random

from locust import HttpUser, task, between, events
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging


class PerformanceMetrics:
    """Track and analyze performance metrics."""
    
    def __init__(self):
        self.response_times: List[float] = []
        self.error_count = 0
        self.success_count = 0
        self.start_time = None
        self.end_time = None
    
    def add_response(self, response_time: float, success: bool = True):
        """Add a response time measurement."""
        self.response_times.append(response_time)
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """Calculate performance statistics."""
        if not self.response_times:
            return {}
        
        sorted_times = sorted(self.response_times)
        total_requests = len(self.response_times)
        
        return {
            "total_requests": total_requests,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / total_requests if total_requests > 0 else 0,
            "min_response_time": min(self.response_times),
            "max_response_time": max(self.response_times),
            "mean_response_time": statistics.mean(self.response_times),
            "median_response_time": statistics.median(self.response_times),
            "p95_response_time": sorted_times[int(0.95 * total_requests)],
            "p99_response_time": sorted_times[int(0.99 * total_requests)],
            "requests_per_second": total_requests / (self.end_time - self.start_time) if self.end_time else 0
        }


class AgencyDarkUser(HttpUser):
    """Locust user for load testing AgencyDark API."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login and setup before tasks."""
        # Login to get access token
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "loadtest@example.com",
                "password": "LoadTest123!"
            }
        )
        if response.status_code == 200:
            self.access_token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.access_token}"}
        else:
            self.headers = {}
        
        # Setup test data
        self.model_id = "123e4567-e89b-12d3-a456-426614174000"
        self.fan_ids = [str(uuid4()) for _ in range(100)]
    
    @task(3)
    def get_analytics(self):
        """Test analytics endpoint."""
        self.client.get(
            f"/api/v1/analytics/models/{self.model_id}",
            headers=self.headers,
            params={
                "date_from": (datetime.now() - timedelta(days=30)).date().isoformat(),
                "date_to": datetime.now().date().isoformat()
            }
        )
    
    @task(2)
    def get_revenue_trends(self):
        """Test revenue trends endpoint."""
        self.client.get(
            "/api/v1/analytics/revenue/trends",
            headers=self.headers,
            params={
                "model_id": self.model_id,
                "period": "daily",
                "days": 30
            }
        )
    
    @task(1)
    def create_bulk_message(self):
        """Test bulk message creation."""
        self.client.post(
            "/api/v1/messaging/bulk",
            headers=self.headers,
            json={
                "campaign_name": f"Load Test {datetime.now().isoformat()}",
                "model_id": self.model_id,
                "message_template": "Test message {{display_name}}",
                "recipient_filters": {
                    "subscription_status": ["active"]
                },
                "platform": "onlyfans"
            }
        )
    
    @task(2)
    def get_transactions(self):
        """Test transaction listing."""
        self.client.get(
            "/api/v1/financial/transactions",
            headers=self.headers,
            params={
                "model_id": self.model_id,
                "limit": 50
            }
        )
    
    @task(1)
    def generate_report(self):
        """Test report generation."""
        self.client.post(
            "/api/v1/reporting/generate",
            headers=self.headers,
            json={
                "template_id": "tpl_123e4567-e89b-12d3-a456",
                "parameters": {
                    "date_from": (datetime.now() - timedelta(days=7)).date().isoformat(),
                    "date_to": datetime.now().date().isoformat()
                },
                "format": "json"
            }
        )


@pytest.mark.performance
class TestAPIPerformance:
    """Performance tests for API endpoints."""
    
    @pytest.fixture
    def api_url(self):
        """API base URL for testing."""
        return "http://localhost:8000"
    
    @pytest.fixture
    async def auth_headers(self, api_url):
        """Get authentication headers."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{api_url}/api/v1/auth/login",
                json={
                    "email": "perftest@example.com",
                    "password": "PerfTest123!"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {"Authorization": f"Bearer {data['access_token']}"}
                return {}
    
    @pytest.mark.asyncio
    async def test_concurrent_analytics_requests(self, api_url, auth_headers):
        """Test concurrent analytics requests."""
        metrics = PerformanceMetrics()
        model_id = "123e4567-e89b-12d3-a456-426614174000"
        concurrent_users = 50
        requests_per_user = 10
        
        async def make_analytics_request(session: aiohttp.ClientSession):
            start_time = time.time()
            try:
                async with session.get(
                    f"{api_url}/api/v1/analytics/models/{model_id}",
                    headers=auth_headers
                ) as response:
                    await response.json()
                    response_time = time.time() - start_time
                    metrics.add_response(response_time, response.status == 200)
            except Exception as e:
                response_time = time.time() - start_time
                metrics.add_response(response_time, False)
        
        metrics.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for _ in range(concurrent_users):
                for _ in range(requests_per_user):
                    tasks.append(make_analytics_request(session))
            
            await asyncio.gather(*tasks)
        
        metrics.end_time = time.time()
        
        stats = metrics.get_statistics()
        print(f"\nAnalytics Endpoint Performance:")
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Success Rate: {(stats['success_count'] / stats['total_requests'] * 100):.2f}%")
        print(f"Mean Response Time: {stats['mean_response_time']*1000:.2f}ms")
        print(f"P95 Response Time: {stats['p95_response_time']*1000:.2f}ms")
        print(f"P99 Response Time: {stats['p99_response_time']*1000:.2f}ms")
        print(f"Requests/Second: {stats['requests_per_second']:.2f}")
        
        # Performance assertions
        assert stats['error_rate'] < 0.05  # Less than 5% error rate
        assert stats['mean_response_time'] < 0.5  # Less than 500ms mean
        assert stats['p95_response_time'] < 1.0  # Less than 1s for 95th percentile
    
    @pytest.mark.asyncio
    async def test_bulk_message_performance(self, api_url, auth_headers):
        """Test bulk message creation performance."""
        metrics = PerformanceMetrics()
        model_id = "123e4567-e89b-12d3-a456-426614174000"
        
        # Test with different recipient counts
        recipient_counts = [100, 500, 1000, 5000]
        
        async with aiohttp.ClientSession() as session:
            for count in recipient_counts:
                start_time = time.time()
                
                async with session.post(
                    f"{api_url}/api/v1/messaging/bulk",
                    headers=auth_headers,
                    json={
                        "campaign_name": f"Perf Test {count} recipients",
                        "model_id": model_id,
                        "message_template": "Test message",
                        "recipient_filters": {
                            "subscription_status": ["active"],
                            "limit": count
                        },
                        "platform": "onlyfans"
                    }
                ) as response:
                    response_time = time.time() - start_time
                    success = response.status == 200
                    
                    print(f"\nBulk Message ({count} recipients):")
                    print(f"Response Time: {response_time*1000:.2f}ms")
                    print(f"Success: {success}")
                    
                    # Performance requirement: linear scaling
                    assert response_time < count * 0.001  # 1ms per recipient max
    
    @pytest.mark.asyncio
    async def test_database_query_performance(self, api_url, auth_headers):
        """Test database query performance with complex filters."""
        metrics = PerformanceMetrics()
        
        # Complex query scenarios
        test_queries = [
            {
                "name": "Simple date range",
                "params": {
                    "date_from": (datetime.now() - timedelta(days=30)).date().isoformat(),
                    "date_to": datetime.now().date().isoformat()
                }
            },
            {
                "name": "Complex filters",
                "params": {
                    "date_from": (datetime.now() - timedelta(days=90)).date().isoformat(),
                    "date_to": datetime.now().date().isoformat(),
                    "transaction_types": ["tip", "ppv", "subscription"],
                    "min_amount": 10,
                    "max_amount": 1000,
                    "group_by": "day"
                }
            },
            {
                "name": "Aggregation query",
                "params": {
                    "aggregate": True,
                    "metrics": ["sum", "avg", "count"],
                    "group_by": "model,transaction_type"
                }
            }
        ]
        
        async with aiohttp.ClientSession() as session:
            for query in test_queries:
                start_time = time.time()
                
                async with session.get(
                    f"{api_url}/api/v1/financial/transactions",
                    headers=auth_headers,
                    params=query["params"]
                ) as response:
                    await response.json()
                    response_time = time.time() - start_time
                    
                    print(f"\nQuery: {query['name']}")
                    print(f"Response Time: {response_time*1000:.2f}ms")
                    
                    # All queries should complete within 2 seconds
                    assert response_time < 2.0
    
    @pytest.mark.asyncio
    async def test_cache_effectiveness(self, api_url, auth_headers):
        """Test caching effectiveness."""
        model_id = "123e4567-e89b-12d3-a456-426614174000"
        
        async with aiohttp.ClientSession() as session:
            # First request (cache miss)
            start_time = time.time()
            async with session.get(
                f"{api_url}/api/v1/analytics/models/{model_id}",
                headers=auth_headers
            ) as response:
                first_response = await response.json()
                first_time = time.time() - start_time
            
            # Second request (cache hit)
            start_time = time.time()
            async with session.get(
                f"{api_url}/api/v1/analytics/models/{model_id}",
                headers=auth_headers
            ) as response:
                second_response = await response.json()
                second_time = time.time() - start_time
            
            print(f"\nCache Performance:")
            print(f"First Request (cache miss): {first_time*1000:.2f}ms")
            print(f"Second Request (cache hit): {second_time*1000:.2f}ms")
            print(f"Speed improvement: {(first_time/second_time):.2f}x")
            
            # Cache hit should be at least 5x faster
            assert second_time < first_time / 5
            
            # Data should be identical
            assert first_response == second_response
    
    @pytest.mark.asyncio
    async def test_websocket_performance(self, api_url, auth_headers):
        """Test WebSocket connection performance."""
        import websockets
        
        ws_url = api_url.replace("http://", "ws://")
        model_id = "123e4567-e89b-12d3-a456-426614174000"
        
        connection_times = []
        message_latencies = []
        
        for i in range(10):
            start_time = time.time()
            
            async with websockets.connect(
                f"{ws_url}/ws/analytics/{model_id}",
                extra_headers=auth_headers
            ) as websocket:
                connection_time = time.time() - start_time
                connection_times.append(connection_time)
                
                # Send subscribe message
                await websocket.send(json.dumps({
                    "type": "subscribe",
                    "metrics": ["revenue", "fans"]
                }))
                
                # Measure message latency
                ping_time = time.time()
                await websocket.send(json.dumps({"type": "ping"}))
                pong = await websocket.recv()
                latency = time.time() - ping_time
                message_latencies.append(latency)
        
        print(f"\nWebSocket Performance:")
        print(f"Avg Connection Time: {statistics.mean(connection_times)*1000:.2f}ms")
        print(f"Avg Message Latency: {statistics.mean(message_latencies)*1000:.2f}ms")
        
        # WebSocket requirements
        assert statistics.mean(connection_times) < 0.1  # 100ms connection time
        assert statistics.mean(message_latencies) < 0.01  # 10ms message latency


@pytest.mark.stress
class TestStressTesting:
    """Stress tests to find system limits."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, api_url, auth_headers):
        """Test rate limiting under stress."""
        endpoint = f"{api_url}/api/v1/analytics/models/test"
        rate_limit = 100  # Expected rate limit per minute
        
        async with aiohttp.ClientSession() as session:
            # Send requests rapidly
            successful_requests = 0
            rate_limited_requests = 0
            
            for i in range(rate_limit + 50):
                async with session.get(endpoint, headers=auth_headers) as response:
                    if response.status == 200:
                        successful_requests += 1
                    elif response.status == 429:
                        rate_limited_requests += 1
            
            print(f"\nRate Limiting Test:")
            print(f"Successful Requests: {successful_requests}")
            print(f"Rate Limited Requests: {rate_limited_requests}")
            
            # Should enforce rate limit
            assert rate_limited_requests > 0
            assert successful_requests <= rate_limit
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, api_url, auth_headers):
        """Test memory usage under sustained load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Generate sustained load
        async with aiohttp.ClientSession() as session:
            tasks = []
            for _ in range(1000):
                task = session.get(
                    f"{api_url}/api/v1/analytics/revenue/trends",
                    headers=auth_headers,
                    params={"days": 365}  # Large dataset
                )
                tasks.append(task)
            
            # Execute in batches
            batch_size = 100
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i+batch_size]
                await asyncio.gather(*batch, return_exceptions=True)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"\nMemory Usage Test:")
        print(f"Initial Memory: {initial_memory:.2f} MB")
        print(f"Final Memory: {final_memory:.2f} MB")
        print(f"Memory Increase: {memory_increase:.2f} MB")
        
        # Memory increase should be reasonable (less than 500MB)
        assert memory_increase < 500


def run_locust_test(duration_seconds: int = 60, users: int = 100, spawn_rate: int = 10):
    """Run Locust load test programmatically."""
    # Setup Locust
    setup_logging("INFO", None)
    
    # Create environment
    env = Environment(user_classes=[AgencyDarkUser])
    env.create_local_runner()
    
    # Start test
    env.runner.start(users, spawn_rate=spawn_rate)
    
    # Run for specified duration
    time.sleep(duration_seconds)
    
    # Stop test
    env.runner.quit()
    
    # Get statistics
    stats = env.stats
    
    print("\nLocust Load Test Results:")
    print(f"Total Requests: {stats.total.num_requests}")
    print(f"Failed Requests: {stats.total.num_failures}")
    print(f"Median Response Time: {stats.total.median_response_time}ms")
    print(f"95% Response Time: {stats.total.get_response_time_percentile(0.95)}ms")
    print(f"Requests/Second: {stats.total.current_rps}")
    
    return stats


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-m", "performance"])
    
    # Run Locust load test
    print("\nRunning Locust Load Test...")
    run_locust_test(duration_seconds=300, users=200, spawn_rate=20)