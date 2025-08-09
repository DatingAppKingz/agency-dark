"""
ML Insights API endpoints
"""
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from core.database import get_db
from core.security_v2 import get_current_user
from models.user import User, UserRole
from ml.service import ml_service
from schemas.ml_insights import (
    RevenueForecastResponse,
    ChurnPredictionResponse,
    ContentRecommendationResponse,
    AnomalyDetectionResponse,
    MLInsightsSummaryResponse,
    TrainingStatusResponse,
    ModelMetricsResponse
)

router = APIRouter()


@router.post("/train/revenue-forecast", response_model=TrainingStatusResponse)
async def train_revenue_forecast(
    agency_id: Optional[UUID] = Body(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Train or retrain the revenue forecasting model
    """
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # If not super admin, can only train for their own agency
    if current_user.role != UserRole.SUPER_ADMIN and agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Can only train models for your own agency")
    
    result = await ml_service.train_revenue_forecast(db, agency_id)
    
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return TrainingStatusResponse(
        model_name="revenue_forecast",
        status="completed",
        metrics=result['metrics'],
        model_path=result['model_path'],
        timestamp=datetime.now()
    )


@router.post("/train/churn-prediction", response_model=TrainingStatusResponse)
async def train_churn_prediction(
    agency_id: Optional[UUID] = Body(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Train or retrain the churn prediction model
    """
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # If not super admin, can only train for their own agency
    if current_user.role != UserRole.SUPER_ADMIN and agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Can only train models for your own agency")
    
    result = await ml_service.train_churn_prediction(db, agency_id)
    
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return TrainingStatusResponse(
        model_name="churn_prediction",
        status="completed",
        metrics=result['metrics'],
        model_path=result['model_path'],
        timestamp=datetime.now()
    )


@router.get("/revenue-forecast", response_model=RevenueForecastResponse)
async def get_revenue_forecast(
    periods: int = Query(30, ge=1, le=365, description="Number of days to forecast"),
    agency_id: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get revenue forecast for the next N days
    """
    # Check permissions
    if current_user.role == UserRole.MODEL:
        # Models can only see their own revenue forecast
        agency_id = current_user.agency_id
    elif current_user.role not in [UserRole.SUPER_ADMIN] and agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Can only view forecasts for your own agency")
    
    result = await ml_service.get_revenue_forecast(db, agency_id, periods)
    
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return RevenueForecastResponse(**result)


@router.get("/churn-predictions", response_model=ChurnPredictionResponse)
async def get_churn_predictions(
    limit: int = Query(100, ge=1, le=1000),
    risk_level: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    agency_id: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get churn predictions and at-risk users
    """
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # If not super admin, can only view their own agency
    if current_user.role != UserRole.SUPER_ADMIN and agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Can only view predictions for your own agency")
    
    result = await ml_service.get_churn_predictions(db, agency_id, limit)
    
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    
    # Filter by risk level if specified
    if risk_level and 'at_risk_users' in result:
        result['at_risk_users'] = [
            u for u in result['at_risk_users'] 
            if u['risk_level'] == risk_level
        ]
    
    return ChurnPredictionResponse(**result)


@router.get("/content-recommendations/{user_id}", response_model=ContentRecommendationResponse)
async def get_content_recommendations(
    user_id: UUID,
    n_recommendations: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get personalized content recommendations for a user
    """
    # Check permissions - users can see their own recommendations
    if str(user_id) != str(current_user.id) and current_user.role not in [
        UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN
    ]:
        raise HTTPException(status_code=403, detail="Can only view your own recommendations")
    
    result = await ml_service.get_content_recommendations(str(user_id), n_recommendations)
    
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return ContentRecommendationResponse(**result)


@router.post("/detect-anomalies", response_model=AnomalyDetectionResponse)
async def detect_anomalies(
    transactions: List[dict] = Body(..., description="List of transactions to analyze"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Detect anomalies in a batch of transactions
    """
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Ensure transactions belong to user's agency if not super admin
    if current_user.role != UserRole.SUPER_ADMIN:
        # Filter transactions to only include those from user's agency
        # This would require transaction data to include agency_id
        pass
    
    result = await ml_service.detect_anomalies(db, transactions)
    
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return AnomalyDetectionResponse(**result)


@router.get("/insights-summary", response_model=MLInsightsSummaryResponse)
async def get_ml_insights_summary(
    agency_id: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive ML insights summary dashboard data
    """
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # If not super admin, can only view their own agency
    if current_user.role != UserRole.SUPER_ADMIN:
        agency_id = current_user.agency_id
    
    result = await ml_service.get_ml_insights_summary(db, agency_id)
    
    return MLInsightsSummaryResponse(**result)


@router.get("/model-metrics/{model_name}", response_model=ModelMetricsResponse)
async def get_model_metrics(
    model_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get performance metrics for a specific model
    """
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    valid_models = ['revenue_forecast', 'churn_prediction', 'content_recommendation', 'anomaly_detection']
    if model_name not in valid_models:
        raise HTTPException(status_code=404, detail=f"Model not found. Valid models: {', '.join(valid_models)}")
    
    if model_name not in ml_service.models:
        raise HTTPException(status_code=404, detail="Model not initialized")
    
    model = ml_service.models[model_name]
    if not model.is_trained:
        raise HTTPException(status_code=400, detail="Model not trained yet")
    
    # Get feature importance if available
    feature_importance = ml_service.get_feature_importance(model_name)
    
    return ModelMetricsResponse(
        model_name=model_name,
        version=model.version,
        is_trained=model.is_trained,
        training_metadata=model.training_metadata,
        feature_importance=feature_importance,
        model_status=ml_service.model_status.get(model_name, {})
    )


@router.get("/feature-importance/{model_name}")
async def get_feature_importance(
    model_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get feature importance for a specific model
    """
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    importance = ml_service.get_feature_importance(model_name)
    if importance is None:
        raise HTTPException(status_code=404, detail="Feature importance not available for this model")
    
    return {"model_name": model_name, "feature_importance": importance}