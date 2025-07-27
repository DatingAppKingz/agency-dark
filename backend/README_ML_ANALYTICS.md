# ML Analytics System

## Overview

The ML Analytics System provides advanced machine learning capabilities for predictive analytics, including revenue forecasting, churn prediction, content optimization, and anomaly detection.

## Features

### 1. Revenue Forecasting
- **Time Series Analysis**: Uses Facebook Prophet for accurate revenue predictions
- **Seasonality Detection**: Identifies weekly, monthly, and yearly patterns
- **Trend Analysis**: Detects revenue trends and changes
- **Confidence Intervals**: Provides upper and lower bounds for predictions
- **Multi-horizon Forecasting**: Generate predictions for 1-365 days ahead

### 2. Prediction Types (Planned)
- **Churn Prediction**: Identify fans likely to cancel subscriptions
- **Content Optimization**: Recommend optimal posting times and content types
- **Anomaly Detection**: Detect unusual patterns in revenue or user behavior
- **Fan Lifetime Value**: Predict long-term value of individual fans
- **Engagement Scoring**: Score fan engagement levels
- **Conversion Rate Prediction**: Predict conversion rates for campaigns

### 3. Model Management
- **Automated Training**: Train models with historical data
- **Model Versioning**: Track and manage multiple model versions
- **Performance Monitoring**: Track model accuracy over time
- **Automatic Retraining**: Retrain models when performance degrades
- **A/B Testing**: Compare model performance

### 4. Insights & Alerts
- **Automated Insights**: Generate actionable insights from predictions
- **Alert System**: Get notified of significant changes or anomalies
- **Recommendations**: Receive AI-powered recommendations
- **Severity Levels**: Prioritize alerts by importance

## Architecture

### Components

1. **Models** (`core/ml_analytics/models.py`)
   - MLModel: Model metadata and configuration
   - Prediction: Individual predictions
   - ModelTrainingJob: Training job tracking
   - FeatureStore: Computed features for ML
   - PredictionFeedback: Actual vs predicted tracking
   - InsightAlert: AI-generated insights

2. **Predictors** (`core/ml_analytics/predictors/`)
   - RevenueForecastPredictor: Prophet-based revenue forecasting
   - (Future) ChurnPredictor, ContentOptimizer, etc.

3. **ML Service** (`core/ml_analytics/services/ml_service.py`)
   - Model training orchestration
   - Prediction generation
   - Performance monitoring
   - Insight generation

4. **API Endpoints** (`api/v1/endpoints/ml_analytics.py`)
   - REST API for all ML operations
   - Dashboard endpoint for overview

## Usage Examples

### Training a Model

```python
from core.ml_analytics.services.ml_service import ml_service
from core.ml_analytics.models import PredictionType

# Train revenue forecast model
model = await ml_service.train_model(
    prediction_type=PredictionType.REVENUE_FORECAST,
    agency_id=agency_id,
    user=current_user,
    session=db,
    config={
        'lookback_days': 365,  # Use 1 year of data
        'test_size': 0.2       # 20% for testing
    }
)
```

### Generating Predictions

```python
# Generate 30-day revenue forecast
predictions = await ml_service.generate_predictions(
    prediction_type=PredictionType.REVENUE_FORECAST,
    agency_id=agency_id,
    session=db,
    horizon_days=30
)

# Each prediction contains:
# - predicted_value: The forecasted revenue
# - confidence_interval_lower/upper: Uncertainty bounds
# - confidence_score: How confident the model is
# - target_date: The date being predicted
```

### Analyzing Trends

```python
# Get trend analysis
analysis = await ml_service.analyze_trends(
    prediction_type=PredictionType.REVENUE_FORECAST,
    agency_id=agency_id,
    session=db
)

# Returns:
# - trend_analysis: Current trends and changes
# - seasonality: Weekly/monthly patterns
# - anomalies: Detected anomalies
# - insights: Actionable recommendations
```

### Recording Feedback

```python
# Record actual outcomes
feedback = await ml_service.record_feedback(
    prediction_id=prediction_id,
    actual_value=actual_revenue,
    user=current_user,
    session=db,
    feedback_notes="End of day revenue"
)
```

### Getting Insights

```python
# Get AI-generated insights
insights = await ml_service.get_insights(
    agency_id=agency_id,
    session=db,
    severity='high',      # Filter by severity
    unread_only=True,     # Only unread insights
    limit=10
)
```

## API Endpoints

