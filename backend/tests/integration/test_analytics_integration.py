"""
Integration tests for analytics module with real data flow.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from modules.analytics.domain.models import (
    ModelAnalytics, FanAnalytics, RevenueAnalytics,
    EngagementAnalytics, ContentAnalytics
)
from modules.analytics.infrastructure.cache import AnalyticsCacheService
from modules.models.domain.models import Model
from modules.analytics.domain.models import Fan
from modules.financial.domain.models import Transaction


class TestAnalyticsIntegration:
    """Test complete analytics data flow from ingestion to reporting."""
    
    @pytest.fixture
    async def setup_test_data(self, test_db: AsyncSession):
        """Setup comprehensive test data."""
        # Create agency
        agency_id = uuid4()
        
        # Create models
        models = []
        for i in range(3):
            model = Model(
                id=uuid4(),
                agency_id=agency_id,
                username=f"model_{i}",
                display_name=f"Model {i}",
                platform="onlyfans",
                is_active=True
            )
            test_db.add(model)
            models.append(model)
        
        # Create fans for each model
        fans = []
        for model in models:
            for j in range(50):
                fan = Fan(
                    id=uuid4(),
                    model_id=model.id,
                    username=f"fan_{model.username}_{j}",
                    display_name=f"Fan {j}",
                    subscription_status="active" if j < 40 else "expired",
                    total_spent=Decimal(str(100 + j * 10)),
                    message_count=j * 2,
                    created_at=datetime.utcnow() - timedelta(days=j)
                )
                test_db.add(fan)
                fans.append(fan)
        
        # Create transactions
        for fan in fans[:100]:  # First 100 fans have transactions
            for k in range(5):
                transaction = Transaction(
                    id=uuid4(),
                    agency_id=agency_id,
                    model_id=fan.model_id,
                    fan_id=fan.id,
                    amount=Decimal(str(20 + k * 5)),
                    transaction_type="tip" if k % 2 == 0 else "ppv",
                    status="completed",
                    created_at=datetime.utcnow() - timedelta(days=k)
                )
                test_db.add(transaction)
        
        await test_db.commit()
        
        return {
            "agency_id": agency_id,
            "models": models,
            "fans": fans
        }
    
    @pytest.mark.asyncio
    async def test_real_time_analytics_aggregation(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        setup_test_data
    ):
        """Test real-time analytics aggregation process."""
        agency_id = setup_test_data["agency_id"]
        model = setup_test_data["models"][0]
        
        # Trigger analytics aggregation
        response = await async_client.post(
            f"/api/v1/analytics/aggregate",
            json={
                "model_id": str(model.id),
                "date": datetime.utcnow().date().isoformat()
            }
        )
        assert response.status_code == 200
        
        # Wait for aggregation to complete
        await asyncio.sleep(2)
        
        # Fetch aggregated analytics
        response = await async_client.get(
            f"/api/v1/analytics/models/{model.id}",
            params={
                "date_from": datetime.utcnow().date().isoformat(),
                "date_to": datetime.utcnow().date().isoformat()
            }
        )
        assert response.status_code == 200
        
        analytics = response.json()
        assert analytics["metrics"]["fans"]["total"] == 50
        assert analytics["metrics"]["fans"]["active"] == 40
        assert analytics["metrics"]["revenue"]["total"] > 0
    
    @pytest.mark.asyncio
    async def test_analytics_caching_performance(
        self,
        async_client: AsyncClient,
        setup_test_data
    ):
        """Test analytics caching for performance."""
        model_id = setup_test_data["models"][0].id
        
        # First request (cache miss)
        import time
        start_time = time.time()
        response = await async_client.get(
            f"/api/v1/analytics/models/{model_id}"
        )
        first_request_time = time.time() - start_time
        assert response.status_code == 200
        
        # Second request (cache hit)
        start_time = time.time()
        response = await async_client.get(
            f"/api/v1/analytics/models/{model_id}"
        )
        second_request_time = time.time() - start_time
        assert response.status_code == 200
        
        # Cache hit should be significantly faster
        assert second_request_time < first_request_time * 0.1
    
    @pytest.mark.asyncio
    async def test_multi_model_comparison(
        self,
        async_client: AsyncClient,
        setup_test_data
    ):
        """Test comparing analytics across multiple models."""
        model_ids = [str(m.id) for m in setup_test_data["models"]]
        
        response = await async_client.post(
            "/api/v1/analytics/compare",
            json={
                "model_ids": model_ids,
                "metrics": ["revenue", "fans", "engagement"],
                "date_from": (datetime.utcnow() - timedelta(days=30)).date().isoformat(),
                "date_to": datetime.utcnow().date().isoformat()
            }
        )
        assert response.status_code == 200
        
        comparison = response.json()
        assert len(comparison["models"]) == 3
        assert all(metric in comparison["models"][0] for metric in ["revenue", "fans", "engagement"])
    
    @pytest.mark.asyncio
    async def test_fan_segmentation(
        self,
        async_client: AsyncClient,
        setup_test_data
    ):
        """Test fan segmentation and analysis."""
        model_id = setup_test_data["models"][0].id
        
        response = await async_client.get(
            f"/api/v1/analytics/fans/segments",
            params={
                "model_id": str(model_id),
                "segment_by": "spending_tier"
            }
        )
        assert response.status_code == 200
        
        segments = response.json()
        assert "segments" in segments
        assert len(segments["segments"]) > 0
        
        # Test custom segmentation
        response = await async_client.post(
            "/api/v1/analytics/fans/segment",
            json={
                "model_id": str(model_id),
                "criteria": {
                    "total_spent": {"min": 200, "max": 500},
                    "subscription_status": ["active"],
                    "last_activity_days": 7
                }
            }
        )
        assert response.status_code == 200
        custom_segment = response.json()
        assert "fan_count" in custom_segment
        assert "total_value" in custom_segment
    
    @pytest.mark.asyncio
    async def test_revenue_forecasting(
        self,
        async_client: AsyncClient,
        setup_test_data
    ):
        """Test revenue forecasting based on historical data."""
        model_id = setup_test_data["models"][0].id
        
        response = await async_client.post(
            "/api/v1/analytics/forecast",
            json={
                "model_id": str(model_id),
                "forecast_days": 30,
                "include_confidence_intervals": True
            }
        )
        assert response.status_code == 200
        
        forecast = response.json()
        assert "predictions" in forecast
        assert len(forecast["predictions"]) == 30
        assert "confidence_intervals" in forecast
        assert forecast["predictions"][0]["revenue"] > 0
    
    @pytest.mark.asyncio
    async def test_engagement_tracking(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        setup_test_data
    ):
        """Test engagement metrics tracking and analysis."""
        model = setup_test_data["models"][0]
        
        # Create engagement data
        engagement = EngagementAnalytics(
            id=uuid4(),
            model_id=model.id,
            agency_id=model.agency_id,
            date=datetime.utcnow().date(),
            messages_sent=150,
            messages_received=120,
            avg_response_time=5.5,
            unique_conversations=45,
            media_sent=30,
            likes_received=500,
            comments_received=200
        )
        test_db.add(engagement)
        await test_db.commit()
        
        # Fetch engagement analytics
        response = await async_client.get(
            f"/api/v1/analytics/engagement/{model.id}",
            params={
                "period": "daily",
                "days": 7
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["summary"]["total_messages_sent"] >= 150
        assert data["summary"]["response_rate"] > 0
        assert "trends" in data
    
    @pytest.mark.asyncio
    async def test_content_performance_analysis(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        setup_test_data
    ):
        """Test content performance analytics."""
        model = setup_test_data["models"][0]
        
        # Create content data
        content_items = []
        for i in range(10):
            content = ContentAnalytics(
                id=uuid4(),
                model_id=model.id,
                agency_id=model.agency_id,
                content_type="post" if i % 2 == 0 else "story",
                title=f"Content {i}",
                posted_at=datetime.utcnow() - timedelta(days=i),
                views=1000 - i * 50,
                likes=100 - i * 5,
                comments=50 - i * 2,
                revenue_generated=Decimal(str(200 - i * 10))
            )
            test_db.add(content)
            content_items.append(content)
        
        await test_db.commit()
        
        # Analyze content performance
        response = await async_client.get(
            f"/api/v1/analytics/content/{model.id}",
            params={
                "sort_by": "engagement_rate",
                "limit": 5
            }
        )
        assert response.status_code == 200
        
        top_content = response.json()
        assert len(top_content["items"]) <= 5
        assert top_content["items"][0]["engagement_rate"] >= top_content["items"][-1]["engagement_rate"]
    
    @pytest.mark.asyncio
    async def test_churn_prediction(
        self,
        async_client: AsyncClient,
        setup_test_data
    ):
        """Test fan churn prediction."""
        model_id = setup_test_data["models"][0].id
        
        response = await async_client.post(
            "/api/v1/analytics/fans/churn-prediction",
            json={
                "model_id": str(model_id),
                "include_risk_factors": True
            }
        )
        assert response.status_code == 200
        
        predictions = response.json()
        assert "at_risk_fans" in predictions
        assert len(predictions["at_risk_fans"]) > 0
        assert "risk_factors" in predictions["at_risk_fans"][0]
        assert predictions["at_risk_fans"][0]["churn_probability"] > 0
    
    @pytest.mark.asyncio
    async def test_analytics_export_formats(
        self,
        async_client: AsyncClient,
        setup_test_data
    ):
        """Test exporting analytics in different formats."""
        model_id = setup_test_data["models"][0].id
        
        formats = ["csv", "excel", "pdf", "json"]
        
        for format in formats:
            response = await async_client.post(
                "/api/v1/reporting/export",
                json={
                    "export_type": "analytics",
                    "format": format,
                    "model_id": str(model_id),
                    "date_from": (datetime.utcnow() - timedelta(days=30)).date().isoformat(),
                    "date_to": datetime.utcnow().date().isoformat()
                }
            )
            assert response.status_code == 200
            
            if format == "json":
                assert isinstance(response.json(), dict)
            else:
                assert len(response.content) > 0


class TestAnalyticsWebSocket:
    """Test real-time analytics updates via WebSocket."""
    
    @pytest.mark.asyncio
    async def test_real_time_revenue_updates(
        self,
        websocket_client,
        setup_test_data
    ):
        """Test receiving real-time revenue updates."""
        model_id = setup_test_data["models"][0].id
        
        # Connect to WebSocket
        async with websocket_client.connect(
            f"/ws/analytics/{model_id}"
        ) as websocket:
            # Simulate a new transaction
            await websocket.send_json({
                "type": "subscribe",
                "metrics": ["revenue", "fans"]
            })
            
            # Should receive initial state
            data = await websocket.receive_json()
            assert data["type"] == "initial_state"
            assert "revenue" in data["data"]
            
            # Simulate revenue update
            # In real scenario, this would be triggered by actual transaction
            await asyncio.sleep(1)
            
            # Should receive update
            data = await websocket.receive_json()
            assert data["type"] == "metric_update"
            assert data["metric"] in ["revenue", "fans"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])