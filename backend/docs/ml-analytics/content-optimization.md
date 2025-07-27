# Content Optimization ML Feature

## Overview

The Content Optimization feature uses machine learning to help agencies maximize engagement and revenue by:
- Predicting optimal posting times
- Recommending content strategies
- Analyzing individual content performance
- Identifying high-performing content patterns

## Models Used

### 1. Time Optimization Model
- **Algorithm**: Gradient Boosting Regressor
- **Purpose**: Predict engagement scores for different posting times
- **Features**: Hour of day, day of week, posting frequency, historical performance

### 2. Engagement Prediction Model
- **Algorithm**: Random Forest Regressor
- **Purpose**: Predict expected engagement for content
- **Features**: Content type, media count, posting time, historical averages

### 3. Revenue Prediction Model
- **Algorithm**: Gradient Boosting Regressor
- **Purpose**: Predict expected revenue from content
- **Features**: Content characteristics, engagement metrics, fan demographics

### 4. Content Clustering Model
- **Algorithm**: K-Means Clustering
- **Purpose**: Identify patterns in successful content
- **Features**: Engagement metrics, revenue, posting times, content types

## API Endpoints

### Train Content Optimization Model
```
POST /api/v1/ml-analytics/models/train
{
  "prediction_type": "content_optimization",
  "config": {
    "lookback_days": 180
  }
}
```

### Get Optimal Posting Times
```
GET /api/v1/ml-analytics/content/optimal-posting-times?days=7
```

Response:
```json
{
  "optimal_times": [
    {
      "date": "2024-01-15",
      "day_of_week": "Monday",
      "optimal_hours": [
        {
          "hour": 20,
          "time": "20:00",
          "score": 0.92,
          "expected_engagement": 0.85,
          "expected_revenue": 0.78
        }
      ],
      "recommendations": [
        "Evening posts capture peak audience activity"
      ]
    }
  ],
  "model_accuracy": 0.82,
  "last_updated": "2024-01-14T10:30:00Z"
}
```

### Get Content Recommendations
```
GET /api/v1/ml-analytics/content/recommendations
```

Response:
```json
{
  "content_types": [
    {
      "type": "High Engagement Pattern",
      "characteristics": {
        "preferred_hours": [20, 21, 22],
        "preferred_days": "Fri",
        "content_types": {"photo": 15, "video": 8}
      },
      "expected_engagement": 45.2,
      "expected_revenue": 120.5,
      "best_time_slots": ["20:00", "21:00", "22:00"],
      "confidence": 0.75
    }
  ],
  "posting_strategy": {
    "optimal_frequency": {
      "posts_per_day": 2,
      "posts_per_week": 14,
      "min_hours_between_posts": 4
    },
    "content_mix": {
      "photos": 0.4,
      "videos": 0.3,
      "text": 0.2,
      "live": 0.1
    },
    "timing_pattern": {
      "morning_slot": {"time": "08:00-10:00", "percentage": 0.3},
      "evening_slot": {"time": "20:00-22:00", "percentage": 0.4}
    }
  },
  "optimization_tips": [
    "Engagement is low - try more interactive content",
    "Maintain content variety to keep audience engaged"
  ],
  "predicted_performance": {
    "potential_engagement_increase": "15-25%",
    "potential_revenue_increase": "10-20%",
    "confidence_level": "medium"
  }
}
```

### Analyze Content Performance
```
POST /api/v1/ml-analytics/content/{content_id}/analyze
```

Response:
```json
{
  "content_id": "123e4567-e89b-12d3-a456-426614174000",
  "content_type": "photo",
  "posted_at": "2024-01-14T20:30:00Z",
  "performance": {
    "actual_engagement": 52,
    "expected_engagement": 45,
    "engagement_ratio": 1.16,
    "actual_revenue": 125.50,
    "expected_revenue": 110.00,
    "revenue_ratio": 1.14
  },
  "insights": [
    "This content exceeded engagement expectations by 20%+",
    "Posted during optimal hours",
    "Media content typically drives higher engagement"
  ],
  "recommendations": [
    "Continue posting similar content",
    "Test similar content at different times"
  ]
}
```

## Features

### 1. Optimal Posting Times
- Analyzes historical engagement patterns
- Considers day of week and time of day effects
- Provides confidence scores for each time slot
- Adapts to agency-specific audience behavior

### 2. Content Strategy Recommendations
- Identifies successful content patterns
- Recommends optimal content mix
- Suggests posting frequency
- Provides actionable optimization tips

### 3. Performance Analysis
- Compares actual vs expected performance
- Identifies over/under-performing content
- Provides insights on why content succeeded/failed
- Generates specific improvement recommendations

### 4. Pattern Recognition
- Clusters content by performance characteristics
- Identifies common traits of successful content
- Tracks emerging trends
- Alerts on significant opportunities

## Model Training

The content optimization model requires:
- Minimum 50 pieces of content
- At least 90 days of historical data
- Engagement metrics (transactions, messages)
- Content metadata (type, media count, posting time)

Training process:
1. Fetches historical content and engagement data
2. Engineers features from raw data
3. Trains separate models for time, engagement, and revenue
4. Performs content clustering for pattern recognition
5. Validates models and calculates accuracy metrics

## Best Practices

1. **Regular Retraining**: Retrain models monthly to capture changing audience behavior
2. **A/B Testing**: Use predictions to A/B test posting strategies
3. **Content Variety**: Maintain diverse content to keep models accurate
4. **Monitor Performance**: Track prediction accuracy and adjust as needed
5. **Combine Insights**: Use alongside revenue and churn predictions for holistic strategy

## Integration Example

```python
# Get optimal posting times for next week
optimal_times = await ml_service.predict_optimal_posting_times(
    next_days=7,
    content_type="photo"
)

# Schedule content based on predictions
for day in optimal_times:
    best_hour = day['optimal_hours'][0]
    schedule_content(
        date=day['date'],
        hour=best_hour['hour'],
        expected_performance=best_hour['score']
    )

# Analyze performance after posting
analysis = await ml_service.analyze_content_performance(
    content_id=posted_content.id
)

# Adjust strategy based on results
if analysis['performance']['engagement_ratio'] > 1.2:
    increase_similar_content()
```

## Metrics and Monitoring

Key metrics to track:
- **Prediction Accuracy**: How close predictions are to actual results
- **Engagement Lift**: Improvement in engagement using optimal times
- **Revenue Impact**: Additional revenue from optimization
- **Pattern Stability**: How consistent successful patterns remain

Monitor through:
- ML Analytics dashboard
- Model performance endpoint
- Insight alerts for opportunities
- Regular performance reports