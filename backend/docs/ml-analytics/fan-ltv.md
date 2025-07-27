# Fan Lifetime Value (LTV) Prediction

## Overview

The Fan LTV Prediction feature uses machine learning to predict the future value of fans, enabling agencies to:
- Identify high-value fans for VIP treatment
- Optimize resource allocation and marketing efforts
- Develop targeted retention strategies
- Forecast future revenue from fan segments

## Prediction Horizons

The system provides LTV predictions for three time horizons:
- **30-day LTV**: Short-term value prediction
- **90-day LTV**: Medium-term value prediction
- **365-day LTV**: Long-term value prediction

## Features Used

### Recency Features
- Days since joining the platform
- Days since first transaction
- Days since last transaction

### Frequency Features
- Total transaction count
- Transaction frequency (transactions per day)
- Number of active days
- Consistency score (regularity of transactions)

### Monetary Features
- Total historical spending
- Average transaction amount
- Maximum transaction amount
- Spending acceleration (trend in spending)

### Engagement Features
- Message count
- Content interaction rate
- Response rate

### Behavioral Features
- Preferred content types
- Preferred transaction hours
- Weekend activity ratio
- Spending variance

### Scoring Features
- Recency score (RFM model)
- Frequency score (RFM model)
- Monetary score (RFM model)
- Spending and engagement trends

## API Endpoints

### Train Fan LTV Model
```
POST /api/v1/ml-analytics/models/train
{
  "prediction_type": "fan_ltv",
  "config": {
    "lookback_days": 365
  }
}
```

### Get LTV Predictions
```
GET /api/v1/ml-analytics/fan-ltv/predictions?limit=50
```

Response:
```json
[
  {
    "fan_id": "123e4567-e89b-12d3-a456-426614174000",
    "ltv_30_days": 150.50,
    "ltv_90_days": 425.75,
    "ltv_365_days": 1250.00,
    "predicted_at": "2024-01-15T10:30:00Z",
    "confidence_intervals": {
      "30_days": [120.40, 180.60],
      "90_days": [319.31, 532.19],
      "365_days": [875.00, 1625.00]
    },
    "recommendations": [
      "VIP fan - prioritize for exclusive content and perks",
      "Consider personalized retention strategies"
    ],
    "features": {
      "days_since_join": 120,
      "transaction_count": 45,
      "total_spent": 850.00,
      "recency_score": 0.95
    }
  }
]
```

### Get Fan Segments
```
GET /api/v1/ml-analytics/fan-ltv/segments?num_segments=5
```

Response:
```json
{
  "segments": {
    "vip": [
      {
        "fan_id": "123e4567-e89b-12d3-a456-426614174000",
        "username": "topfan123",
        "ltv_365_days": 2500.00,
        "ltv_90_days": 800.00,
        "ltv_30_days": 250.00,
        "segment": "vip",
        "recommendations": [
          "Provide exclusive VIP content and early access",
          "Assign dedicated account management"
        ]
      }
    ],
    "high_value": [...],
    "medium_value": [...],
    "low_value": [...],
    "at_risk": [...]
  },
  "statistics": {
    "vip": {
      "count": 50,
      "avg_ltv_365": 2850.00,
      "total_ltv_365": 142500.00,
      "percentage": 5.0
    }
  },
  "total_fans": 1000
}
```

### Analyze Individual Fan LTV
```
GET /api/v1/ml-analytics/fan-ltv/analyze/123e4567-e89b-12d3-a456-426614174000
```

Response:
```json
{
  "fan_id": "123e4567-e89b-12d3-a456-426614174000",
  "ltv_30_days": 200.00,
  "ltv_90_days": 550.00,
  "ltv_365_days": 1800.00,
  "fan_details": {
    "username": "valuablefan",
    "created_at": "2023-06-15T08:00:00Z",
    "is_active": true
  },
  "historical_data": {
    "total_transactions": 75,
    "historical_spent": 1200.00,
    "last_transaction": "2024-01-14T15:30:00Z"
  },
  "confidence_intervals": {...},
  "recommendations": [
    "Rapidly growing value - nurture engagement",
    "Introduce loyalty rewards to maintain momentum"
  ],
  "features": {...}
}
```

## Fan Segments

