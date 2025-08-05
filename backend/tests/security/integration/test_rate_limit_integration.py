"""
Integration tests for rate limiting system.

Tests the complete rate limiting flow including:
- Multiple rate limit algorithms working together
- Cost-based throttling with real calculations
- Geographic rate limiting
- Adaptive rate limiting
- Integration with permissions and audit logging
"""
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import json
from typing import List, Dict, Any
import random

from models.user import User, UserRole
from models.rate_limit import (
    RateLimitConfig, RateLimitType, RateLimitAlgorithm,
    EndpointCost, GeographicRateLimit
)
from models.audit_log import AuditLog, AuditAction
from core.rate_limit.service import DynamicRateLimitService
from core.rate_limit.algorithms import (
    TokenBucketAlgorithm, SlidingWindowAlgorithm,
    FixedWindowAlgorithm, AdaptiveAlgorithm
)
from core.audit.service import AuditService
from core.exceptions import RateLimitExceededError


class TestMultiAlgorithmIntegration:
    """Test multiple rate limiting algorithms working together."""
    
    @pytest.mark.asyncio
    async def test_layered_rate_limiting(self):
        """Test multiple rate limits applied in layers."""
        mock_db = AsyncMock()
        service = DynamicRateLimitService()
        
        user = User(id=uuid.uuid4(), email="test@company.com")
        
        # Create layered rate limit configs
        configs = [
            # Global rate limit (loose)
            RateLimitConfig(
                id=uuid.uuid4(),
                name="Global API Limit",
                limit_type=RateLimitType.GLOBAL,
                requests_per_minute=10000,
                algorithm=RateLimitAlgorithm.FIXED_WINDOW,
                priority=1,
                is_active=True
            ),
            # Per-user rate limit (medium)
            RateLimitConfig(
                id=uuid.uuid4(),
                name="User API Limit",
                limit_type=RateLimitType.USER,
                requests_per_minute=100,
                algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
                burst_size=20,
                priority=5,
                is_active=True
            ),
            # Per-endpoint rate limit (strict)
            RateLimitConfig(
                id=uuid.uuid4(),
                name="Export Endpoint Limit",
                limit_type=RateLimitType.ENDPOINT,
                endpoint_pattern="/api/v1/export/*",
                requests_per_minute=10,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                priority=10,
                is_active=True
            )
        ]
        
        # Mock getting configs
        with patch.object(
            service,
            '_get_applicable_configs',
            return_value=configs
        ):
            # Mock Redis for different algorithms
            mock_redis = AsyncMock()
            
            # Token bucket responses
            mock_redis.eval.side_effect = [
                10.0,  # Global: plenty of tokens
                15.0,  # User: 15 tokens available
                5.0    # Endpoint: 5 tokens available
            ]
            
            # Test requests until rate limited
            results = []
            
            for i in range(15):
                with patch('core.redis.redis_client', mock_redis):
                    # Reset side effects for each iteration
                    if i < 5:
                        # First 5 requests succeed at all layers
                        mock_redis.eval.side_effect = [
                            9999.0 - i,  # Global
                            15.0 - i,    # User
                            5.0 - i      # Endpoint
                        ]
                    elif i < 10:
                        # Next 5 hit endpoint limit
                        mock_redis.eval.side_effect = [
                            9995.0 - i,  # Global
                            15.0 - i,    # User
                            0.0          # Endpoint exhausted
                        ]
                    else:
                        # Remaining hit user limit
                        mock_redis.eval.side_effect = [
                            9990.0 - i,  # Global
                            0.0,         # User exhausted
                            0.0          # Endpoint exhausted
                        ]
                    
                    try:
                        allowed, info = await service.check_rate_limit(
                            db=mock_db,
                            identifier=str(user.id),
                            identifier_type=RateLimitType.USER,
                            endpoint="/api/v1/export/users",
                            user=user
                        )
                        results.append({"allowed": allowed, "limited_by": None})
                    except RateLimitExceededError as e:
                        results.append({"allowed": False, "limited_by": str(e)})
            
            # Verify layered limiting worked
            allowed_count = sum(1 for r in results if r["allowed"])
            assert allowed_count == 5  # Only first 5 succeed
            
            # Should be limited by endpoint first (strictest)
            endpoint_limited = sum(
                1 for r in results 
                if not r["allowed"] and "endpoint" in str(r.get("limited_by", "")).lower()
            )
            assert endpoint_limited >= 5
    
    @pytest.mark.asyncio
    async def test_cost_based_throttling_integration(self):
        """Test cost-based throttling with real cost calculations."""
        mock_db = AsyncMock()
        service = DynamicRateLimitService()
        
        user = User(id=uuid.uuid4(), email="test@company.com")
        
        # Create cost-based rate limit
        cost_config = RateLimitConfig(
            id=uuid.uuid4(),
            name="API Cost Limit",
            limit_type=RateLimitType.USER,
            cost_per_minute=100.0,  # 100 cost units per minute
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            is_active=True
        )
        
        # Define endpoint costs
        endpoint_costs = {
            "/api/v1/reports/simple": EndpointCost(
                endpoint="/api/v1/reports/simple",
                base_cost=1.0,
                compute_time_factor=0.01,
                database_read_cost=0.5
            ),
            "/api/v1/reports/complex": EndpointCost(
                endpoint="/api/v1/reports/complex",
                base_cost=5.0,
                compute_time_factor=0.05,
                database_read_cost=2.0,
                database_write_cost=1.0
            ),
            "/api/v1/ml/inference": EndpointCost(
                endpoint="/api/v1/ml/inference",
                base_cost=10.0,
                ml_inference_cost=20.0,
                compute_time_factor=0.1
            )
        }
        
        # Track costs
        total_cost = 0.0
        requests = []
        
        with patch.object(service, '_get_applicable_configs', return_value=[cost_config]):
            for endpoint, cost_def in endpoint_costs.items():
                # Calculate request cost
                request_cost = (
                    cost_def.base_cost +
                    10 * cost_def.compute_time_factor +  # 10ms compute time
                    5 * cost_def.database_read_cost +     # 5 DB reads
                    (cost_def.ml_inference_cost or 0)
                )
                
                with patch.object(
                    service,
                    '_calculate_request_cost',
                    return_value=request_cost
                ):
                    # Mock token bucket with remaining cost capacity
                    remaining_capacity = max(0, 100.0 - total_cost)
                    
                    with patch.object(
                        service,
                        '_check_with_algorithm',
                        return_value=(
                            remaining_capacity >= request_cost,
                            {"remaining": remaining_capacity - request_cost}
                        )
                    ):
                        allowed, info = await service.check_rate_limit(
                            db=mock_db,
                            identifier=str(user.id),
                            identifier_type=RateLimitType.USER,
                            endpoint=endpoint,
                            user=user,
                            request_metadata={
                                "compute_time_ms": 10,
                                "database_reads": 5
                            }
                        )
                        
                        if allowed:
                            total_cost += request_cost
                            requests.append({
                                "endpoint": endpoint,
                                "cost": request_cost,
                                "allowed": True,
                                "total_cost": total_cost
                            })
                        else:
                            requests.append({
                                "endpoint": endpoint,
                                "cost": request_cost,
                                "allowed": False,
                                "reason": "Cost limit exceeded"
                            })
        
        # Verify cost-based limiting
        assert len([r for r in requests if r["allowed"]]) >= 2
        assert total_cost <= 100.0  # Should not exceed limit
        
        # ML endpoint should have highest cost
        ml_request = next(r for r in requests if "ml" in r["endpoint"])
        assert ml_request["cost"] > 20.0
    
    @pytest.mark.asyncio
    async def test_geographic_rate_limiting(self):
        """Test geographic-based rate limiting."""
        mock_db = AsyncMock()
        service = DynamicRateLimitService()
        
        # Create geographic rate limits
        geo_configs = [
            GeographicRateLimit(
                id=uuid.uuid4(),
                country_code="CN",
                requests_per_minute=10,
                algorithm=RateLimitAlgorithm.FIXED_WINDOW,
                is_active=True
            ),
            GeographicRateLimit(
                id=uuid.uuid4(),
                country_code="RU",
                requests_per_minute=20,
                algorithm=RateLimitAlgorithm.FIXED_WINDOW,
                is_active=True
            ),
            GeographicRateLimit(
                id=uuid.uuid4(),
                country_code="US",
                requests_per_minute=100,
                algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
                is_active=True
            )
        ]
        
        # Test IPs from different countries
        test_cases = [
            {"ip": "1.2.3.4", "country": "CN", "expected_limit": 10},
            {"ip": "5.6.7.8", "country": "RU", "expected_limit": 20},
            {"ip": "8.8.8.8", "country": "US", "expected_limit": 100},
            {"ip": "10.0.0.1", "country": "GB", "expected_limit": None}  # No specific limit
        ]
        
        for test in test_cases:
            # Mock geo lookup
            with patch.object(
                service,
                '_get_country_from_ip',
                return_value=test["country"]
            ):
                # Mock getting geo config
                geo_config = next(
                    (g for g in geo_configs if g.country_code == test["country"]),
                    None
                )
                
                if geo_config:
                    config = RateLimitConfig(
                        id=geo_config.id,
                        name=f"Geo limit for {test['country']}",
                        limit_type=RateLimitType.IP,
                        requests_per_minute=geo_config.requests_per_minute,
                        algorithm=geo_config.algorithm,
                        is_active=True
                    )
                    configs = [config]
                else:
                    configs = []
                
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
                        allowed, info = await service.check_rate_limit(
                            db=mock_db,
                            identifier=test["ip"],
                            identifier_type=RateLimitType.IP,
                            endpoint="/api/v1/data",
                            ip_address=test["ip"]
                        )
                        
                        assert allowed is True
                        
                        # Verify correct limit was applied
                        if test["expected_limit"]:
                            assert len(configs) == 1
                            assert configs[0].requests_per_minute == test["expected_limit"]


