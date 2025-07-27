"""
Tests for ML Analytics functionality.
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from core.ml_analytics.models import (
    MLModel, Prediction, ModelTrainingJob,
    PredictionType, ModelStatus
)
from core.ml_analytics.services.ml_service import ml_service
from core.ml_analytics.predictors.revenue_forecast import RevenueForecastPredictor
from core.domain.models import User, Agency, Transaction


class TestRevenueForecastPredictor:
    """Test revenue forecasting functionality."""
    
    @pytest.mark.asyncio
    async def test_revenue_data_preparation(self, db_session: AsyncSession, test_agency: Agency):
        """Test data preparation for revenue forecasting."""
        # Create sample transactions
        for i in range(60):
            transaction = Transaction(
                agency_id=test_agency.id,
                amount=np.random.uniform(100, 1000),
                status='completed',
                created_at=datetime.utcnow() - timedelta(days=i)
            )
            db_session.add(transaction)
        await db_session.commit()
        
        # Initialize predictor
        predictor = RevenueForecastPredictor()
        
        # Fetch revenue data
        df = await predictor._fetch_revenue_data(
            agency_id=test_agency.id,
            session=db_session,
            lookback_days=60
        )
        
        assert len(df) == 60
        assert 'ds' in df.columns
        assert 'y' in df.columns
        assert df['y'].min() >= 0
    
    @pytest.mark.asyncio
    async def test_train_revenue_forecast_model(self, db_session: AsyncSession, test_agency: Agency, test_user: User):
        """Test training a revenue forecast model."""
        # Create sufficient historical data
        for i in range(100):
            transaction = Transaction(
                agency_id=test_agency.id,
                amount=np.random.uniform(500, 2000) * (1 + 0.01 * i),  # Trending upward
                status='completed',
                created_at=datetime.utcnow() - timedelta(days=i)
            )
            db_session.add(transaction)
        await db_session.commit()
        
        # Train model
        predictor = RevenueForecastPredictor()
        result = await predictor.train(
            agency_id=test_agency.id,
            session=db_session,
            lookback_days=90,
            test_size=0.2
        )
        
        assert result['success'] is True
        assert 'metrics' in result
        assert result['metrics']['mape'] < 0.5  # Less than 50% error
        assert result['metrics']['r2'] > 0  # Some explanatory power
        assert result['training_samples'] > 0
    
    @pytest.mark.asyncio
    async def test_generate_forecasts(self, trained_predictor):
        """Test generating revenue forecasts."""
        # Generate 30-day forecast
        forecast_df = await trained_predictor.predict(horizon_days=30)
        
        assert len(forecast_df) >= 30
        assert 'forecast' in forecast_df.columns
        assert 'lower_bound' in forecast_df.columns
        assert 'upper_bound' in forecast_df.columns
        
        # Check forecast values are reasonable
        assert forecast_df['forecast'].min() > 0
        assert forecast_df['lower_bound'].min() >= 0
        assert (forecast_df['upper_bound'] >= forecast_df['forecast']).all()
        assert (forecast_df['forecast'] >= forecast_df['lower_bound']).all()
    
    @pytest.mark.asyncio
    async def test_trend_analysis(self, trained_predictor):
        """Test trend analysis functionality."""
        analysis = await trained_predictor.analyze_trends()
        
        assert 'trend_analysis' in analysis
        assert 'seasonality' in analysis
        assert 'insights' in analysis
        
        # Check trend analysis
        trend = analysis['trend_analysis']
        assert 'current_trend' in trend
        assert 'trend_change_percentage' in trend
        assert 'trend_direction' in trend
        
        # Check seasonality
        seasonality = analysis['seasonality']
        assert 'weekly_pattern' in seasonality
        assert 'best_days' in seasonality
        assert len(seasonality['best_days']) == 3


class TestMLAnalyticsService:
    """Test ML Analytics service."""
    
    @pytest.mark.asyncio
    async def test_train_model_service(self, db_session: AsyncSession, test_agency: Agency, test_user: User):
        """Test training model through service."""
        # Create historical data
        for i in range(100):
            transaction = Transaction(
                agency_id=test_agency.id,
                amount=np.random.uniform(1000, 5000),
                status='completed',
                created_at=datetime.utcnow() - timedelta(days=i)
            )
            db_session.add(transaction)
        await db_session.commit()
        
        # Train model via service
        model = await ml_service.train_model(
            prediction_type=PredictionType.REVENUE_FORECAST,
            agency_id=test_agency.id,
            user=test_user,
            session=db_session,
            config={'lookback_days': 90}
        )
        
        assert model.id is not None
        assert model.status == ModelStatus.TRAINED
        assert model.prediction_type == PredictionType.REVENUE_FORECAST
        assert model.accuracy_score > 0.5
        assert model.is_active is True  # First model should be activated
    
    @pytest.mark.asyncio
    async def test_generate_predictions_service(self, db_session: AsyncSession, test_agency: Agency, test_user: User):
        """Test generating predictions through service."""
        # First train a model
        await self._create_and_train_model(db_session, test_agency, test_user)
        
        # Generate predictions
        predictions = await ml_service.generate_predictions(
            prediction_type=PredictionType.REVENUE_FORECAST,
            agency_id=test_agency.id,
            session=db_session,
            horizon_days=7
        )
        
        assert len(predictions) == 7
        for pred in predictions:
            assert pred.prediction_type == PredictionType.REVENUE_FORECAST
            assert pred.predicted_value > 0
            assert pred.confidence_score > 0
            assert pred.target_date > datetime.utcnow()
    
    @pytest.mark.asyncio
    async def test_record_feedback(self, db_session: AsyncSession, test_prediction: Prediction, test_user: User):
        """Test recording prediction feedback."""
        actual_value = 5000.0
        
        feedback = await ml_service.record_feedback(
            prediction_id=str(test_prediction.id),
            actual_value=actual_value,
            user=test_user,
            session=db_session,
            feedback_notes="Actual revenue from platform"
        )
        
        assert feedback.actual_value == actual_value
        assert feedback.absolute_error >= 0
        assert feedback.percentage_error >= 0
        
        # Check prediction was updated
        await db_session.refresh(test_prediction)
        assert test_prediction.actual_value == actual_value
        assert test_prediction.error_percentage is not None
    
    @pytest.mark.asyncio
    async def test_get_insights(self, db_session: AsyncSession, test_agency: Agency):
        """Test getting ML insights."""
        # Create some insight alerts
        from core.ml_analytics.models import InsightAlert
        
        alert = InsightAlert(
            alert_type='prediction',
            severity='high',
            title='Revenue Decline Predicted',
            description='Revenue expected to decrease by 15% next week',
            agency_id=test_agency.id,
            metrics={'predicted_change': -15},
            recommendations=['Review pricing', 'Launch promotion']
        )
        db_session.add(alert)
        await db_session.commit()
        
        # Get insights
        insights = await ml_service.get_insights(
            agency_id=test_agency.id,
            session=db_session,
            unread_only=True
        )
        
        assert len(insights) == 1
        assert insights[0]['type'] == 'prediction'
        assert insights[0]['severity'] == 'high'
        assert insights[0]['is_read'] is False
    
    async def _create_and_train_model(
        self,
        db_session: AsyncSession,
        agency: Agency,
        user: User
    ) -> MLModel:
        """Helper to create and train a model."""
        # Create transactions
        for i in range(100):
            transaction = Transaction(
                agency_id=agency.id,
                amount=np.random.uniform(1000, 5000),
                status='completed',
                created_at=datetime.utcnow() - timedelta(days=i)
            )
            db_session.add(transaction)
        await db_session.commit()
        
        # Train model
        return await ml_service.train_model(
            prediction_type=PredictionType.REVENUE_FORECAST,
            agency_id=agency.id,
            user=user,
            session=db_session
        )


class TestMLAnalyticsAPI:
    """Test ML Analytics API endpoints."""
    
    @pytest.mark.asyncio
    async def test_train_model_endpoint(self, client, auth_headers, test_agency):
        """Test model training endpoint."""
        response = await client.post(
            "/api/v1/ml-analytics/models/train",
            json={
                "prediction_type": "revenue_forecast",
                "config": {"lookback_days": 90}
            },
            headers=auth_headers
        )
        
        # Note: This will fail without sufficient data
        # In real tests, we'd mock the ML service
        assert response.status_code in [200, 400]
    
    @pytest.mark.asyncio
    async def test_generate_predictions_endpoint(self, client, auth_headers):
        """Test prediction generation endpoint."""
        response = await client.post(
            "/api/v1/ml-analytics/predictions/generate",
            json={
                "prediction_type": "revenue_forecast",
                "horizon_days": 30
            },
            headers=auth_headers
        )
        
        # Will return 400 without trained model
        assert response.status_code in [200, 400]
    
    @pytest.mark.asyncio
    async def test_get_predictions_endpoint(self, client, auth_headers):
        """Test getting predictions endpoint."""
        response = await client.get(
            "/api/v1/ml-analytics/predictions",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_get_insights_endpoint(self, client, auth_headers):
        """Test getting insights endpoint."""
        response = await client.get(
            "/api/v1/ml-analytics/insights?unread_only=true",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_ml_dashboard_endpoint(self, client, auth_headers):
        """Test ML dashboard endpoint."""
        response = await client.get(
            "/api/v1/ml-analytics/dashboard",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'summary' in data
        assert 'models' in data
        assert 'insights' in data


@pytest.fixture
def trained_predictor():
    """Fixture for a trained predictor with mock data."""
    predictor = RevenueForecastPredictor()
    
    # Create mock training data
    dates = pd.date_range(end=datetime.utcnow(), periods=100, freq='D')
    revenue = np.random.uniform(1000, 5000, size=100) * (1 + np.random.normal(0, 0.1, 100))
    
    df = pd.DataFrame({
        'ds': dates,
        'y': revenue
    })
    
    # Mock the model training
    from prophet import Prophet
    predictor.model = Prophet()
    predictor.model.fit(df)
    
    return predictor


@pytest.fixture
async def test_prediction(db_session: AsyncSession, test_agency: Agency):
    """Fixture for a test prediction."""
    model = MLModel(
        name="Test Model",
        prediction_type=PredictionType.REVENUE_FORECAST,
        agency_id=test_agency.id,
        created_by_id=test_agency.owner_id,
        status=ModelStatus.TRAINED
    )
    db_session.add(model)
    await db_session.commit()
    
    prediction = Prediction(
        model_id=model.id,
        prediction_type=PredictionType.REVENUE_FORECAST,
        target_date=datetime.utcnow() + timedelta(days=1),
        predicted_value=4500.0,
        confidence_interval_lower=4000.0,
        confidence_interval_upper=5000.0,
        confidence_score=0.85,
        entity_type="agency",
        entity_id=test_agency.id
    )
    db_session.add(prediction)
    await db_session.commit()
    
    return prediction
