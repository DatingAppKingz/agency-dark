"""
ML Service for managing and executing ML models
"""
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import asyncio
from pathlib import Path
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from core.database import get_db
from models.user import User
from models.financial import Transaction, Earning
from models.analytics import ModelAnalytics
# UserActivity doesn't exist yet - would need to be created
# from models.user import UserActivity

from . import ML_DISABLED

# Import ML models conditionally
if ML_DISABLED:
    RevenueForecastModel = None
    ChurnPredictionModel = None
    ContentRecommendationEngine = None
    AnomalyDetectionModel = None
else:
    try:
        from .models.revenue_forecast import RevenueForecastModel
        from .models.churn_prediction import ChurnPredictionModel
        from .models.content_recommendation import ContentRecommendationEngine
        from .models.anomaly_detection import AnomalyDetectionModel
    except ImportError as e:
        print(f"Warning: ML dependencies not installed. ML features disabled. Error: {e}")
        RevenueForecastModel = None
        ChurnPredictionModel = None
        ContentRecommendationEngine = None
        AnomalyDetectionModel = None

logger = logging.getLogger(__name__)


class MLService:
    """
    Main service for ML operations
    """
    
    def __init__(self):
        self.models = {}
        
        # Only initialize models if they're available
        if RevenueForecastModel:
            self.models['revenue_forecast'] = RevenueForecastModel()
        if ChurnPredictionModel:
            self.models['churn_prediction'] = ChurnPredictionModel()
        if ContentRecommendationEngine:
            self.models['content_recommendation'] = ContentRecommendationEngine()
        if AnomalyDetectionModel:
            self.models['anomaly_detection'] = AnomalyDetectionModel()
            
        self.model_status = {}
        
        if not self.models:
            logger.warning("No ML models available. ML features will be disabled.")
        else:
            self._initialize_models()
    
    def _initialize_models(self):
        """Load pre-trained models if available"""
        for name, model in self.models.items():
            model_path = Path(f"ml/saved_models/{name}")
            if model_path.exists():
                try:
                    latest_model = sorted(model_path.glob("*.pkl"))[-1]
                    model.load_model(str(latest_model))
                    self.model_status[name] = {
                        'loaded': True,
                        'path': str(latest_model),
                        'timestamp': datetime.now()
                    }
                    logger.info(f"Loaded {name} model from {latest_model}")
                except Exception as e:
                    logger.error(f"Failed to load {name} model: {e}")
                    self.model_status[name] = {'loaded': False, 'error': str(e)}
            else:
                self.model_status[name] = {'loaded': False, 'error': 'No saved model found'}
    
    async def train_revenue_forecast(self, db: AsyncSession, agency_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Train revenue forecasting model
        """
        try:
            # Fetch revenue data
            query = select(Earning).order_by(Earning.date)
            if agency_id:
                query = query.where(Earning.agency_id == agency_id)
            
            result = await db.execute(query)
            revenues = result.scalars().all()
            
            if len(revenues) < 30:
                return {'error': 'Insufficient data for training (minimum 30 days required)'}
            
            # Prepare data
            data = pd.DataFrame([{
                'date': r.date,
                'revenue': float(r.total_revenue),
                'model_id': r.model_id
            } for r in revenues])
            
            # Train model
            metrics = self.models['revenue_forecast'].train(data)
            
            # Save model
            model_path = self.models['revenue_forecast'].save_model()
            
            return {
                'success': True,
                'metrics': metrics,
                'model_path': model_path
            }
            
        except Exception as e:
            logger.error(f"Revenue forecast training failed: {e}")
            return {'error': str(e)}
    
    async def train_churn_prediction(self, db: AsyncSession, agency_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Train churn prediction model
        """
        try:
            # TODO: UserActivity model doesn't exist yet
            # For now, use User model directly
            query = select(User)
            if agency_id:
                query = query.where(User.agency_id == agency_id)
            
            result = await db.execute(query)
            activities = result.scalars().all()
            
            if len(activities) < 100:
                return {'error': 'Insufficient data for training (minimum 100 users required)'}
            
            # Aggregate user data
            user_data = []
            for activity in activities:
                user_data.append({
                    'subscriber_id': activity.user_id,
                    'subscription_date': activity.first_activity,
                    'last_active_date': activity.last_activity,
                    'total_spent': float(activity.total_spent or 0),
                    'message_count': activity.message_count,
                    'content_views': activity.content_views,
                    'login_frequency': activity.login_count,
                    'days_since_last_activity': (datetime.now() - activity.last_activity).days
                })
            
            data = pd.DataFrame(user_data)
            
            # Train model
            metrics = self.models['churn_prediction'].train(data)
            
            # Save model
            model_path = self.models['churn_prediction'].save_model()
            
            return {
                'success': True,
                'metrics': metrics,
                'model_path': model_path
            }
            
        except Exception as e:
            logger.error(f"Churn prediction training failed: {e}")
            return {'error': str(e)}
    
    async def get_revenue_forecast(self, 
                                  db: AsyncSession, 
                                  agency_id: Optional[str] = None,
                                  periods: int = 30) -> Dict[str, Any]:
        """
        Generate revenue forecast
        """
        try:
            if not self.models['revenue_forecast'].is_trained:
                return {'error': 'Revenue forecast model not trained'}
            
            # Fetch historical data
            query = select(Earning).order_by(Earning.date.desc()).limit(90)
            if agency_id:
                query = query.where(Earning.agency_id == agency_id)
            
            result = await db.execute(query)
            revenues = result.scalars().all()
            
            if not revenues:
                return {'error': 'No historical revenue data found'}
            
            # Prepare data
            historical_data = pd.DataFrame([{
                'date': r.date,
                'revenue': float(r.total_revenue)
            } for r in reversed(revenues)])
            
            # Generate forecast
            forecast = self.models['revenue_forecast'].forecast(
                historical_data, 
                periods=periods,
                include_confidence=True
            )
            
            # Detect anomalies in historical data
            anomalies = self.models['revenue_forecast'].detect_anomalies(historical_data)
            
            return {
                'forecast': forecast.to_dict('records'),
                'historical_anomalies': anomalies[anomalies['is_anomaly']].to_dict('records'),
                'model_metrics': self.models['revenue_forecast'].training_metadata.get('metrics', {})
            }
            
        except Exception as e:
            logger.error(f"Revenue forecast generation failed: {e}")
            return {'error': str(e)}
    
    async def get_churn_predictions(self, 
                                   db: AsyncSession,
                                   agency_id: Optional[str] = None,
                                   limit: int = 100) -> Dict[str, Any]:
        """
        Get churn predictions for users
        """
        try:
            if not self.models['churn_prediction'].is_trained:
                return {'error': 'Churn prediction model not trained'}
            
            # TODO: UserActivity model doesn't exist yet
            # For now, use User model directly
            query = select(User).order_by(
                User.updated_at.desc()
            ).limit(limit)
            
            if agency_id:
                query = query.where(User.agency_id == agency_id)
            
            result = await db.execute(query)
            activities = result.scalars().all()
            
            if not activities:
                return {'error': 'No user activity data found'}
            
            # Prepare data
            user_data = pd.DataFrame([{
                'subscriber_id': a.user_id,
                'subscription_date': a.first_activity,
                'last_active_date': a.last_activity,
                'total_spent': float(a.total_spent or 0),
                'message_count': a.message_count,
                'content_views': a.content_views,
                'login_frequency': a.login_count,
                'days_since_last_activity': (datetime.now() - a.last_activity).days
            } for a in activities])
            
            # Get predictions
            risk_scores = self.models['churn_prediction'].get_risk_scores(user_data)
            
            # Get cohort analysis
            cohort_analysis = self.models['churn_prediction'].get_cohort_analysis(user_data)
            
            return {
                'at_risk_users': risk_scores[risk_scores['risk_level'].isin(['high', 'critical'])].to_dict('records'),
                'risk_distribution': risk_scores['risk_level'].value_counts().to_dict(),
                'cohort_analysis': cohort_analysis.to_dict('records'),
                'model_metrics': self.models['churn_prediction'].training_metadata.get('model_scores', {})
            }
            
        except Exception as e:
            logger.error(f"Churn prediction failed: {e}")
            return {'error': str(e)}
    
    async def get_content_recommendations(self,
                                        user_id: str,
                                        n_recommendations: int = 10) -> Dict[str, Any]:
        """
        Get content recommendations for a user
        """
        try:
            if not self.models['content_recommendation'].is_trained:
                return {'error': 'Content recommendation model not trained'}
            
            # Get recommendations
            recommendations = self.models['content_recommendation'].predict(
                user_id, 
                n_recommendations
            )
            
            # Get explanations for top recommendations
            explanations = []
            for content_id, score in recommendations[:3]:
                explanation = self.models['content_recommendation'].explain_recommendation(
                    user_id, 
                    content_id
                )
                explanations.append(explanation)
            
            return {
                'recommendations': [
                    {'content_id': c_id, 'score': score, 'rank': i + 1}
                    for i, (c_id, score) in enumerate(recommendations)
                ],
                'explanations': explanations
            }
            
        except Exception as e:
            logger.error(f"Content recommendation failed: {e}")
            return {'error': str(e)}
    
    async def detect_anomalies(self,
                              db: AsyncSession,
                              transaction_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect anomalies in transactions
        """
        try:
            if not self.models['anomaly_detection'].is_trained:
                return {'error': 'Anomaly detection model not trained'}
            
            # Prepare data
            df = pd.DataFrame(transaction_data)
            
            # Get anomaly scores
            anomaly_results = self.models['anomaly_detection'].get_anomaly_scores(df)
            
            # Filter high-risk anomalies
            high_risk = anomaly_results[anomaly_results['risk_level'].isin(['medium_risk', 'high_risk'])]
            
            # Get explanations for high-risk transactions
            explanations = []
            for _, row in high_risk.iterrows():
                explanation = self.models['anomaly_detection'].explain_anomaly(row)
                explanations.append(explanation)
            
            return {
                'total_transactions': len(df),
                'anomalies_detected': len(high_risk),
                'high_risk_transactions': high_risk.to_dict('records'),
                'explanations': explanations,
                'risk_summary': anomaly_results['risk_level'].value_counts().to_dict()
            }
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return {'error': str(e)}
    
    async def get_ml_insights_summary(self, 
                                     db: AsyncSession,
                                     agency_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive ML insights summary
        """
        insights = {}
        
        # Revenue insights
        revenue_forecast = await self.get_revenue_forecast(db, agency_id, periods=30)
        if 'forecast' in revenue_forecast:
            next_30_days = sum([f['forecast'] for f in revenue_forecast['forecast']])
            insights['revenue'] = {
                'forecast_30_days': next_30_days,
                'anomalies_detected': len(revenue_forecast.get('historical_anomalies', [])),
                'model_accuracy': revenue_forecast.get('model_metrics', {}).get('r2', 0)
            }
        
        # Churn insights
        churn_predictions = await self.get_churn_predictions(db, agency_id, limit=1000)
        if 'at_risk_users' in churn_predictions:
            insights['churn'] = {
                'high_risk_users': len(churn_predictions['at_risk_users']),
                'risk_distribution': churn_predictions['risk_distribution'],
                'potential_revenue_loss': sum([u['potential_revenue_loss'] for u in churn_predictions['at_risk_users']])
            }
        
        # Model status
        insights['model_status'] = self.model_status
        
        return insights
    
    def get_feature_importance(self, model_name: str) -> Optional[Dict[str, float]]:
        """Get feature importance for a specific model"""
        if model_name in self.models and self.models[model_name].is_trained:
            return self.models[model_name].get_feature_importance()
        return None


# Singleton instance
ml_service = MLService()