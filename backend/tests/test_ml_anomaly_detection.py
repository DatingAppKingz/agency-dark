"""
Tests for anomaly detection ML functionality.
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
import numpy as np

from core.ml_analytics.predictors.anomaly_detection import AnomalyDetector
from core.ml_analytics.models import PredictionType, ModelStatus
from core.domain.models import Agency, User, Model, Transaction, Fan, Message


@pytest.mark.asyncio
async def test_anomaly_detector_training(db_session, test_agency, test_user):
    """Test training anomaly detection models."""
    # Create test fans
    fans = []
    for i in range(30):
        fan = Fan(
            id=uuid4(),
            username=f"fan{i}",
            agency_id=test_agency.id,
            is_active=True
        )
        fans.append(fan)
        db_session.add(fan)
    
    # Create test model
    model = Model(
        id=uuid4(),
        username="testmodel",
        display_name="Test Model",
        agency_id=test_agency.id,
        created_by_id=test_user.id
    )
    db_session.add(model)
    
    # Create normal transactions
    for i in range(200):
        fan_idx = i % len(fans)
        transaction = Transaction(
            id=uuid4(),
            fan_id=fans[fan_idx].id,
            model_id=model.id,
            amount=float(np.random.normal(50, 15)),  # Normal distribution
            status='completed',
            type='tip',
            agency_id=test_agency.id,
            created_at=datetime.utcnow() - timedelta(days=90-i//3, hours=i%24)
        )
        db_session.add(transaction)
    
    # Create anomalous transactions
    for i in range(10):
        transaction = Transaction(
            id=uuid4(),
            fan_id=fans[0].id,  # All from same fan
            model_id=model.id,
            amount=float(np.random.uniform(200, 500)),  # Much higher amounts
            status='completed',
            type='tip',
            agency_id=test_agency.id,
            created_at=datetime.utcnow() - timedelta(hours=i)  # Rapid succession
        )
        db_session.add(transaction)
    
    await db_session.commit()
    
    # Train detector
    detector = AnomalyDetector()
    result = await detector.train(
        agency_id=test_agency.id,
        session=db_session,
        lookback_days=90,
        contamination=0.05
    )
    
    assert result['success'] is True
    assert 'metrics' in result
    assert result['training_samples'] >= 100
    
    # Verify all detectors were trained
    assert detector.transaction_detector is not None
    assert detector.behavior_detector is not None
    assert detector.pattern_detector is not None
    assert detector.velocity_detector is not None


@pytest.mark.asyncio
async def test_anomaly_detection(db_session, test_agency, test_user):
    """Test detecting anomalies in recent activity."""
    # Setup test data
    fan = Fan(
        id=uuid4(),
        username="suspicious_fan",
        agency_id=test_agency.id
    )
    db_session.add(fan)
    
    model = Model(
        id=uuid4(),
        username="testmodel",
        display_name="Test Model",
        agency_id=test_agency.id,
        created_by_id=test_user.id
    )
    db_session.add(model)
    
    # Create suspicious transactions
    for i in range(5):
        transaction = Transaction(
            id=uuid4(),
            fan_id=fan.id,
            model_id=model.id,
            amount=500.0,  # High amount
            status='completed',
            type='tip',
            agency_id=test_agency.id,
            created_at=datetime.utcnow() - timedelta(minutes=i*2)  # Rapid
        )
        db_session.add(transaction)
    
    await db_session.commit()
    
    # Mock trained detector
    detector = AnomalyDetector()
    detector.transaction_detector = "mock"
    detector.behavior_detector = "mock"
    detector.pattern_detector = "mock"
    detector.velocity_detector = {'threshold': 5.0, 'trained': True}
    
    # Mock detection methods
    async def mock_detect_velocity(*args, **kwargs):
        return [{
            'type': 'velocity_anomaly',
            'entity_type': 'fan',
            'entity_id': str(fan.id),
            'detected_at': datetime.utcnow(),
            'severity_score': 8.5,
            'details': {
                'spike_hour': datetime.utcnow().isoformat(),
                'transaction_count': 5,
                'spike_ratio': 10.0
            },
            'reasons': ["Transaction rate 10.0x normal"],
            'recommended_actions': ["Investigate transaction burst"]
        }]
    
    detector._detect_velocity_anomalies = mock_detect_velocity
    detector._detect_transaction_anomalies = lambda *args, **kwargs: []
    detector._detect_behavior_anomalies = lambda *args, **kwargs: []
    detector._detect_pattern_anomalies = lambda *args, **kwargs: []
    
    # Detect anomalies
    anomalies = await detector.detect_anomalies(
        agency_id=test_agency.id,
        session=db_session,
        time_window_hours=24,
        anomaly_types=['velocity']
    )
    
    assert len(anomalies) == 1
    assert anomalies[0]['type'] == 'velocity_anomaly'
    assert anomalies[0]['severity_score'] == 8.5
    assert 'reasons' in anomalies[0]
    assert 'recommended_actions' in anomalies[0]


@pytest.mark.asyncio
async def test_entity_analysis(db_session, test_agency, test_user):
    """Test analyzing specific entities for anomalies."""
    # Create test fan with transaction history
    fan = Fan(
        id=uuid4(),
        username="test_fan",
        agency_id=test_agency.id
    )
    db_session.add(fan)
    
    model = Model(
        id=uuid4(),
        username="testmodel",
        display_name="Test Model",
        agency_id=test_agency.id,
        created_by_id=test_user.id
    )
    db_session.add(model)
    
    # Normal transactions
    for i in range(10):
        transaction = Transaction(
            id=uuid4(),
            fan_id=fan.id,
            model_id=model.id,
            amount=50.0,
            status='completed',
            type='tip',
            agency_id=test_agency.id,
            created_at=datetime.utcnow() - timedelta(days=20-i*2)
        )
        db_session.add(transaction)
    
    # Anomalous transaction
    anomaly_transaction = Transaction(
        id=uuid4(),
        fan_id=fan.id,
        model_id=model.id,
        amount=500.0,  # 10x normal
        status='completed',
        type='tip',
        agency_id=test_agency.id,
        created_at=datetime.utcnow() - timedelta(hours=1)
    )
    db_session.add(anomaly_transaction)
    
    await db_session.commit()
    
    # Analyze fan
    detector = AnomalyDetector()
    analysis = await detector.analyze_entity(
        entity_type='fan',
        entity_id=str(fan.id),
        session=db_session,
        lookback_days=30
    )
    
    assert 'risk_score' in analysis
    assert 'anomaly_count' in analysis
    assert 'total_transactions' in analysis
    assert analysis['total_transactions'] == 11
    assert analysis['risk_score'] > 0  # Should detect the anomaly
    assert 'risk_factors' in analysis
    assert 'recommendation' in analysis


@pytest.mark.asyncio
async def test_risk_scores(db_session, test_agency):
    """Test calculating risk scores for entities."""
    # Create fans with different risk profiles
    low_risk_fan = Fan(
        id=uuid4(),
        username="low_risk",
        agency_id=test_agency.id
    )
    high_risk_fan = Fan(
        id=uuid4(),
        username="high_risk",
        agency_id=test_agency.id
    )
    db_session.add_all([low_risk_fan, high_risk_fan])
    
    model = Model(
        id=uuid4(),
        username="testmodel",
        display_name="Test Model",
        agency_id=test_agency.id
    )
    db_session.add(model)
    
    # Low risk behavior
    for i in range(5):
        transaction = Transaction(
            id=uuid4(),
            fan_id=low_risk_fan.id,
            model_id=model.id,
            amount=30.0,
            status='completed',
            type='tip',
            agency_id=test_agency.id,
            created_at=datetime.utcnow() - timedelta(days=i*7)
        )
        db_session.add(transaction)
    
    # High risk behavior
    for i in range(20):
        transaction = Transaction(
            id=uuid4(),
            fan_id=high_risk_fan.id,
            model_id=model.id,
            amount=200.0,
            status='completed',
            type='tip',
            agency_id=test_agency.id,
            created_at=datetime.utcnow() - timedelta(hours=i)
        )
        db_session.add(transaction)
    
    await db_session.commit()
    
    # Get risk scores
    detector = AnomalyDetector()
    risk_scores = await detector.get_risk_scores(
        agency_id=test_agency.id,
        session=db_session,
        entity_type='fan',
        limit=10
    )
    
    assert len(risk_scores) == 2
    assert all('risk_score' in score for score in risk_scores)
    assert all('fan_id' in score for score in risk_scores)
    assert all('risk_factors' in score for score in risk_scores)
    
    # High risk fan should have higher score
    high_risk_score = next(s for s in risk_scores if s['fan_id'] == str(high_risk_fan.id))
    low_risk_score = next(s for s in risk_scores if s['fan_id'] == str(low_risk_fan.id))
    assert high_risk_score['risk_score'] > low_risk_score['risk_score']


@pytest.mark.asyncio
async def test_transaction_anomaly_features(db_session, test_agency):
    """Test transaction feature engineering."""
    detector = AnomalyDetector()
    
    # Create sample transaction data
    import pandas as pd
    data = {
        'transaction_id': [uuid4() for _ in range(10)],
        'amount': [50, 45, 55, 200, 48, 52, 49, 51, 300, 47],
        'created_at': [datetime.utcnow() - timedelta(hours=i) for i in range(10)],
        'fan_id': ['fan1'] * 5 + ['fan2'] * 5,
        'model_id': ['model1'] * 10,
        'type': ['tip'] * 10,
        'fan_age_days': [30] * 10,
        'fan_total_transactions': [50] * 5 + [100] * 5,
        'fan_total_spent': [2500] * 5 + [5000] * 5
    }
    df = pd.DataFrame(data)
    
    # Add features
    df_with_features = detector._add_transaction_features(df)
    
    # Check features were added
    assert 'hour' in df_with_features.columns
    assert 'day_of_week' in df_with_features.columns
    assert 'is_weekend' in df_with_features.columns
    assert 'amount_zscore' in df_with_features.columns
    assert 'time_since_last' in df_with_features.columns
    assert 'amount_to_avg_ratio' in df_with_features.columns
    
    # Check z-scores for anomalous amounts
    high_amount_rows = df_with_features[df_with_features['amount'] > 100]
    assert all(high_amount_rows['amount_zscore'] > 2)


@pytest.mark.asyncio
async def test_save_load_model(tmp_path, db_session, test_agency):
    """Test saving and loading anomaly detection models."""
    detector = AnomalyDetector()
    
    # Mock trained models
    from sklearn.ensemble import IsolationForest
    detector.transaction_detector = IsolationForest(n_estimators=10)
    detector.behavior_detector = IsolationForest(n_estimators=10)
    detector.pattern_detector = "mock_pattern"
    detector.velocity_detector = {'threshold': 5.0}
    detector.model_metadata = {'test': 'metadata'}
    
    # Fit with dummy data
    X_dummy = np.random.rand(20, 10)
    detector.transaction_detector.fit(X_dummy)
    detector.behavior_detector.fit(X_dummy)
    
    # Save
    model_path = tmp_path / "anomaly_model.joblib"
    detector.save_model(str(model_path))
    
    # Load in new instance
    new_detector = AnomalyDetector()
    new_detector.load_model(str(model_path))
    
    assert new_detector.transaction_detector is not None
    assert new_detector.behavior_detector is not None
    assert new_detector.pattern_detector == "mock_pattern"
    assert new_detector.velocity_detector == {'threshold': 5.0}
    assert new_detector.model_metadata == {'test': 'metadata'}