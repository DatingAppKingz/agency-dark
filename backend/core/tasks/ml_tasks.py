"""
Machine learning model training and prediction tasks
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import numpy as np
import pickle
import os

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select, func, and_

from core.database import get_db_context
from core.models import ModelProfile, Transaction, MLModel
from modules.ml.revenue_forecasting import RevenueForecastModel
from modules.ml.churn_prediction import ChurnPredictionModel
from modules.ml.content_recommendation import ContentRecommendationEngine
from modules.ml.anomaly_detection import AnomalyDetector

logger = get_task_logger(__name__)


@shared_task(bind=True)
def retrain_revenue_forecast_model(self) -> Dict[str, Any]:
    """
    Retrain revenue forecasting model
    """
    try:
        async def _retrain():
            async with get_db_context() as db:
                # Get all active models with sufficient data
                min_transactions = 100
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                
                # Find models with enough recent transactions
                model_ids_result = await db.execute(
                    select(
                        Transaction.model_id,
                        func.count(Transaction.id).label('tx_count')
                    ).where(
                        and_(
                            Transaction.created_at >= thirty_days_ago,
                            Transaction.type.in_(['payment', 'tip', 'subscription'])
                        )
                    ).group_by(
                        Transaction.model_id
                    ).having(
                        func.count(Transaction.id) >= min_transactions
                    )
                )
                
                model_data = model_ids_result.all()
                
                results = {
                    'models_trained': 0,
                    'errors': [],
                    'performance_metrics': {}
                }
                
                for model_id, tx_count in model_data:
                    try:
                        # Get transaction history
                        tx_result = await db.execute(
                            select(Transaction).where(
                                and_(
                                    Transaction.model_id == model_id,
                                    Transaction.type.in_(['payment', 'tip', 'subscription'])
                                )
                            ).order_by(
                                Transaction.created_at
                            )
                        )
                        transactions = tx_result.scalars().all()
                        
                        # Prepare training data
                        forecast_model = RevenueForecastModel()
                        
                        # Train model
                        metrics = forecast_model.train(
                            transactions=transactions,
                            model_id=str(model_id)
                        )
                        
                        # Save model
                        model_path = f"/models/revenue_forecast/{model_id}.pkl"
                        os.makedirs(os.path.dirname(model_path), exist_ok=True)
                        
                        with open(model_path, 'wb') as f:
                            pickle.dump(forecast_model, f)
                        
                        # Save model metadata
                        ml_model = await db.execute(
                            select(MLModel).where(
                                and_(
                                    MLModel.model_id == model_id,
                                    MLModel.model_type == 'revenue_forecast'
                                )
                            )
                        )
                        ml_model_record = ml_model.scalar_one_or_none()
                        
                        if not ml_model_record:
                            ml_model_record = MLModel(
                                model_id=model_id,
                                model_type='revenue_forecast',
                                model_path=model_path,
                                version=1,
                                metrics=metrics,
                                trained_at=datetime.utcnow()
                            )
                            db.add(ml_model_record)
                        else:
                            ml_model_record.model_path = model_path
                            ml_model_record.version += 1
                            ml_model_record.metrics = metrics
                            ml_model_record.trained_at = datetime.utcnow()
                        
                        results['models_trained'] += 1
                        results['performance_metrics'][str(model_id)] = metrics
                        
                    except Exception as exc:
                        logger.error(f"Failed to train revenue model for {model_id}: {exc}")
                        results['errors'].append({
                            'model_id': str(model_id),
                            'error': str(exc)
                        })
                
                await db.commit()
                
                logger.info(f"Revenue forecast model training completed: {results}")
                return results
        
        # Run async function
        import asyncio
        return asyncio.run(_retrain())
        
    except Exception as exc:
        logger.error(f"Revenue forecast model training failed: {exc}")
        raise


@shared_task(bind=True)
def retrain_churn_prediction_model(self) -> Dict[str, Any]:
    """
    Retrain churn prediction model
    """
    try:
        async def _retrain():
            async with get_db_context() as db:
                # Get fan activity data
                churn_model = ChurnPredictionModel()
                
                # Get all users with transaction history
                ninety_days_ago = datetime.utcnow() - timedelta(days=90)
                
                user_activity_result = await db.execute(
                    select(
                        Transaction.user_id,
                        func.count(Transaction.id).label('transaction_count'),
                        func.max(Transaction.created_at).label('last_transaction'),
                        func.sum(Transaction.amount).label('total_spent'),
                        func.avg(Transaction.amount).label('avg_transaction')
                    ).where(
                        Transaction.created_at >= ninety_days_ago
                    ).group_by(
                        Transaction.user_id
                    )
                )
                
                user_data = user_activity_result.all()
                
                if len(user_data) < 100:
                    return {
                        'status': 'skipped',
                        'reason': 'Insufficient data for training',
                        'user_count': len(user_data)
                    }
                
                # Train model
                metrics = churn_model.train(user_data)
                
                # Save model
                model_path = "/models/churn_prediction/global_model.pkl"
                os.makedirs(os.path.dirname(model_path), exist_ok=True)
                
                with open(model_path, 'wb') as f:
                    pickle.dump(churn_model, f)
                
                # Save model metadata
                ml_model_record = MLModel(
                    model_type='churn_prediction',
                    model_path=model_path,
                    version=1,
                    metrics=metrics,
                    trained_at=datetime.utcnow()
                )
                db.add(ml_model_record)
                
                await db.commit()
                
                logger.info(f"Churn prediction model trained with metrics: {metrics}")
                
                return {
                    'status': 'success',
                    'metrics': metrics,
                    'users_processed': len(user_data)
                }
        
        # Run async function
        import asyncio
        return asyncio.run(_retrain())
        
    except Exception as exc:
        logger.error(f"Churn prediction model training failed: {exc}")
        raise


@shared_task
def update_content_recommendations() -> Dict[str, Any]:
    """
    Update content recommendations for all models
    """
    try:
        async def _update():
            async with get_db_context() as db:
                # Get active models
                result = await db.execute(
                    select(ModelProfile).where(
                        ModelProfile.is_active == True
                    )
                )
                models = result.scalars().all()
                
                recommendation_engine = ContentRecommendationEngine()
                
                results = {
                    'models_processed': 0,
                    'recommendations_generated': 0,
                    'errors': []
                }
                
                for model in models:
                    try:
                        # Get model's content and fan interactions
                        # This is simplified - in reality would analyze content performance
                        recommendations = recommendation_engine.generate_recommendations(
                            model_id=str(model.id),
                            limit=10
                        )
                        
                        # Store recommendations in cache
                        from core.redis import redis_client
                        cache_key = f"recommendations:model:{model.id}"
                        await redis_client.setex(
                            cache_key,
                            86400,  # 24 hours
                            json.dumps(recommendations)
                        )
                        
                        results['models_processed'] += 1
                        results['recommendations_generated'] += len(recommendations)
                        
                    except Exception as exc:
                        logger.error(f"Failed to generate recommendations for model {model.id}: {exc}")
                        results['errors'].append({
                            'model_id': str(model.id),
                            'error': str(exc)
                        })
                
                logger.info(f"Content recommendations updated: {results}")
                return results
        
        # Run async function
        import asyncio
        return asyncio.run(_update())
        
    except Exception as exc:
        logger.error(f"Content recommendation update failed: {exc}")
        raise


@shared_task
def detect_anomalies(model_id: str) -> Dict[str, Any]:
    """
    Detect anomalies in model's transactions
    """
    try:
        async def _detect():
            async with get_db_context() as db:
                # Get recent transactions
                seven_days_ago = datetime.utcnow() - timedelta(days=7)
                
                result = await db.execute(
                    select(Transaction).where(
                        and_(
                            Transaction.model_id == model_id,
                            Transaction.created_at >= seven_days_ago
                        )
                    ).order_by(
                        Transaction.created_at
                    )
                )
                transactions = result.scalars().all()
                
                if len(transactions) < 10:
                    return {
                        'status': 'skipped',
                        'reason': 'Insufficient recent transactions',
                        'transaction_count': len(transactions)
                    }
                
                # Initialize anomaly detector
                detector = AnomalyDetector()
                
                # Detect anomalies
                anomalies = detector.detect_anomalies(transactions)
                
                # Store results
                if anomalies:
                    # Create alerts for anomalies
                    from core.redis import redis_client
                    alert_key = f"anomalies:model:{model_id}"
                    await redis_client.setex(
                        alert_key,
                        3600,  # 1 hour
                        json.dumps({
                            'anomalies': anomalies,
                            'detected_at': datetime.utcnow().isoformat(),
                            'transaction_count': len(transactions)
                        })
                    )
                    
                    logger.warning(f"Detected {len(anomalies)} anomalies for model {model_id}")
                
                return {
                    'status': 'success',
                    'anomalies_detected': len(anomalies),
                    'transactions_analyzed': len(transactions),
                    'anomalies': anomalies
                }
        
        # Run async function
        import asyncio
        return asyncio.run(_detect())
        
    except Exception as exc:
        logger.error(f"Anomaly detection failed for model {model_id}: {exc}")
        raise


@shared_task
def generate_ml_insights(model_id: str) -> Dict[str, Any]:
    """
    Generate ML-based insights for a model
    """
    try:
        async def _generate():
            insights = {}
            
            # Load trained models
            revenue_model_path = f"/models/revenue_forecast/{model_id}.pkl"
            if os.path.exists(revenue_model_path):
                with open(revenue_model_path, 'rb') as f:
                    revenue_model = pickle.load(f)
                
                # Generate revenue forecast
                forecast = revenue_model.predict_next_30_days()
                insights['revenue_forecast'] = {
                    'next_7_days': forecast[:7],
                    'next_30_days': forecast,
                    'expected_total': sum(forecast),
                    'confidence': 0.85  # Simplified
                }
            
            # Check for anomalies
            from core.redis import redis_client
            anomaly_key = f"anomalies:model:{model_id}"
            anomaly_data = await redis_client.get(anomaly_key)
            if anomaly_data:
                insights['anomalies'] = json.loads(anomaly_data)
            
            # Get recommendations
            rec_key = f"recommendations:model:{model_id}"
            rec_data = await redis_client.get(rec_key)
            if rec_data:
                insights['content_recommendations'] = json.loads(rec_data)
            
            # Store insights
            insights_key = f"ml_insights:model:{model_id}"
            await redis_client.setex(
                insights_key,
                3600,  # 1 hour
                json.dumps({
                    'insights': insights,
                    'generated_at': datetime.utcnow().isoformat()
                })
            )
            
            logger.info(f"Generated ML insights for model {model_id}")
            
            return {
                'status': 'success',
                'insights_generated': len(insights),
                'insights': insights
            }
        
        # Run async function
        import asyncio
        return asyncio.run(_generate())
        
    except Exception as exc:
        logger.error(f"ML insights generation failed for model {model_id}: {exc}")
        raise