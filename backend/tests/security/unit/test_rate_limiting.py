"""
Unit tests for advanced rate limiting system.

Tests rate limiting algorithms, dynamic configuration,
cost-based throttling, and geographic restrictions.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import json

from models.user import User, UserRole
from models.rate_limit import (
    RateLimitConfig, RateLimitType, RateLimitAlgorithm,
    RateLimitBucket, RateLimitViolation
)
from core.rate_limit.algorithms import (
    TokenBucketAlgorithm, SlidingWindowAlgorithm,
    FixedWindowAlgorithm, AdaptiveRateLimiter
)
from core.rate_limit.service import DynamicRateLimitService
from core.exceptions import RateLimitExceededError


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    return AsyncMock()


@pytest.fixture
def rate_limit_service():
    """Create rate limit service instance."""
    return DynamicRateLimitService()


@pytest.fixture
def test_user():
    """Create test user."""
    return User(
        id=uuid.uuid4(),
        email="test@example.com",
        role=UserRole.USER,
        agency_id=uuid.uuid4()
    )


@pytest.fixture
def test_config():
    """Create test rate limit configuration."""
    return RateLimitConfig(
        id=uuid.uuid4(),
        name="Test Rate Limit",
        limit_type=RateLimitType.USER,
        requests_per_minute=60,
        requests_per_hour=1000,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
        burst_size=100,
        is_active=True,
        priority=10
    )


class TestTokenBucketAlgorithm:
    """Test cases for token bucket algorithm."""
    
    @pytest.mark.asyncio
    async def test_token_bucket_allow_request(self, mock_redis):
        """Test token bucket allowing request when tokens available."""
        algorithm = TokenBucketAlgorithm(mock_redis)
        
        # Mock Lua script execution returning tokens remaining
        mock_redis.eval.return_value = 50.0
        
        allowed, info = await algorithm.check_and_update(
            key="test_key",
            limit=60,
            window_seconds=60,
            burst_size=100
        )
        
        assert allowed is True
        assert info["tokens_remaining"] == 50.0
        assert info["algorithm"] == "token_bucket"
    
    @pytest.mark.asyncio
    async def test_token_bucket_deny_request(self, mock_redis):
        """Test token bucket denying request when no tokens available."""
        algorithm = TokenBucketAlgorithm(mock_redis)
        
        # Mock Lua script execution returning -1 (no tokens)
        mock_redis.eval.return_value = -1
        
        allowed, info = await algorithm.check_and_update(
            key="test_key",
            limit=60,
            window_seconds=60,
            burst_size=100
        )
        
        assert allowed is False
        assert info["tokens_remaining"] == 0
        assert "retry_after" in info
    
    @pytest.mark.asyncio
    async def test_token_bucket_with_cost(self, mock_redis):
        """Test token bucket with request cost."""
        algorithm = TokenBucketAlgorithm(mock_redis)
        
        # Mock Lua script execution
        mock_redis.eval.return_value = 45.0
        
        allowed, info = await algorithm.check_and_update(
            key="test_key",
            limit=60,
            window_seconds=60,
            burst_size=100,
            cost=5.0
        )
        
        assert allowed is True
        assert info["tokens_remaining"] == 45.0
        assert info["cost"] == 5.0


class TestSlidingWindowAlgorithm:
    """Test cases for sliding window algorithm."""
    
    @pytest.mark.asyncio
    async def test_sliding_window_allow_request(self, mock_redis):
        """Test sliding window allowing request within limit."""
        algorithm = SlidingWindowAlgorithm(mock_redis)
        
        current_time = datetime.utcnow()
        window_start = current_time - timedelta(seconds=60)
        
        # Mock pipeline operations
        pipeline = AsyncMock()
        pipeline.zremrangebyscore = AsyncMock()
        pipeline.zadd = AsyncMock()
        pipeline.zcard = AsyncMock()
        pipeline.execute = AsyncMock(return_value=[None, None, 30])
        
        mock_redis.pipeline.return_value = pipeline
        
        allowed, info = await algorithm.check_and_update(
            key="test_key",
            limit=60,
            window_seconds=60
        )
        
        assert allowed is True
        assert info["current_count"] == 31  # 30 + 1 new request
        assert info["remaining"] == 29
    
    @pytest.mark.asyncio
    async def test_sliding_window_deny_request(self, mock_redis):
        """Test sliding window denying request when limit exceeded."""
        algorithm = SlidingWindowAlgorithm(mock_redis)
        
        # Mock pipeline returning count at limit
        pipeline = AsyncMock()
        pipeline.execute = AsyncMock(return_value=[None, None, 60])
        mock_redis.pipeline.return_value = pipeline
        
        allowed, info = await algorithm.check_and_update(
            key="test_key",
            limit=60,
            window_seconds=60
        )
        
        assert allowed is False
        assert info["current_count"] == 60
        assert info["remaining"] == 0


class TestAdaptiveRateLimiter:
    """Test cases for adaptive rate limiter."""
    
    @pytest.mark.asyncio
    async def test_adaptive_high_reputation_user(self, mock_redis):
        """Test adaptive limiter giving bonus to high reputation user."""
        limiter = AdaptiveRateLimiter(mock_redis)
        
        # Mock reputation score
        mock_redis.get.return_value = "0.9"  # High reputation
        
        # Mock base algorithm allowing request
        with patch.object(limiter.base_algorithm, 'check_and_update', 
                         return_value=(True, {"remaining": 50})):
            
            allowed, info = await limiter.check_and_update(
                key="user:123",
                limit=60,
                window_seconds=60,
                user_id="123"
            )
            
            assert allowed is True
            # High reputation user gets 1.5x limit (90 instead of 60)
            limiter.base_algorithm.check_and_update.assert_called_with(
                key="user:123",
                limit=90,
                window_seconds=60,
                burst_size=None,
                cost=1.0
            )
    
    @pytest.mark.asyncio
    async def test_adaptive_low_reputation_user(self, mock_redis):
        """Test adaptive limiter penalizing low reputation user."""
        limiter = AdaptiveRateLimiter(mock_redis)
        
        # Mock low reputation score
        mock_redis.get.return_value = "0.3"
        
        with patch.object(limiter.base_algorithm, 'check_and_update',
                         return_value=(True, {"remaining": 20})):
            
            allowed, info = await limiter.check_and_update(
                key="user:456",
                limit=60,
                window_seconds=60,
                user_id="456"
            )
            
            # Low reputation user gets 0.7x limit (42 instead of 60)
            limiter.base_algorithm.check_and_update.assert_called_with(
                key="user:456",
                limit=42,
                window_seconds=60,
                burst_size=None,
                cost=1.0
            )
    
    @pytest.mark.asyncio
    async def test_adaptive_system_load_adjustment(self, mock_redis):
        """Test adaptive limiter adjusting based on system load."""
        limiter = AdaptiveRateLimiter(mock_redis)
        
        # Mock system metrics showing high load
        with patch.object(limiter, '_get_system_load', return_value=0.85):
            # Mock normal reputation
            mock_redis.get.return_value = "0.5"
            
            with patch.object(limiter.base_algorithm, 'check_and_update',
                             return_value=(True, {"remaining": 30})):
                
                allowed, info = await limiter.check_and_update(
                    key="user:789",
                    limit=60,
                    window_seconds=60,
                    user_id="789"
                )
                
                # High load reduces limit to 85% (51 instead of 60)
                limiter.base_algorithm.check_and_update.assert_called_with(
                    key="user:789",
                    limit=51,
                    window_seconds=60,
                    burst_size=None,
                    cost=1.0
                )


class TestDynamicRateLimitService:
    """Test cases for dynamic rate limit service."""
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(
        self, rate_limit_service, mock_redis, test_user, test_config
    ):
        """Test rate limit check when request is allowed."""
        mock_db = AsyncMock()
        
        # Mock getting configs
        with patch.object(
            rate_limit_service,
            '_get_applicable_configs',
            return_value=[test_config]
        ):
            # Mock algorithm check
            with patch.object(
                rate_limit_service,
                '_check_with_algorithm',
                return_value=(True, {"remaining": 50})
            ):
                # Mock cost calculation
                with patch.object(
                    rate_limit_service,
                    '_calculate_request_cost',
                    return_value=1.0
                ):
                    allowed, info = await rate_limit_service.check_rate_limit(
                        db=mock_db,
                        identifier="user123",
                        identifier_type=RateLimitType.USER,
                        endpoint="/api/v1/test",
                        user=test_user
                    )
                    
                    assert allowed is True
                    assert info["allowed"] is True
                    assert "limits" in info
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_denied(
        self, rate_limit_service, mock_redis, test_user, test_config
    ):
        """Test rate limit check when request is denied."""
        mock_db = AsyncMock()
        
        with patch.object(
            rate_limit_service,
            '_get_applicable_configs',
            return_value=[test_config]
        ):
            with patch.object(
                rate_limit_service,
                '_check_with_algorithm',
                return_value=(False, {"remaining": 0, "retry_after": 30})
            ):
                # Mock violation logging
                with patch.object(
                    rate_limit_service,
                    '_log_violation',
                    return_value=None
                ):
                    allowed, info = await rate_limit_service.check_rate_limit(
                        db=mock_db,
                        identifier="user123",
                        identifier_type=RateLimitType.USER,
                        endpoint="/api/v1/test",
                        user=test_user
                    )
                    
                    assert allowed is False
                    assert info["allowed"] is False
                    assert info["retry_after"] == 30
    
    @pytest.mark.asyncio
    async def test_check_multiple_limits(
        self, rate_limit_service, mock_redis, test_user
    ):
        """Test checking multiple rate limit types."""
        mock_db = AsyncMock()
        
        # Create configs for different limit types
        user_config = RateLimitConfig(
            limit_type=RateLimitType.USER,
            requests_per_minute=60,
            priority=10
        )
        
        ip_config = RateLimitConfig(
            limit_type=RateLimitType.IP,
            requests_per_minute=30,
            priority=5
        )
        
        with patch.object(
            rate_limit_service,
            '_get_applicable_configs',
            side_effect=[[user_config], [ip_config], []]  # User, IP, Global configs
        ):
            # User limit passes, IP limit fails
            with patch.object(
                rate_limit_service,
                '_check_with_algorithm',
                side_effect=[
                    (True, {"remaining": 50}),  # User check passes
                    (False, {"remaining": 0, "retry_after": 60})  # IP check fails
                ]
            ):
                with patch.object(
                    rate_limit_service,
                    '_log_violation',
                    return_value=None
                ):
                    allowed, info = await rate_limit_service.check_rate_limit(
                        db=mock_db,
                        identifier="user123",
                        identifier_type=RateLimitType.USER,
                        endpoint="/api/v1/test",
                        user=test_user,
                        ip_address="192.168.1.100"
                    )
                    
                    assert allowed is False
                    assert "IP rate limit exceeded" in info["reason"]
    
    @pytest.mark.asyncio
    async def test_geographic_rate_limit(
        self, rate_limit_service, mock_redis, test_user
    ):
        """Test geographic rate limiting."""
        mock_db = AsyncMock()
        
        # Create config with geographic restrictions
        geo_config = RateLimitConfig(
            limit_type=RateLimitType.GEOGRAPHIC,
            blocked_countries=["CN", "RU"],
            geographic_multiplier={"US": 1.0, "EU": 0.8, "AS": 0.5},
            requests_per_minute=60
        )
        
        # Test blocked country
        with patch.object(
            rate_limit_service,
            '_get_applicable_configs',
            return_value=[geo_config]
        ):
            allowed, info = await rate_limit_service.check_rate_limit(
                db=mock_db,
                identifier="user123",
                identifier_type=RateLimitType.USER,
                endpoint="/api/v1/test",
                user=test_user,
                country_code="CN"
            )
            
            assert allowed is False
            assert "blocked" in info["reason"].lower()
    
    @pytest.mark.asyncio
    async def test_cost_based_throttling(
        self, rate_limit_service, mock_redis, test_user
    ):
        """Test cost-based rate limiting."""
        mock_db = AsyncMock()
        
        # Create config with cost limits
        cost_config = RateLimitConfig(
            limit_type=RateLimitType.USER,
            cost_per_minute=100.0,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET
        )
        
        # Mock endpoint cost
        endpoint_cost = MagicMock(
            base_cost=5.0,
            compute_time_factor=0.01,
            database_read_cost=1.0
        )
        
        with patch.object(
            rate_limit_service,
            '_get_applicable_configs',
            return_value=[cost_config]
        ):
            with patch.object(
                rate_limit_service,
                '_get_endpoint_cost',
                return_value=endpoint_cost
            ):
                # Mock algorithm check with cost
                with patch.object(
                    rate_limit_service,
                    '_check_with_algorithm',
                    return_value=(True, {"remaining": 80.0, "cost": 6.0})
                ) as mock_check:
                    allowed, info = await rate_limit_service.check_rate_limit(
                        db=mock_db,
                        identifier="user123",
                        identifier_type=RateLimitType.USER,
                        endpoint="/api/v1/expensive",
                        user=test_user
                    )
                    
                    assert allowed is True
                    # Verify cost was calculated and passed
                    _, kwargs = mock_check.call_args
                    assert kwargs["cost"] >= 6.0  # Base cost + overhead
    
    @pytest.mark.asyncio
    async def test_create_override(
        self, rate_limit_service, mock_redis, test_user
    ):
        """Test creating rate limit override."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        override = await rate_limit_service.create_override(
            db=mock_db,
            target_type=RateLimitType.USER,
            target_identifier="user123",
            reason="Customer escalation",
            expires_in_hours=24,
            created_by=test_user,
            requests_per_minute=1000
        )
        
        assert override.target_type == RateLimitType.USER
        assert override.target_identifier == "user123"
        assert override.requests_per_minute == 1000
        assert override.is_active is True
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_violation_analysis(
        self, rate_limit_service, mock_redis
    ):
        """Test violation analysis."""
        mock_db = AsyncMock()
        
        # Mock query results
        mock_patterns = [
            ("user123", 50),
            ("user456", 30),
            ("user789", 20)
        ]
        
        mock_hourly = [
            (14, 100),
            (15, 150),
            (16, 80)
        ]
        
        mock_db.execute.side_effect = [
            MagicMock(all=lambda: mock_patterns),
            MagicMock(all=lambda: mock_hourly)
        ]
        
        analysis = await rate_limit_service.get_violation_analysis(
            db=mock_db,
            days=7
        )
        
        assert len(analysis["top_violators"]) == 3
        assert analysis["top_violators"][0]["identifier"] == "user123"
        assert analysis["top_violators"][0]["count"] == 50
        
        assert len(analysis["hourly_pattern"]) == 3
        assert analysis["hourly_pattern"][1]["hour"] == 15
        assert analysis["hourly_pattern"][1]["violations"] == 150