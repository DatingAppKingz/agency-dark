"""
ML Analytics API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from pydantic import BaseModel, Field

from core.dependencies import get_db, get_current_user
from core.domain.models import User, UserRole, Fan, Model, Transaction
from core.ml_analytics.models import PredictionType, ModelStatus
from core.ml_analytics.services.ml_service import ml_service
from core.domain.schemas import BaseResponse

router = APIRouter(prefix="/ml-analytics", tags=["ml-analytics"])


# Schemas
class ModelTrainRequest(BaseModel):
    """Request to train a new ML model."""
    prediction_type: PredictionType
    config: Optional[Dict[str, Any]] = Field(None, description="Model configuration")


class PredictionRequest(BaseModel):
    """Request to generate predictions."""
    prediction_type: PredictionType
    horizon_days: int = Field(30, ge=1, le=365)
    entity_id: Optional[UUID] = None


class FeedbackRequest(BaseModel):
    """Record prediction feedback."""
    prediction_id: UUID
    actual_value: float
    feedback_notes: Optional[str] = None


class ModelResponse(BaseModel):
    """ML model response."""
    id: UUID
    name: str
    prediction_type: str
    status: str
    accuracy_score: Optional[float]
    is_active: bool
    last_trained_at: Optional[datetime]
    metrics: Optional[Dict[str, Any]]


class PredictionResponse(BaseModel):
    """Prediction response."""
    id: UUID
    type: str
    target_date: datetime
    predicted_value: float
    confidence_interval: List[float]
    confidence_score: float
    entity_type: Optional[str]
    entity_id: Optional[UUID]
    actual_value: Optional[float]
    error_percentage: Optional[float]


class InsightResponse(BaseModel):
    """Insight/alert response."""
    id: UUID
    type: str
    severity: str
    title: str
    description: str
    metrics: Dict[str, Any]
    recommendations: List[str]
    is_read: bool
    is_resolved: bool
    created_at: datetime


# Endpoints

@router.post("/models/train", response_model=ModelResponse)
async def train_model(
    request: ModelTrainRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ModelResponse:
    """Train a new ML model."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(
            status_code=403,
            detail="Only agency owners and admins can train models"
        )
    
    try:
        # Train model
        model = await ml_service.train_model(
            prediction_type=request.prediction_type,
            agency_id=current_user.agency_id,
            user=current_user,
            session=db,
            config=request.config
        )
        
        return ModelResponse(
            id=model.id,
            name=model.name,
            prediction_type=model.prediction_type.value,
            status=model.status.value,
            accuracy_score=model.accuracy_score,
            is_active=model.is_active,
            last_trained_at=model.last_trained_at,
            metrics=model.metrics
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.post("/predictions/generate", response_model=List[PredictionResponse])
async def generate_predictions(
    request: PredictionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[PredictionResponse]:
    """Generate new predictions."""
    try:
        predictions = await ml_service.generate_predictions(
            prediction_type=request.prediction_type,
            agency_id=current_user.agency_id,
            session=db,
            horizon_days=request.horizon_days,
            entity_id=str(request.entity_id) if request.entity_id else None
        )
        
        return [
            PredictionResponse(
                id=pred.id,
                type=pred.prediction_type.value,
                target_date=pred.target_date,
                predicted_value=pred.predicted_value,
                confidence_interval=[
                    pred.confidence_interval_lower,
                    pred.confidence_interval_upper
                ],
                confidence_score=pred.confidence_score,
                entity_type=pred.entity_type,
                entity_id=pred.entity_id,
                actual_value=pred.actual_value,
                error_percentage=pred.error_percentage
            )
            for pred in predictions
        ]
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/predictions", response_model=List[Dict[str, Any]])
async def get_predictions(
    prediction_type: Optional[PredictionType] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    entity_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get existing predictions."""
    predictions = await ml_service.get_predictions(
        agency_id=current_user.agency_id,
        session=db,
        prediction_type=prediction_type,
        start_date=start_date,
        end_date=end_date,
        entity_id=str(entity_id) if entity_id else None
    )
    
    return predictions


@router.get("/predictions/{prediction_type}/trends")
async def analyze_trends(
    prediction_type: PredictionType,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Analyze trends and patterns."""
    try:
        analysis = await ml_service.analyze_trends(
            prediction_type=prediction_type,
            agency_id=current_user.agency_id,
            session=db
        )
        return analysis
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/feedback", response_model=BaseResponse)
async def record_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Record actual outcomes for predictions."""
    try:
        await ml_service.record_feedback(
            prediction_id=str(request.prediction_id),
            actual_value=request.actual_value,
            user=current_user,
            session=db,
            feedback_notes=request.feedback_notes
        )
        
        return BaseResponse(
            success=True,
            message="Feedback recorded successfully"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/insights", response_model=List[InsightResponse])
async def get_insights(
    severity: Optional[str] = None,
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[InsightResponse]:
    """Get ML-generated insights and alerts."""
    insights = await ml_service.get_insights(
        agency_id=current_user.agency_id,
        session=db,
        severity=severity,
        unread_only=unread_only,
        limit=limit
    )
    
    return [
        InsightResponse(
            id=insight['id'],
            type=insight['type'],
            severity=insight['severity'],
            title=insight['title'],
            description=insight['description'],
            metrics=insight['metrics'],
            recommendations=insight['recommendations'],
            is_read=insight['is_read'],
            is_resolved=insight['is_resolved'],
            created_at=insight['created_at']
        )
        for insight in insights
    ]


@router.patch("/insights/{insight_id}/read", response_model=BaseResponse)
async def mark_insight_read(
    insight_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Mark an insight as read."""
    await ml_service.mark_insight_read(
        insight_id=str(insight_id),
        user=current_user,
        session=db
    )
    
    return BaseResponse(
        success=True,
        message="Insight marked as read"
    )


@router.get("/models")
async def list_models(
    prediction_type: Optional[PredictionType] = None,
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[ModelResponse]:
    """List available ML models."""
    from sqlalchemy import select, and_
    from core.ml_analytics.models import MLModel
    
    query = select(MLModel).where(MLModel.agency_id == current_user.agency_id)
    
    if prediction_type:
        query = query.where(MLModel.prediction_type == prediction_type)
    
    if active_only:
        query = query.where(MLModel.is_active == True)
    
    query = query.order_by(MLModel.created_at.desc())
    
    result = await db.execute(query)
    models = result.scalars().all()
    
    return [
        ModelResponse(
            id=model.id,
            name=model.name,
            prediction_type=model.prediction_type.value,
            status=model.status.value,
            accuracy_score=model.accuracy_score,
            is_active=model.is_active,
            last_trained_at=model.last_trained_at,
            metrics=model.metrics
        )
        for model in models
    ]


@router.get("/models/{model_id}/performance")
async def get_model_performance(
    model_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get model performance metrics."""
    try:
        performance = await ml_service.get_model_performance(
            model_id=str(model_id),
            session=db
        )
        return performance
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/predictions/churn/high-risk-fans")
async def get_high_risk_fans(
    min_probability: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get fans with high churn risk."""
    # Get churn predictions
    predictions = await ml_service.get_predictions(
        agency_id=current_user.agency_id,
        session=db,
        prediction_type=PredictionType.CHURN_PREDICTION,
        start_date=datetime.utcnow() - timedelta(days=7),  # Recent predictions
        end_date=datetime.utcnow() + timedelta(days=30)
    )
    
    # Filter by risk level
    high_risk = [
        p for p in predictions
        if p['predicted_value'] >= min_probability
    ]
    
    # Sort by risk level
    high_risk.sort(key=lambda x: x['predicted_value'], reverse=True)
    
    # Get fan details for top risks
    results = []
    for pred in high_risk[:limit]:
        if pred.get('entity_id') and pred.get('entity_type') == 'fan':
            # Get fan details
            from core.domain.models import Fan
            result = await db.execute(
                select(Fan).where(Fan.id == pred['entity_id'])
            )
            fan = result.scalar_one_or_none()
            
            if fan:
                pred_json = pred.get('predictions_json', {})
                results.append({
                    'fan_id': pred['entity_id'],
                    'fan_username': fan.username,
                    'churn_probability': pred['predicted_value'],
                    'risk_level': pred_json.get('risk_level', 'unknown'),
                    'top_risk_factors': pred_json.get('top_risk_factors', []),
                    'recommended_actions': pred_json.get('recommended_actions', []),
                    'days_since_last_transaction': pred_json.get('days_since_last_transaction'),
                    'total_spent': pred_json.get('total_spent'),
                    'prediction_date': pred['target_date']
                })
    
    return results


@router.get("/content/optimal-posting-times")
async def get_optimal_posting_times(
    days: int = Query(7, ge=1, le=30),
    content_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get optimal posting times for content."""
    # Check if content optimization model exists
    from sqlalchemy import select, and_
    from core.ml_analytics.models import MLModel
    
    result = await db.execute(
        select(MLModel).where(
            and_(
                MLModel.agency_id == current_user.agency_id,
                MLModel.prediction_type == PredictionType.CONTENT_OPTIMIZATION,
                MLModel.is_active == True,
                MLModel.status == ModelStatus.TRAINED
            )
        )
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(
            status_code=404,
            detail="No active content optimization model. Please train a model first."
        )
    
    # Get predictor
    predictor = ml_service.predictors.get(PredictionType.CONTENT_OPTIMIZATION)
    predictor.load_model(model.model_path)
    
    # Get predictions
    predictions = await predictor.predict_optimal_posting_times(
        next_days=days,
        content_type=content_type
    )
    
    return {
        'optimal_times': predictions,
        'model_accuracy': model.accuracy_score,
        'last_updated': model.last_trained_at.isoformat() if model.last_trained_at else None
    }


@router.get("/content/recommendations")
async def get_content_recommendations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get content recommendations based on ML analysis."""
    # Check if content optimization model exists
    from sqlalchemy import select, and_
    from core.ml_analytics.models import MLModel
    
    result = await db.execute(
        select(MLModel).where(
            and_(
                MLModel.agency_id == current_user.agency_id,
                MLModel.prediction_type == PredictionType.CONTENT_OPTIMIZATION,
                MLModel.is_active == True,
                MLModel.status == ModelStatus.TRAINED
            )
        )
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(
            status_code=404,
            detail="No active content optimization model. Please train a model first."
        )
    
    # Get predictor
    predictor = ml_service.predictors.get(PredictionType.CONTENT_OPTIMIZATION)
    predictor.load_model(model.model_path)
    
    # Get recent performance metrics
    from datetime import datetime, timedelta
    recent_cutoff = datetime.utcnow() - timedelta(days=30)
    
    # Simple performance calculation (in production, would be more sophisticated)
    recent_performance = {
        'engagement_rate': 0.08,  # 8% engagement rate
        'revenue_per_post': 150,  # $150 average
        'off_peak_posts': 0.25    # 25% posts during off-peak
    }
    
    # Get recommendations
    recommendations = await predictor.recommend_content(
        recent_performance=recent_performance
    )
    
    return recommendations


@router.post("/content/{content_id}/analyze")
async def analyze_content_performance(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Analyze individual content performance using ML."""
    # Verify content belongs to user's agency
    from core.domain.models import Content, Model
    
    result = await db.execute(
        select(Content).join(Model).where(
            and_(
                Content.id == content_id,
                Model.agency_id == current_user.agency_id
            )
        )
    )
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=404,
            detail="Content not found or access denied"
        )
    
    # Check if model exists
    from core.ml_analytics.models import MLModel
    
    model_result = await db.execute(
        select(MLModel).where(
            and_(
                MLModel.agency_id == current_user.agency_id,
                MLModel.prediction_type == PredictionType.CONTENT_OPTIMIZATION,
                MLModel.is_active == True,
                MLModel.status == ModelStatus.TRAINED
            )
        )
    )
    model = model_result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(
            status_code=404,
            detail="No active content optimization model. Please train a model first."
        )
    
    # Get predictor
    predictor = ml_service.predictors.get(PredictionType.CONTENT_OPTIMIZATION)
    predictor.load_model(model.model_path)
    
    # Analyze content
    try:
        analysis = await predictor.analyze_content_performance(
            content_id=str(content_id),
            session=db
        )
        return analysis
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.get("/anomalies/detect")
async def detect_anomalies(
    time_window_hours: int = Query(24, ge=1, le=168),
    anomaly_types: Optional[List[str]] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Detect anomalies in recent activity."""
    # Check if anomaly detection model exists
    from sqlalchemy import select, and_
    from core.ml_analytics.models import MLModel
    
    result = await db.execute(
        select(MLModel).where(
            and_(
                MLModel.agency_id == current_user.agency_id,
                MLModel.prediction_type == PredictionType.ANOMALY_DETECTION,
                MLModel.is_active == True,
                MLModel.status == ModelStatus.TRAINED
            )
        )
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(
            status_code=404,
            detail="No active anomaly detection model. Please train a model first."
        )
    
    # Get predictor
    predictor = ml_service.predictors.get(PredictionType.ANOMALY_DETECTION)
    predictor.load_model(model.model_path)
    
    # Detect anomalies
    if anomaly_types is None:
        anomaly_types = ['transaction', 'behavior', 'velocity']
    
    try:
        anomalies = await predictor.detect_anomalies(
            agency_id=current_user.agency_id,
            session=db,
            time_window_hours=time_window_hours,
            anomaly_types=anomaly_types
        )
        
        # Limit results
        return anomalies[:limit]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Anomaly detection failed: {str(e)}"
        )


@router.get("/anomalies/risk-scores")
async def get_risk_scores(
    entity_type: str = Query("fan", enum=["fan", "model"]),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get risk scores for entities."""
    # Check if model exists
    from sqlalchemy import select, and_
    from core.ml_analytics.models import MLModel
    
    result = await db.execute(
        select(MLModel).where(
            and_(
                MLModel.agency_id == current_user.agency_id,
                MLModel.prediction_type == PredictionType.ANOMALY_DETECTION,
                MLModel.is_active == True,
                MLModel.status == ModelStatus.TRAINED
            )
        )
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(
            status_code=404,
            detail="No active anomaly detection model. Please train a model first."
        )
    
    # Get predictor
    predictor = ml_service.predictors.get(PredictionType.ANOMALY_DETECTION)
    predictor.load_model(model.model_path)
    
    # Get risk scores
    try:
        risk_scores = await predictor.get_risk_scores(
            agency_id=current_user.agency_id,
            session=db,
            entity_type=entity_type,
            limit=limit
        )
        
        return risk_scores
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Risk score calculation failed: {str(e)}"
        )


@router.post("/anomalies/analyze/{entity_type}/{entity_id}")
async def analyze_entity(
    entity_type: str,
    entity_id: UUID,
    lookback_days: int = Query(30, ge=1, le=180),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Analyze a specific entity for anomalous behavior."""
    # Validate entity type
    if entity_type not in ['fan', 'model', 'transaction']:
        raise HTTPException(
            status_code=400,
            detail="Invalid entity type. Must be 'fan', 'model', or 'transaction'"
        )
    
    # Check if model exists
    from sqlalchemy import select, and_
    from core.ml_analytics.models import MLModel
    
    result = await db.execute(
        select(MLModel).where(
            and_(
                MLModel.agency_id == current_user.agency_id,
                MLModel.prediction_type == PredictionType.ANOMALY_DETECTION,
                MLModel.is_active == True,
                MLModel.status == ModelStatus.TRAINED
            )
        )
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(
            status_code=404,
            detail="No active anomaly detection model. Please train a model first."
        )
    
    # Verify entity belongs to agency
    if entity_type == 'fan':
        entity_result = await db.execute(
            select(Fan).where(
                and_(
                    Fan.id == entity_id,
                    Fan.agency_id == current_user.agency_id
                )
            )
        )
        if not entity_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Fan not found")
    elif entity_type == 'model':
        entity_result = await db.execute(
            select(Model).where(
                and_(
                    Model.id == entity_id,
                    Model.agency_id == current_user.agency_id
                )
            )
        )
        if not entity_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Model not found")
    elif entity_type == 'transaction':
        entity_result = await db.execute(
            select(Transaction).where(
                and_(
                    Transaction.id == entity_id,
                    Transaction.agency_id == current_user.agency_id
                )
            )
        )
        if not entity_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Get predictor
    predictor = ml_service.predictors.get(PredictionType.ANOMALY_DETECTION)
    predictor.load_model(model.model_path)
    
    # Analyze entity
    try:
        analysis = await predictor.analyze_entity(
            entity_type=entity_type,
            entity_id=str(entity_id),
            session=db,
            lookback_days=lookback_days
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Entity analysis failed: {str(e)}"
        )


@router.get("/dashboard")
async def ml_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get ML analytics dashboard data."""
    # Get latest predictions
    revenue_predictions = await ml_service.get_predictions(
        agency_id=current_user.agency_id,
        session=db,
        prediction_type=PredictionType.REVENUE_FORECAST,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=7)
    )
    
    # Get churn predictions
    churn_predictions = await ml_service.get_predictions(
        agency_id=current_user.agency_id,
        session=db,
        prediction_type=PredictionType.CHURN_PREDICTION,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30)
    )
    
    # Count high-risk fans
    high_risk_fans = len([p for p in churn_predictions if p['predicted_value'] >= 0.6])
    
    # Get recent insights
    insights = await ml_service.get_insights(
        agency_id=current_user.agency_id,
        session=db,
        unread_only=True,
        limit=5
    )
    
    # Get active models
    from sqlalchemy import select
    from core.ml_analytics.models import MLModel
    
    result = await db.execute(
        select(MLModel).where(
            and_(
                MLModel.agency_id == current_user.agency_id,
                MLModel.is_active == True
            )
        )
    )
    active_models = result.scalars().all()
    
    # Calculate summary metrics
    next_week_revenue = sum(
        pred['predicted_value'] for pred in revenue_predictions
    ) if revenue_predictions else 0
    
    return {
        'summary': {
            'active_models': len(active_models),
            'unread_insights': len(insights),
            'next_week_revenue_forecast': next_week_revenue,
            'high_risk_fans': high_risk_fans
        },
        'models': [
            {
                'type': model.prediction_type.value,
                'accuracy': model.accuracy_score,
                'last_trained': model.last_trained_at.isoformat() if model.last_trained_at else None
            }
            for model in active_models
        ],
        'recent_predictions': revenue_predictions[:7],
        'insights': insights,
        'trends': {
            'revenue': await ml_service.analyze_trends(
                PredictionType.REVENUE_FORECAST,
                current_user.agency_id,
                db
            ) if any(m.prediction_type == PredictionType.REVENUE_FORECAST for m in active_models) else None,
            'churn': await ml_service.analyze_trends(
                PredictionType.CHURN_PREDICTION,
                current_user.agency_id,
                db
            ) if any(m.prediction_type == PredictionType.CHURN_PREDICTION for m in active_models) else None,
            'content': await ml_service.analyze_trends(
                PredictionType.CONTENT_OPTIMIZATION,
                current_user.agency_id,
                db
            ) if any(m.prediction_type == PredictionType.CONTENT_OPTIMIZATION for m in active_models) else None,
            'anomaly': await ml_service.analyze_trends(
                PredictionType.ANOMALY_DETECTION,
                current_user.agency_id,
                db
            ) if any(m.prediction_type == PredictionType.ANOMALY_DETECTION for m in active_models) else None
        }
    }