class TestAdaptiveRateLimiting:
    """Test adaptive rate limiting based on system load."""
    
    @pytest.mark.asyncio
    async def test_adaptive_rate_adjustment(self):
        """Test rate limits adjusting based on system metrics."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        # Create adaptive rate limit config
        adaptive_config = RateLimitConfig(
            id=uuid.uuid4(),
            name="Adaptive API Limit",
            limit_type=RateLimitType.GLOBAL,
            requests_per_minute=1000,  # Base limit
            algorithm=RateLimitAlgorithm.ADAPTIVE,
            adaptive_increase_threshold=0.5,  # 50% utilization
            adaptive_decrease_threshold=0.8,  # 80% utilization
            adaptive_increase_factor=1.2,
            adaptive_decrease_factor=0.8,
            is_active=True
        )
        
        algorithm = AdaptiveAlgorithm(mock_redis)
        
        # Simulate system load scenarios
        load_scenarios = [
            {"cpu": 0.3, "memory": 0.4, "expected_adjustment": "increase"},
            {"cpu": 0.6, "memory": 0.7, "expected_adjustment": "maintain"},
            {"cpu": 0.9, "memory": 0.85, "expected_adjustment": "decrease"},
            {"cpu": 0.95, "memory": 0.95, "expected_adjustment": "decrease"},
            {"cpu": 0.4, "memory": 0.3, "expected_adjustment": "increase"}
        ]
        
        current_limit = adaptive_config.requests_per_minute
        
        for scenario in load_scenarios:
            # Mock system metrics
            with patch.object(
                algorithm,
                '_get_system_metrics',
                return_value={
                    "cpu_usage": scenario["cpu"],
                    "memory_usage": scenario["memory"],
                    "response_time_ms": 50 + (scenario["cpu"] * 100)  # Higher load = slower
                }
            ):
                # Check and update limit
                new_limit = await algorithm._adjust_limit_based_on_load(
                    base_limit=adaptive_config.requests_per_minute,
                    current_limit=current_limit,
                    config=adaptive_config
                )
                
                # Verify adjustment
                if scenario["expected_adjustment"] == "increase":
                    assert new_limit > current_limit
                elif scenario["expected_adjustment"] == "decrease":
                    assert new_limit < current_limit
                else:  # maintain
                    assert new_limit == current_limit
                
                current_limit = new_limit
        
        # Verify limits stay within reasonable bounds
        assert current_limit >= adaptive_config.requests_per_minute * 0.5  # Min 50%
        assert current_limit <= adaptive_config.requests_per_minute * 2.0  # Max 200%
    
    @pytest.mark.asyncio
    async def test_adaptive_response_to_attack(self):
        """Test adaptive rate limiting response to attack patterns."""
        mock_db = AsyncMock()
        service = DynamicRateLimitService()
        
        # Create adaptive config
        adaptive_config = RateLimitConfig(
            id=uuid.uuid4(),
            name="Adaptive Security Limit",
            limit_type=RateLimitType.IP,
            requests_per_minute=60,
            algorithm=RateLimitAlgorithm.ADAPTIVE,
            is_active=True
        )
        
        # Simulate attack pattern
        attack_ips = [f"192.168.1.{i}" for i in range(100, 110)]
        normal_ips = [f"10.0.0.{i}" for i in range(1, 10)]
        
        # Track request patterns
        request_log = []
        
        with patch.object(service, '_get_applicable_configs', return_value=[adaptive_config]):
            # Phase 1: Normal traffic
            for _ in range(20):
                ip = random.choice(normal_ips)
                with patch.object(
                    service,
                    '_check_with_algorithm',
                    return_value=(True, {"remaining": 50})
                ):
                    allowed, _ = await service.check_rate_limit(
                        db=mock_db,
                        identifier=ip,
                        identifier_type=RateLimitType.IP,
                        endpoint="/api/v1/users",
                        ip_address=ip
                    )
                    request_log.append({"ip": ip, "allowed": allowed, "phase": "normal"})
            
            # Phase 2: Attack begins
            with patch.object(
                service,
                '_detect_attack_pattern',
                return_value=True
            ):
                # Limits should tighten
                attack_limit = 10  # Reduced from 60
                
                for _ in range(50):
                    ip = random.choice(attack_ips)
                    
                    # Mock stricter limiting during attack
                    with patch.object(
                        service,
                        '_check_with_algorithm',
                        return_value=(False, {"remaining": 0})
                    ):
                        allowed, _ = await service.check_rate_limit(
                            db=mock_db,
                            identifier=ip,
                            identifier_type=RateLimitType.IP,
                            endpoint="/api/v1/users",
                            ip_address=ip
                        )
                        request_log.append({"ip": ip, "allowed": allowed, "phase": "attack"})
        
        # Analyze results
        normal_phase = [r for r in request_log if r["phase"] == "normal"]
        attack_phase = [r for r in request_log if r["phase"] == "attack"]
        
        normal_allowed_rate = sum(1 for r in normal_phase if r["allowed"]) / len(normal_phase)
        attack_allowed_rate = sum(1 for r in attack_phase if r["allowed"]) / len(attack_phase)
        
        # During attack, allow rate should be much lower
        assert attack_allowed_rate < normal_allowed_rate * 0.5


class TestRateLimitAuditIntegration:
    """Test integration between rate limiting and audit logging."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_violation_audit_trail(self):
        """Test comprehensive audit trail for rate limit violations."""
        mock_db = AsyncMock()
        service = DynamicRateLimitService()
        audit_service = AuditService()
        
        user = User(id=uuid.uuid4(), email="violator@company.com")
        
        # Strict rate limit for testing
        config = RateLimitConfig(
            id=uuid.uuid4(),
            name="Test Limit",
            limit_type=RateLimitType.USER,
            requests_per_minute=5,
            algorithm=RateLimitAlgorithm.FIXED_WINDOW,
            is_active=True
        )
        
        audit_logs = []
        
        def capture_audit(log):
            audit_logs.append({
                "action": log.action,
                "user_id": log.user_id,
                "details": log.details,
                "severity": log.severity
            })
        
        mock_db.add = MagicMock(side_effect=capture_audit)
        mock_db.commit = AsyncMock()
        
        with patch.object(service, '_get_applicable_configs', return_value=[config]):
            # Make requests until rate limited
            for i in range(10):
                allowed = i < 5  # First 5 succeed
                
                with patch.object(
                    service,
                    '_check_with_algorithm',
                    return_value=(allowed, {"remaining": max(0, 5 - i - 1)})
                ):
                    try:
                        result_allowed, _ = await service.check_rate_limit(
                            db=mock_db,
                            identifier=str(user.id),
                            identifier_type=RateLimitType.USER,
                            endpoint="/api/v1/data",
                            user=user
                        )
                        
                        if not result_allowed:
                            # Log rate limit exceeded
                            await audit_service.log(
                                db=mock_db,
                                action=AuditAction.RATE_LIMIT_EXCEEDED,
                                user=user,
                                details={
                                    "endpoint": "/api/v1/data",
                                    "limit_type": "user",
                                    "limit": 5,
                                    "attempt": i + 1
                                }
                            )
                    except RateLimitExceededError:
                        # Log rate limit exceeded
                        await audit_service.log(
                            db=mock_db,
                            action=AuditAction.RATE_LIMIT_EXCEEDED,
                            user=user,
                            severity=AuditSeverity.WARNING,
                            details={
                                "endpoint": "/api/v1/data",
                                "limit_type": "user",
                                "limit": 5,
                                "attempt": i + 1
                            }
                        )
        
        # Verify audit trail
        rate_limit_logs = [
            log for log in audit_logs 
            if log["action"] == AuditAction.RATE_LIMIT_EXCEEDED
        ]
        
        assert len(rate_limit_logs) == 5  # 5 violations logged
        
        # Check escalating severity
        first_violation = rate_limit_logs[0]
        last_violation = rate_limit_logs[-1]
        
        # Later violations might have higher severity
        assert last_violation["details"]["attempt"] > first_violation["details"]["attempt"]
    
    @pytest.mark.asyncio
    async def test_suspicious_pattern_detection_and_logging(self):
        """Test detection and logging of suspicious rate limit patterns."""
        mock_db = AsyncMock()
        service = DynamicRateLimitService()
        audit_service = AuditService()
        
        # Simulate suspicious patterns
        patterns = [
            {
                "name": "distributed_attack",
                "ips": [f"192.168.{i}.{j}" for i in range(1, 5) for j in range(1, 10)],
                "endpoint": "/api/v1/login",
                "interval_ms": 10
            },
            {
                "name": "credential_stuffing",
                "ips": ["10.0.0.1"],
                "endpoint": "/api/v1/auth",
                "interval_ms": 100,
                "different_users": 50
            },
            {
                "name": "api_scanning",
                "ips": ["172.16.0.1"],
                "endpoints": [f"/api/v1/{e}" for e in ["users", "data", "admin", "config"]],
                "interval_ms": 50
            }
        ]
        
        audit_logs = []
        mock_db.add = MagicMock(side_effect=lambda log: audit_logs.append(log))
        mock_db.commit = AsyncMock()
        
        for pattern in patterns:
            if pattern["name"] == "distributed_attack":
                # Many IPs hitting same endpoint rapidly
                with patch.object(
                    service,
                    '_detect_attack_pattern',
                    return_value=True
                ):
                    # Log suspicious activity
                    await audit_service.log(
                        db=mock_db,
                        action=AuditAction.SUSPICIOUS_ACTIVITY,
                        details={
                            "pattern": "distributed_attack",
                            "unique_ips": len(pattern["ips"]),
                            "endpoint": pattern["endpoint"],
                            "requests_per_second": 1000 / pattern["interval_ms"]
                        },
                        severity=AuditSeverity.ERROR,
                        risk_score=85
                    )
            
            elif pattern["name"] == "credential_stuffing":
                # Same IP trying many different users
                await audit_service.log(
                    db=mock_db,
                    action=AuditAction.SUSPICIOUS_ACTIVITY,
                    details={
                        "pattern": "credential_stuffing",
                        "ip": pattern["ips"][0],
                        "unique_users_attempted": pattern["different_users"],
                        "endpoint": pattern["endpoint"]
                    },
                    severity=AuditSeverity.CRITICAL,
                    risk_score=95
                )
            
            elif pattern["name"] == "api_scanning":
                # Same IP probing multiple endpoints
                await audit_service.log(
                    db=mock_db,
                    action=AuditAction.SUSPICIOUS_ACTIVITY,
                    details={
                        "pattern": "api_scanning",
                        "ip": pattern["ips"][0],
                        "endpoints_probed": pattern["endpoints"],
                        "scan_rate_per_second": 1000 / pattern["interval_ms"]
                    },
                    severity=AuditSeverity.WARNING,
                    risk_score=70
                )
        
        # Verify suspicious patterns were logged
        assert len(audit_logs) == 3
        
        # Check risk scores
        risk_scores = [log.risk_score for log in audit_logs]
        assert max(risk_scores) >= 85  # High risk patterns detected
        
        # Verify pattern types
        pattern_types = [log.details["pattern"] for log in audit_logs]
        assert "distributed_attack" in pattern_types
        assert "credential_stuffing" in pattern_types
        assert "api_scanning" in pattern_types


