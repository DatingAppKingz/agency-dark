"""
Integration tests for rate limiting system.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from core.rate_limiting.rate_limiter import rate_limiter, RateLimitTier, RateLimitResult
from core.rate_limiting.models import (
    RateLimitConfig, UserRateLimit, IPRateLimit,
    RateLimitViolation, RateLimitWhitelist
)
from core.middleware.rate_limit import DynamicRateLimiter
from core.domain.models import User, Agency


class TestRateLimiter:
    
    @pytest.mark.asyncio
    async def test_basic_rate_limiting(self):
        """Test basic rate limiting functionality."""
        identifier = "test_user_123"
        endpoint = "/api/v1/test"
        
        # First request should be allowed
        result = await rate_limiter.check_rate_limit(
            identifier=identifier,
            endpoint=endpoint,
            tier=RateLimitTier.FREE
        )
        
        assert result.allowed is True
        assert result.remaining > 0
        
        # Make multiple requests to hit the limit
        for _ in range(20):  # Free tier has 20 req/min by default
            await rate_limiter.check_rate_limit(
                identifier=identifier,
                endpoint=endpoint,
                tier=RateLimitTier.FREE
            )
        
        # Next request should be denied
        result = await rate_limiter.check_rate_limit(
            identifier=identifier,
            endpoint=endpoint,
            tier=RateLimitTier.FREE
        )
        
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after is not None
    
    @pytest.mark.asyncio
    async def test_burst_handling(self):
        """Test burst request handling."""
        identifier = "burst_test_user"
        endpoint = "/api/v1/burst"
        
        # Make burst requests
        results = []
        for _ in range(7):  # Free tier has burst size of 5
            result = await rate_limiter.check_rate_limit(
                identifier=identifier,
                endpoint=endpoint,
                tier=RateLimitTier.FREE
            )
            results.append(result.allowed)
            await asyncio.sleep(0.1)  # Small delay
        
        # First 5 should be allowed (burst), rest should check normal rate
        allowed_count = sum(results)
        assert allowed_count >= 5  # At least burst size should be allowed
    
    @pytest.mark.asyncio
    async def test_different_tiers(self):
        """Test rate limits for different tiers."""
        endpoint = "/api/v1/tier_test"
        
        # Test each tier
        tier_limits = {
            RateLimitTier.FREE: 20,
            RateLimitTier.BASIC: 60,
            RateLimitTier.PROFESSIONAL: 200,
            RateLimitTier.ENTERPRISE: 1000
        }
        
        for tier, expected_limit in tier_limits.items():
            identifier = f"tier_test_{tier.value}"
            
            # Check initial limit
            result = await rate_limiter.check_rate_limit(
                identifier=identifier,
                endpoint=endpoint,
                tier=tier
            )
            
            assert result.allowed is True
            assert result.limit == expected_limit
    
    @pytest.mark.asyncio
    async def test_whitelist(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test whitelisting functionality."""
        # Add user to whitelist
        whitelist = RateLimitWhitelist(
            user_id=test_user.id,
            endpoint_pattern="*",
            reason="Test whitelist",
            approved_by_id=test_user.id
        )
        db_session.add(whitelist)
        await db_session.commit()
        
        # Clear cache
        await rate_limiter.redis.delete(f"whitelist:{test_user.id}:::")
        
        # Make many requests - should all be allowed
        identifier = f"user:{test_user.id}"
        for _ in range(100):
            result = await rate_limiter.check_rate_limit(
                identifier=identifier,
                endpoint="/api/v1/test",
                user_id=str(test_user.id),
                tier=RateLimitTier.FREE
            )
            assert result.allowed is True
            assert result.reason == "whitelisted"
    
    @pytest.mark.asyncio
    async def test_ip_blocking(
        self,
        db_session: AsyncSession
    ):
        """Test IP blocking functionality."""
        blocked_ip = "192.168.1.100"
        
        # Add IP to blocklist
        ip_block = IPRateLimit(
            ip_address=blocked_ip,
            action="block",
            reason="Test block"
        )
        db_session.add(ip_block)
        await db_session.commit()
        
        # Clear cache
        await rate_limiter.redis.delete(f"ip_block:{blocked_ip}")
        
        # Request from blocked IP should be denied
        result = await rate_limiter.check_rate_limit(
            identifier=f"ip:{blocked_ip}",
            endpoint="/api/v1/test",
            ip_address=blocked_ip,
            tier=RateLimitTier.FREE
        )
        
        assert result.allowed is False
        assert result.reason == "ip_blocked"
    
    @pytest.mark.asyncio
    async def test_user_rate_limit_override(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test user-specific rate limit overrides."""
        # Set custom limit for user
        user_limit = UserRateLimit(
            user_id=test_user.id,
            limit_multiplier=2.0,  # Double the limits
            reason="Premium user"
        )
        db_session.add(user_limit)
        await db_session.commit()
        
        # Check rate limit
        identifier = f"user:{test_user.id}"
        result = await rate_limiter.check_rate_limit(
            identifier=identifier,
            endpoint="/api/v1/test",
            user_id=str(test_user.id),
            tier=RateLimitTier.FREE
        )
        
        # Should have double the normal limit (20 * 2 = 40)
        assert result.limit == 40
    
    @pytest.mark.asyncio
    async def test_endpoint_specific_limits(
        self,
        db_session: AsyncSession
    ):
        """Test endpoint-specific rate limit configurations."""
        # Add specific config for analytics endpoint
        config = RateLimitConfig(
            tier=RateLimitTier.FREE,
            endpoint_pattern="/api/v1/analytics/*",
            limit_type="api_calls",
            requests_per_minute=10,  # Lower limit for analytics
            burst_size=3,
            is_active=True
        )
        db_session.add(config)
        await db_session.commit()
        
        # Clear cache
        cache_key = f"config:{RateLimitTier.FREE}:/api/v1/analytics/revenue"
        if cache_key in rate_limiter._config_cache:
            del rate_limiter._config_cache[cache_key]
        
        # Check limit for analytics endpoint
        result = await rate_limiter.check_rate_limit(
            identifier="test_analytics_user",
            endpoint="/api/v1/analytics/revenue",
            tier=RateLimitTier.FREE
        )
        
        assert result.limit == 10  # Should use specific config
    
    @pytest.mark.asyncio
    async def test_violation_logging(
        self,
        db_session: AsyncSession
    ):
        """Test that violations are logged correctly."""
        identifier = "violation_test_user"
        endpoint = "/api/v1/test"
        
        # Hit the rate limit
        for _ in range(25):  # Exceed free tier limit
            await rate_limiter.check_rate_limit(
                identifier=identifier,
                endpoint=endpoint,
                tier=RateLimitTier.FREE
            )
        
        # Check for violation record
        from sqlalchemy import select
        result = await db_session.execute(
            select(RateLimitViolation)
            .where(RateLimitViolation.endpoint == endpoint)
            .order_by(RateLimitViolation.violated_at.desc())
        )
        
        violation = result.scalar_one_or_none()
        assert violation is not None
        assert violation.limit_type == "combined"
        assert violation.limit_value == 20
    
    @pytest.mark.asyncio
    async def test_usage_stats(self):
        """Test usage statistics retrieval."""
        identifier = "stats_test_user"
        endpoint = "/api/v1/test"
        
        # Make some requests
        for _ in range(5):
            await rate_limiter.check_rate_limit(
                identifier=identifier,
                endpoint=endpoint,
                tier=RateLimitTier.FREE
            )
        
        # Get usage stats
        stats = await rate_limiter.get_usage_stats(identifier, endpoint)
        
        assert stats["requests_per_minute"] >= 5
        assert "requests_per_hour" in stats
        assert "requests_per_day" in stats


class TestDynamicRateLimiter:
    
    @pytest.mark.asyncio
    async def test_set_user_limit(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test setting custom user limits."""
        await DynamicRateLimiter.set_user_limit(
            user_id=str(test_user.id),
            limit_multiplier=1.5,
            custom_limits={"requests_per_hour": 5000},
            valid_days=7,
            reason="Test custom limit"
        )
        
        # Verify limit was created
        from sqlalchemy import select
        result = await db_session.execute(
            select(UserRateLimit).where(UserRateLimit.user_id == test_user.id)
        )
        
        user_limit = result.scalar_one()
        assert user_limit.limit_multiplier == 1.5
        assert user_limit.custom_limits["requests_per_hour"] == 5000
    
    @pytest.mark.asyncio
    async def test_block_ip(
        self,
        db_session: AsyncSession
    ):
        """Test IP blocking through dynamic limiter."""
        test_ip = "10.0.0.100"
        
        await DynamicRateLimiter.block_ip(
            ip_address=test_ip,
            duration_hours=2,
            reason="Suspicious activity"
        )
        
        # Verify IP was blocked
        from sqlalchemy import select
        result = await db_session.execute(
            select(IPRateLimit).where(IPRateLimit.ip_address == test_ip)
        )
        
        ip_block = result.scalar_one()
        assert ip_block.action == "block"
        assert ip_block.expires_at > datetime.utcnow()
    
    @pytest.mark.asyncio
    async def test_get_violations(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test retrieving violations."""
        # Create test violation
        violation = RateLimitViolation(
            user_id=test_user.id,
            ip_address="192.168.1.1",
            endpoint="/api/v1/test",
            method="GET",
            limit_type="requests_per_minute",
            limit_value=20,
            actual_value=25
        )
        db_session.add(violation)
        await db_session.commit()
        
        # Get violations
        violations = await DynamicRateLimiter.get_violations(
            user_id=str(test_user.id),
            hours=1
        )
        
        assert len(violations) >= 1
        assert violations[0].user_id == test_user.id


class TestRateLimitHeaders:
    
    def test_rate_limit_result_headers(self):
        """Test rate limit headers generation."""
        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=75,
            reset_at=datetime.utcnow() + timedelta(minutes=1)
        )
        
        headers = result.to_headers()
        
        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "75"
        assert "X-RateLimit-Reset" in headers
        assert "Retry-After" not in headers  # Only for denied requests
        
        # Test denied request headers
        denied_result = RateLimitResult(
            allowed=False,
            limit=100,
            remaining=0,
            reset_at=datetime.utcnow() + timedelta(minutes=1),
            retry_after=60
        )
        
        denied_headers = denied_result.to_headers()
        assert denied_headers["X-RateLimit-Remaining"] == "0"
        assert denied_headers["Retry-After"] == "60"