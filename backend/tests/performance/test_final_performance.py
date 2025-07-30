"""
Final performance testing suite for production readiness.
"""

import asyncio
import time
import statistics
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor
import pytest
import httpx
from locust import HttpUser, task, between
import psutil
import asyncpg
import redis.asyncio as redis

from core.config import settings
from core.database import get_db_engine
from core.optimization import CacheManager


class PerformanceTestSuite:
    """Comprehensive performance testing for production readiness."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {
            "api_latency": [],
            "database_performance": [],
            "cache_performance": [],
            "concurrent_users": [],
            "memory_usage": [],
            "cpu_usage": []
        }
        
        # Performance thresholds
        self.thresholds = {
            "api_p95_latency_ms": 100,
            "api_p99_latency_ms": 200,
            "database_query_ms": 50,
            "cache_hit_rate": 0.8,
            "concurrent_users": 1000,
            "memory_usage_mb": 500,
            "cpu_usage_percent": 70
        }
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all performance tests."""
        print("Starting comprehensive performance tests...")
        
        # API latency tests
        await self.test_api_latency()
        
        # Database performance
        await self.test_database_performance()
        
        # Cache performance
        await self.test_cache_performance()
        
        # Concurrent user load
        await self.test_concurrent_users()
        
        # Resource usage
        await self.test_resource_usage()
        
        # Generate report
        return self.generate_performance_report()
    
    async def test_api_latency(self, num_requests: int = 1000):
        """Test API endpoint latency."""
        print(f"\nTesting API latency with {num_requests} requests...")
        
        endpoints = [
            "/api/v1/health",
            "/api/v1/users/me",
            "/api/v1/clients",
            "/api/v1/campaigns",
            "/api/v1/tasks"
        ]
        
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            for endpoint in endpoints:
                latencies = []
                
                for _ in range(num_requests // len(endpoints)):
                    start = time.time()
                    try:
                        response = await client.get(endpoint)
                        latency = (time.time() - start) * 1000  # ms
                        
                        if response.status_code == 200:
                            latencies.append(latency)
                    except Exception as e:
                        print(f"Error testing {endpoint}: {e}")
                
                if latencies:
                    self.results["api_latency"].append({
                        "endpoint": endpoint,
                        "mean": statistics.mean(latencies),
                        "median": statistics.median(latencies),
                        "p95": statistics.quantiles(latencies, n=20)[18],
                        "p99": statistics.quantiles(latencies, n=100)[98],
                        "min": min(latencies),
                        "max": max(latencies)
                    })
    
    async def test_database_performance(self):
        """Test database query performance."""
        print("\nTesting database performance...")
        
        # Test queries
        queries = [
            ("Simple SELECT", "SELECT 1"),
            ("User lookup", "SELECT * FROM users WHERE id = $1"),
            ("Campaign list", "SELECT * FROM campaigns ORDER BY created_at DESC LIMIT 100"),
            ("Complex join", """
                SELECT c.*, COUNT(t.id) as task_count 
                FROM campaigns c 
                LEFT JOIN tasks t ON t.campaign_id = c.id 
                GROUP BY c.id 
                LIMIT 50
            """),
            ("Aggregation", """
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as count,
                    AVG(budget) as avg_budget
                FROM campaigns
                WHERE created_at > NOW() - INTERVAL '30 days'
                GROUP BY DATE(created_at)
            """)
        ]
        
        # Create connection pool
        pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=10, max_size=20)
        
        try:
            for query_name, query in queries:
                latencies = []
                
                for _ in range(100):
                    async with pool.acquire() as conn:
                        start = time.time()
                        
                        if "$1" in query:
                            await conn.fetch(query, 1)
                        else:
                            await conn.fetch(query)
                        
                        latency = (time.time() - start) * 1000
                        latencies.append(latency)
                
                self.results["database_performance"].append({
                    "query": query_name,
                    "mean_ms": statistics.mean(latencies),
                    "p95_ms": statistics.quantiles(latencies, n=20)[18],
                    "p99_ms": statistics.quantiles(latencies, n=100)[98]
                })
        
        finally:
            await pool.close()
    
    async def test_cache_performance(self):
        """Test cache performance and hit rates."""
        print("\nTesting cache performance...")
        
        cache = await CacheManager.create()
        
        # Populate cache
        print("Populating cache...")
        for i in range(1000):
            key = f"test_key_{i}"
            value = f"test_value_{i}" * 100  # Larger values
            await cache.set(key, value)
        
        # Test cache hits
        hits = 0
        misses = 0
        hit_latencies = []
        miss_latencies = []
        
        for i in range(2000):
            key = f"test_key_{i % 1200}"  # Some will miss
            
            start = time.time()
            value = await cache.get(key)
            latency = (time.time() - start) * 1000
            
            if value:
                hits += 1
                hit_latencies.append(latency)
            else:
                misses += 1
                miss_latencies.append(latency)
        
        hit_rate = hits / (hits + misses)
        
        self.results["cache_performance"] = {
            "hit_rate": hit_rate,
            "hits": hits,
            "misses": misses,
            "hit_latency_mean_ms": statistics.mean(hit_latencies) if hit_latencies else 0,
            "miss_latency_mean_ms": statistics.mean(miss_latencies) if miss_latencies else 0,
            "cache_stats": cache.get_stats()
        }
        
        await cache.close()
    
    async def test_concurrent_users(self):
        """Test system under concurrent user load."""
        print("\nTesting concurrent user load...")
        
        async def simulate_user_session():
            """Simulate a user session."""
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                # Login
                start = time.time()
                
                # Browse campaigns
                await client.get("/api/v1/campaigns")
                
                # View specific campaign
                await client.get("/api/v1/campaigns/1")
                
                # Create a task
                await client.post("/api/v1/tasks", json={
                    "title": "Test task",
                    "campaign_id": 1
                })
                
                # Get user data
                await client.get("/api/v1/users/me")
                
                return time.time() - start
        
        # Test with increasing concurrent users
        for num_users in [10, 50, 100, 500, 1000]:
            print(f"Testing with {num_users} concurrent users...")
            
            start = time.time()
            tasks = [simulate_user_session() for _ in range(num_users)]
            session_times = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = time.time() - start
            
            # Filter out exceptions
            successful_sessions = [t for t in session_times if isinstance(t, (int, float))]
            failed_sessions = len(session_times) - len(successful_sessions)
            
            self.results["concurrent_users"].append({
                "users": num_users,
                "total_time": total_time,
                "successful": len(successful_sessions),
                "failed": failed_sessions,
                "avg_session_time": statistics.mean(successful_sessions) if successful_sessions else 0,
                "requests_per_second": (len(successful_sessions) * 4) / total_time  # 4 requests per session
            })
    
    async def test_resource_usage(self):
        """Monitor resource usage during load."""
        print("\nMonitoring resource usage...")
        
        # Start monitoring
        process = psutil.Process()
        
        # Simulate load
        async def generate_load():
            tasks = []
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                for _ in range(100):
                    tasks.append(client.get("/api/v1/health"))
                await asyncio.gather(*tasks)
        
        # Monitor during load
        memory_samples = []
        cpu_samples = []
        
        monitor_task = asyncio.create_task(generate_load())
        
        while not monitor_task.done():
            memory_samples.append(process.memory_info().rss / 1024 / 1024)  # MB
            cpu_samples.append(process.cpu_percent())
            await asyncio.sleep(0.1)
        
        await monitor_task
        
        self.results["memory_usage"] = {
            "mean_mb": statistics.mean(memory_samples),
            "max_mb": max(memory_samples),
            "min_mb": min(memory_samples)
        }
        
        self.results["cpu_usage"] = {
            "mean_percent": statistics.mean(cpu_samples),
            "max_percent": max(cpu_samples)
        }
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        report = {
            "summary": {
                "passed": True,
                "timestamp": time.time(),
                "thresholds": self.thresholds
            },
            "results": self.results,
            "violations": []
        }
        
        # Check API latency
        for endpoint_stats in self.results["api_latency"]:
            if endpoint_stats["p95"] > self.thresholds["api_p95_latency_ms"]:
                report["violations"].append({
                    "metric": "API P95 latency",
                    "endpoint": endpoint_stats["endpoint"],
                    "value": endpoint_stats["p95"],
                    "threshold": self.thresholds["api_p95_latency_ms"]
                })
                report["summary"]["passed"] = False
        
        # Check database performance
        for query_stats in self.results["database_performance"]:
            if query_stats["mean_ms"] > self.thresholds["database_query_ms"]:
                report["violations"].append({
                    "metric": "Database query time",
                    "query": query_stats["query"],
                    "value": query_stats["mean_ms"],
                    "threshold": self.thresholds["database_query_ms"]
                })
                report["summary"]["passed"] = False
        
        # Check cache performance
        cache_stats = self.results["cache_performance"]
        if cache_stats["hit_rate"] < self.thresholds["cache_hit_rate"]:
            report["violations"].append({
                "metric": "Cache hit rate",
                "value": cache_stats["hit_rate"],
                "threshold": self.thresholds["cache_hit_rate"]
            })
            report["summary"]["passed"] = False
        
        # Check resource usage
        if self.results["memory_usage"]["max_mb"] > self.thresholds["memory_usage_mb"]:
            report["violations"].append({
                "metric": "Memory usage",
                "value": self.results["memory_usage"]["max_mb"],
                "threshold": self.thresholds["memory_usage_mb"]
            })
            report["summary"]["passed"] = False
        
        if self.results["cpu_usage"]["max_percent"] > self.thresholds["cpu_usage_percent"]:
            report["violations"].append({
                "metric": "CPU usage",
                "value": self.results["cpu_usage"]["max_percent"],
                "threshold": self.thresholds["cpu_usage_percent"]
            })
            report["summary"]["passed"] = False
        
        # Add recommendations
        report["recommendations"] = self._generate_recommendations(report["violations"])
        
        return report
    
    def _generate_recommendations(self, violations: List[Dict]) -> List[str]:
        """Generate performance recommendations based on violations."""
        recommendations = []
        
        for violation in violations:
            metric = violation["metric"]
            
            if "API" in metric:
                recommendations.append(
                    f"Consider optimizing {violation['endpoint']} endpoint: "
                    f"add caching, optimize queries, or implement pagination"
                )
            
            elif "Database" in metric:
                recommendations.append(
                    f"Optimize query '{violation['query']}': "
                    f"add indexes, simplify joins, or implement query caching"
                )
            
            elif "Cache" in metric:
                recommendations.append(
                    "Improve cache hit rate: review cache keys, "
                    "increase TTL for frequently accessed data, implement cache warming"
                )
            
            elif "Memory" in metric:
                recommendations.append(
                    "Reduce memory usage: optimize data structures, "
                    "implement pagination, fix memory leaks"
                )
            
            elif "CPU" in metric:
                recommendations.append(
                    "Reduce CPU usage: optimize algorithms, "
                    "implement caching, use async operations"
                )
        
        return recommendations


