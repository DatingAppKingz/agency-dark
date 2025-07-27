"""
Tests for content optimization ML functionality.
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
import numpy as np

from core.ml_analytics.predictors.content_optimization import ContentOptimizer
from core.ml_analytics.models import PredictionType, ModelStatus
from core.domain.models import Agency, User, Model, Content, Transaction, Message, Fan


@pytest.mark.asyncio
async def test_content_optimizer_training(db_session, test_agency, test_user):
    """Test training content optimization model."""
    # Create test model
    model = Model(
        id=uuid4(),
        username="testmodel",
        display_name="Test Model",
        agency_id=test_agency.id,
        created_by_id=test_user.id
    )
    db_session.add(model)
    
    # Create test fans
    fans = []
    for i in range(20):
        fan = Fan(
            id=uuid4(),
            username=f"fan{i}",
            agency_id=test_agency.id,
            is_active=True
        )
        fans.append(fan)
        db_session.add(fan)
    
    # Create test content with varied posting times and engagement
    for i in range(100):
        content = Content(
            id=uuid4(),
            model_id=model.id,
            type="post" if i % 3 == 0 else "photo",
            media_count=i % 3,
            created_at=datetime.utcnow() - timedelta(days=90-i, hours=i%24)
        )
        db_session.add(content)
        
        # Create varied transactions and messages
        if i % 2 == 0:  # 50% have transactions
            for j in range(np.random.randint(1, 5)):
                transaction = Transaction(
                    id=uuid4(),
                    fan_id=fans[j % len(fans)].id,
                    model_id=model.id,
                    content_id=content.id,
                    amount=float(np.random.randint(10, 100)),
                    status='completed',
                    type='tip',
                    agency_id=test_agency.id
                )
                db_session.add(transaction)
        
        # Messages
        for j in range(np.random.randint(0, 10)):
            message = Message(
                id=uuid4(),
                sender_id=fans[j % len(fans)].id,
                recipient_id=model.id,
                content_id=content.id,
                content="Test message",
                agency_id=test_agency.id
            )
            db_session.add(message)
    
    await db_session.commit()
    
    # Train optimizer
    optimizer = ContentOptimizer()
    result = await optimizer.train(
        agency_id=test_agency.id,
        session=db_session,
        lookback_days=90
    )
    
    assert result['success'] is True
    assert 'metrics' in result
    assert result['training_samples'] >= 50
    assert result['metrics']['overall_accuracy'] >= 0
    
    # Verify models were trained
    assert optimizer.time_model is not None
    assert optimizer.engagement_model is not None
    assert optimizer.content_clustering_model is not None


@pytest.mark.asyncio
async def test_optimal_posting_times_prediction(db_session, test_agency):
    """Test predicting optimal posting times."""
    optimizer = ContentOptimizer()
    
    # Mock a trained model (in real tests, would train first)
    optimizer.time_model = "mock_model"
    optimizer.engagement_model = "mock_model"
    optimizer.revenue_model = "mock_model"
    optimizer.model_metadata = {'agency_id': test_agency.id}
    
    # Override prediction methods for testing
    optimizer._predict_engagement_score = lambda x: 0.8
    optimizer._predict_revenue_score = lambda x: 0.7
    
    # Get predictions
    predictions = await optimizer.predict_optimal_posting_times(
        next_days=7,
        content_type="photo"
    )
    
    assert len(predictions) == 7
    for day_pred in predictions:
        assert 'date' in day_pred
        assert 'day_of_week' in day_pred
        assert 'optimal_hours' in day_pred
        assert len(day_pred['optimal_hours']) <= 3
        
        for hour in day_pred['optimal_hours']:
            assert 'hour' in hour
            assert 'time' in hour
            assert 'score' in hour
            assert 'expected_engagement' in hour
            assert 'expected_revenue' in hour
            assert 0 <= hour['hour'] <= 23


@pytest.mark.asyncio
async def test_content_recommendations(db_session, test_agency):
    """Test content recommendations generation."""
    optimizer = ContentOptimizer()
    
    # Mock trained state
    optimizer.model_metadata = {'agency_id': test_agency.id}
    optimizer.content_patterns = [
        {
            'avg_engagement': 50,
            'avg_revenue': 100,
            'dominant_hours': [20, 21, 22],
            'dominant_days': [5, 6],  # Weekend
            'content_types': {'photo': 10, 'video': 5},
            'size': 100
        }
    ]
    
    # Get recommendations
    recommendations = await optimizer.recommend_content(
        recent_performance={'engagement_rate': 0.05, 'revenue_per_post': 80}
    )
    
    assert 'content_types' in recommendations
    assert 'posting_strategy' in recommendations
    assert 'optimization_tips' in recommendations
    assert 'predicted_performance' in recommendations
    
    # Check strategy details
    strategy = recommendations['posting_strategy']
    assert 'optimal_frequency' in strategy
    assert 'content_mix' in strategy
    assert 'timing_pattern' in strategy


@pytest.mark.asyncio
async def test_content_performance_analysis(db_session, test_agency, test_user):
    """Test analyzing individual content performance."""
    # Create test content
    model = Model(
        id=uuid4(),
        username="testmodel",
        display_name="Test Model",
        agency_id=test_agency.id,
        created_by_id=test_user.id
    )
    db_session.add(model)
    
    content = Content(
        id=uuid4(),
        model_id=model.id,
        type="photo",
        media_count=1,
        created_at=datetime.utcnow() - timedelta(days=1)
    )
    db_session.add(content)
    
    # Add some engagement
    fan = Fan(
        id=uuid4(),
        username="testfan",
        agency_id=test_agency.id
    )
    db_session.add(fan)
    
    transaction = Transaction(
        id=uuid4(),
        fan_id=fan.id,
        model_id=model.id,
        content_id=content.id,
        amount=50.0,
        status='completed',
        type='tip',
        agency_id=test_agency.id
    )
    db_session.add(transaction)
    
    await db_session.commit()
    
    # Analyze
    optimizer = ContentOptimizer()
    optimizer.engagement_model = "mock"
    optimizer.revenue_model = "mock"
    optimizer._predict_content_engagement = lambda x: 40.0
    optimizer._predict_content_revenue = lambda x: 45.0
    
    analysis = await optimizer.analyze_content_performance(
        content_id=str(content.id),
        session=db_session
    )
    
    assert 'content_id' in analysis
    assert 'performance' in analysis
    assert 'insights' in analysis
    assert 'recommendations' in analysis
    
    perf = analysis['performance']
    assert 'actual_engagement' in perf
    assert 'expected_engagement' in perf
    assert 'engagement_ratio' in perf
    assert 'actual_revenue' in perf
    assert 'expected_revenue' in perf
    assert 'revenue_ratio' in perf


@pytest.mark.asyncio
async def test_save_load_model(tmp_path, db_session, test_agency):
    """Test saving and loading content optimization models."""
    # Train a simple model
    optimizer = ContentOptimizer()
    
    # Mock training
    from sklearn.ensemble import RandomForestRegressor
    optimizer.time_model = RandomForestRegressor(n_estimators=10)
    optimizer.engagement_model = RandomForestRegressor(n_estimators=10)
    optimizer.revenue_model = RandomForestRegressor(n_estimators=10)
    optimizer.content_clustering_model = "mock_clustering"
    optimizer.model_metadata = {'test': 'data'}
    
    # Fit with dummy data
    X_dummy = np.random.rand(10, 4)
    y_dummy = np.random.rand(10)
    optimizer.time_model.fit(X_dummy, y_dummy)
    optimizer.engagement_model.fit(X_dummy, y_dummy)
    optimizer.revenue_model.fit(X_dummy, y_dummy)
    
    # Save
    model_path = tmp_path / "content_model.joblib"
    optimizer.save_model(str(model_path))
    
    # Load in new instance
    new_optimizer = ContentOptimizer()
    new_optimizer.load_model(str(model_path))
    
    assert new_optimizer.time_model is not None
    assert new_optimizer.engagement_model is not None
    assert new_optimizer.revenue_model is not None
    assert new_optimizer.model_metadata == {'test': 'data'}