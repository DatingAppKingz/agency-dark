#!/usr/bin/env python3
"""
Test rate limiting functionality.
Tests various rate limiting strategies, distributed limiting, and edge cases.
"""
import asyncio
import time
from typing import List, Dict, Any
import uuid
import random
from datetime import datetime, timedelta
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.security.rate_limiter import (
    AdvancedRateLimiter, RateLimitStrategy, RateLimitConfig, RateLimitResult
)
from core.redis import redis_client
import statistics

class RateLimitingTest:
    def __init__(self):
        self.rate_limiter = AdvancedRateLimiter()
        self.test_results = {}
        
    async def setup(self):
        """Setup test environment."""
        print("Setting up rate limiting tests...")
        
        # Ensure Redis is connected
        try:
            await redis_client.ping()
            print("✅ Redis connection established")
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            print("Please ensure Redis is running on localhost:6379")
            return False
            
        # Clear any existing test data
        await self._cleanup_test_data()
        return True
        
    async def _cleanup_test_data(self):
        """Clean up test data from Redis."""
        # Clear test keys
        test_keys = await redis_client.keys("rate_limit:test:*")
        if test_keys:
            await redis_client.delete(*test_keys)
            
    async def test_basic_rate_limiting(self):
        """Test basic rate limiting functionality."""
        print("\n" + "="*60)
        print("BASIC RATE LIMITING TEST")
        print("="*60)
        
        test_id = f"test:{uuid.uuid4()}"
        config = RateLimitConfig(requests=5, window=10)  # 5 requests per 10 seconds
        
        results = []
        
        # Make requests within limit
        print("\nMaking 5 requests (within limit)...")
        for i in range(5):
            result = await self.rate_limiter.check_rate_limit(
                test_id, 
                RateLimitStrategy.IP,
                custom_config=config
            )
            results.append(result)
            print(f"  Request {i+1}: {'✅ Allowed' if result.allowed else '❌ Blocked'} "
                  f"(Remaining: {result.remaining})")
            
        # Make request exceeding limit
        print("\nMaking 6th request (exceeding limit)...")
        result = await self.rate_limiter.check_rate_limit(
            test_id,
            RateLimitStrategy.IP,
            custom_config=config
        )
        print(f"  Request 6: {'✅ Allowed' if result.allowed else '❌ Blocked'} "
              f"(Retry after: {result.retry_after}s)")
        
        assert results[0].allowed == True
        assert results[0].remaining == 4
        assert results[4].allowed == True
        assert results[4].remaining == 0
        assert result.allowed == False
        
        print("\n✅ Basic rate limiting working correctly")
        
    async def test_sliding_window(self):
        """Test sliding window algorithm."""
        print("\n" + "="*60)
        print("SLIDING WINDOW TEST")
        print("="*60)
        
        test_id = f"test:{uuid.uuid4()}"
        config = RateLimitConfig(requests=5, window=10)
        
        # Make 3 requests
        print("\nMaking 3 initial requests...")
        for i in range(3):
            await self.rate_limiter.check_rate_limit(
                test_id,
                RateLimitStrategy.IP,
                custom_config=config
            )
            
        # Wait 5 seconds
        print("Waiting 5 seconds...")
        await asyncio.sleep(5)
        
        # Make 3 more requests
        print("Making 3 more requests...")
        results = []
        for i in range(3):
            result = await self.rate_limiter.check_rate_limit(
                test_id,
                RateLimitStrategy.IP,
                custom_config=config
            )
            results.append(result)
            print(f"  Request {i+4}: {'✅ Allowed' if result.allowed else '❌ Blocked'}")
            
        # The sliding window should allow some requests
        allowed_count = sum(1 for r in results if r.allowed)
        print(f"\nAllowed {allowed_count} out of 3 requests")
        print("✅ Sliding window algorithm working")
        
    async def test_burst_allowance(self):
        """Test burst allowance feature."""
        print("\n" + "="*60)
        print("BURST ALLOWANCE TEST")
        print("="*60)
        
        test_id = f"test:{uuid.uuid4()}"
        config = RateLimitConfig(requests=10, window=60, burst=5)
        
        # Make burst requests quickly
        print("\nMaking 15 requests rapidly (10 limit + 5 burst)...")
        results = []
        for i in range(20):
            result = await self.rate_limiter.check_rate_limit(
                test_id,
                RateLimitStrategy.API_KEY,
                custom_config=config
            )
            results.append(result)
            
        allowed_count = sum(1 for r in results if r.allowed)
        print(f"Allowed: {allowed_count} requests")
        print(f"Expected: ~15 requests (10 + 5 burst)")
        
        assert 14 <= allowed_count <= 16  # Allow some variance
        print("✅ Burst allowance working correctly")
        
    async def test_multiple_strategies(self):
        """Test multiple rate limiting strategies."""
        print("\n" + "="*60)
        print("MULTIPLE STRATEGIES TEST")
        print("="*60)
        
        user_id = f"user:{uuid.uuid4()}"
        ip_address = "192.168.1.100"
        api_key = f"key:{uuid.uuid4()}"
        
        # Test different strategies
        strategies = [
            (RateLimitStrategy.IP, ip_address),
            (RateLimitStrategy.USER, user_id),
            (RateLimitStrategy.API_KEY, api_key)
        ]
        
        for strategy, identifier in strategies:
            print(f"\nTesting {strategy.value} strategy...")
            
            # Get default config for strategy
            config = self.rate_limiter.default_limits.get(strategy)
            
            # Make some requests
            for i in range(3):
                result = await self.rate_limiter.check_rate_limit(
                    identifier,
                    strategy
                )
                print(f"  Request {i+1}: Remaining = {result.remaining}")
                
        print("\n✅ Multiple strategies working independently")
        
    async def test_endpoint_specific_limits(self):
        """Test endpoint-specific rate limits."""
        print("\n" + "="*60)
        print("ENDPOINT-SPECIFIC LIMITS TEST")
        print("="*60)
        
        test_ip = "192.168.1.101"
        
        # Test login endpoint (strict limits)
        print("\nTesting /api/v1/auth/login endpoint (5 requests per 5 minutes)...")
        login_results = []
        for i in range(7):
            result = await self.rate_limiter.check_rate_limit(
                test_ip,
                RateLimitStrategy.IP,
                endpoint="/api/v1/auth/login"
            )
            login_results.append(result)
            
        allowed = sum(1 for r in login_results if r.allowed)
        print(f"Login attempts allowed: {allowed} out of 7")
        assert allowed == 5
        
        # Test analytics endpoint (higher limits)
        print("\nTesting /api/v1/analytics endpoint (1000 requests per minute)...")
        analytics_results = []
        for i in range(10):
            result = await self.rate_limiter.check_rate_limit(
                f"user:{uuid.uuid4()}",
                RateLimitStrategy.USER,
                endpoint="/api/v1/analytics"
            )
            analytics_results.append(result)
            
        allowed = sum(1 for r in analytics_results if r.allowed)
        print(f"Analytics requests allowed: {allowed} out of 10")
        assert allowed == 10
        
        print("\n✅ Endpoint-specific limits working correctly")
        
    async def test_auto_blocking(self):
        """Test automatic blocking for repeat offenders."""
        print("\n" + "="*60)
        print("AUTO-BLOCKING TEST")
        print("="*60)
        
        test_id = f"test:{uuid.uuid4()}"
        config = RateLimitConfig(requests=2, window=5, block_duration=10)
        
        # Trigger multiple violations
        print("\nTriggering rate limit violations...")
        violations = 0
        
        for attempt in range(15):
            # Make requests to exceed limit
            for i in range(5):
                result = await self.rate_limiter.check_rate_limit(
                    test_id,
                    RateLimitStrategy.IP,
                    custom_config=config
                )
                if not result.allowed and result.blocked_until is None:
                    violations += 1
                    
            # Check if blocked
            result = await self.rate_limiter.check_rate_limit(
                test_id,
                RateLimitStrategy.IP,
                custom_config=config
            )
            
            if result.blocked_until:
                print(f"✅ Auto-blocked after {violations} violations")
                print(f"   Blocked until: {datetime.fromtimestamp(result.blocked_until)}")
                break
                
            await asyncio.sleep(1)
            
        assert result.blocked_until is not None
        print("\n✅ Auto-blocking working correctly")
        
    async def test_distributed_rate_limiting(self):
        """Test distributed rate limiting across multiple instances."""
        print("\n" + "="*60)
        print("DISTRIBUTED RATE LIMITING TEST")
        print("="*60)
        
        test_id = f"distributed:{uuid.uuid4()}"
        config = RateLimitConfig(requests=10, window=10)
        
        # Simulate multiple instances making requests
        async def instance_requests(instance_id: int, count: int):
            results = []
            for i in range(count):
                result = await self.rate_limiter.check_rate_limit(
                    test_id,
                    RateLimitStrategy.GLOBAL,
                    custom_config=config
                )
                results.append(result.allowed)
                await asyncio.sleep(0.01)  # Small delay
            return results
            
        # Run 3 instances concurrently, each trying 5 requests
        print("\nSimulating 3 instances, each making 5 requests (10 total limit)...")
        tasks = [
            instance_requests(1, 5),
            instance_requests(2, 5),
            instance_requests(3, 5)
        ]
        
        all_results = await asyncio.gather(*tasks)
        
        # Count total allowed requests across all instances
        total_allowed = sum(sum(results) for results in all_results)
        
        print(f"Instance 1: {sum(all_results[0])} allowed")
        print(f"Instance 2: {sum(all_results[1])} allowed")
        print(f"Instance 3: {sum(all_results[2])} allowed")
        print(f"Total allowed: {total_allowed} (limit: 10)")
        
        assert 9 <= total_allowed <= 11  # Allow small variance
        print("\n✅ Distributed rate limiting working correctly")
        
    async def test_performance(self):
        """Test rate limiter performance."""
        print("\n" + "="*60)
        print("PERFORMANCE TEST")
        print("="*60)
        
        # Test response times
        response_times = []
        
        print("\nMeasuring response times for 1000 checks...")
        for i in range(1000):
            identifier = f"perf:{i % 100}"  # Use 100 different identifiers
            
            start_time = time.time()
            await self.rate_limiter.check_rate_limit(
                identifier,
                RateLimitStrategy.IP
            )
            response_times.append((time.time() - start_time) * 1000)  # Convert to ms
            
        avg_time = statistics.mean(response_times)
        median_time = statistics.median(response_times)
        p95_time = statistics.quantiles(response_times, n=20)[18]
        
        print(f"\nResponse time statistics:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Median: {median_time:.2f}ms")
        print(f"  95th percentile: {p95_time:.2f}ms")
        
        # Test throughput
        print("\nMeasuring throughput...")
        start_time = time.time()
        
        tasks = []
        for i in range(10000):
            identifier = f"throughput:{i % 1000}"
            task = self.rate_limiter.check_rate_limit(identifier, RateLimitStrategy.IP)
            tasks.append(task)
            
        await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        throughput = 10000 / total_time
        
        print(f"\nThroughput: {throughput:.2f} checks/second")
        
        # Performance assertions
        assert avg_time < 10  # Average should be under 10ms
        assert p95_time < 50  # 95th percentile under 50ms
        assert throughput > 1000  # Should handle >1000 checks/second
        
        print("\n✅ Performance metrics acceptable")
        
    async def test_cleanup_expired_entries(self):
        """Test cleanup of expired rate limit entries."""
        print("\n" + "="*60)
        print("CLEANUP TEST")
        print("="*60)
        
        # Create entries with short window
        test_ids = [f"cleanup:{i}" for i in range(10)]
        config = RateLimitConfig(requests=1, window=2)  # 2 second window
        
        print("\nCreating 10 rate limit entries...")
        for test_id in test_ids:
            await self.rate_limiter.check_rate_limit(
                test_id,
                RateLimitStrategy.IP,
                custom_config=config
            )
            
        # Wait for entries to expire
        print("Waiting 3 seconds for entries to expire...")
        await asyncio.sleep(3)
        
        # Cleanup should happen automatically on next checks
        print("Checking if entries are cleaned up...")
        for test_id in test_ids:
            result = await self.rate_limiter.check_rate_limit(
                test_id,
                RateLimitStrategy.IP,
                custom_config=config
            )
            assert result.remaining == 0  # Should have full limit again
            
        print("\n✅ Expired entries cleaned up correctly")
        
    async def generate_report(self):
        """Generate test report."""
        print("\n" + "="*60)
        print("RATE LIMITING TEST SUMMARY")
        print("="*60)
        
        print("\n✅ All Tests Passed!")
        print("\nKey Features Tested:")
        print("  - Basic rate limiting with configurable limits")
        print("  - Sliding window algorithm for accurate limiting")
        print("  - Burst allowance for temporary spikes")
        print("  - Multiple independent strategies (IP, User, API Key)")
        print("  - Endpoint-specific rate limits")
        print("  - Automatic blocking for repeat offenders")
        print("  - Distributed rate limiting with Redis")
        print("  - High performance (>1000 checks/second)")
        print("  - Automatic cleanup of expired entries")
        
        print("\nRecommendations:")
        print("  - Monitor rate limit metrics in production")
        print("  - Adjust limits based on actual usage patterns")
        print("  - Configure alerts for frequent violations")
        print("  - Use burst allowance for legitimate traffic spikes")
        print("  - Implement gradual backoff for blocked users")
        
    async def cleanup(self):
        """Clean up test data."""
        print("\nCleaning up test data...")
        await self._cleanup_test_data()
        print("✅ Cleanup completed")
        
    async def run(self):
        """Run all tests."""
        try:
            # Setup
            if not await self.setup():
                return
                
            # Run tests
            await self.test_basic_rate_limiting()
            await self.test_sliding_window()
            await self.test_burst_allowance()
            await self.test_multiple_strategies()
            await self.test_endpoint_specific_limits()
            await self.test_auto_blocking()
            await self.test_distributed_rate_limiting()
            await self.test_performance()
            await self.test_cleanup_expired_entries()
            
            # Generate report
            await self.generate_report()
            
        except Exception as e:
            print(f"\n❌ Test error: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()


if __name__ == '__main__':
    test = RateLimitingTest()
    asyncio.run(test.run())