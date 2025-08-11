"""
Load testing for OAuth implementation.
Tests performance under high load conditions.
"""
import asyncio
import time
import random
import statistics
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from uuid import uuid4
import aiohttp
import psutil
import pytest
from locust import HttpUser, task, between, events
import numpy as np

# Configuration
LOAD_TEST_CONFIG = {
    "base_url": "http://localhost:8000",
    "num_users": 1000,
    "spawn_rate": 50,
    "test_duration": 300,  # 5 minutes
    "ramp_up_time": 60,  # 1 minute
}

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "authorization_p95": 500,  # 95th percentile < 500ms
    "token_p95": 200,  # 95th percentile < 200ms
    "introspection_p95": 100,  # 95th percentile < 100ms
    "error_rate": 0.01,  # < 1% error rate
    "cpu_threshold": 80,  # < 80% CPU usage
    "memory_threshold": 80,  # < 80% memory usage
}


@dataclass
class LoadTestResult:
    """Load test result metrics."""
    endpoint: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_rate: float
    cpu_usage: float
    memory_usage: float
    timestamp: datetime


class OAuthLoadTest:
    """OAuth load testing suite."""
    
    def __init__(self, base_url: str = LOAD_TEST_CONFIG["base_url"]):
        self.base_url = base_url
        self.results: List[LoadTestResult] = []
        self.session = None
        
    async def setup(self):
        """Set up test environment."""
        self.session = aiohttp.ClientSession()
        
    async def teardown(self):
        """Clean up test environment."""
        if self.session:
            await self.session.close()
    
    async def measure_endpoint(
        self,
        endpoint: str,
        method: str,
        data: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        num_requests: int = 100
    ) -> LoadTestResult:
        """Measure endpoint performance."""
        response_times = []
        errors = 0
        start_time = time.time()
        
        # Get initial resource usage
        initial_cpu = psutil.cpu_percent(interval=0.1)
        initial_memory = psutil.virtual_memory().percent
        
        async def make_request():
            """Make a single request."""
            try:
                start = time.time()
                async with self.session.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    json=data,
                    headers=headers
                ) as response:
                    await response.text()
                    elapsed = (time.time() - start) * 1000  # Convert to ms
                    if response.status >= 400:
                        return None, elapsed
                    return elapsed, None
            except Exception as e:
                return None, None
        
        # Execute requests concurrently
        tasks = [make_request() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
        
        # Process results
        for success_time, error_time in results:
            if success_time is not None:
                response_times.append(success_time)
            else:
                errors += 1
        
        total_time = time.time() - start_time
        
        # Get final resource usage
        final_cpu = psutil.cpu_percent(interval=0.1)
        final_memory = psutil.virtual_memory().percent
        
        # Calculate metrics
        successful = len(response_times)
        
        if response_times:
            return LoadTestResult(
                endpoint=endpoint,
                total_requests=num_requests,
                successful_requests=successful,
                failed_requests=errors,
                avg_response_time=statistics.mean(response_times),
                min_response_time=min(response_times),
                max_response_time=max(response_times),
                p50_response_time=np.percentile(response_times, 50),
                p95_response_time=np.percentile(response_times, 95),
                p99_response_time=np.percentile(response_times, 99),
                requests_per_second=num_requests / total_time,
                error_rate=errors / num_requests,
                cpu_usage=max(initial_cpu, final_cpu),
                memory_usage=max(initial_memory, final_memory),
                timestamp=datetime.now(timezone.utc)
            )
        else:
            return LoadTestResult(
                endpoint=endpoint,
                total_requests=num_requests,
                successful_requests=0,
                failed_requests=num_requests,
                avg_response_time=0,
                min_response_time=0,
                max_response_time=0,
                p50_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                requests_per_second=0,
                error_rate=1.0,
                cpu_usage=max(initial_cpu, final_cpu),
                memory_usage=max(initial_memory, final_memory),
                timestamp=datetime.now(timezone.utc)
            )
    
    @pytest.mark.asyncio
    async def test_authorization_endpoint_load(self):
        """Test authorization endpoint under load."""
        await self.setup()
        
        try:
            # Test parameters
            auth_params = {
                "response_type": "code",
                "client_id": f"test_client_{uuid4()}",
                "redirect_uri": "http://localhost:3000/callback",
                "scope": "read write",
                "state": str(uuid4()),
            }
            
            # Test with increasing load
            for num_requests in [100, 500, 1000, 2000]:
                result = await self.measure_endpoint(
                    "/oauth/authorize",
                    "GET",
                    data=auth_params,
                    num_requests=num_requests
                )
                
                self.results.append(result)
                
                # Check performance thresholds
                assert result.p95_response_time < PERFORMANCE_THRESHOLDS["authorization_p95"], \
                    f"Authorization p95 ({result.p95_response_time}ms) exceeds threshold"
                assert result.error_rate < PERFORMANCE_THRESHOLDS["error_rate"], \
                    f"Error rate ({result.error_rate}) exceeds threshold"
                
                print(f"Authorization Load Test ({num_requests} requests):")
                print(f"  - P95 Response Time: {result.p95_response_time:.2f}ms")
                print(f"  - Requests/Second: {result.requests_per_second:.2f}")
                print(f"  - Error Rate: {result.error_rate:.2%}")
                
        finally:
            await self.teardown()
    
    @pytest.mark.asyncio
    async def test_token_endpoint_load(self):
        """Test token endpoint under load."""
        await self.setup()
        
        try:
            # Test token generation
            token_data = {
                "grant_type": "authorization_code",
                "code": str(uuid4()),
                "client_id": "test_client",
                "client_secret": "test_secret",
                "redirect_uri": "http://localhost:3000/callback",
            }
            
            # Test with different load levels
            for num_requests in [100, 500, 1000, 2000]:
                result = await self.measure_endpoint(
                    "/oauth/token",
                    "POST",
                    data=token_data,
                    num_requests=num_requests
                )
                
                self.results.append(result)
                
                # Check thresholds
                assert result.p95_response_time < PERFORMANCE_THRESHOLDS["token_p95"], \
                    f"Token p95 ({result.p95_response_time}ms) exceeds threshold"
                
                print(f"Token Generation Load Test ({num_requests} requests):")
                print(f"  - P95 Response Time: {result.p95_response_time:.2f}ms")
                print(f"  - Requests/Second: {result.requests_per_second:.2f}")
                
        finally:
            await self.teardown()
    
    @pytest.mark.asyncio
    async def test_refresh_token_load(self):
        """Test refresh token endpoint under load."""
        await self.setup()
        
        try:
            # Test refresh token
            refresh_data = {
                "grant_type": "refresh_token",
                "refresh_token": str(uuid4()),
                "client_id": "test_client",
                "client_secret": "test_secret",
            }
            
            result = await self.measure_endpoint(
                "/oauth/token",
                "POST",
                data=refresh_data,
                num_requests=1000
            )
            
            self.results.append(result)
            
            print(f"Refresh Token Load Test:")
            print(f"  - P95 Response Time: {result.p95_response_time:.2f}ms")
            print(f"  - Requests/Second: {result.requests_per_second:.2f}")
            
        finally:
            await self.teardown()
    
    @pytest.mark.asyncio
    async def test_introspection_endpoint_load(self):
        """Test token introspection under load."""
        await self.setup()
        
        try:
            # Test introspection
            introspect_data = {
                "token": str(uuid4()),
                "token_type_hint": "access_token",
            }
            
            headers = {
                "Authorization": "Basic dGVzdF9jbGllbnQ6dGVzdF9zZWNyZXQ="
            }
            
            result = await self.measure_endpoint(
                "/oauth/introspect",
                "POST",
                data=introspect_data,
                headers=headers,
                num_requests=2000
            )
            
            self.results.append(result)
            
            # Check threshold
            assert result.p95_response_time < PERFORMANCE_THRESHOLDS["introspection_p95"], \
                f"Introspection p95 ({result.p95_response_time}ms) exceeds threshold"
            
            print(f"Introspection Load Test:")
            print(f"  - P95 Response Time: {result.p95_response_time:.2f}ms")
            print(f"  - Requests/Second: {result.requests_per_second:.2f}")
            
        finally:
            await self.teardown()
    
    @pytest.mark.asyncio
    async def test_concurrent_provider_callbacks(self):
        """Test handling concurrent OAuth provider callbacks."""
        await self.setup()
        
        try:
            # Simulate provider callbacks
            callback_data = {
                "code": str(uuid4()),
                "state": str(uuid4()),
                "provider": "google",
            }
            
            # Test concurrent callbacks from multiple providers
            providers = ["google", "instagram", "microsoft"]
            tasks = []
            
            for provider in providers:
                data = {**callback_data, "provider": provider}
                for _ in range(100):
                    tasks.append(
                        self.measure_endpoint(
                            f"/oauth/callback/{provider}",
                            "POST",
                            data=data,
                            num_requests=1
                        )
                    )
            
            results = await asyncio.gather(*tasks)
            
            # Analyze results
            avg_response = statistics.mean([r.avg_response_time for r in results if r])
            error_rate = statistics.mean([r.error_rate for r in results if r])
            
            print(f"Concurrent Provider Callbacks Test:")
            print(f"  - Average Response Time: {avg_response:.2f}ms")
            print(f"  - Overall Error Rate: {error_rate:.2%}")
            
        finally:
            await self.teardown()
    
    @pytest.mark.asyncio
    async def test_resource_utilization(self):
        """Test resource utilization under sustained load."""
        await self.setup()
        
        try:
            # Monitor resources during sustained load
            resource_samples = []
            test_duration = 60  # 1 minute
            sample_interval = 1  # 1 second
            
            async def generate_load():
                """Generate continuous load."""
                while True:
                    await self.measure_endpoint(
                        "/oauth/token",
                        "POST",
                        data={"grant_type": "client_credentials"},
                        num_requests=10
                    )
                    await asyncio.sleep(0.1)
            
            # Start load generation
            load_task = asyncio.create_task(generate_load())
            
            # Sample resources
            start_time = time.time()
            while time.time() - start_time < test_duration:
                cpu_percent = psutil.cpu_percent(interval=sample_interval)
                memory_percent = psutil.virtual_memory().percent
                disk_io = psutil.disk_io_counters()
                net_io = psutil.net_io_counters()
                
                resource_samples.append({
                    "timestamp": time.time() - start_time,
                    "cpu": cpu_percent,
                    "memory": memory_percent,
                    "disk_read_mb": disk_io.read_bytes / 1024 / 1024,
                    "disk_write_mb": disk_io.write_bytes / 1024 / 1024,
                    "net_sent_mb": net_io.bytes_sent / 1024 / 1024,
                    "net_recv_mb": net_io.bytes_recv / 1024 / 1024,
                })
                
                await asyncio.sleep(sample_interval)
            
            # Cancel load generation
            load_task.cancel()
            
            # Analyze resource usage
            avg_cpu = statistics.mean([s["cpu"] for s in resource_samples])
            max_cpu = max([s["cpu"] for s in resource_samples])
            avg_memory = statistics.mean([s["memory"] for s in resource_samples])
            max_memory = max([s["memory"] for s in resource_samples])
            
            # Check thresholds
            assert max_cpu < PERFORMANCE_THRESHOLDS["cpu_threshold"], \
                f"CPU usage ({max_cpu}%) exceeds threshold"
            assert max_memory < PERFORMANCE_THRESHOLDS["memory_threshold"], \
                f"Memory usage ({max_memory}%) exceeds threshold"
            
            print(f"Resource Utilization Test:")
            print(f"  - Average CPU: {avg_cpu:.1f}%")
            print(f"  - Max CPU: {max_cpu:.1f}%")
            print(f"  - Average Memory: {avg_memory:.1f}%")
            print(f"  - Max Memory: {max_memory:.1f}%")
            
        finally:
            await self.teardown()
    
    def generate_report(self) -> str:
        """Generate load test report."""
        if not self.results:
            return "No test results available"
        
        report = ["=" * 60]
        report.append("OAuth Load Test Report")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        report.append("")
        
        # Summary statistics
        report.append("Summary Statistics")
        report.append("-" * 40)
        
        total_requests = sum(r.total_requests for r in self.results)
        total_successful = sum(r.successful_requests for r in self.results)
        overall_error_rate = 1 - (total_successful / total_requests) if total_requests else 0
        
        report.append(f"Total Requests: {total_requests:,}")
        report.append(f"Successful Requests: {total_successful:,}")
        report.append(f"Overall Error Rate: {overall_error_rate:.2%}")
        report.append("")
        
        # Per-endpoint results
        report.append("Endpoint Performance")
        report.append("-" * 40)
        
        for result in self.results:
            report.append(f"\nEndpoint: {result.endpoint}")
            report.append(f"  Requests: {result.total_requests}")
            report.append(f"  Success Rate: {(1 - result.error_rate):.1%}")
            report.append(f"  Avg Response: {result.avg_response_time:.2f}ms")
            report.append(f"  P50: {result.p50_response_time:.2f}ms")
            report.append(f"  P95: {result.p95_response_time:.2f}ms")
            report.append(f"  P99: {result.p99_response_time:.2f}ms")
            report.append(f"  RPS: {result.requests_per_second:.2f}")
        
        # Performance analysis
        report.append("\nPerformance Analysis")
        report.append("-" * 40)
        
        # Check if thresholds are met
        auth_results = [r for r in self.results if "authorize" in r.endpoint]
        token_results = [r for r in self.results if "token" in r.endpoint]
        
        if auth_results:
            auth_p95 = max(r.p95_response_time for r in auth_results)
            auth_pass = auth_p95 < PERFORMANCE_THRESHOLDS["authorization_p95"]
            report.append(f"Authorization P95: {auth_p95:.2f}ms {'✓' if auth_pass else '✗'}")
        
        if token_results:
            token_p95 = max(r.p95_response_time for r in token_results)
            token_pass = token_p95 < PERFORMANCE_THRESHOLDS["token_p95"]
            report.append(f"Token P95: {token_p95:.2f}ms {'✓' if token_pass else '✗'}")
        
        report.append(f"Error Rate: {overall_error_rate:.2%} {'✓' if overall_error_rate < PERFORMANCE_THRESHOLDS['error_rate'] else '✗'}")
        
        return "\n".join(report)


class OAuthLocustUser(HttpUser):
    """Locust user for OAuth load testing."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Initialize user session."""
        self.client_id = f"client_{uuid4()}"
        self.tokens = []
        
    @task(3)
    def authorize(self):
        """Test authorization endpoint."""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read write",
            "state": str(uuid4()),
        }
        
        with self.client.get("/oauth/authorize", params=params, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Authorization failed: {response.status_code}")
    
    @task(5)
    def get_token(self):
        """Test token endpoint."""
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": "test_secret",
            "scope": "read write",
        }
        
        with self.client.post("/oauth/token", json=data, catch_response=True) as response:
            if response.status_code == 200:
                token_data = response.json()
                self.tokens.append(token_data.get("access_token"))
                response.success()
            else:
                response.failure(f"Token generation failed: {response.status_code}")
    
    @task(2)
    def refresh_token(self):
        """Test refresh token."""
        if not self.tokens:
            return
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": random.choice(self.tokens),
            "client_id": self.client_id,
        }
        
        with self.client.post("/oauth/token", json=data, catch_response=True) as response:
            if response.status_code in [200, 400]:  # 400 for invalid token is acceptable
                response.success()
            else:
                response.failure(f"Refresh failed: {response.status_code}")
    
    @task(4)
    def introspect_token(self):
        """Test token introspection."""
        if not self.tokens:
            return
        
        data = {
            "token": random.choice(self.tokens),
            "token_type_hint": "access_token",
        }
        
        headers = {
            "Authorization": f"Basic {self.client_id}:test_secret"
        }
        
        with self.client.post("/oauth/introspect", json=data, headers=headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Introspection failed: {response.status_code}")
    
    @task(1)
    def revoke_token(self):
        """Test token revocation."""
        if not self.tokens:
            return
        
        token = self.tokens.pop() if self.tokens else str(uuid4())
        
        data = {
            "token": token,
            "token_type_hint": "access_token",
        }
        
        with self.client.post("/oauth/revoke", json=data, catch_response=True) as response:
            if response.status_code in [200, 400]:  # 400 for invalid token is acceptable
                response.success()
            else:
                response.failure(f"Revocation failed: {response.status_code}")


# Custom event handlers for Locust
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Handle test start event."""
    print("Starting OAuth load test...")
    print(f"Target URL: {environment.host}")
    print(f"Number of users: {environment.parsed_options.num_users}")
    print(f"Spawn rate: {environment.parsed_options.spawn_rate}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Handle test stop event."""
    print("\nTest completed!")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Total failures: {environment.stats.total.num_failures}")
    print(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")
    print(f"RPS: {environment.stats.total.current_rps:.2f}")


if __name__ == "__main__":
    # Run load tests
    import sys
    
    if "--locust" in sys.argv:
        # Run with Locust
        from locust import main as locust_main
        locust_main.main()
    else:
        # Run with pytest
        load_test = OAuthLoadTest()
        
        async def run_all_tests():
            """Run all load tests."""
            await load_test.test_authorization_endpoint_load()
            await load_test.test_token_endpoint_load()
            await load_test.test_refresh_token_load()
            await load_test.test_introspection_endpoint_load()
            await load_test.test_concurrent_provider_callbacks()
            await load_test.test_resource_utilization()
            
            # Generate report
            report = load_test.generate_report()
            print("\n" + report)
            
            # Save report to file
            with open("oauth_load_test_report.txt", "w") as f:
                f.write(report)
        
        # Run tests
        asyncio.run(run_all_tests())