### Model Management
- `POST /api/v1/ml-analytics/models/train` - Train new model
- `GET /api/v1/ml-analytics/models` - List models
- `GET /api/v1/ml-analytics/models/{id}/performance` - Get model metrics

### Predictions
- `POST /api/v1/ml-analytics/predictions/generate` - Generate predictions
- `GET /api/v1/ml-analytics/predictions` - Get existing predictions
- `GET /api/v1/ml-analytics/predictions/{type}/trends` - Analyze trends
- `POST /api/v1/ml-analytics/feedback` - Record actual outcomes

### Insights
- `GET /api/v1/ml-analytics/insights` - Get insights/alerts
- `PATCH /api/v1/ml-analytics/insights/{id}/read` - Mark as read

### Dashboard
- `GET /api/v1/ml-analytics/dashboard` - Complete ML dashboard

## Revenue Forecasting Details

### Algorithm
The revenue forecasting uses Facebook Prophet, which:
- Handles missing data and outliers
- Detects multiple seasonality patterns
- Provides uncertainty intervals
- Works well with limited data (minimum 30 days)

### Features Used
- Historical daily revenue
- Day of week effects
- Monthly patterns
- Holiday effects (configurable)
- Custom regressors (weekend, month start/end)

### Model Evaluation
Models are evaluated using:
- MAPE (Mean Absolute Percentage Error)
- RMSE (Root Mean Square Error)
- R² Score
- Prediction interval coverage

## Configuration

### Environment Variables
```bash
# ML Model Storage
ML_MODEL_PATH=/var/ml_models
ML_MAX_MODEL_SIZE_MB=500

# Training Configuration
ML_MIN_TRAINING_SAMPLES=30
ML_DEFAULT_LOOKBACK_DAYS=365
ML_RETRAIN_THRESHOLD_ERROR=20  # Retrain if error > 20%

# Prediction Limits
ML_MAX_HORIZON_DAYS=365
ML_MAX_PREDICTIONS_PER_REQUEST=1000
```

### Model Parameters
Revenue forecast models can be configured with:
- `changepoint_prior_scale`: Flexibility of trend (default: 0.05)
- `seasonality_prior_scale`: Strength of seasonality (default: 10)
- `daily_seasonality`: Enable daily patterns (default: true)
- `weekly_seasonality`: Enable weekly patterns (default: true)
- `yearly_seasonality`: Enable yearly patterns (default: true)

## Performance Optimization

### Caching
- Model predictions are cached for 1 hour
- Trend analysis cached for quick retrieval
- Feature computations cached in feature store

### Async Processing
- Model training runs asynchronously
- Batch prediction generation
- Parallel feature computation

### Resource Management
- Models stored efficiently with joblib
- Old model versions archived
- Automatic cleanup of expired predictions

## Security Considerations

### Access Control
- Only agency owners/admins can train models
- Models isolated by agency
- Predictions accessible only to authorized users

### Data Privacy
- No cross-agency data leakage
- Sensitive data excluded from features
- Audit logging for all operations

## Monitoring

### Model Performance
- Track prediction accuracy over time
- Monitor for data drift
- Alert on performance degradation

### System Metrics
- Training job duration and resources
- Prediction generation latency
- Cache hit rates

## Testing

```bash
# Run ML analytics tests
pytest tests/test_ml_analytics.py -v

# Test specific components
pytest tests/test_ml_analytics.py::TestRevenueForecastPredictor -v
pytest tests/test_ml_analytics.py::TestMLAnalyticsService -v
```

## Troubleshooting

### Common Issues

1. **Insufficient training data**
   - Ensure at least 30 days of historical data
   - Check for data gaps or quality issues

2. **Poor prediction accuracy**
   - Review data quality and outliers
   - Consider adjusting model parameters
   - Check for seasonal events not captured

3. **Training failures**
   - Verify sufficient memory available
   - Check for data access permissions
   - Review error logs for details

## Future Enhancements

### Phase 3.2: Churn Prediction
- Random Forest classifier for churn
- Feature engineering from user behavior
- Early warning system

### Phase 3.3: Content Optimization
- Optimal posting time prediction
- Content type recommendations
- A/B testing framework

### Phase 3.4: Enhanced Anomaly Detection
- Isolation Forest for anomalies
- Real-time detection
- Fraud pattern learning

### Phase 3.5: Fan LTV Prediction
- Regression models for LTV
- Cohort analysis
- Retention predictions
