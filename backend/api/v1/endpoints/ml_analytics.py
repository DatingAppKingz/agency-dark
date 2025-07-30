"""ML Analytics endpoints for anomaly detection and predictive analytics."""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from core.dependencies import get_db, get_current_user
from models.user import User
from core.application.ml_analytics_service import MLAnalyticsService
from core.exceptions import ValidationError, NotFoundError

router = APIRouter()


# Request/Response schemas
class TrainModelRequest(BaseModel):
    """Request to train ML model."""
    prediction_type: str = Field(..., pattern="^(anomaly_detection|churn_prediction|revenue_forecast)$")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AnomalyResponse(BaseModel):
    """Anomaly detection response."""
    type: str
    entity_type: str
    entity_id: str
    detected_at: str
    severity_score: float
    details: Dict[str, Any]
    reasons: List[str]
    recommended_actions: List[str]


class RiskScoreResponse(BaseModel):
    """Risk score response."""
    fan_id: Optional[int] = None
    model_id: Optional[int] = None
    username: Optional[str] = None
    risk_score: int
    transaction_count: Optional[int] = None
    total_spent: Optional[float] = None
    risk_factors: List[str]
    last_activity: Optional[str] = None


class ConversationInsightsResponse(BaseModel):
    """Conversation insights response."""
    conversation_id: int
    total_messages: int
    avg_message_length: float
    avg_response_time_seconds: float
    topics: List[str]
    sentiment: Dict[str, Any]
    engagement_score: float
    insights: List[str]


class ChurnPredictionResponse(BaseModel):
    """Churn prediction response."""
    fan_id: int
    churn_risk_score: int
    risk_level: str
    risk_factors: List[str]
    metrics: Dict[str, Any]
    recommendation: str
    predicted_churn_probability: float


class EntityAnalysisResponse(BaseModel):
    """Entity analysis response."""
    fan_id: Optional[int] = None
    model_id: Optional[int] = None
    risk_score: int
    anomaly_count: int
    total_transactions: Optional[int] = None
    total_spent: Optional[float] = None
    avg_transaction_amount: Optional[float] = None
    anomalies: List[Dict[str, Any]]
    risk_factors: List[str]
    recommendation: str


