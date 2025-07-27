"""
Tests for Fan LTV prediction functionality.
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
import numpy as np
import pandas as pd

from core.ml_analytics.predictors.fan_ltv import FanLTVPredictor
from core.ml_analytics.models import PredictionType, ModelStatus
from core.domain.models import Agency, User, Model, Fan, Transaction, Message


@pytest.mark.asyncio
async def test_fan_ltv_training(db_session, test_agency, test_user):
    """Test training Fan LTV prediction models."""
    # Create test model
    model = Model(
        id=uuid4(),
        username="testmodel",
        display_name="Test Model",
        agency_id=test_agency.id,
        created_by_id=test_user.id
    )
    db_session.add(model)
    
    # Create fans with different spending patterns
    fans = []
    
    # High-value fans
    for i in range(20):
        fan = Fan(
            id=uuid4(),
            username=f"high_value_fan{i}",
            agency_id=test_agency.id,
            created_at=datetime.utcnow() - timedelta(days=180)
        )
        fans.append(fan)
        db_session.add(fan)
        
        # Create transaction history
        for j in range(50):
            transaction = Transaction(
                id=uuid4(),
                fan_id=fan.id,
                model_id=model.id,
                amount=float(np.random.uniform(50, 200)),
                status='completed',
                type='tip',
                agency_id=test_agency.id,
                created_at=datetime.utcnow() - timedelta(days=180-j*3)
            )
            db_session.add(transaction)
    
    # Medium-value fans
    for i in range(30):
        fan = Fan(
            id=uuid4(),
            username=f"medium_value_fan{i}",
            agency_id=test_agency.id,
            created_at=datetime.utcnow() - timedelta(days=120)
        )
        fans.append(fan)
        db_session.add(fan)
        
        # Create transaction history
        for j in range(20):
            transaction = Transaction(
                id=uuid4(),
                fan_id=fan.id,
                model_id=model.id,
                amount=float(np.random.uniform(20, 50)),
                status='completed',
                type='tip',
                agency_id=test_agency.id,
                created_at=datetime.utcnow() - timedelta(days=120-j*5)
            )
            db_session.add(transaction)
    
    # Low-value fans
    for i in range(50):
        fan = Fan(
            id=uuid4(),
            username=f"low_value_fan{i}",
            agency_id=test_agency.id,
            created_at=datetime.utcnow() - timedelta(days=60)
        )
        fans.append(fan)
        db_session.add(fan)
        
        # Create sparse transaction history
        for j in range(5):
            transaction = Transaction(
                id=uuid4(),
                fan_id=fan.id,
                model_id=model.id,
                amount=float(np.random.uniform(5, 20)),
                status='completed',
                type='tip',
                agency_id=test_agency.id,
                created_at=datetime.utcnow() - timedelta(days=60-j*10)
            )
            db_session.add(transaction)
    
    await db_session.commit()
    
    # Train LTV predictor
    predictor = FanLTVPredictor()
    result = await predictor.train(
        agency_id=test_agency.id,
        session=db_session,
        lookback_days=365
    )
    
    assert result['success'] is True
    assert 'metrics' in result
    assert result['training_samples'] >= 100
    
    # Check all models were trained
    assert predictor.short_term_model is not None
    assert predictor.medium_term_model is not None
    assert predictor.long_term_model is not None
    
    # Check metrics
    assert result['metrics']['overall_accuracy'] > 0
    assert 'short_term_r2' in result['metrics']
    assert 'medium_term_r2' in result['metrics']
    assert 'long_term_r2' in result['metrics']


@pytest.mark.asyncio
async def test_fan_ltv_prediction(db_session, test_agency, test_user):
    """Test predicting LTV for specific fans."""
    # Create test data
    model = Model(
        id=uuid4(),
        username="testmodel",
        display_name="Test Model",
        agency_id=test_agency.id,
        created_by_id=test_user.id
    )
    db_session.add(model)
    
    fan = Fan(
        id=uuid4(),
        username="test_fan",
        agency_id=test_agency.id
    )
    db_session.add(fan)
    
    # Create transaction history
    total_spent = 0
    for i in range(10):
        amount = float(np.random.uniform(20, 100))
        total_spent += amount
        transaction = Transaction(
            id=uuid4(),
            fan_id=fan.id,
            model_id=model.id,
            amount=amount,
            status='completed',
            type='tip',
            agency_id=test_agency.id,
            created_at=datetime.utcnow() - timedelta(days=30-i*3)
        )
        db_session.add(transaction)
    
    await db_session.commit()
    
    # Mock trained predictor
    predictor = FanLTVPredictor()
    predictor.short_term_model = "mock"
    predictor.medium_term_model = "mock"
    predictor.long_term_model = "mock"
    
    # Mock prediction methods
    predictor.short_term_model = type('MockModel', (), {
        'predict': lambda self, x: np.array([150.0])
    })()
    predictor.medium_term_model = type('MockModel', (), {
        'predict': lambda self, x: np.array([400.0])
    })()
    predictor.long_term_model = type('MockModel', (), {
        'predict': lambda self, x: np.array([1200.0])
    })()
    
    # Get predictions
    predictions = await predictor.predict_ltv(
        fan_ids=[str(fan.id)],
        session=db_session,
        include_confidence=True
    )
    
    assert len(predictions) == 1
    pred = predictions[0]
    
    assert pred['fan_id'] == str(fan.id)
    assert 'ltv_30_days' in pred
    assert 'ltv_90_days' in pred
    assert 'ltv_365_days' in pred
    assert pred['ltv_30_days'] > 0
    assert pred['ltv_90_days'] >= pred['ltv_30_days']
    assert pred['ltv_365_days'] >= pred['ltv_90_days']
    assert 'confidence_intervals' in pred
    assert 'recommendations' in pred
    assert 'features' in pred


@pytest.mark.asyncio
async def test_fan_segmentation(db_session, test_agency):
    """Test segmenting fans by LTV."""
    # Create fans with different value levels
    fans_data = []
    for i in range(100):
        fan = Fan(
            id=uuid4(),
            username=f"fan_{i}",
            agency_id=test_agency.id,
            is_active=True
        )
        db_session.add(fan)
        fans_data.append({
            'fan': fan,
            'ltv': float(np.random.exponential(100) * (5 - i/20))  # Decreasing LTV
        })
    
    await db_session.commit()
    
    # Mock predictor
    predictor = FanLTVPredictor()
    predictor.short_term_model = "mock"
    predictor.medium_term_model = "mock"
    predictor.long_term_model = "mock"
    
    # Mock predict_ltv to return predetermined values
    async def mock_predict_ltv(fan_ids, session, include_confidence):
        predictions = []
        for fan_id in fan_ids:
            fan_data = next((f for f in fans_data if str(f['fan'].id) == fan_id), None)
            if fan_data:
                ltv = fan_data['ltv']
                predictions.append({
                    'fan_id': fan_id,
                    'ltv_30_days': ltv * 0.1,
                    'ltv_90_days': ltv * 0.3,
                    'ltv_365_days': ltv,
                    'recommendations': []
                })
        return predictions
    
    predictor.predict_ltv = mock_predict_ltv
    
    # Get segments
    segments_result = await predictor.segment_fans_by_ltv(
        agency_id=test_agency.id,
        session=db_session,
        num_segments=5
    )
    
    assert 'segments' in segments_result
    assert 'statistics' in segments_result
    assert segments_result['total_fans'] == 100
    
    # Check segments
    segments = segments_result['segments']
    assert len(segments) == 5
    assert all(seg in segments for seg in ['vip', 'high_value', 'medium_value', 'low_value', 'at_risk'])
    
    # Check statistics
    stats = segments_result['statistics']
    assert all(seg in stats for seg in segments.keys())
    
    # VIP should have highest average LTV
    if 'vip' in stats and 'high_value' in stats:
        assert stats['vip']['avg_ltv_365'] > stats['high_value']['avg_ltv_365']


@pytest.mark.asyncio
async def test_ltv_trends_analysis(db_session, test_agency):
    """Test analyzing LTV trends."""
    predictor = FanLTVPredictor()
    
    # Create mock historical data
    fans = []
    for i in range(50):
        fan = Fan(
            id=uuid4(),
            username=f"fan_{i}",
            agency_id=test_agency.id,
            created_at=datetime.utcnow() - timedelta(days=180-i)
        )
        fans.append(fan)
        db_session.add(fan)
    
    model = Model(
        id=uuid4(),
        username="testmodel",
        agency_id=test_agency.id
    )
    db_session.add(model)
    
    # Create transactions
    for fan in fans:
        num_transactions = np.random.randint(5, 30)
        for j in range(num_transactions):
            transaction = Transaction(
                id=uuid4(),
                fan_id=fan.id,
                model_id=model.id,
                amount=float(np.random.uniform(10, 100)),
                status='completed',
                type='tip',
                agency_id=test_agency.id,
                created_at=fan.created_at + timedelta(days=j*5)
            )
            db_session.add(transaction)
    
    await db_session.commit()
    
    # Analyze trends
    trends = await predictor.analyze_ltv_trends(
        agency_id=test_agency.id,
        session=db_session
    )
    
    assert 'trends' in trends
    assert 'insights' in trends
    assert 'recommendations' in trends
    
    # Check trend components
    if 'trends' in trends and trends['trends']:
        assert 'overall' in trends['trends']
        assert 'by_cohort' in trends['trends']
        assert 'by_segment' in trends['trends']
        assert 'drivers' in trends['trends']


@pytest.mark.asyncio
async def test_ltv_recommendations(db_session, test_agency):
    """Test LTV-based recommendations."""
    predictor = FanLTVPredictor()
    
    # Test high-value fan recommendations
    high_ltv_recs = predictor._generate_ltv_recommendations(
        ltv_30d=200,
        ltv_90d=600,
        ltv_365d=2000,
        features=[10, 10, 5, 50, 0.5, 30, 0.8, 300, 100, 150, 0.2, 20, 0.5, 0.6, 0, 12, 0.3, 30, 0.1, 0.2, 0.9, 0.8, 0.9]
    )
    
    assert len(high_ltv_recs) > 0
    assert any("VIP" in rec for rec in high_ltv_recs)
    
    # Test low-value fan recommendations
    low_ltv_recs = predictor._generate_ltv_recommendations(
        ltv_30d=10,
        ltv_90d=25,
        ltv_365d=50,
        features=[60, 60, 45, 5, 0.01, 2, 0.1, 50, 25, 30, -0.5, 3, 0.1, 0.2, 0, 12, 0.3, 10, -0.3, -0.2, 0.1, 0.1, 0.1]
    )
    
    assert len(low_ltv_recs) > 0
    assert any("re-engagement" in rec.lower() or "inactive" in rec.lower() for rec in low_ltv_recs)


@pytest.mark.asyncio
async def test_save_load_ltv_model(tmp_path, db_session, test_agency):
    """Test saving and loading LTV models."""
    predictor = FanLTVPredictor()
    
    # Mock trained models
    from sklearn.ensemble import GradientBoostingRegressor
    predictor.short_term_model = GradientBoostingRegressor(n_estimators=10)
    predictor.medium_term_model = GradientBoostingRegressor(n_estimators=10)
    predictor.long_term_model = GradientBoostingRegressor(n_estimators=10)
    predictor.model_metadata = {'test': 'metadata'}
    
    # Fit with dummy data
    X_dummy = np.random.rand(50, 23)
    y_dummy = np.random.rand(50)
    predictor.short_term_model.fit(X_dummy, y_dummy)
    predictor.medium_term_model.fit(X_dummy, y_dummy * 2)
    predictor.long_term_model.fit(X_dummy, y_dummy * 5)
    
    # Save
    model_path = tmp_path / "ltv_model.joblib"
    predictor.save_model(str(model_path))
    
    # Load in new instance
    new_predictor = FanLTVPredictor()
    new_predictor.load_model(str(model_path))
    
    assert new_predictor.short_term_model is not None
    assert new_predictor.medium_term_model is not None
    assert new_predictor.long_term_model is not None
    assert new_predictor.model_metadata == {'test': 'metadata'}