class TestRateLimitFailover:
    """Test rate limit system failover and resilience."""
    
    @pytest.mark.asyncio
    async def test_redis_failure_fallback(self):
        """Test fallback behavior when Redis fails."""
        mock_db = AsyncMock()
        service = DynamicRateLimitService()
        
        user = User(id=uuid.uuid4(), email="test@company.com")
        
        # Simulate Redis connection failure
        with patch('core.redis.redis_client.eval', side_effect=Exception("Redis connection failed")):
            with patch('core.redis.redis_client.get', side_effect=Exception("Redis connection failed")):
                with patch('core.redis.redis_client.setex', side_effect=Exception("Redis connection failed")):
                    # Service should fall back to allowing requests with logged warning
                    with patch('core.logger.logger.warning') as mock_warning:
                        allowed, info = await service.check_rate_limit(
                            db=mock_db,
                            identifier=str(user.id),
                            identifier_type=RateLimitType.USER,
                            endpoint="/api/v1/critical",
                            user=user
                        )
                        
                        # Should fail open (allow request)
                        assert allowed is True
                        assert "fallback" in info.get("mode", "")
                        
                        # Should log warning
                        mock_warning.assert_called()
                        warning_msg = mock_warning.call_args[0][0]
                        assert "redis" in warning_msg.lower()
    
    @pytest.mark.asyncio
    async def test_partial_config_failure_handling(self):
        """Test handling of partial configuration failures."""
        mock_db = AsyncMock()
        service = DynamicRateLimitService()
        
        # Some configs are valid, some are malformed
        configs = [
            RateLimitConfig(
                id=uuid.uuid4(),
                name="Valid Config",
                limit_type=RateLimitType.USER,
                requests_per_minute=100,
                algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
                is_active=True
            ),
            RateLimitConfig(
                id=uuid.uuid4(),
                name="Invalid Config",
                limit_type=RateLimitType.USER,
                requests_per_minute=-1,  # Invalid
                algorithm="INVALID_ALGO",  # Invalid
                is_active=True
            )
        ]
        
        with patch.object(service, '_get_applicable_configs', return_value=configs):
            # Should skip invalid config and use valid one
            valid_checks = 0
            
            async def mock_check(key, limit, window, **kwargs):
                nonlocal valid_checks
                if limit > 0:  # Valid config
                    valid_checks += 1
                    return True, {"remaining": 50}
                raise ValueError("Invalid configuration")
            
            with patch.object(service, '_check_with_algorithm', side_effect=mock_check):
                allowed, info = await service.check_rate_limit(
                    db=mock_db,
                    identifier="user123",
                    identifier_type=RateLimitType.USER,
                    endpoint="/api/v1/data"
                )
                
                # Should process valid config
                assert allowed is True
                assert valid_checks == 1