@router.post("/models/train")
async def train_model(
    request: TrainModelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Train ML model for predictions.
    
    - Requires admin role
    - Supports anomaly detection, churn prediction, revenue forecast
    - Model is cached for reuse
    """
    # Check permissions - include standard admin role and super_admin
    if current_user.role not in ["admin", "super_admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    if request.prediction_type == "anomaly_detection":
        # Extract config
        model_type = request.config.get("model_type", "transaction")
        lookback_days = request.config.get("lookback_days", 90)
        contamination = request.config.get("contamination", 0.01)
        
        result = await MLAnalyticsService.train_anomaly_model(
            db=db,
            model_type=model_type,
            lookback_days=lookback_days,
            contamination=contamination
        )
        
        return result
    else:
        # Other model types not implemented yet
        return {
            "status": "not_implemented",
            "message": f"Model type {request.prediction_type} not implemented yet",
            "available_types": ["anomaly_detection"]
        }


@router.get("/anomalies/detect", response_model=List[AnomalyResponse])
async def detect_anomalies(
    time_window_hours: int = Query(24, ge=1, le=168),
    anomaly_types: Optional[str] = Query(None, description="Comma-separated types: transaction,behavior,velocity"),
    min_severity: float = Query(5.0, ge=0, le=10),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[AnomalyResponse]:
    """
    Detect anomalies in recent data.
    
    - Multiple anomaly types supported
    - Returns anomalies above severity threshold
    - Sorted by severity (highest first)
    """
    # Check permissions - include standard admin role and super_admin
    if current_user.role not in ["admin", "super_admin", "owner", "agency_admin", "agency_owner", "manager", "agency_manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Parse anomaly types
    types_list = None
    if anomaly_types:
        types_list = [t.strip() for t in anomaly_types.split(",")]
    
    anomalies = await MLAnalyticsService.detect_anomalies(
        db=db,
        time_window_hours=time_window_hours,
        anomaly_types=types_list,
        min_severity=min_severity
    )
    
    return [AnomalyResponse(**anomaly) for anomaly in anomalies]


@router.get("/anomalies/risk-scores", response_model=List[RiskScoreResponse])
async def get_risk_scores(
    entity_type: str = Query("fan", pattern="^(fan|model)$"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[RiskScoreResponse]:
    """
    Get risk scores for entities.
    
    - Calculate risk based on multiple factors
    - Returns top risky entities
    - Includes risk factors explanation
    """
    # Check permissions - include standard admin role and super_admin
    if current_user.role not in ["admin", "super_admin", "owner", "agency_admin", "agency_owner", "manager", "agency_manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    scores = await MLAnalyticsService.get_risk_scores(
        db=db,
        entity_type=entity_type,
        limit=limit
    )
    
    return [RiskScoreResponse(**score) for score in scores]


@router.post("/anomalies/analyze/{entity_type}/{entity_id}")
async def analyze_entity(
    entity_type: str,
    entity_id: int,
    lookback_days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> EntityAnalysisResponse:
    """
    Analyze specific entity for anomalies.
    
    - Deep analysis of transaction patterns
    - Identifies specific anomalies
    - Provides recommendations
    """
    # Check permissions - include standard admin role and super_admin
    if current_user.role not in ["admin", "super_admin", "owner", "agency_admin", "agency_owner", "manager", "agency_manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Validate entity type
    if entity_type not in ["fan", "model"]:
        raise HTTPException(status_code=400, detail="Invalid entity type")
    
    try:
        analysis = await MLAnalyticsService.analyze_entity(
            db=db,
            entity_type=entity_type,
            entity_id=entity_id,
            lookback_days=lookback_days
        )
        
        return EntityAnalysisResponse(**analysis)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/conversations/insights/{conversation_id}", response_model=ConversationInsightsResponse)
async def get_conversation_insights(
    conversation_id: int,
    include_sentiment: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ConversationInsightsResponse:
    """
    Extract ML insights from conversation.
    
    - Topic extraction
    - Sentiment analysis
    - Engagement metrics
    - Actionable insights
    """
    try:
        insights = await MLAnalyticsService.get_conversation_insights(
            db=db,
            conversation_id=conversation_id,
            include_sentiment=include_sentiment
        )
        
        return ConversationInsightsResponse(**insights)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/fans/churn-risk/{fan_id}", response_model=ChurnPredictionResponse)
async def predict_churn_risk(
    fan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ChurnPredictionResponse:
    """
    Predict fan churn risk.
    
    - Analyzes activity patterns
    - Identifies risk factors
    - Provides retention recommendations
    """
    # Check permissions - include standard admin role and super_admin
    if current_user.role not in ["admin", "super_admin", "owner", "agency_admin", "agency_owner", "manager", "agency_manager", "model"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    prediction = await MLAnalyticsService.predict_churn_risk(
        db=db,
        fan_id=fan_id
    )
    
    return ChurnPredictionResponse(**prediction)


@router.get("/dashboard")
async def get_ml_analytics_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get ML analytics dashboard data.
    
    - Recent anomalies
    - High risk entities
    - Churn predictions
    - System insights
    """
    # Check permissions - include standard admin role and super_admin
    if current_user.role not in ["admin", "super_admin", "owner", "agency_admin", "agency_owner"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get recent anomalies
    anomalies = await MLAnalyticsService.detect_anomalies(
        db=db,
        time_window_hours=24,
        min_severity=7.0
    )
    
    # Get high risk fans
    risk_scores = await MLAnalyticsService.get_risk_scores(
        db=db,
        entity_type="fan",
        limit=10
    )
    
    # Filter high risk only
    high_risk_fans = [s for s in risk_scores if s["risk_score"] >= 60]
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "summary": {
            "critical_anomalies": len([a for a in anomalies if a["severity_score"] >= 8]),
            "high_risk_fans": len(high_risk_fans),
            "total_anomalies_24h": len(anomalies)
        },
        "recent_anomalies": anomalies[:5],
        "high_risk_entities": high_risk_fans[:5],
        "insights": [
            f"{len(anomalies)} anomalies detected in last 24 hours",
            f"{len(high_risk_fans)} fans with high risk scores",
            "ML models are actively monitoring for suspicious patterns"
        ]
    }


@router.get("/test")
async def test_ml_analytics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Test ML analytics functionality.
    
    - Returns sample ML analysis
    - For testing and demonstration
    """
    # Detect some anomalies
    anomalies = await MLAnalyticsService.detect_anomalies(
        db=db,
        time_window_hours=1,
        min_severity=5.0
    )
    
    # Get a risk score
    risk_scores = await MLAnalyticsService.get_risk_scores(
        db=db,
        entity_type="fan",
        limit=1
    )
    
    return {
        "message": "ML Analytics is operational",
        "capabilities": [
            "Anomaly detection (transaction, behavior, velocity)",
            "Risk scoring for fans and models",
            "Conversation insights and sentiment analysis",
            "Churn prediction",
            "Pattern recognition"
        ],
        "sample_data": {
            "anomalies_detected": len(anomalies),
            "sample_anomaly": anomalies[0] if anomalies else None,
            "sample_risk_score": risk_scores[0] if risk_scores else None
        }
    }