# Enhanced Anomaly Detection

## Overview

The Enhanced Anomaly Detection feature uses machine learning to identify unusual patterns, fraudulent behavior, and security threats in real-time. It employs multiple detection algorithms to catch different types of anomalies across transactions, user behavior, and system activity.

## Detection Types

### 1. Transaction Anomalies
- **Purpose**: Detect fraudulent or unusual transactions
- **Algorithm**: Isolation Forest
- **Features Analyzed**:
  - Transaction amount (absolute and relative)
  - Time between transactions
  - Daily transaction count and volume
  - Fan spending history
  - Transaction patterns

### 2. Behavior Anomalies
- **Purpose**: Identify accounts with suspicious behavior patterns
- **Algorithm**: Isolation Forest with behavior clustering
- **Features Analyzed**:
  - Message and transaction rates
  - Average transaction amounts
  - Active hours per day
  - Unique fan interactions
  - Session durations

### 3. Velocity Anomalies
- **Purpose**: Detect sudden spikes in activity
- **Algorithm**: Statistical threshold detection
- **Features Analyzed**:
  - Transaction frequency over time
  - Hourly/daily activity rates
  - Deviation from normal patterns
  - Burst detection

### 4. Pattern Anomalies
- **Purpose**: Find deviations from established patterns
- **Algorithm**: DBSCAN clustering
- **Features Analyzed**:
  - Time-of-day patterns
  - Day-of-week patterns
  - Spending patterns
  - Interaction sequences

## API Endpoints

### Train Anomaly Detection Model
```
POST /api/v1/ml-analytics/models/train
{
  "prediction_type": "anomaly_detection",
  "config": {
    "lookback_days": 90,
    "contamination": 0.01
  }
}
```

### Detect Anomalies
```
GET /api/v1/ml-analytics/anomalies/detect?time_window_hours=24&anomaly_types=transaction,behavior,velocity
```

Response:
```json
[
  {
    "type": "transaction_anomaly",
    "entity_type": "transaction",
    "entity_id": "550e8400-e29b-41d4-a716-446655440000",
    "detected_at": "2024-01-15T14:30:00Z",
    "severity_score": 8.5,
    "details": {
      "amount": 500.00,
      "fan_id": "123e4567-e89b-12d3-a456-426614174000",
      "anomaly_score": -0.85
    },
    "reasons": [
      "Unusually high amount: $500.00",
      "Rapid consecutive transactions"
    ],
    "recommended_actions": [
      "Review transaction details",
      "Check fan transaction history",
      "Verify payment method"
    ]
  },
  {
    "type": "velocity_anomaly",
    "entity_type": "fan",
    "entity_id": "123e4567-e89b-12d3-a456-426614174000",
    "detected_at": "2024-01-15T14:35:00Z",
    "severity_score": 9.2,
    "details": {
      "spike_hour": "2024-01-15T14:00:00Z",
      "transaction_count": 15,
      "normal_rate": 2,
      "spike_ratio": 7.5
    },
    "reasons": [
      "Transaction rate 7.5x normal"
    ],
    "recommended_actions": [
      "Investigate transaction burst",
      "Check for automated activity",
      "Review transaction details"
    ]
  }
]
```

### Get Risk Scores
```
GET /api/v1/ml-analytics/anomalies/risk-scores?entity_type=fan&limit=100
```

Response:
```json
[
  {
    "fan_id": "123e4567-e89b-12d3-a456-426614174000",
    "username": "suspicious_user",
    "risk_score": 75,
    "transaction_count": 50,
    "total_spent": 5000.00,
    "risk_factors": [
      "High average transaction amount",
      "High recent activity"
    ],
    "last_activity": "2024-01-15T14:00:00Z"
  }
]
```

### Analyze Specific Entity
```
POST /api/v1/ml-analytics/anomalies/analyze/fan/123e4567-e89b-12d3-a456-426614174000?lookback_days=30
```

Response:
```json
{
  "fan_id": "123e4567-e89b-12d3-a456-426614174000",
  "risk_score": 65,
  "anomaly_count": 3,
  "total_transactions": 45,
  "total_spent": 2250.00,
  "avg_transaction_amount": 50.00,
  "anomalies": [
    {
      "type": "amount_anomaly",
      "transaction_index": 42,
      "amount": 500.00,
      "z_score": 4.2
    }
  ],
  "risk_factors": [
    "Unusual transaction amounts",
    "Rapid transaction patterns"
  ],
  "recommendation": "Monitor closely - elevated risk indicators"
}
```

