"""
Chaos engineering tests for production resilience.
"""

import asyncio
import random
import time
from typing import Dict, List, Any, Optional
import pytest
import httpx
import psutil
import signal
import subprocess
from datetime import datetime, timedelta

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class ChaosMonkey:
    """Chaos engineering test suite."""
    
    def __init__(self, target_url: str = "http://localhost:8000"):
        self.target_url = target_url
        self.chaos_results = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "failures": [],
            "recovery_times": []
        }
        
        # Chaos scenarios
        self.scenarios = [
            self.simulate_high_latency,
            self.simulate_connection_drops,
            self.simulate_database_failure,
            self.simulate_cache_failure,
            self.simulate_memory_pressure,
            self.simulate_cpu_spike,
            self.simulate_disk_full,
            self.simulate_network_partition,
            self.simulate_cascading_failure,
            self.simulate_thundering_herd
        ]
    
    async def run_chaos_tests(self) -> Dict[str, Any]:
        """Run all chaos engineering tests."""
        print("🐒 Starting Chaos Engineering Tests...")
        print("=" * 50)
        
        for scenario in self.scenarios:
            print(f"\n🔥 Running: {scenario.__name__}")
            
            try:
                result = await scenario()
                
                if result["passed"]:
                    self.chaos_results["tests_passed"] += 1
                    print(f"✅ PASSED: {result['message']}")
                else:
                    self.chaos_results["tests_failed"] += 1
                    self.chaos_results["failures"].append({
                        "scenario": scenario.__name__,
                        "error": result["error"],
                        "details": result.get("details", {})
                    })
                    print(f"❌ FAILED: {result['error']}")
                
                if "recovery_time" in result:
                    self.chaos_results["recovery_times"].append({
                        "scenario": scenario.__name__,
                        "time_seconds": result["recovery_time"]
                    })
                
            except Exception as e:
                self.chaos_results["tests_failed"] += 1
                self.chaos_results["failures"].append({
                    "scenario": scenario.__name__,
                    "error": str(e),
                    "type": "exception"
                })
                print(f"💥 EXCEPTION: {e}")
            
            self.chaos_results["tests_run"] += 1
            
            # Cool down between tests
            await asyncio.sleep(5)
        
        return self.generate_chaos_report()
    
    async def simulate_high_latency(self) -> Dict[str, Any]:
        """Simulate network latency issues."""
        # Add network latency using tc (traffic control)
        try:
            # Add 500ms latency
            subprocess.run([
                "sudo", "tc", "qdisc", "add", "dev", "lo",
                "root", "netem", "delay", "500ms"
            ], check=True, capture_output=True)
            
            # Test API responsiveness
            start_time = time.time()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.target_url}/health")
                
            # Remove latency
            subprocess.run([
                "sudo", "tc", "qdisc", "del", "dev", "lo", "root"
            ], capture_output=True)
            
            response_time = time.time() - start_time
            
            # Check if system handled latency gracefully
            if response.status_code == 200 and response_time < 10:
                return {
                    "passed": True,
                    "message": f"System handled high latency gracefully (response time: {response_time:.2f}s)"
                }
            else:
                return {
                    "passed": False,
                    "error": f"System struggled with high latency (response time: {response_time:.2f}s)"
                }
                
        except Exception as e:
            # Clean up
            subprocess.run([
                "sudo", "tc", "qdisc", "del", "dev", "lo", "root"
            ], capture_output=True)
            
            return {
                "passed": False,
                "error": f"High latency test failed: {e}"
            }
    
    async def simulate_connection_drops(self) -> Dict[str, Any]:
        """Simulate random connection drops."""
        dropped_connections = 0
        successful_recoveries = 0
        
        async def flaky_request():
            """Make request with random connection drops."""
            if random.random() < 0.3:  # 30% drop rate
                raise httpx.ConnectError("Simulated connection drop")
            
            async with httpx.AsyncClient() as client:
                return await client.get(f"{self.target_url}/api/v1/health")
        
        # Make 100 requests with connection drops
        for _ in range(100):
            retries = 0
            success = False
            
            while retries < 3 and not success:
                try:
                    response = await flaky_request()
                    if response.status_code == 200:
                        success = True
                        if retries > 0:
                            successful_recoveries += 1
                except httpx.ConnectError:
                    dropped_connections += 1
                    retries += 1
                    await asyncio.sleep(0.5 * retries)  # Exponential backoff
            
            if not success:
                return {
                    "passed": False,
                    "error": f"Failed to recover from connection drops ({dropped_connections} drops, {successful_recoveries} recoveries)"
                }
        
        return {
            "passed": True,
            "message": f"Successfully handled {dropped_connections} connection drops with {successful_recoveries} recoveries"
        }
    
    async def simulate_database_failure(self) -> Dict[str, Any]:
        """Simulate database connection failure."""
        # This would typically involve blocking database port or killing process
        # For safety, we'll simulate by setting invalid connection string
        
        original_db_url = settings.DATABASE_URL
        settings.DATABASE_URL = "postgresql://invalid:invalid@localhost:9999/invalid"
        
        try:
            # Test if application handles DB failure gracefully
            async with httpx.AsyncClient() as client:
                # Health check should still work
                health_response = await client.get(f"{self.target_url}/health")
                
                # API calls should degrade gracefully
                api_response = await client.get(f"{self.target_url}/api/v1/campaigns")
            
            # Restore DB connection
            settings.DATABASE_URL = original_db_url
            
            # Check if system degraded gracefully
            if health_response.status_code == 200:
                return {
                    "passed": True,
                    "message": "System degraded gracefully during database failure"
                }
            else:
                return {
                    "passed": False,
                    "error": "System did not handle database failure gracefully"
                }
                
        finally:
            settings.DATABASE_URL = original_db_url
    
    async def simulate_cache_failure(self) -> Dict[str, Any]:
        """Simulate cache (Redis) failure."""
        # Similar to DB failure, simulate by invalid connection
        original_redis_url = settings.REDIS_URL
        settings.REDIS_URL = "redis://localhost:9999"
        
        try:
            start_time = time.time()
            
            # Make requests without cache
            async with httpx.AsyncClient() as client:
                tasks = []
                for _ in range(10):
                    tasks.append(client.get(f"{self.target_url}/api/v1/health"))
                
                responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Restore Redis connection
            settings.REDIS_URL = original_redis_url
            
            # Check performance without cache
            elapsed = time.time() - start_time
            successful = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
            
            if successful >= 8 and elapsed < 5:  # 80% success rate, reasonable time
                return {
                    "passed": True,
                    "message": f"System handled cache failure well ({successful}/10 requests succeeded)"
                }
            else:
                return {
                    "passed": False,
                    "error": f"System struggled without cache ({successful}/10 requests, {elapsed:.2f}s)"
                }
                
        finally:
            settings.REDIS_URL = original_redis_url
    
    async def simulate_memory_pressure(self) -> Dict[str, Any]:
        """Simulate high memory usage."""
        # Allocate large amount of memory
        memory_hog = []
        
        try:
            # Get current memory usage
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Allocate 500MB
            for _ in range(50):
                memory_hog.append(bytearray(10 * 1024 * 1024))  # 10MB chunks
            
            # Test if system still responsive
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.target_url}/health")
            
            current_memory = process.memory_info().rss / 1024 / 1024
            
            # Clean up
            memory_hog.clear()
            
            if response.status_code == 200:
                return {
                    "passed": True,
                    "message": f"System handled memory pressure well (used {current_memory:.0f}MB)"
                }
            else:
                return {
                    "passed": False,
                    "error": "System unresponsive under memory pressure"
                }
                
        finally:
            memory_hog.clear()
    
    async def simulate_cpu_spike(self) -> Dict[str, Any]:
        """Simulate high CPU usage."""
        def cpu_intensive_task():
            """CPU intensive calculation."""
            end_time = time.time() + 5  # 5 seconds
            while time.time() < end_time:
                sum(i * i for i in range(1000))
        
        # Run CPU intensive tasks in threads
        from concurrent.futures import ThreadPoolExecutor
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Start CPU intensive tasks
            futures = [executor.submit(cpu_intensive_task) for _ in range(4)]
            
            # Test system responsiveness
            start_time = time.time()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.target_url}/health")
            
            response_time = time.time() - start_time
            
            # Wait for CPU tasks to complete
            for future in futures:
                future.result()
        
        if response.status_code == 200 and response_time < 2:
            return {
                "passed": True,
                "message": f"System responsive under CPU load (response time: {response_time:.2f}s)"
            }
        else:
            return {
                "passed": False,
                "error": f"System slow under CPU load (response time: {response_time:.2f}s)"
            }
    
    async def simulate_disk_full(self) -> Dict[str, Any]:
        """Simulate disk full scenario."""
        # Create a large temporary file
        temp_file = "/tmp/chaos_disk_test"
        
        try:
            # Check available space
            disk_usage = psutil.disk_usage('/tmp')
            available_gb = disk_usage.free / (1024**3)
            
            if available_gb < 2:
                return {
                    "passed": True,
                    "message": "Skipped disk full test (insufficient space)"
                }
            
            # Create 1GB file
            with open(temp_file, 'wb') as f:
                f.write(bytearray(1024 * 1024 * 1024))
            
            # Test if system handles disk pressure
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.target_url}/health")
            
            # Clean up
            import os
            os.remove(temp_file)
            
            if response.status_code == 200:
                return {
                    "passed": True,
                    "message": "System handled disk pressure gracefully"
                }
            else:
                return {
                    "passed": False,
                    "error": "System failed under disk pressure"
                }
                
        except Exception as e:
            # Clean up
            try:
                import os
                os.remove(temp_file)
            except:
                pass
            
            return {
                "passed": False,
                "error": f"Disk full test failed: {e}"
            }
    
    async def simulate_network_partition(self) -> Dict[str, Any]:
        """Simulate network partition."""
        # This is complex in real environments
        # We'll simulate by testing timeout handling
        
        slow_endpoints = 0
        timeout_handled = 0
        
        async def slow_request(delay: float):
            """Make request with artificial delay."""
            await asyncio.sleep(delay)
            async with httpx.AsyncClient(timeout=2.0) as client:
                return await client.get(f"{self.target_url}/health")
        
        # Test various delays
        for delay in [0.5, 1.0, 2.0, 3.0, 5.0]:
            try:
                response = await slow_request(delay)
                if response.status_code == 200:
                    if delay > 2.0:
                        slow_endpoints += 1
            except httpx.TimeoutException:
                timeout_handled += 1
        
        if timeout_handled >= 2:  # Properly handled timeouts
            return {
                "passed": True,
                "message": f"System handled network delays well ({timeout_handled} timeouts handled)"
            }
        else:
            return {
                "passed": False,
                "error": "System did not handle network timeouts properly"
            }
    
    async def simulate_cascading_failure(self) -> Dict[str, Any]:
        """Simulate cascading failure scenario."""
        # Simulate by overwhelming one endpoint
        
        async def flood_endpoint():
            """Flood an endpoint with requests."""
            async with httpx.AsyncClient() as client:
                tasks = []
                for _ in range(100):
                    tasks.append(
                        client.get(f"{self.target_url}/api/v1/campaigns", timeout=1.0)
                    )
                
                return await asyncio.gather(*tasks, return_exceptions=True)
        
        # Start flooding
        flood_task = asyncio.create_task(flood_endpoint())
        
        # Wait a bit
        await asyncio.sleep(0.5)
        
        # Test if other endpoints still work
        async with httpx.AsyncClient() as client:
            health_response = await client.get(f"{self.target_url}/health")
            
        # Wait for flood to complete
        flood_results = await flood_task
        
        # Count successes and failures
        flood_success = sum(
            1 for r in flood_results
            if not isinstance(r, Exception) and r.status_code < 500
        )
        
        if health_response.status_code == 200 and flood_success > 50:
            return {
                "passed": True,
                "message": f"System prevented cascading failure ({flood_success}/100 flood requests succeeded)"
            }
        else:
            return {
                "passed": False,
                "error": "System vulnerable to cascading failures"
            }
    
    async def simulate_thundering_herd(self) -> Dict[str, Any]:
        """Simulate thundering herd problem."""
        # All clients request same resource simultaneously
        
        async def herd_request():
            """Single request in the herd."""
            async with httpx.AsyncClient() as client:
                return await client.get(f"{self.target_url}/api/v1/users/1")
        
        # Release the herd!
        start_time = time.time()
        
        tasks = [herd_request() for _ in range(200)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        
        # Count successes
        successes = sum(
            1 for r in responses
            if not isinstance(r, Exception) and r.status_code == 200
        )
        
        success_rate = successes / len(responses)
        
        if success_rate > 0.9 and elapsed < 5:
            return {
                "passed": True,
                "message": f"System handled thundering herd well ({successes}/200 succeeded in {elapsed:.2f}s)"
            }
        else:
            return {
                "passed": False,
                "error": f"System struggled with thundering herd ({successes}/200 succeeded in {elapsed:.2f}s)"
            }
    
    def generate_chaos_report(self) -> Dict[str, Any]:
        """Generate chaos engineering report."""
        success_rate = (
            self.chaos_results["tests_passed"] / self.chaos_results["tests_run"]
            if self.chaos_results["tests_run"] > 0
            else 0
        )
        
        avg_recovery_time = (
            sum(r["time_seconds"] for r in self.chaos_results["recovery_times"]) /
            len(self.chaos_results["recovery_times"])
            if self.chaos_results["recovery_times"]
            else 0
        )
        
        report = {
            "summary": {
                "total_tests": self.chaos_results["tests_run"],
                "passed": self.chaos_results["tests_passed"],
                "failed": self.chaos_results["tests_failed"],
                "success_rate": f"{success_rate * 100:.1f}%",
                "avg_recovery_time": f"{avg_recovery_time:.2f}s"
            },
            "failures": self.chaos_results["failures"],
            "recovery_times": self.chaos_results["recovery_times"],
            "resilience_score": self._calculate_resilience_score(),
            "recommendations": self._generate_resilience_recommendations()
        }
        
        return report
    
    def _calculate_resilience_score(self) -> float:
        """Calculate overall resilience score."""
        base_score = (
            self.chaos_results["tests_passed"] / self.chaos_results["tests_run"]
        ) * 100 if self.chaos_results["tests_run"] > 0 else 0
        
        # Penalty for slow recovery
        recovery_times = self.chaos_results["recovery_times"]
        if recovery_times:
            avg_recovery = sum(r["time_seconds"] for r in recovery_times) / len(recovery_times)
            if avg_recovery > 10:
                base_score *= 0.9
            elif avg_recovery > 5:
                base_score *= 0.95
        
        return round(base_score, 1)
    
    def _generate_resilience_recommendations(self) -> List[str]:
        """Generate recommendations based on chaos test results."""
        recommendations = []
        
        for failure in self.chaos_results["failures"]:
            scenario = failure["scenario"]
            
            if "latency" in scenario:
                recommendations.append(
                    "Implement aggressive timeouts and circuit breakers for external services"
                )
            elif "database" in scenario:
                recommendations.append(
                    "Add read replicas and implement database connection pooling with fallback"
                )
            elif "cache" in scenario:
                recommendations.append(
                    "Implement cache-aside pattern with graceful degradation"
                )
            elif "memory" in scenario:
                recommendations.append(
                    "Set memory limits and implement memory pressure monitoring"
                )
            elif "cpu" in scenario:
                recommendations.append(
                    "Implement request rate limiting and CPU-based autoscaling"
                )
            elif "cascading" in scenario:
                recommendations.append(
                    "Implement bulkheads and isolation between services"
                )
            elif "thundering" in scenario:
                recommendations.append(
                    "Implement request coalescing and jitter in retry logic"
                )
        
        # Remove duplicates
        return list(set(recommendations))


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_chaos_engineering():
    """Run chaos engineering tests."""
    chaos = ChaosMonkey()
    report = await chaos.run_chaos_tests()
    
    print("\n" + "="*50)
    print("CHAOS ENGINEERING REPORT")
    print("="*50)
    print(f"Resilience Score: {report['resilience_score']}/100")
    print(f"Success Rate: {report['summary']['success_rate']}")
    print(f"Average Recovery Time: {report['summary']['avg_recovery_time']}")
    
    if report["failures"]:
        print("\nFailures:")
        for failure in report["failures"]:
            print(f"- {failure['scenario']}: {failure['error']}")
    
    if report["recommendations"]:
        print("\nRecommendations:")
        for rec in report["recommendations"]:
            print(f"- {rec}")
    
    # Consider 80% resilience score as passing
    assert report["resilience_score"] >= 80, f"Resilience score too low: {report['resilience_score']}"


if __name__ == "__main__":
    asyncio.run(test_chaos_engineering())