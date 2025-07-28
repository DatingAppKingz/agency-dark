"""
Schemas for ML Insights API
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID


class ForecastData(BaseModel):
    date: datetime
    forecast: float
    lower_80: Optional[float] = None
    upper_80: Optional[float] = None
    lower_95: Optional[float] = None
    upper_95: Optional[float] = None


class RevenueAnomaly(BaseModel):
    date: datetime
    revenue: float
    predicted_revenue: float
    z_score: float
    is_anomaly: bool
    anomaly_severity: str


class RevenueForecastResponse(BaseModel):
    forecast: List[ForecastData]
    historical_anomalies: List[RevenueAnomaly]
    model_metrics: Dict[str, float]


class AtRiskUser(BaseModel):
    subscriber_id: str
    churn_probability: float
    churn_risk_score: float
    risk_level: str
    recommended_action: str
    potential_revenue_loss: float


class CohortAnalysis(BaseModel):
    subscription_month: str
    total_subscribers: int
    churned_count: int
    churn_rate: float
    avg_revenue: float
    avg_lifetime: float


class ChurnPredictionResponse(BaseModel):
    at_risk_users: List[AtRiskUser]
    risk_distribution: Dict[str, int]
    cohort_analysis: List[CohortAnalysis]
    model_metrics: Dict[str, Dict[str, float]]


class ContentRecommendation(BaseModel):
    content_id: str
    score: float
    rank: int


class RecommendationExplanation(BaseModel):
    content_id: str
    user_id: str
    reasons: List[str]
    collaborative_score: Optional[float] = None
    similar_to_history: Optional[List[str]] = None
    popularity_data: Optional[Dict[str, Any]] = None


class ContentRecommendationResponse(BaseModel):
    recommendations: List[ContentRecommendation]
    explanations: List[RecommendationExplanation]


class AnomalousTransaction(BaseModel):
    user_id: str
    timestamp: datetime
    amount: float
    transaction_type: str
    anomaly_score: float
    risk_level: str
    rule_violations: List[Dict[str, str]]


class AnomalyExplanation(BaseModel):
    anomaly_score: float
    risk_level: str
    model_scores: Dict[str, float]
    rule_violations: List[Dict[str, str]]
    contributing_factors: List[Dict[str, str]]


class AnomalyDetectionResponse(BaseModel):
    total_transactions: int
    anomalies_detected: int
    high_risk_transactions: List[AnomalousTransaction]
    explanations: List[AnomalyExplanation]
    risk_summary: Dict[str, int]


class MLInsightsSummaryResponse(BaseModel):
    revenue: Optional[Dict[str, Any]] = None
    churn: Optional[Dict[str, Any]] = None
    model_status: Dict[str, Dict[str, Any]]


class TrainingStatusResponse(BaseModel):
    model_name: str
    status: str
    metrics: Dict[str, Any]
    model_path: str
    timestamp: datetime


class ModelMetricsResponse(BaseModel):
    model_name: str
    version: str
    is_trained: bool
    training_metadata: Dict[str, Any]
    feature_importance: Optional[Dict[str, float]] = None
    model_status: Dict[str, Any]


# Request schemas
class TransactionData(BaseModel):
    user_id: str
    timestamp: datetime
    amount: float
    transaction_type: str
    ip_address: Optional[str] = None
    device_id: Optional[str] = None
    location_country: Optional[str] = None
    location_city: Optional[str] = None


class TrainModelRequest(BaseModel):
    agency_id: Optional[UUID] = None
    force_retrain: bool = False