## Risk Scoring

Risk scores are calculated on a 0-100 scale:
- **0-20**: Minimal risk - normal activity patterns
- **20-40**: Low risk - continue standard monitoring
- **40-60**: Moderate risk - review activity
- **60-80**: High risk - monitor closely
- **80-100**: Critical risk - immediate review required

## Features and Algorithms

### Isolation Forest
- Used for transaction and behavior anomaly detection
- Isolates anomalies by randomly selecting features and split values
- Effective for high-dimensional data
- Contamination parameter controls expected anomaly rate

### DBSCAN Clustering
- Used for pattern anomaly detection
- Density-based clustering to find outliers
- Identifies patterns that don't fit established clusters
- Adaptive to varying densities

### Statistical Analysis
- Z-score calculation for amount anomalies
- Rolling averages for velocity detection
- Time series analysis for trend detection
- Percentile ranking for relative comparisons

## Real-time Detection

The system provides near real-time anomaly detection:
1. **Streaming Analysis**: Processes transactions as they occur
2. **Batch Analysis**: Periodic comprehensive analysis
3. **Alert Generation**: Immediate alerts for high-severity anomalies
4. **Feedback Loop**: Continuous model improvement

## Integration with Other Features

### Revenue Forecasting
- Anomalies can impact revenue predictions
- Helps identify and exclude outliers

### Churn Prediction
- Anomalous behavior may indicate churn risk
- Combined analysis for better predictions

### Content Optimization
- Detect unusual content performance
- Identify potential gaming or manipulation

## Best Practices

1. **Model Training**:
   - Train with at least 90 days of data
   - Set contamination based on expected fraud rate
   - Retrain monthly or when performance degrades

2. **Alert Management**:
   - Set appropriate severity thresholds
   - Implement escalation procedures
   - Document resolution actions

3. **Investigation Process**:
   - Review high-severity anomalies first
   - Check entity history and patterns
   - Look for correlated anomalies

4. **False Positive Handling**:
   - Mark legitimate anomalies
   - Use feedback to improve models
   - Adjust thresholds as needed

## Security Considerations

1. **Data Privacy**: All analysis is performed on aggregated patterns
2. **Access Control**: Only authorized users can view anomaly details
3. **Audit Trail**: All investigations are logged
4. **Compliance**: Meets fraud detection requirements

## Performance Metrics

Monitor these metrics to ensure effectiveness:
- **Detection Rate**: Percentage of true anomalies detected
- **False Positive Rate**: Legitimate activity flagged as anomalous
- **Response Time**: Time from detection to resolution
- **Model Accuracy**: Overall prediction accuracy

## Example Use Cases

### 1. Fraud Detection
```python
# Detect potentially fraudulent transactions
anomalies = await detect_anomalies(
    time_window_hours=24,
    anomaly_types=['transaction']
)

for anomaly in anomalies:
    if anomaly['severity_score'] > 8:
        # High severity - immediate action
        await flag_transaction(anomaly['entity_id'])
        await notify_security_team(anomaly)
```

### 2. Account Monitoring
```python
# Get risk scores for all fans
risk_scores = await get_risk_scores(
    entity_type='fan',
    limit=100
)

high_risk_fans = [
    fan for fan in risk_scores 
    if fan['risk_score'] >= 60
]

for fan in high_risk_fans:
    await enable_enhanced_monitoring(fan['fan_id'])
```

### 3. Pattern Analysis
```python
# Analyze specific fan behavior
analysis = await analyze_entity(
    entity_type='fan',
    entity_id=fan_id,
    lookback_days=30
)

if analysis['risk_score'] > 40:
    # Review transaction history
    await generate_detailed_report(fan_id)
```

## Dashboard Integration

The ML Analytics dashboard includes:
- Real-time anomaly count
- Risk distribution charts
- Recent high-severity anomalies
- Trend analysis over time
- Top risk entities

## Continuous Improvement

The anomaly detection system improves over time through:
1. **Feedback Integration**: Learn from confirmed/rejected anomalies
2. **Pattern Evolution**: Adapt to changing behavior patterns
3. **Feature Engineering**: Add new detection features
4. **Algorithm Updates**: Incorporate latest ML techniques