# Locust load testing
class ProductionLoadTest(HttpUser):
    """Load test simulating production traffic patterns."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login before testing."""
        self.client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "testpass"
        })
    
    @task(3)
    def view_campaigns(self):
        """View campaign list (most common)."""
        self.client.get("/api/v1/campaigns")
    
    @task(2)
    def view_campaign_detail(self):
        """View specific campaign."""
        campaign_id = 1  # In reality, randomize
        self.client.get(f"/api/v1/campaigns/{campaign_id}")
    
    @task(2)
    def view_tasks(self):
        """View task list."""
        self.client.get("/api/v1/tasks")
    
    @task(1)
    def create_task(self):
        """Create a new task."""
        self.client.post("/api/v1/tasks", json={
            "title": "Load test task",
            "description": "Created during load testing",
            "campaign_id": 1,
            "assigned_to": 1
        })
    
    @task(1)
    def update_task(self):
        """Update existing task."""
        task_id = 1  # In reality, track created tasks
        self.client.patch(f"/api/v1/tasks/{task_id}", json={
            "status": "in_progress"
        })


@pytest.mark.asyncio
async def test_production_performance():
    """Run production performance tests."""
    tester = PerformanceTestSuite()
    report = await tester.run_all_tests()
    
    print("\n" + "="*50)
    print("PERFORMANCE TEST REPORT")
    print("="*50)
    print(f"Overall Status: {'PASSED' if report['summary']['passed'] else 'FAILED'}")
    
    if report["violations"]:
        print("\nViolations:")
        for violation in report["violations"]:
            print(f"- {violation['metric']}: {violation['value']} > {violation['threshold']}")
    
    if report["recommendations"]:
        print("\nRecommendations:")
        for rec in report["recommendations"]:
            print(f"- {rec}")
    
    assert report["summary"]["passed"], "Performance tests failed"


if __name__ == "__main__":
    # Run performance tests
    asyncio.run(test_production_performance())