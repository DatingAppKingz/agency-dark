"""
Tests for intelligent routing service.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
import json

from modules.api_orchestration.application.routing_service import (
    IntelligentRouter,
    RoutingFactor,
    RouteScore
)
from modules.api_orchestration.domain.schemas import DataSource
from core.domain.models import ModelProfile, Fan
from modules.analytics.domain.models import AnalyticsEvent


@pytest.fixture
def model_profile():
    """Create test model profile."""
    return ModelProfile(
        id="test-model-id",
        user_id="test-user-id",
        agency_id="test-agency-id",
        onlyfans_api_key="of_key",
        inflow_api_key="if_key",
        metadata={}
    )


@pytest.fixture
def fan():
    """Create test fan."""
    return Fan(
        id="test-fan-id",
        model_id="test-model-id",
        onlyfans_user_id="of_fan_123",
        username="testfan",
        total_spent=500.0,
        message_count=20
    )


@pytest.fixture
async def router(db_session):
    """Create router instance."""
    return IntelligentRouter(db_session)


class TestIntelligentRouter:
    """Tests for IntelligentRouter."""
    
    @pytest.mark.asyncio
    async def test_determine_best_source_both_available(
        self, router, model_profile, fan, redis_mock
    ):
        """Test routing when both sources are available."""
        # Mock Redis responses
        redis_mock.get.return_value = None  # No cache, no errors, no rate limits
        
        # Mock performance query
        with patch.object(router.db, 'execute', new_callable=AsyncMock) as mock_execute:
            # Mock result for performance query
            mock_result = AsyncMock()
            mock_result.one.return_value = (500.0, 20)  # 500ms avg, 20 calls
            mock_execute.return_value = mock_result
            
            source = await router.determine_best_source(
                model_profile,
                operation_type="message",
                fan=fan
            )
            
            assert source in [DataSource.ONLYFANS, DataSource.INFLOW]
            
    @pytest.mark.asyncio
    async def test_determine_best_source_rate_limited(
        self, router, model_profile, fan, redis_mock
    ):
        """Test routing when one source is rate limited."""
        # Mock OnlyFans at rate limit
        async def redis_get_side_effect(key):
            if "rate_limit:onlyfans" in key:
                return "59"  # Near limit
            return None
            
        redis_mock.get.side_effect = redis_get_side_effect
        
        # Mock performance query
        with patch.object(router.db, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_result = AsyncMock()
            mock_result.one.return_value = (500.0, 20)
            mock_execute.return_value = mock_result
            
            source = await router.determine_best_source(
                model_profile,
                operation_type="message",
                fan=fan
            )
            
            # Should prefer Inflow due to OnlyFans rate limit
            assert source == DataSource.INFLOW
            
    @pytest.mark.asyncio
    async def test_determine_best_source_feature_requirements(
        self, router, model_profile, fan, redis_mock
    ):
        """Test routing with specific feature requirements."""
        redis_mock.get.return_value = None
        
        with patch.object(router.db, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_result = AsyncMock()
            mock_result.one.return_value = (500.0, 20)
            mock_execute.return_value = mock_result
            
            # Request feature that only Inflow supports
            source = await router.determine_best_source(
                model_profile,
                operation_type="message",
                fan=fan,
                features_required=["webhooks", "automation"]
            )
            
            # Should prefer Inflow for these features
            assert source == DataSource.INFLOW
            
    @pytest.mark.asyncio
    async def test_determine_best_source_cached(
        self, router, model_profile, fan, redis_mock
    ):
        """Test routing with cached result."""
        # Mock cached route
        cached_data = {
            "source": "onlyfans",
            "score": 0.85,
            "factors": {}
        }
        redis_mock.get.return_value = json.dumps(cached_data)
        
        source = await router.determine_best_source(
            model_profile,
            operation_type="message",
            fan=fan
        )
        
        assert source == DataSource.ONLYFANS
        # Should not execute any DB queries due to cache
        
    @pytest.mark.asyncio
    async def test_calculate_source_score(
        self, router, model_profile, redis_mock
    ):
        """Test score calculation for a source."""
        redis_mock.get.return_value = None
        
        with patch.object(router.db, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_result = AsyncMock()
            mock_result.one.return_value = (300.0, 50)  # Good performance
            mock_execute.return_value = mock_result
            
            score = await router._calculate_source_score(
                model_profile,
                DataSource.ONLYFANS,
                operation_type="message",
                fan=None,
                payload_size=1000,
                features_required=None
            )
            
            assert isinstance(score, RouteScore)
            assert score.source == DataSource.ONLYFANS
            assert 0 <= score.score <= 1
            assert all(f in score.factors for f in RoutingFactor)
            
    @pytest.mark.asyncio
    async def test_check_availability_with_errors(
        self, router, redis_mock
    ):
        """Test availability check with high error rate."""
        redis_mock.get.return_value = "15"  # High error count
        
        availability = await router._check_availability(DataSource.ONLYFANS)
        
        assert availability == 0.2  # Low availability due to errors
        
    @pytest.mark.asyncio
    async def test_check_availability_maintenance(
        self, router, redis_mock
    ):
        """Test availability during maintenance."""
        async def redis_get_side_effect(key):
            if "maintenance" in key:
                return "true"
            return None
            
        redis_mock.get.side_effect = redis_get_side_effect
        
        availability = await router._check_availability(DataSource.INFLOW)
        
        assert availability == 0.0  # No availability during maintenance
        
    @pytest.mark.asyncio
    async def test_check_rate_limits(self, router, model_profile, redis_mock):
        """Test rate limit checking."""
        test_cases = [
            (None, 1.0),      # No usage
            ("10", 1.0),      # Low usage
            ("45", 0.7),      # Medium usage
            ("55", 0.3),      # High usage
            ("60", 0.0),      # At limit
        ]
        
        for usage, expected_score in test_cases:
            redis_mock.get.return_value = usage
            
            score = await router._check_rate_limits(
                model_profile, DataSource.ONLYFANS
            )
            
            assert score == expected_score
            
    def test_calculate_cost_score(self, router):
        """Test cost score calculation."""
        # Lower cost should give higher score
        score1 = router._calculate_cost_score(
            DataSource.INFLOW,
            "message",
            None
        )
        
        score2 = router._calculate_cost_score(
            DataSource.ONLYFANS,
            "mass_message",
            5000  # Large payload
        )
        
        assert 0 <= score1 <= 1
        assert 0 <= score2 <= 1
        
    def test_check_feature_support(self, router):
        """Test feature support checking."""
        # OnlyFans exclusive features
        score = router._check_feature_support(
            DataSource.ONLYFANS,
            ["live_streaming", "vault"]
        )
        assert score == 1.0
        
        # Inflow exclusive features
        score = router._check_feature_support(
            DataSource.INFLOW,
            ["webhooks", "automation", "campaigns"]
        )
        assert score == 1.0
        
        # Mixed features
        score = router._check_feature_support(
            DataSource.ONLYFANS,
            ["ppv_messages", "webhooks"]  # Only supports first
        )
        assert score == 0.5
        
    def test_get_user_preference_score(self, router, model_profile):
        """Test user preference scoring."""
        # No preference
        score = router._get_user_preference_score(
            model_profile, DataSource.ONLYFANS
        )
        assert score == 0.7
        
        # With preference
        model_profile.metadata = {"preferred_api_source": "onlyfans"}
        score = router._get_user_preference_score(
            model_profile, DataSource.ONLYFANS
        )
        assert score == 1.0
        
        score = router._get_user_preference_score(
            model_profile, DataSource.INFLOW
        )
        assert score == 0.5
        
    @pytest.mark.asyncio
    async def test_record_api_call_success(
        self, router, model_profile, db_session, redis_mock
    ):
        """Test recording successful API call."""
        await router.record_api_call(
            model_profile,
            DataSource.ONLYFANS,
            "message",
            response_time=250.0,
            success=True
        )
        
        # Should create analytics event
        await db_session.commit()
        
        # Should increment rate limit counter
        redis_mock.incr.assert_called()
        
    @pytest.mark.asyncio
    async def test_record_api_call_failure(
        self, router, model_profile, db_session, redis_mock
    ):
        """Test recording failed API call."""
        await router.record_api_call(
            model_profile,
            DataSource.INFLOW,
            "message",
            response_time=5000.0,
            success=False,
            error="Timeout"
        )
        
        # Should increment error counter
        error_calls = [
            call for call in redis_mock.incr.call_args_list
            if "api_errors" in str(call)
        ]
        assert len(error_calls) > 0