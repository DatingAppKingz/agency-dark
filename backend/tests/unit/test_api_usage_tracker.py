"""
Unit tests for API Usage Tracker Service
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import json
import redis.asyncio as redis

from services.api_usage_tracker import APIUsageTracker, UsageMetric, RateLimitConfig, UsageStats


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    client = Mock(spec=redis.Redis)
    client.pipeline = Mock(return_value=Mock())
    client.incrby = AsyncMock(return_value=1)
    client.expire = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.setex = AsyncMock(return_value=True)
    client.zadd = AsyncMock(return_value=1)
    return client


@pytest.fixture
def api_usage_tracker(mock_redis_client):
    """Create API usage tracker instance."""
    return APIUsageTracker(redis_client=mock_redis_client)


@pytest.fixture
def sample_rate_limits():
    """Create sample rate limit configuration."""
    return RateLimitConfig(
        requests_per_minute=30,
        requests_per_hour=500,
        requests_per_day=5000,
        sync_operations_per_day=50,
        data_fetch_mb_per_day=500,
        webhooks_per_hour=100
    )


class TestAPIUsageTracker:
    """Test cases for API Usage Tracker"""
    
    @pytest.mark.asyncio
    async def test_track_usage_within_limits(self, api_usage_tracker, mock_redis_client):
        """Test tracking usage within rate limits."""
        api_key_id = "test_key_123"
        
        # Mock pipeline operations
        mock_pipeline = Mock()
        mock_pipeline.incrby = Mock()
        mock_pipeline.expire = Mock()
        mock_pipeline.execute = AsyncMock(return_value=[10, True])  # Count=10, expire success
        mock_redis_client.pipeline.return_value = mock_pipeline
        
        # Mock rate limits
        with patch.object(api_usage_tracker, '_get_rate_limits', return_value=api_usage_tracker._default_limits):
            # Mock other internal methods
            with patch.object(api_usage_tracker, '_store_usage_detail', new_callable=AsyncMock):
                with patch.object(api_usage_tracker, '_update_last_used', new_callable=AsyncMock):
                    result = await api_usage_tracker.track_usage(
                        api_key_id,
                        UsageMetric.REQUESTS,
                        value=1
                    )
                    
                    assert result is True
                    assert mock_pipeline.incrby.called
                    assert mock_pipeline.expire.called
    
    @pytest.mark.asyncio
    async def test_track_usage_exceeds_minute_limit(self, api_usage_tracker, mock_redis_client):
        """Test when minute rate limit is exceeded."""
        api_key_id = "test_key_123"
        
        # Mock pipeline to return count exceeding limit
        mock_pipeline = Mock()
        mock_pipeline.incrby = Mock()
        mock_pipeline.expire = Mock()
        mock_pipeline.execute = AsyncMock(return_value=[100, True])  # Exceeds default 60/min
        mock_redis_client.pipeline.return_value = mock_pipeline
        
        with patch.object(api_usage_tracker, '_get_rate_limits', return_value=api_usage_tracker._default_limits):
            with patch('services.api_usage_tracker.logger') as mock_logger:
                result = await api_usage_tracker.track_usage(
                    api_key_id,
                    UsageMetric.REQUESTS
                )
                
                assert result is False
                mock_logger.warning.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_track_sync_operations(self, api_usage_tracker, mock_redis_client):
        """Test tracking sync operations with daily limit."""
        api_key_id = "test_key_123"
        
        # Mock pipeline for day counter only
        mock_pipeline = Mock()
        mock_pipeline.incrby = Mock()
        mock_pipeline.expire = Mock()
        mock_pipeline.execute = AsyncMock(return_value=[10, True])
        mock_redis_client.pipeline.return_value = mock_pipeline
        
        with patch.object(api_usage_tracker, '_get_rate_limits', return_value=api_usage_tracker._default_limits):
            with patch.object(api_usage_tracker, '_store_usage_detail', new_callable=AsyncMock):
                with patch.object(api_usage_tracker, '_update_last_used', new_callable=AsyncMock):
                    result = await api_usage_tracker.track_usage(
                        api_key_id,
                        UsageMetric.SYNC_OPERATIONS,
                        metadata={"platform": "test"}
                    )
                    
                    assert result is True
    
    @pytest.mark.asyncio
    async def test_get_rate_limits_from_cache(self, api_usage_tracker, mock_redis_client, sample_rate_limits):
        """Test getting rate limits from cache."""
        api_key_id = "test_key_123"
        
        # Mock cached limits
        cached_data = json.dumps({
            "requests_per_minute": sample_rate_limits.requests_per_minute,
            "requests_per_hour": sample_rate_limits.requests_per_hour,
            "requests_per_day": sample_rate_limits.requests_per_day,
            "sync_operations_per_day": sample_rate_limits.sync_operations_per_day,
            "data_fetch_mb_per_day": sample_rate_limits.data_fetch_mb_per_day,
            "webhooks_per_hour": sample_rate_limits.webhooks_per_hour
        })
        mock_redis_client.get = AsyncMock(return_value=cached_data)
        
        limits = await api_usage_tracker._get_rate_limits(api_key_id)
        
        assert limits.requests_per_minute == sample_rate_limits.requests_per_minute
        assert limits.requests_per_hour == sample_rate_limits.requests_per_hour
        mock_redis_client.get.assert_called_once_with(f"limits:{api_key_id}")
    
    @pytest.mark.asyncio
    async def test_get_rate_limits_from_database(self, api_usage_tracker, mock_redis_client, sample_rate_limits):
        """Test getting rate limits from database when not cached."""
        api_key_id = "test_key_123"
        
        # Mock no cache
        mock_redis_client.get = AsyncMock(return_value=None)
        
        # Mock database
        mock_api_key = Mock()
        mock_api_key.key_metadata = {
            "rate_limits": {
                "requests_per_minute": sample_rate_limits.requests_per_minute,
                "requests_per_hour": sample_rate_limits.requests_per_hour,
                "requests_per_day": sample_rate_limits.requests_per_day,
                "sync_operations_per_day": sample_rate_limits.sync_operations_per_day,
                "data_fetch_mb_per_day": sample_rate_limits.data_fetch_mb_per_day,
                "webhooks_per_hour": sample_rate_limits.webhooks_per_hour
            }
        }
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_api_key
        mock_db.close = AsyncMock()
        
        with patch('services.api_usage_tracker.get_db') as mock_get_db:
            mock_get_db.return_value.__aiter__.return_value = [mock_db]
            
            limits = await api_usage_tracker._get_rate_limits(api_key_id)
            
            assert limits.requests_per_minute == sample_rate_limits.requests_per_minute
            # Verify cache was set
            mock_redis_client.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_store_usage_detail(self, api_usage_tracker, mock_redis_client):
        """Test storing detailed usage data."""
        api_key_id = "test_key_123"
        
        with patch('services.api_usage_tracker.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 10, 30, 0)
            
            await api_usage_tracker._store_usage_detail(
                api_key_id,
                UsageMetric.REQUESTS,
                5,
                {"endpoint": "/api/v1/users"}
            )
            
            # Verify zadd was called
            mock_redis_client.zadd.assert_called_once()
            call_args = mock_redis_client.zadd.call_args
            
            # Check key format
            expected_key = f"usage:detail:{api_key_id}:{UsageMetric.REQUESTS}:20240115"
            assert call_args[0][0] == expected_key
            
            # Verify expire was set
            mock_redis_client.expire.assert_called_with(expected_key, 30 * 86400)
    
    @pytest.mark.asyncio
    async def test_update_last_used_debounce(self, api_usage_tracker, mock_redis_client):
        """Test that last_used updates are debounced."""
        api_key_id = "test_key_123"
        
        # First call - should update
        mock_redis_client.set = AsyncMock(return_value=True)
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.close = AsyncMock()
        
        with patch('services.api_usage_tracker.get_db') as mock_get_db:
            mock_get_db.return_value.__aiter__.return_value = [mock_db]
            
            await api_usage_tracker._update_last_used(api_key_id)
            
            # Verify database update
            mock_db.execute.assert_called_once()
            mock_db.commit.assert_called_once()
        
        # Second call within debounce window - should not update
        mock_redis_client.set = AsyncMock(return_value=False)  # nx=True fails
        mock_db.execute.reset_mock()
        
        await api_usage_tracker._update_last_used(api_key_id)
        mock_db.execute.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_usage_stats(self, api_usage_tracker):
        """Test getting usage statistics."""
        api_key_id = "test_key_123"
        
        # Mock _get_period_total to return some data
        with patch.object(api_usage_tracker, '_get_period_total', new_callable=AsyncMock) as mock_get_total:
            mock_get_total.side_effect = [
                100,  # requests for period 1
                0,    # sync_operations for period 1
                0,    # data_fetched for period 1
                50,   # webhooks_sent for period 1
                10,   # errors for period 1
                200,  # requests for period 2
                5,    # sync_operations for period 2
                0,    # data_fetched for period 2
                0,    # webhooks_sent for period 2
                0,    # errors for period 2
            ] + [0] * 100  # Rest return 0
            
            stats = await api_usage_tracker.get_usage_stats(
                api_key_id,
                period="day",
                lookback_days=2
            )
            
            assert len(stats) >= 1
            assert stats[0].api_key_id == api_key_id
            assert UsageMetric.REQUESTS.value in stats[0].metrics
            assert stats[0].metrics[UsageMetric.REQUESTS.value] == 100
    
    @pytest.mark.asyncio
    async def test_check_limit_helper(self, api_usage_tracker, mock_redis_client):
        """Test the check_limit helper method."""
        api_key_id = "test_key_123"
        
        # Mock successful check
        with patch.object(api_usage_tracker, 'track_usage', return_value=True):
            result = await api_usage_tracker.check_limit(api_key_id, UsageMetric.REQUESTS)
            assert result is True
        
        # Mock failed check
        with patch.object(api_usage_tracker, 'track_usage', return_value=False):
            result = await api_usage_tracker.check_limit(api_key_id, UsageMetric.REQUESTS)
            assert result is False
    
    def test_usage_stats_to_dict(self):
        """Test UsageStats to_dict conversion."""
        stats = UsageStats(
            api_key_id="test_123",
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 2),
            metrics={
                UsageMetric.REQUESTS.value: 1000,
                UsageMetric.ERRORS.value: 5
            }
        )
        
        result = stats.to_dict()
        
        assert result["api_key_id"] == "test_123"
        assert result["period_start"] == "2024-01-01T00:00:00"
        assert result["period_end"] == "2024-01-02T00:00:00"
        assert result["metrics"][UsageMetric.REQUESTS.value] == 1000
        assert result["metrics"][UsageMetric.ERRORS.value] == 5
    
    def test_rate_limit_config_defaults(self):
        """Test RateLimitConfig default values."""
        config = RateLimitConfig()
        
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.requests_per_day == 10000
        assert config.sync_operations_per_day == 100
        assert config.data_fetch_mb_per_day == 1000
        assert config.webhooks_per_hour == 500