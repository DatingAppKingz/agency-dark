export interface RevenueForecast {
  date: string;
  predicted_revenue: number;
  lower_bound: number;
  upper_bound: number;
  confidence: number;
}

export interface RevenueForecastResponse {
  forecasts: RevenueForecast[];
  summary: {
    total_predicted: number;
    average_daily: number;
    growth_rate: number;
    confidence_score: number;
  };
  model_info: {
    last_trained: string;
    accuracy_metrics: {
      mae: number;
      rmse: number;
      r2_score: number;
    };
  };
}

export interface ChurnRisk {
  fan_id: string;
  fan_username: string;
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  factors: string[];
  last_active: string;
  lifetime_value: number;
}

export interface ChurnPredictionResponse {
  high_risk_fans: ChurnRisk[];
  risk_distribution: {
    low: number;
    medium: number;
    high: number;
    critical: number;
  };
  recommendations: string[];
  model_info: {
    last_trained: string;
    accuracy: number;
    feature_importance: Record<string, number>;
  };
}

export interface ContentRecommendation {
  content_type: string;
  title: string;
  description: string;
  predicted_engagement: number;
  predicted_revenue: number;
  confidence: number;
  optimal_time: string;
  target_segments: string[];
}

export interface ContentRecommendationResponse {
  recommendations: ContentRecommendation[];
  personalized_for_fans: Array<{
    fan_id: string;
    fan_username: string;
    recommendations: ContentRecommendation[];
  }>;
  trending_topics: string[];
  optimal_posting_times: string[];
}

export interface Anomaly {
  anomaly_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  detected_at: string;
  affected_entity: string;
  metric_value: number;
  expected_range: {
    min: number;
    max: number;
  };
  action_required: boolean;
  suggested_action?: string;
}

export interface AnomalyDetectionResponse {
  anomalies: Anomaly[];
  summary: {
    total_anomalies: number;
    critical_count: number;
    requires_action_count: number;
  };
  system_health: {
    status: 'healthy' | 'warning' | 'critical';
    score: number;
  };
}

export interface MLInsightsSummary {
  revenue_forecast: {
    next_30_days: number;
    trend: 'up' | 'down' | 'stable';
    confidence: number;
  };
  churn_risk: {
    at_risk_count: number;
    potential_revenue_loss: number;
    top_risk_factors: string[];
  };
  content_performance: {
    engagement_trend: 'up' | 'down' | 'stable';
    top_performing_types: string[];
    optimization_opportunities: number;
  };
  anomalies: {
    active_count: number;
    critical_count: number;
    last_24h_count: number;
  };
}

export interface TrainingStatus {
  model_name: string;
  status: 'pending' | 'training' | 'completed' | 'failed';
  progress?: number;
  metrics?: Record<string, any>;
  model_path?: string;
  timestamp: string;
  error?: string;
}

export interface ModelMetrics {
  model_name: string;
  accuracy: number;
  precision?: number;
  recall?: number;
  f1_score?: number;
  rmse?: number;
  mae?: number;
  r2_score?: number;
  last_trained: string;
  training_samples: number;
  feature_importance?: Record<string, number>;
}