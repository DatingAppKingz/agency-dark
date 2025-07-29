"""
Unit tests for resilience components
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from core.resilience.circuit_breaker import (
    CircuitBreaker, 
    CircuitState, 
    CircuitBreakerError,
    DistributedCircuitBreaker
)
from core.resilience.retry_policy import (
    RetryPolicy,
    ExponentialBackoff,
    LinearBackoff,
    FibonacciBackoff,
    DecorrelatedJitterBackoff
)
from core.resilience.failover import (
    FailoverManager,
    FailoverStrategy,
    Endpoint,
    EndpointHealth
)
from core.resilience.graceful_degradation import (
    GracefulDegradation,
    DegradationLevel,
    FeatureFlag
)


class TestCircuitBreaker:
    """Test circuit breaker functionality"""
    
    @pytest.mark.unit
    async def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state allows calls"""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=60
        )
        
        # Successful call
        @cb
        async def successful_call():
            return "success"
        
        result = await successful_call()
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    @pytest.mark.unit
    async def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures"""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=60
        )
        
        @cb
        async def failing_call():
            raise Exception("Test failure")
        
        # Fail threshold times
        for _ in range(3):
            with pytest.raises(Exception):
                await failing_call()
        
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3
        
        # Next call should fail fast
        with pytest.raises(CircuitBreakerError):
            await failing_call()
    
    @pytest.mark.unit
    async def test_circuit_breaker_half_open_state(self):
        """Test circuit breaker transitions to half-open"""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms
            success_threshold=2
        )
        
        call_count = 0
        
        @cb
        async def test_call():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Fail")
            return "success"
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await test_call()
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Should be half-open now
        result = await test_call()
        assert result == "success"
        assert cb.state == CircuitState.HALF_OPEN
        
        # One more success should close circuit
        result = await test_call()
        assert cb.state == CircuitState.CLOSED
    
    @pytest.mark.unit
    async def test_distributed_circuit_breaker(self, redis_mock):
        """Test distributed circuit breaker with Redis"""
        dcb = DistributedCircuitBreaker(
            name="distributed_test",
            failure_threshold=3,
            recovery_timeout=60,
            redis_client=redis_mock
        )
        
        # Simulate failures from multiple instances
        await dcb.record_failure()
        await dcb.record_failure()
        
        # Check state is shared
        state = await dcb.get_state()
        assert state["failure_count"] == 2
        
        # One more failure should open circuit
        await dcb.record_failure()
        state = await dcb.get_state()
        assert state["state"] == CircuitState.OPEN.value


class TestRetryPolicy:
    """Test retry policies"""
    
    @pytest.mark.unit
    async def test_exponential_backoff(self):
        """Test exponential backoff retry policy"""
        policy = ExponentialBackoff(
            base_delay=0.1,
            max_delay=1.0,
            multiplier=2
        )
        
        delays = []
        for attempt in range(5):
            delay = policy.get_delay(attempt)
            delays.append(delay)
        
        # Verify exponential growth
        assert delays[0] == 0.1
        assert delays[1] == 0.2
        assert delays[2] == 0.4
        assert delays[3] == 0.8
        assert delays[4] == 1.0  # Max delay
    
    @pytest.mark.unit
    async def test_retry_with_policy(self):
        """Test retry decorator with policy"""
        call_count = 0
        
        @RetryPolicy(max_attempts=3, backoff=LinearBackoff(0.01))
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        result = await flaky_function()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.unit
    async def test_retry_with_specific_exceptions(self):
        """Test retry only on specific exceptions"""
        @RetryPolicy(
            max_attempts=3,
            retry_on=(ValueError,),
            backoff=LinearBackoff(0.01)
        )
        async def selective_retry():
            raise TypeError("Should not retry")
        
        with pytest.raises(TypeError):
            await selective_retry()
    
    @pytest.mark.unit
    def test_fibonacci_backoff(self):
        """Test Fibonacci backoff sequence"""
        policy = FibonacciBackoff(base_delay=0.1, max_delay=10.0)
        
        delays = [policy.get_delay(i) for i in range(7)]
        
        # Verify Fibonacci sequence
        assert delays[0] == 0.1  # 1 * 0.1
        assert delays[1] == 0.1  # 1 * 0.1
        assert delays[2] == 0.2  # 2 * 0.1
        assert delays[3] == 0.3  # 3 * 0.1
        assert delays[4] == 0.5  # 5 * 0.1
        assert delays[5] == 0.8  # 8 * 0.1
        assert delays[6] == 1.3  # 13 * 0.1
    
    @pytest.mark.unit
    def test_decorrelated_jitter_backoff(self):
        """Test decorrelated jitter backoff"""
        policy = DecorrelatedJitterBackoff(
            base_delay=1.0,
            max_delay=60.0
        )
        
        # Get multiple delays
        delays = [policy.get_delay(3) for _ in range(10)]
        
        # All should be different due to randomization
        assert len(set(delays)) > 1
        
        # All should be within bounds
        for delay in delays:
            assert 0 <= delay <= 60.0


class TestFailover:
    """Test failover mechanisms"""
    
    @pytest.mark.unit
    async def test_round_robin_failover(self):
        """Test round-robin failover strategy"""
        endpoints = [
            Endpoint("http://api1.example.com", priority=1),
            Endpoint("http://api2.example.com", priority=1),
            Endpoint("http://api3.example.com", priority=1)
        ]
        
        manager = FailoverManager(
            endpoints=endpoints,
            strategy=FailoverStrategy.ROUND_ROBIN
        )
        
        # Should cycle through endpoints
        selected = []
        for _ in range(6):
            endpoint = await manager.get_endpoint()
            selected.append(endpoint.url)
        
        assert selected == [
            "http://api1.example.com",
            "http://api2.example.com",
            "http://api3.example.com",
            "http://api1.example.com",
            "http://api2.example.com",
            "http://api3.example.com"
        ]
    
    @pytest.mark.unit
    async def test_priority_failover(self):
        """Test priority-based failover"""
        endpoints = [
            Endpoint("http://primary.example.com", priority=1),
            Endpoint("http://secondary.example.com", priority=2),
            Endpoint("http://tertiary.example.com", priority=3)
        ]
        
        manager = FailoverManager(
            endpoints=endpoints,
            strategy=FailoverStrategy.PRIORITY
        )
        
        # Should always select highest priority healthy endpoint
        for _ in range(3):
            endpoint = await manager.get_endpoint()
            assert endpoint.url == "http://primary.example.com"
        
        # Mark primary as unhealthy
        await manager.mark_unhealthy("http://primary.example.com")
        
        # Should now select secondary
        endpoint = await manager.get_endpoint()
        assert endpoint.url == "http://secondary.example.com"
    
    @pytest.mark.unit
    async def test_health_checking(self):
        """Test endpoint health checking"""
        endpoint = Endpoint("http://api.example.com")
        manager = FailoverManager(endpoints=[endpoint])
        
        # Mock health check
        async def mock_health_check(url):
            return url == "http://api.example.com"
        
        manager.health_check = mock_health_check
        
        # Run health check
        await manager.check_endpoint_health(endpoint)
        assert endpoint.health == EndpointHealth.HEALTHY
        
        # Simulate failure
        async def failing_health_check(url):
            return False
        
        manager.health_check = failing_health_check
        await manager.check_endpoint_health(endpoint)
        assert endpoint.health == EndpointHealth.UNHEALTHY


class TestGracefulDegradation:
    """Test graceful degradation functionality"""
    
    @pytest.mark.unit
    def test_degradation_levels(self):
        """Test degradation level transitions"""
        gd = GracefulDegradation()
        
        assert gd.current_level == DegradationLevel.NORMAL
        
        # Degrade service
        gd.set_level(DegradationLevel.DEGRADED)
        assert gd.current_level == DegradationLevel.DEGRADED
        
        # Check feature availability
        assert gd.is_feature_available("core_functionality")
        assert gd.is_feature_available("enhanced_features")
        assert not gd.is_feature_available("luxury_features")
    
    @pytest.mark.unit
    def test_feature_flags_respect_degradation(self):
        """Test feature flags respect degradation levels"""
        gd = GracefulDegradation()
        
        # Add feature flags
        gd.add_feature_flag(FeatureFlag(
            name="premium_feature",
            enabled=True,
            min_level=DegradationLevel.NORMAL
        ))
        
        gd.add_feature_flag(FeatureFlag(
            name="basic_feature",
            enabled=True,
            min_level=DegradationLevel.ESSENTIAL
        ))
        
        # Normal mode - all features available
        assert gd.is_feature_available("premium_feature")
        assert gd.is_feature_available("basic_feature")
        
        # Essential mode - only basic features
        gd.set_level(DegradationLevel.ESSENTIAL)
        assert not gd.is_feature_available("premium_feature")
        assert gd.is_feature_available("basic_feature")
    
    @pytest.mark.unit
    async def test_auto_degradation(self):
        """Test automatic degradation based on metrics"""
        gd = GracefulDegradation()
        
        # Simulate high load
        metrics = {
            "cpu_usage": 95,
            "memory_usage": 80,
            "error_rate": 0.02
        }
        
        gd.evaluate_metrics(metrics)
        assert gd.current_level == DegradationLevel.DEGRADED
        
        # Simulate recovery
        metrics = {
            "cpu_usage": 50,
            "memory_usage": 60,
            "error_rate": 0.001
        }
        
        gd.evaluate_metrics(metrics)
        assert gd.current_level == DegradationLevel.NORMAL
    
    @pytest.mark.unit
    def test_degradation_callbacks(self):
        """Test callbacks on degradation level changes"""
        gd = GracefulDegradation()
        callback_called = False
        new_level = None
        
        def on_level_change(level):
            nonlocal callback_called, new_level
            callback_called = True
            new_level = level
        
        gd.on_level_change(on_level_change)
        gd.set_level(DegradationLevel.ESSENTIAL)
        
        assert callback_called
        assert new_level == DegradationLevel.ESSENTIAL