### VIP (Top 20%)
- Highest predicted LTV
- Most valuable fans requiring special attention
- Recommendations: VIP perks, dedicated support, exclusive content

### High Value (Next 20%)
- Strong LTV with growth potential
- Recommendations: Premium packages, loyalty programs, personalized engagement

### Medium Value (Middle 20%)
- Average LTV with room for growth
- Recommendations: Targeted promotions, engagement campaigns, content variety

### Low Value (Next 20%)
- Below-average LTV
- Recommendations: Re-engagement campaigns, simplified interactions, surveys

### At Risk (Bottom 20%)
- Lowest LTV, potential churn candidates
- Recommendations: Win-back offers, investigate issues, alternative channels

## Model Architecture

### Gradient Boosting Regressors
- Separate models for each time horizon
- Handles non-linear relationships
- Feature importance analysis

### Polynomial Features
- Captures interaction effects between features
- Degree 2 polynomials for complexity without overfitting

### Feature Scaling
- StandardScaler for numerical stability
- Consistent scaling across all models

## Training Process

1. **Data Collection**: Gather historical transaction and engagement data
2. **Feature Engineering**: Extract 23+ features per fan
3. **Target Calculation**: Calculate actual LTV for different periods
4. **Model Training**: Train three separate models (30, 90, 365 days)
5. **Validation**: Cross-validation and performance metrics
6. **Deployment**: Automatic activation of best-performing model

## Metrics and Evaluation

- **R² Score**: Measures prediction accuracy (target: >0.7)
- **MAE (Mean Absolute Error)**: Average prediction error in dollars
- **RMSE (Root Mean Square Error)**: Penalizes large errors
- **MAPE (Mean Absolute Percentage Error)**: Percentage-based error

## Use Cases

### 1. VIP Program Management
```python
# Identify VIP fans for special treatment
segments = await get_fan_ltv_segments(num_segments=5)
vip_fans = segments['segments']['vip']

for fan in vip_fans:
    await assign_vip_status(fan['fan_id'])
    await send_vip_welcome_package(fan['fan_id'])
```

### 2. Targeted Marketing
```python
# Get predictions for specific fan cohort
predictions = await get_ltv_predictions(fan_ids=target_fan_ids)

for pred in predictions:
    if pred['ltv_365_days'] > 500 and pred['ltv_30_days'] < 50:
        # High potential but low recent activity
        await send_reactivation_campaign(pred['fan_id'])
```

### 3. Resource Allocation
```python
# Analyze LTV distribution
segments = await get_fan_ltv_segments()
stats = segments['statistics']

# Allocate support resources based on segment value
vip_percentage = stats['vip']['percentage']
allocate_support_hours(vip_percentage * 2)  # Double allocation for VIPs
```

## Best Practices

1. **Regular Retraining**: Update models monthly to capture changing behaviors
2. **Segment Monitoring**: Track segment movements and transitions
3. **Action Triggers**: Set up automated actions based on LTV thresholds
4. **Combine with Other Metrics**: Use alongside churn and engagement predictions
5. **Test and Learn**: A/B test different strategies for each segment

## Integration with Other Features

### Churn Prevention
- High LTV + High churn risk = Immediate intervention required
- Prioritize retention efforts for valuable at-risk fans

### Content Optimization
- Tailor content strategies based on fan value segments
- Premium content for high-LTV fans

### Revenue Forecasting
- Use LTV predictions to improve revenue forecasts
- Better long-term planning

### Anomaly Detection
- Monitor unusual changes in predicted LTV
- Detect potential fraud or account issues

## Dashboard Integration

The ML Analytics dashboard displays:
- LTV distribution charts
- Segment breakdown and statistics
- Top valuable fans list
- LTV trend analysis
- Growth opportunities

## Privacy and Ethics

- All predictions based on aggregated behavioral data
- No personal information used in models
- Fans can opt-out of predictive analytics
- Transparent about how data is used

## Future Enhancements

1. **Dynamic Segmentation**: Real-time segment updates
2. **Cohort Analysis**: LTV by acquisition channel
3. **Predictive Interventions**: Automated actions based on LTV changes
4. **Multi-model Ensemble**: Combine multiple algorithms for better accuracy
5. **External Data Integration**: Incorporate market trends and seasonality