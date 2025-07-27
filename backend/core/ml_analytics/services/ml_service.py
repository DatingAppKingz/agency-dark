"""
Main ML Analytics service for managing predictions.
"""
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, distinct
import numpy as np
import pandas as pd
from pathlib import Path
import json

from core.ml_analytics.models import (
    MLModel, Prediction, ModelTrainingJob, FeatureStore,
    PredictionFeedback, InsightAlert,
    PredictionType, ModelStatus
)
from core.ml_analytics.predictors.revenue_forecast import RevenueForecastPredictor
from core.ml_analytics.predictors.churn_prediction import ChurnPredictor
from core.ml_analytics.predictors.content_optimization import ContentOptimizer
from core.ml_analytics.predictors.anomaly_detection import AnomalyDetector
from core.ml_analytics.predictors.fan_ltv import FanLTVPredictor
from core.domain.models import User, Agency, Transaction, Model, Fan, Content
from core.redis import redis_client
from core.cache import cache_service

logger = logging.getLogger(__name__)


class MLAnalyticsService:
    """Main service for ML analytics and predictions."""
    
    def __init__(self):
        self.predictors = {
            PredictionType.REVENUE_FORECAST: RevenueForecastPredictor(),
            PredictionType.CHURN_PREDICTION: ChurnPredictor(),
            PredictionType.CONTENT_OPTIMIZATION: ContentOptimizer(),
            PredictionType.ANOMALY_DETECTION: AnomalyDetector(),
            PredictionType.FAN_LTV: FanLTVPredictor()
        }
        self.model_storage_path = Path("ml_models")
        self.model_storage_path.mkdir(exist_ok=True)
    
    async def train_model(
        self,
        prediction_type: PredictionType,
        agency_id: str,
        user: User,
        session: AsyncSession,
        config: Optional[Dict[str, Any]] = None
    ) -> MLModel:
        """Train a new ML model."""
        logger.info(f"Training {prediction_type.value} model for agency {agency_id}")
        
        # Create model record
        ml_model = MLModel(
            name=f"{prediction_type.value}_v{datetime.utcnow().strftime('%Y%m%d')}",
            description=f"Auto-trained {prediction_type.value} model",
            prediction_type=prediction_type,
            agency_id=agency_id,
            created_by_id=user.id,
            status=ModelStatus.TRAINING
        )
        session.add(ml_model)
        await session.commit()
        
        # Create training job
        job = ModelTrainingJob(
            model_id=ml_model.id,
            job_type="initial",
            parameters=config or {},
            triggered_by_id=user.id,
            status="running",
            started_at=datetime.utcnow()
        )
        session.add(job)
        await session.commit()
        
        try:
            # Get appropriate predictor
            predictor = self.predictors.get(prediction_type)
            if not predictor:
                raise ValueError(f"No predictor available for {prediction_type.value}")
            
            # Train model
            if prediction_type == PredictionType.REVENUE_FORECAST:
                result = await predictor.train(
                    agency_id=agency_id,
                    session=session,
                    lookback_days=config.get('lookback_days', 365) if config else 365
                )
            elif prediction_type == PredictionType.CHURN_PREDICTION:
                result = await predictor.train(
                    agency_id=agency_id,
                    session=session,
                    lookback_days=config.get('lookback_days', 180) if config else 180,
                    churn_days=config.get('churn_days', 30) if config else 30
                )
            elif prediction_type == PredictionType.CONTENT_OPTIMIZATION:
                result = await predictor.train(
                    agency_id=agency_id,
                    session=session,
                    lookback_days=config.get('lookback_days', 180) if config else 180
                )
            elif prediction_type == PredictionType.ANOMALY_DETECTION:
                result = await predictor.train(
                    agency_id=agency_id,
                    session=session,
                    lookback_days=config.get('lookback_days', 90) if config else 90,
                    contamination=config.get('contamination', 0.01) if config else 0.01
                )
            elif prediction_type == PredictionType.FAN_LTV:
                result = await predictor.train(
                    agency_id=agency_id,
                    session=session,
                    lookback_days=config.get('lookback_days', 365) if config else 365
                )
            else:
                raise NotImplementedError(f"Training not implemented for {prediction_type.value}")
            
            # Save model artifacts
            model_path = self.model_storage_path / f"{ml_model.id}.joblib"
            predictor.save_model(str(model_path))
            
            # Update model record
            ml_model.status = ModelStatus.TRAINED
            ml_model.model_path = str(model_path)
            ml_model.metrics = result['metrics']
            if prediction_type == PredictionType.REVENUE_FORECAST:
                ml_model.accuracy_score = 1 - result['metrics'].get('mape', 0)
                ml_model.algorithm = "prophet"
            elif prediction_type == PredictionType.CHURN_PREDICTION:
                ml_model.accuracy_score = result['metrics'].get('roc_auc', 0)
                ml_model.algorithm = "random_forest"
            elif prediction_type == PredictionType.CONTENT_OPTIMIZATION:
                ml_model.accuracy_score = result['metrics'].get('overall_accuracy', 0)
                ml_model.algorithm = "ensemble"
            elif prediction_type == PredictionType.ANOMALY_DETECTION:
                ml_model.accuracy_score = result['metrics'].get('overall_accuracy', 0)
                ml_model.algorithm = "isolation_forest"
            elif prediction_type == PredictionType.FAN_LTV:
                ml_model.accuracy_score = result['metrics'].get('overall_accuracy', 0)
                ml_model.algorithm = "gradient_boosting"
            ml_model.hyperparameters = result['model_metadata']
            ml_model.training_samples = result['training_samples']
            ml_model.last_trained_at = datetime.utcnow()
            
            # Update job
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
            job.metrics = result['metrics']
            job.model_artifact_path = str(model_path)
            
            await session.commit()
            
            # Activate model if it's the first one
            await self._auto_activate_model(ml_model, session)
            
            logger.info(f"Successfully trained {prediction_type.value} model {ml_model.id}")
            return ml_model
            
        except Exception as e:
            logger.error(f"Error training model: {e}")
            
            # Update status
            ml_model.status = ModelStatus.FAILED
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            
            await session.commit()
            raise
    
    async def generate_predictions(
        self,
        prediction_type: PredictionType,
        agency_id: str,
        session: AsyncSession,
        horizon_days: int = 30,
        entity_id: Optional[str] = None
    ) -> List[Prediction]:
        """Generate predictions using the active model."""
        # Get active model
        model = await self._get_active_model(prediction_type, agency_id, session)
        if not model:
            raise ValueError(f"No active {prediction_type.value} model for agency")
        
        # Load predictor
        predictor = self.predictors.get(prediction_type)
        if not predictor:
            raise ValueError(f"No predictor available for {prediction_type.value}")
        
        # Load model from disk
        predictor.load_model(model.model_path)
        
        # Generate predictions based on type
        predictions = []
        
        if prediction_type == PredictionType.REVENUE_FORECAST:
            forecast_df = await predictor.predict(horizon_days=horizon_days)
            
            # Convert to prediction records
            for _, row in forecast_df.iterrows():
                if row['date'] > datetime.utcnow():
                    prediction = Prediction(
                        model_id=model.id,
                        prediction_type=prediction_type,
                        target_date=row['date'],
                        prediction_horizon=(row['date'] - datetime.utcnow()).days,
                        predicted_value=np.expm1(row['forecast']),  # Transform back from log
                        confidence_interval_lower=np.expm1(row['lower_bound']),
                        confidence_interval_upper=np.expm1(row['upper_bound']),
                        confidence_score=float(row.get('confidence_interval', 0.95)),
                        entity_type="agency",
                        entity_id=agency_id,
                        predictions_json={
                            'trend': float(row.get('trend', 0)),
                            'seasonality': {
                                'weekly': float(row.get('weekly_seasonality', 0)),
                                'yearly': float(row.get('yearly_seasonality', 0))
                            }
                        }
                    )
                    predictions.append(prediction)
                    session.add(prediction)
        
        elif prediction_type == PredictionType.CHURN_PREDICTION:
            # Get high-risk fans
            churn_predictions = await predictor.predict_all_fans(
                agency_id=agency_id,
                session=session,
                min_probability=0.3  # Include medium to high risk fans
            )
            
            # Convert to prediction records
            for churn_pred in churn_predictions[:horizon_days]:  # Limit to requested number
                prediction = Prediction(
                    model_id=model.id,
                    prediction_type=prediction_type,
                    target_date=datetime.utcnow() + timedelta(days=30),  # 30-day churn prediction
                    prediction_horizon=30,
                    predicted_value=churn_pred['churn_probability'],
                    probability=churn_pred['churn_probability'],
                    confidence_score=0.85,  # Based on model performance
                    entity_type="fan",
                    entity_id=churn_pred['fan_id'],
                    predictions_json={
                        'risk_level': churn_pred['risk_level'],
                        'top_risk_factors': churn_pred['top_risk_factors'],
                        'recommended_actions': churn_pred['recommended_actions'],
                        'days_since_last_transaction': churn_pred['days_since_last_transaction'],
                        'total_spent': churn_pred['total_spent']
                    }
                )
                predictions.append(prediction)
                session.add(prediction)
        
        elif prediction_type == PredictionType.ANOMALY_DETECTION:
            # Detect anomalies in recent activity
            anomalies = await predictor.detect_anomalies(
                agency_id=agency_id,
                session=session,
                time_window_hours=horizon_days * 24,  # Convert days to hours
                anomaly_types=['transaction', 'behavior', 'velocity']
            )
            
            # Convert to prediction records
            for anomaly in anomalies[:horizon_days * 10]:  # Limit number of anomalies
                prediction = Prediction(
                    model_id=model.id,
                    prediction_type=prediction_type,
                    target_date=anomaly['detected_at'],
                    prediction_horizon=0,  # Real-time detection
                    predicted_value=anomaly['severity_score'],
                    probability=min(anomaly['severity_score'] / 10, 1.0),  # Normalize to 0-1
                    confidence_score=0.9,  # High confidence in anomaly detection
                    entity_type=anomaly['entity_type'],
                    entity_id=anomaly['entity_id'],
                    predictions_json={
                        'anomaly_type': anomaly['type'],
                        'details': anomaly['details'],
                        'reasons': anomaly['reasons'],
                        'recommended_actions': anomaly['recommended_actions']
                    }
                )
                predictions.append(prediction)
                session.add(prediction)
        
        elif prediction_type == PredictionType.FAN_LTV:
            # Get LTV predictions for fans
            # If entity_id is provided, predict for specific fan, otherwise top fans
            if entity_id:
                fan_ids = [entity_id]
            else:
                # Get recent active fans
                result = await session.execute(
                    select(Fan.id).join(
                        Transaction,
                        and_(
                            Transaction.fan_id == Fan.id,
                            Transaction.status == 'completed'
                        )
                    ).where(
                        Fan.agency_id == agency_id
                    ).group_by(Fan.id).order_by(
                        func.max(Transaction.created_at).desc()
                    ).limit(horizon_days * 5)  # Predict for top active fans
                )
                fan_ids = [str(row.id) for row in result.fetchall()]
            
            ltv_predictions = await predictor.predict_ltv(
                fan_ids=fan_ids,
                session=session,
                include_confidence=True
            )
            
            # Convert to prediction records
            for ltv_pred in ltv_predictions:
                # Create predictions for different time horizons
                for days, ltv_key in [(30, 'ltv_30_days'), (90, 'ltv_90_days'), (365, 'ltv_365_days')]:
                    prediction = Prediction(
                        model_id=model.id,
                        prediction_type=prediction_type,
                        target_date=datetime.utcnow() + timedelta(days=days),
                        prediction_horizon=days,
                        predicted_value=ltv_pred[ltv_key],
                        confidence_interval_lower=ltv_pred['confidence_intervals'][f'{days}_days'][0],
                        confidence_interval_upper=ltv_pred['confidence_intervals'][f'{days}_days'][1],
                        confidence_score=0.85,  # Based on model performance
                        entity_type="fan",
                        entity_id=ltv_pred['fan_id'],
                        predictions_json={
                            'ltv_predictions': {
                                '30_days': ltv_pred['ltv_30_days'],
                                '90_days': ltv_pred['ltv_90_days'],
                                '365_days': ltv_pred['ltv_365_days']
                            },
                            'recommendations': ltv_pred['recommendations'],
                            'features': ltv_pred['features']
                        }
                    )
                    predictions.append(prediction)
                    session.add(prediction)
        
        else:
            raise NotImplementedError(f"Predictions not implemented for {prediction_type.value}")
        
        await session.commit()
        
        # Generate insights
        await self._generate_insights(model, predictions, session)
        
        return predictions
    
    async def get_predictions(
        self,
        agency_id: str,
        session: AsyncSession,
        prediction_type: Optional[PredictionType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        entity_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get existing predictions."""
        query = select(Prediction).join(MLModel).where(
            MLModel.agency_id == agency_id
        )
        
        if prediction_type:
            query = query.where(Prediction.prediction_type == prediction_type)
        
        if start_date:
            query = query.where(Prediction.target_date >= start_date)
        
        if end_date:
            query = query.where(Prediction.target_date <= end_date)
        
        if entity_id:
            query = query.where(Prediction.entity_id == entity_id)
        
        query = query.order_by(Prediction.target_date)
        
        result = await session.execute(query)
        predictions = result.scalars().all()
        
        return [
            {
                'id': str(pred.id),
                'type': pred.prediction_type.value,
                'target_date': pred.target_date.isoformat(),
                'predicted_value': pred.predicted_value,
                'confidence_interval': [
                    pred.confidence_interval_lower,
                    pred.confidence_interval_upper
                ],
                'confidence_score': pred.confidence_score,
                'entity_type': pred.entity_type,
                'entity_id': str(pred.entity_id) if pred.entity_id else None,
                'actual_value': pred.actual_value,
                'error_percentage': pred.error_percentage,
                'created_at': pred.created_at.isoformat()
            }
            for pred in predictions
        ]
    
    async def analyze_trends(
        self,
        prediction_type: PredictionType,
        agency_id: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Analyze trends and patterns."""
        # Get active model
        model = await self._get_active_model(prediction_type, agency_id, session)
        if not model:
            raise ValueError(f"No active {prediction_type.value} model")
        
        # Load predictor
        predictor = self.predictors.get(prediction_type)
        if not predictor:
            raise ValueError(f"No predictor available for {prediction_type.value}")
        
        predictor.load_model(model.model_path)
        
        # Get trend analysis
        if prediction_type == PredictionType.REVENUE_FORECAST:
            analysis = await predictor.analyze_trends()
            
            # Cache results
            cache_key = f"ml_trends:{agency_id}:{prediction_type.value}"
            await cache_service.set(cache_key, analysis, ttl=3600)
            
            return analysis
        elif prediction_type == PredictionType.CHURN_PREDICTION:
            analysis = await predictor.analyze_churn_patterns(agency_id, session)
            
            # Cache results
            cache_key = f"ml_trends:{agency_id}:{prediction_type.value}"
            await cache_service.set(cache_key, analysis, ttl=3600)
            
            return analysis
        elif prediction_type == PredictionType.ANOMALY_DETECTION:
            # Get risk analysis
            risk_scores = await predictor.get_risk_scores(
                agency_id=agency_id,
                session=session,
                entity_type='fan',
                limit=50
            )
            
            # Get recent anomalies
            recent_anomalies = await predictor.detect_anomalies(
                agency_id=agency_id,
                session=session,
                time_window_hours=168,  # Last week
                anomaly_types=['transaction', 'behavior', 'velocity']
            )
            
            # Categorize anomalies
            anomaly_summary = {
                'transaction': 0,
                'behavior': 0,
                'velocity': 0,
                'pattern': 0
            }
            
            for anomaly in recent_anomalies:
                anomaly_type = anomaly['type'].replace('_anomaly', '')
                if anomaly_type in anomaly_summary:
                    anomaly_summary[anomaly_type] += 1
            
            analysis = {
                'risk_summary': {
                    'high_risk_entities': len([s for s in risk_scores if s['risk_score'] >= 60]),
                    'medium_risk_entities': len([s for s in risk_scores if 30 <= s['risk_score'] < 60]),
                    'low_risk_entities': len([s for s in risk_scores if s['risk_score'] < 30])
                },
                'anomaly_summary': anomaly_summary,
                'recent_anomalies': recent_anomalies[:10],  # Top 10 recent
                'top_risk_entities': risk_scores[:5],  # Top 5 highest risk
                'insights': [
                    f"Detected {len(recent_anomalies)} anomalies in the past week",
                    f"{anomaly_summary['transaction']} transaction anomalies require review",
                    "Anomaly detection helps prevent fraud and identify unusual patterns"
                ]
            }
            
            # Cache results
            cache_key = f"ml_trends:{agency_id}:{prediction_type.value}"
            await cache_service.set(cache_key, analysis, ttl=3600)
            
            return analysis
        elif prediction_type == PredictionType.FAN_LTV:
            # Get LTV segments and trends
            segments = await predictor.segment_fans_by_ltv(
                agency_id=agency_id,
                session=session,
                num_segments=5
            )
            
            # Get LTV trends
            trends = await predictor.analyze_ltv_trends(
                agency_id=agency_id,
                session=session
            )
            
            analysis = {
                'segments': segments['segments'],
                'segment_statistics': segments['statistics'],
                'trends': trends.get('trends', {}),
                'insights': trends.get('insights', []),
                'recommendations': trends.get('recommendations', []),
                'total_fans': segments['total_fans']
            }
            
            # Cache results
            cache_key = f"ml_trends:{agency_id}:{prediction_type.value}"
            await cache_service.set(cache_key, analysis, ttl=3600)
            
            return analysis
        else:
            raise NotImplementedError(f"Trend analysis not implemented for {prediction_type.value}")
    
    async def record_feedback(
        self,
        prediction_id: str,
        actual_value: float,
        user: User,
        session: AsyncSession,
        feedback_notes: Optional[str] = None
    ) -> PredictionFeedback:
        """Record actual outcomes for predictions."""
        # Get prediction
        result = await session.execute(
            select(Prediction).where(Prediction.id == prediction_id)
        )
        prediction = result.scalar_one_or_none()
        
        if not prediction:
            raise ValueError("Prediction not found")
        
        # Calculate errors
        absolute_error = abs(actual_value - prediction.predicted_value)
        percentage_error = (absolute_error / prediction.predicted_value) * 100 if prediction.predicted_value > 0 else 0
        
        # Create feedback record
        feedback = PredictionFeedback(
            prediction_id=prediction.id,
            actual_value=actual_value,
            actual_date=prediction.target_date,
            absolute_error=absolute_error,
            percentage_error=percentage_error,
            squared_error=absolute_error ** 2,
            feedback_notes=feedback_notes,
            recorded_by_id=user.id
        )
        session.add(feedback)
        
        # Update prediction
        prediction.actual_value = actual_value
        prediction.error_percentage = percentage_error
        prediction.feedback_received_at = datetime.utcnow()
        
        await session.commit()
        
        # Check if model needs retraining
        await self._check_model_performance(prediction.model_id, session)
        
        return feedback
    
    async def get_insights(
        self,
        agency_id: str,
        session: AsyncSession,
        severity: Optional[str] = None,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get ML-generated insights and alerts."""
        query = select(InsightAlert).where(
            InsightAlert.agency_id == agency_id
        )
        
        if severity:
            query = query.where(InsightAlert.severity == severity)
        
        if unread_only:
            query = query.where(InsightAlert.is_read == False)
        
        query = query.order_by(InsightAlert.created_at.desc()).limit(limit)
        
        result = await session.execute(query)
        alerts = result.scalars().all()
        
        return [
            {
                'id': str(alert.id),
                'type': alert.alert_type,
                'severity': alert.severity,
                'title': alert.title,
                'description': alert.description,
                'metrics': alert.metrics,
                'recommendations': alert.recommendations,
                'entity_type': alert.entity_type,
                'entity_id': str(alert.entity_id) if alert.entity_id else None,
                'is_read': alert.is_read,
                'is_resolved': alert.is_resolved,
                'created_at': alert.created_at.isoformat()
            }
            for alert in alerts
        ]
    
    async def mark_insight_read(
        self,
        insight_id: str,
        user: User,
        session: AsyncSession
    ):
        """Mark an insight as read."""
        result = await session.execute(
            select(InsightAlert).where(InsightAlert.id == insight_id)
        )
        alert = result.scalar_one_or_none()
        
        if alert and alert.agency_id == user.agency_id:
            alert.is_read = True
            await session.commit()
    
    async def get_model_performance(
        self,
        model_id: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Get model performance metrics."""
        # Get model
        result = await session.execute(
            select(MLModel).where(MLModel.id == model_id)
        )
        model = result.scalar_one_or_none()
        
        if not model:
            raise ValueError("Model not found")
        
        # Get prediction accuracy
        feedback_query = select(
            func.avg(PredictionFeedback.percentage_error).label('avg_error'),
            func.count(PredictionFeedback.id).label('feedback_count'),
            func.stddev(PredictionFeedback.percentage_error).label('error_stddev')
        ).join(Prediction).where(
            Prediction.model_id == model_id
        )
        
        feedback_result = await session.execute(feedback_query)
        feedback_stats = feedback_result.first()
        
        return {
            'model_id': str(model.id),
            'model_name': model.name,
            'status': model.status.value,
            'training_metrics': model.metrics,
            'live_performance': {
                'average_error_percentage': float(feedback_stats.avg_error or 0),
                'feedback_count': feedback_stats.feedback_count or 0,
                'error_standard_deviation': float(feedback_stats.error_stddev or 0)
            },
            'last_trained': model.last_trained_at.isoformat() if model.last_trained_at else None,
            'is_active': model.is_active
        }
    
    async def _get_active_model(
        self,
        prediction_type: PredictionType,
        agency_id: str,
        session: AsyncSession
    ) -> Optional[MLModel]:
        """Get the active model for a prediction type."""
        result = await session.execute(
            select(MLModel).where(
                and_(
                    MLModel.agency_id == agency_id,
                    MLModel.prediction_type == prediction_type,
                    MLModel.is_active == True,
                    MLModel.status == ModelStatus.TRAINED
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _auto_activate_model(
        self,
        model: MLModel,
        session: AsyncSession
    ):
        """Automatically activate model if it's the first or best performing."""
        # Check if there's an active model
        active_model = await self._get_active_model(
            model.prediction_type,
            model.agency_id,
            session
        )
        
        if not active_model:
            # No active model, activate this one
            model.is_active = True
            model.deployment_date = datetime.utcnow()
            await session.commit()
        else:
            # Compare performance
            if model.accuracy_score and active_model.accuracy_score:
                if model.accuracy_score > active_model.accuracy_score:
                    # New model is better
                    active_model.is_active = False
                    model.is_active = True
                    model.deployment_date = datetime.utcnow()
                    await session.commit()
    
    async def _generate_insights(
        self,
        model: MLModel,
        predictions: List[Prediction],
        session: AsyncSession
    ):
        """Generate insights from predictions."""
        if not predictions:
            return
        
        if model.prediction_type == PredictionType.REVENUE_FORECAST:
            # Check for significant changes
            future_revenue = sum(p.predicted_value for p in predictions[:7])  # Next week
            
            # Get last week's actual revenue
            last_week = datetime.utcnow() - timedelta(days=7)
            result = await session.execute(
                select(func.sum(Transaction.amount)).where(
                    and_(
                        Transaction.agency_id == model.agency_id,
                        Transaction.created_at >= last_week,
                        Transaction.status == 'completed'
                    )
                )
            )
            past_revenue = result.scalar() or 0
            
            if past_revenue > 0:
                change_percentage = ((future_revenue - past_revenue) / past_revenue) * 100
                
                if abs(change_percentage) > 20:
                    # Significant change detected
                    alert = InsightAlert(
                        alert_type='prediction',
                        severity='high' if change_percentage < -20 else 'medium',
                        title=f"Significant Revenue {'Decrease' if change_percentage < 0 else 'Increase'} Predicted",
                        description=f"Revenue is predicted to {('decrease' if change_percentage < 0 else 'increase')} by {abs(change_percentage):.1f}% next week",
                        model_id=model.id,
                        entity_type='agency',
                        entity_id=model.agency_id,
                        agency_id=model.agency_id,
                        metrics={
                            'predicted_revenue': future_revenue,
                            'past_revenue': past_revenue,
                            'change_percentage': change_percentage
                        },
                        recommendations=[
                            "Review upcoming content schedule",
                            "Consider promotional campaigns" if change_percentage < 0 else "Prepare for increased activity",
                            "Monitor daily performance closely"
                        ]
                    )
                    session.add(alert)
                    await session.commit()
        
        elif model.prediction_type == PredictionType.CHURN_PREDICTION:
            # Analyze churn predictions
            high_risk_fans = [p for p in predictions if p.predicted_value >= 0.6]
            medium_risk_fans = [p for p in predictions if 0.4 <= p.predicted_value < 0.6]
            
            if high_risk_fans:
                # Create alert for high-risk fans
                alert = InsightAlert(
                    alert_type='prediction',
                    severity='critical',
                    title=f"{len(high_risk_fans)} Fans at High Risk of Churning",
                    description=f"Immediate action required for {len(high_risk_fans)} fans with >60% churn probability",
                    model_id=model.id,
                    entity_type='agency',
                    entity_id=model.agency_id,
                    agency_id=model.agency_id,
                    metrics={
                        'high_risk_count': len(high_risk_fans),
                        'medium_risk_count': len(medium_risk_fans),
                        'total_at_risk': len(high_risk_fans) + len(medium_risk_fans),
                        'average_churn_probability': np.mean([p.predicted_value for p in predictions])
                    },
                    recommendations=[
                        "Send immediate personalized retention offers",
                        "Initiate direct outreach to high-value fans",
                        "Create exclusive content for at-risk segments",
                        "Review and address common churn factors"
                    ]
                )
                session.add(alert)
                await session.commit()
            
            # Additional insight for churn trends
            if predictions:
                avg_churn_prob = np.mean([p.predicted_value for p in predictions])
                if avg_churn_prob > 0.3:
                    alert = InsightAlert(
                        alert_type='trend',
                        severity='high',
                        title="Elevated Churn Risk Across Fan Base",
                        description=f"Average churn probability is {avg_churn_prob:.1%}, indicating systemic issues",
                        model_id=model.id,
                        entity_type='agency',
                        entity_id=model.agency_id,
                        agency_id=model.agency_id,
                        metrics={'average_churn_probability': avg_churn_prob},
                        recommendations=[
                            "Review recent content strategy",
                            "Analyze competitor activities",
                            "Survey fans for feedback",
                            "Implement loyalty program"
                        ]
                    )
                    session.add(alert)
                    await session.commit()
        
        elif model.prediction_type == PredictionType.CONTENT_OPTIMIZATION:
            # Analyze content optimization insights
            if predictions:
                # Group predictions by day
                daily_scores = {}
                for pred in predictions:
                    date_key = pred.target_date.date()
                    if date_key not in daily_scores:
                        daily_scores[date_key] = []
                    daily_scores[date_key].append(pred.predicted_value)
                
                # Find days with exceptional opportunities
                high_potential_days = [
                    date for date, scores in daily_scores.items()
                    if max(scores) > 0.8
                ]
                
                if high_potential_days:
                    alert = InsightAlert(
                        alert_type='opportunity',
                        severity='medium',
                        title=f"High Engagement Opportunities Detected",
                        description=f"Found {len(high_potential_days)} days with exceptional posting opportunities",
                        model_id=model.id,
                        entity_type='agency',
                        entity_id=model.agency_id,
                        agency_id=model.agency_id,
                        metrics={
                            'high_potential_days': len(high_potential_days),
                            'avg_opportunity_score': float(np.mean([max(daily_scores[d]) for d in high_potential_days]))
                        },
                        recommendations=[
                            "Prepare high-quality content for optimal time slots",
                            "Schedule posts in advance for peak times",
                            "Monitor engagement metrics closely",
                            "Test different content types during optimal hours"
                        ]
                    )
                    session.add(alert)
                    await session.commit()
        
        elif model.prediction_type == PredictionType.ANOMALY_DETECTION:
            # Analyze anomaly patterns
            if predictions:
                # Group by anomaly type
                anomaly_types = {}
                high_severity_count = 0
                
                for pred in predictions:
                    anomaly_type = pred.predictions_json.get('anomaly_type', 'unknown')
                    if anomaly_type not in anomaly_types:
                        anomaly_types[anomaly_type] = 0
                    anomaly_types[anomaly_type] += 1
                    
                    if pred.predicted_value > 5:  # High severity threshold
                        high_severity_count += 1
                
                if high_severity_count > 5:
                    alert = InsightAlert(
                        alert_type='anomaly',
                        severity='critical',
                        title=f"Multiple High-Severity Anomalies Detected",
                        description=f"Found {high_severity_count} high-severity anomalies requiring immediate attention",
                        model_id=model.id,
                        entity_type='agency',
                        entity_id=model.agency_id,
                        agency_id=model.agency_id,
                        metrics={
                            'high_severity_count': high_severity_count,
                            'total_anomalies': len(predictions),
                            'anomaly_breakdown': anomaly_types
                        },
                        recommendations=[
                            "Review all high-severity anomalies immediately",
                            "Check for potential security breaches",
                            "Implement additional verification measures",
                            "Monitor affected accounts closely"
                        ]
                    )
                    session.add(alert)
                    await session.commit()
        
        elif model.prediction_type == PredictionType.FAN_LTV:
            # Analyze LTV predictions
            if predictions:
                # Group by fan and get highest LTV predictions
                fan_ltvs = {}
                for pred in predictions:
                    if pred.entity_id not in fan_ltvs:
                        fan_ltvs[pred.entity_id] = []
                    fan_ltvs[pred.entity_id].append(pred)
                
                # Find high-value fans
                high_value_fans = []
                total_predicted_ltv = 0
                
                for fan_id, fan_preds in fan_ltvs.items():
                    # Get 365-day LTV prediction
                    ltv_365 = next((p.predicted_value for p in fan_preds if p.prediction_horizon == 365), 0)
                    if ltv_365 > 1000:  # High value threshold
                        high_value_fans.append((fan_id, ltv_365))
                    total_predicted_ltv += ltv_365
                
                if high_value_fans:
                    alert = InsightAlert(
                        alert_type='opportunity',
                        severity='medium',
                        title=f"Identified {len(high_value_fans)} High-Value Fans",
                        description=f"Found {len(high_value_fans)} fans with predicted LTV > $1000",
                        model_id=model.id,
                        entity_type='agency',
                        entity_id=model.agency_id,
                        agency_id=model.agency_id,
                        metrics={
                            'high_value_count': len(high_value_fans),
                            'total_predicted_ltv': total_predicted_ltv,
                            'avg_ltv_365': total_predicted_ltv / len(fan_ltvs) if fan_ltvs else 0,
                            'top_fan_ltvs': sorted(high_value_fans, key=lambda x: x[1], reverse=True)[:5]
                        },
                        recommendations=[
                            "Prioritize engagement with high-value fans",
                            "Create VIP programs for top LTV fans",
                            "Develop retention strategies for valuable segments",
                            "Monitor and nurture growing LTV fans"
                        ]
                    )
                    session.add(alert)
                    await session.commit()
    
    async def _check_model_performance(
        self,
        model_id: str,
        session: AsyncSession
    ):
        """Check if model needs retraining based on performance."""
        # Get recent feedback
        result = await session.execute(
            select(func.avg(PredictionFeedback.percentage_error)).join(Prediction).where(
                and_(
                    Prediction.model_id == model_id,
                    PredictionFeedback.recorded_at >= datetime.utcnow() - timedelta(days=30)
                )
            )
        )
        avg_error = result.scalar()
        
        if avg_error and avg_error > 20:  # 20% error threshold
            # Create alert for retraining
            model_result = await session.execute(
                select(MLModel).where(MLModel.id == model_id)
            )
            model = model_result.scalar_one()
            
            alert = InsightAlert(
                alert_type='anomaly',
                severity='high',
                title="Model Performance Degradation Detected",
                description=f"The {model.prediction_type.value} model is showing {avg_error:.1f}% average error. Consider retraining.",
                model_id=model_id,
                agency_id=model.agency_id,
                metrics={'average_error': avg_error},
                recommendations=["Retrain model with recent data", "Review data quality", "Check for data drift"]
            )
            session.add(alert)
            await session.commit()


# Singleton instance
ml_service = MLAnalyticsService()
