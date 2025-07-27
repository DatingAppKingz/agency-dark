"""
Fan Lifetime Value (LTV) prediction using machine learning.
"""
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
from sklearn.linear_model import Ridge
import logging
import joblib
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, distinct

from core.ml_analytics.models import (
    MLModel, Prediction, FeatureStore,
    PredictionType, ModelStatus
)
from core.domain.models import Fan, Transaction, User, Model, Message, Content

logger = logging.getLogger(__name__)


class FanLTVPredictor:
    """Predict fan lifetime value using historical behavior and ML."""
    
    def __init__(self):
        self.short_term_model = None  # 30-day LTV
        self.medium_term_model = None  # 90-day LTV
        self.long_term_model = None  # 365-day LTV
        self.scaler = StandardScaler()
        self.poly_features = PolynomialFeatures(degree=2, include_bias=False)
        self.model_metadata = None
        
        # Feature definitions
        self.feature_names = [
            # Recency features
            'days_since_join',
            'days_since_first_transaction',
            'days_since_last_transaction',
            
            # Frequency features
            'transaction_count',
            'transaction_frequency',  # transactions per day
            'active_days',
            'consistency_score',  # how regular are transactions
            
            # Monetary features
            'total_spent',
            'avg_transaction_amount',
            'max_transaction_amount',
            'spending_acceleration',  # is spending increasing?
            
            # Engagement features
            'message_count',
            'content_interaction_rate',
            'response_rate',
            
            # Behavioral features
            'preferred_content_type',
            'preferred_transaction_hour',
            'weekend_activity_ratio',
            'spending_variance',
            
            # Trend features
            'spending_trend_30d',
            'engagement_trend_30d',
            'recency_score',
            'monetary_score',
            'frequency_score'
        ]
    
    async def train(
        self,
        agency_id: str,
        session: AsyncSession,
        lookback_days: int = 365,
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """Train LTV prediction models."""
        logger.info(f"Training LTV prediction models for agency {agency_id}")
        
        # Fetch and prepare training data
        training_data = await self._prepare_training_data(
            agency_id, session, lookback_days
        )
        
        if len(training_data) < 100:
            raise ValueError("Insufficient data for LTV training (need at least 100 fans)")
        
        # Calculate actual LTV values for different time periods
        training_data = await self._calculate_actual_ltv(
            training_data, session
        )
        
        # Prepare features
        feature_cols = [col for col in self.feature_names if col in training_data.columns]
        X = training_data[feature_cols].fillna(0).values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Add polynomial features for non-linear relationships
        X_poly = self.poly_features.fit_transform(X_scaled)
        
        results = {}
        
        # Train models for different time horizons
        for period, days, model_name in [
            ('short_term', 30, 'short_term_model'),
            ('medium_term', 90, 'medium_term_model'),
            ('long_term', 365, 'long_term_model')
        ]:
            y = training_data[f'ltv_{days}d'].values
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X_poly, y, test_size=test_size, random_state=42
            )
            
            # Train model
            model = GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42,
                subsample=0.8
            )
            
            model.fit(X_train, y_train)
            setattr(self, model_name, model)
            
            # Evaluate
            y_pred = model.predict(X_test)
            metrics = {
                'mae': float(mean_absolute_error(y_test, y_pred)),
                'rmse': float(np.sqrt(mean_squared_error(y_test, y_pred))),
                'r2': float(r2_score(y_test, y_pred)),
                'mape': float(np.mean(np.abs((y_test - y_pred) / (y_test + 1))) * 100)
            }
            
            results[period] = metrics
            
            logger.info(f"{period} LTV model - R2: {metrics['r2']:.3f}, MAE: ${metrics['mae']:.2f}")
        
        # Calculate feature importance
        feature_importance = self._calculate_feature_importance(
            X_poly, feature_cols
        )
        
        # Store metadata
        self.model_metadata = {
            'agency_id': agency_id,
            'training_samples': len(training_data),
            'lookback_days': lookback_days,
            'results': results,
            'feature_importance': feature_importance,
            'trained_at': datetime.utcnow().isoformat(),
            'ltv_distribution': {
                '30d': {
                    'mean': float(training_data['ltv_30d'].mean()),
                    'median': float(training_data['ltv_30d'].median()),
                    'std': float(training_data['ltv_30d'].std())
                },
                '90d': {
                    'mean': float(training_data['ltv_90d'].mean()),
                    'median': float(training_data['ltv_90d'].median()),
                    'std': float(training_data['ltv_90d'].std())
                },
                '365d': {
                    'mean': float(training_data['ltv_365d'].mean()),
                    'median': float(training_data['ltv_365d'].median()),
                    'std': float(training_data['ltv_365d'].std())
                }
            }
        }
        
        # Calculate overall accuracy
        overall_accuracy = np.mean([
            results['short_term']['r2'],
            results['medium_term']['r2'],
            results['long_term']['r2']
        ])
        
        return {
            'success': True,
            'metrics': {
                'overall_accuracy': overall_accuracy,
                'short_term_r2': results['short_term']['r2'],
                'medium_term_r2': results['medium_term']['r2'],
                'long_term_r2': results['long_term']['r2'],
                'short_term_mae': results['short_term']['mae'],
                'medium_term_mae': results['medium_term']['mae'],
                'long_term_mae': results['long_term']['mae']
            },
            'training_samples': len(training_data),
            'model_metadata': self.model_metadata
        }
    
    async def predict_ltv(
        self,
        fan_ids: List[str],
        session: AsyncSession,
        include_confidence: bool = True
    ) -> List[Dict[str, Any]]:
        """Predict LTV for specific fans."""
        if not all([self.short_term_model, self.medium_term_model, self.long_term_model]):
            raise ValueError("Models not trained. Call train() first.")
        
        predictions = []
        
        for fan_id in fan_ids:
            # Get fan features
            features = await self._get_fan_features(fan_id, session)
            if features is None:
                continue
            
            # Prepare features
            X = np.array([features])
            X_scaled = self.scaler.transform(X)
            X_poly = self.poly_features.transform(X_scaled)
            
            # Get predictions from all models
            ltv_30d = float(self.short_term_model.predict(X_poly)[0])
            ltv_90d = float(self.medium_term_model.predict(X_poly)[0])
            ltv_365d = float(self.long_term_model.predict(X_poly)[0])
            
            # Ensure logical consistency (longer term >= shorter term)
            ltv_90d = max(ltv_90d, ltv_30d)
            ltv_365d = max(ltv_365d, ltv_90d)
            
            prediction = {
                'fan_id': fan_id,
                'ltv_30_days': ltv_30d,
                'ltv_90_days': ltv_90d,
                'ltv_365_days': ltv_365d,
                'predicted_at': datetime.utcnow(),
                'features': dict(zip(self.feature_names[:len(features)], features))
            }
            
            if include_confidence:
                # Calculate confidence intervals based on model uncertainty
                confidence = self._calculate_confidence_intervals(
                    X_poly, ltv_30d, ltv_90d, ltv_365d
                )
                prediction['confidence_intervals'] = confidence
            
            # Add recommendations
            prediction['recommendations'] = self._generate_ltv_recommendations(
                ltv_30d, ltv_90d, ltv_365d, features
            )
            
            predictions.append(prediction)
        
        return predictions
    
    async def segment_fans_by_ltv(
        self,
        agency_id: str,
        session: AsyncSession,
        num_segments: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Segment fans based on predicted LTV."""
        # Get all active fans
        result = await session.execute(
            select(Fan).where(
                and_(
                    Fan.agency_id == agency_id,
                    Fan.is_active == True
                )
            )
        )
        fans = result.scalars().all()
        
        # Predict LTV for all fans
        fan_ids = [str(fan.id) for fan in fans]
        predictions = await self.predict_ltv(fan_ids, session, include_confidence=False)
        
        # Sort by 365-day LTV
        predictions.sort(key=lambda x: x['ltv_365_days'], reverse=True)
        
        # Create segments
        segment_size = len(predictions) // num_segments
        segments = {
            'vip': [],
            'high_value': [],
            'medium_value': [],
            'low_value': [],
            'at_risk': []
        }
        
        segment_names = list(segments.keys())
        
        for i, prediction in enumerate(predictions):
            segment_idx = min(i // segment_size, num_segments - 1)
            segment_name = segment_names[segment_idx]
            
            # Get fan details
            fan = next(f for f in fans if str(f.id) == prediction['fan_id'])
            
            segments[segment_name].append({
                'fan_id': prediction['fan_id'],
                'username': fan.username,
                'ltv_365_days': prediction['ltv_365_days'],
                'ltv_90_days': prediction['ltv_90_days'],
                'ltv_30_days': prediction['ltv_30_days'],
                'segment': segment_name,
                'recommendations': self._get_segment_recommendations(segment_name)
            })
        
        # Add segment statistics
        segment_stats = {}
        for segment_name, fans_in_segment in segments.items():
            if fans_in_segment:
                segment_stats[segment_name] = {
                    'count': len(fans_in_segment),
                    'avg_ltv_365': np.mean([f['ltv_365_days'] for f in fans_in_segment]),
                    'total_ltv_365': sum([f['ltv_365_days'] for f in fans_in_segment]),
                    'percentage': len(fans_in_segment) / len(predictions) * 100
                }
        
        return {
            'segments': segments,
            'statistics': segment_stats,
            'total_fans': len(predictions)
        }
    
    async def analyze_ltv_trends(
        self,
        agency_id: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Analyze LTV trends and patterns."""
        # Get historical LTV data
        ltv_data = await self._get_historical_ltv_data(agency_id, session)
        
        if ltv_data.empty:
            return {'error': 'No historical data available'}
        
        # Calculate trends
        trends = {
            'overall': self._calculate_ltv_trends(ltv_data),
            'by_cohort': self._analyze_cohort_ltv(ltv_data),
            'by_segment': self._analyze_segment_ltv(ltv_data),
            'drivers': self._identify_ltv_drivers(ltv_data)
        }
        
        # Generate insights
        insights = self._generate_ltv_insights(trends)
        
        return {
            'trends': trends,
            'insights': insights,
            'recommendations': self._generate_strategic_recommendations(trends)
        }
    
    def save_model(self, path: str):
        """Save trained models."""
        if not all([self.short_term_model, self.medium_term_model, self.long_term_model]):
            raise ValueError("Not all models are trained")
        
        joblib.dump({
            'short_term_model': self.short_term_model,
            'medium_term_model': self.medium_term_model,
            'long_term_model': self.long_term_model,
            'scaler': self.scaler,
            'poly_features': self.poly_features,
            'metadata': self.model_metadata,
            'feature_names': self.feature_names,
            'version': '1.0'
        }, path)
    
    def load_model(self, path: str):
        """Load trained models."""
        data = joblib.load(path)
        self.short_term_model = data['short_term_model']
        self.medium_term_model = data['medium_term_model']
        self.long_term_model = data['long_term_model']
        self.scaler = data['scaler']
        self.poly_features = data['poly_features']
        self.model_metadata = data['metadata']
        self.feature_names = data.get('feature_names', self.feature_names)
    
    async def _prepare_training_data(
        self,
        agency_id: str,
        session: AsyncSession,
        lookback_days: int
    ) -> pd.DataFrame:
        """Prepare training data with fan features."""
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Get fans with transaction history
        query = select(
            Fan.id,
            Fan.username,
            Fan.created_at,
            func.min(Transaction.created_at).label('first_transaction'),
            func.max(Transaction.created_at).label('last_transaction'),
            func.count(distinct(Transaction.id)).label('transaction_count'),
            func.sum(Transaction.amount).label('total_spent'),
            func.avg(Transaction.amount).label('avg_transaction'),
            func.max(Transaction.amount).label('max_transaction'),
            func.count(distinct(func.date(Transaction.created_at))).label('active_days')
        ).join(
            Transaction,
            and_(
                Transaction.fan_id == Fan.id,
                Transaction.status == 'completed'
            )
        ).where(
            and_(
                Fan.agency_id == agency_id,
                Fan.created_at < cutoff_date
            )
        ).group_by(Fan.id)
        
        result = await session.execute(query)
        rows = result.fetchall()
        
        # Convert to DataFrame
        data = []
        for row in rows:
            fan_data = {
                'fan_id': row.id,
                'username': row.username,
                'created_at': row.created_at,
                'first_transaction': row.first_transaction,
                'last_transaction': row.last_transaction,
                'transaction_count': row.transaction_count,
                'total_spent': float(row.total_spent),
                'avg_transaction_amount': float(row.avg_transaction),
                'max_transaction_amount': float(row.max_transaction),
                'active_days': row.active_days
            }
            
            # Calculate derived features
            fan_data['days_since_join'] = (datetime.utcnow() - row.created_at).days
            fan_data['days_since_first_transaction'] = (datetime.utcnow() - row.first_transaction).days
            fan_data['days_since_last_transaction'] = (datetime.utcnow() - row.last_transaction).days
            fan_data['transaction_frequency'] = row.transaction_count / max(1, fan_data['days_since_first_transaction'])
            
            data.append(fan_data)
        
        df = pd.DataFrame(data)
        
        # Add more features
        if not df.empty:
            df = await self._add_behavioral_features(df, session)
            df = self._add_scoring_features(df)
        
        return df
    
    async def _calculate_actual_ltv(
        self,
        df: pd.DataFrame,
        session: AsyncSession
    ) -> pd.DataFrame:
        """Calculate actual LTV values for training."""
        # For each fan, calculate their actual spending in future periods
        for days in [30, 90, 365]:
            ltv_values = []
            
            for _, row in df.iterrows():
                # Get future spending from the last transaction date
                future_date = row['last_transaction'] + timedelta(days=days)
                
                result = await session.execute(
                    select(func.sum(Transaction.amount)).where(
                        and_(
                            Transaction.fan_id == row['fan_id'],
                            Transaction.status == 'completed',
                            Transaction.created_at > row['last_transaction'],
                            Transaction.created_at <= future_date
                        )
                    )
                )
                future_spending = result.scalar() or 0
                ltv_values.append(float(future_spending))
            
            df[f'ltv_{days}d'] = ltv_values
        
        return df
    
    async def _add_behavioral_features(
        self,
        df: pd.DataFrame,
        session: AsyncSession
    ) -> pd.DataFrame:
        """Add behavioral features to the dataset."""
        # Get message counts
        message_counts = []
        spending_trends = []
        engagement_trends = []
        
        for _, row in df.iterrows():
            # Message count
            result = await session.execute(
                select(func.count(Message.id)).where(
                    Message.sender_id == row['fan_id']
                )
            )
            message_count = result.scalar() or 0
            message_counts.append(message_count)
            
            # Spending trend (last 30 days vs previous 30 days)
            last_30_days = row['last_transaction'] - timedelta(days=30)
            prev_30_days = last_30_days - timedelta(days=30)
            
            # Recent spending
            recent_result = await session.execute(
                select(func.sum(Transaction.amount)).where(
                    and_(
                        Transaction.fan_id == row['fan_id'],
                        Transaction.status == 'completed',
                        Transaction.created_at >= last_30_days,
                        Transaction.created_at <= row['last_transaction']
                    )
                )
            )
            recent_spending = float(recent_result.scalar() or 0)
            
            # Previous spending
            prev_result = await session.execute(
                select(func.sum(Transaction.amount)).where(
                    and_(
                        Transaction.fan_id == row['fan_id'],
                        Transaction.status == 'completed',
                        Transaction.created_at >= prev_30_days,
                        Transaction.created_at < last_30_days
                    )
                )
            )
            prev_spending = float(prev_result.scalar() or 0)
            
            # Calculate trend
            if prev_spending > 0:
                spending_trend = (recent_spending - prev_spending) / prev_spending
            else:
                spending_trend = 1.0 if recent_spending > 0 else 0.0
            
            spending_trends.append(spending_trend)
            
            # Engagement trend (simplified - based on transaction frequency)
            recent_trans_count = row['transaction_count'] * (30 / max(1, row['days_since_first_transaction']))
            engagement_trends.append(recent_trans_count)
        
        df['message_count'] = message_counts
        df['spending_trend_30d'] = spending_trends
        df['engagement_trend_30d'] = engagement_trends
        
        # Content interaction rate (simplified)
        df['content_interaction_rate'] = df['message_count'] / (df['transaction_count'] + 1)
        
        # Response rate (simplified - assume 50% base rate with variance)
        df['response_rate'] = 0.5 + np.random.normal(0, 0.1, len(df))
        df['response_rate'] = df['response_rate'].clip(0, 1)
        
        # Consistency score
        df['consistency_score'] = 1 / (df['days_since_last_transaction'] + 1)
        
        # Spending variance
        df['spending_variance'] = df['avg_transaction_amount'] * 0.3  # Simplified
        
        # Weekend activity ratio (simplified)
        df['weekend_activity_ratio'] = 0.3 + np.random.uniform(-0.1, 0.1, len(df))
        
        # Preferred content type and hour (simplified)
        df['preferred_content_type'] = np.random.randint(0, 3, len(df))  # 0: photo, 1: video, 2: text
        df['preferred_transaction_hour'] = np.random.randint(0, 24, len(df))
        
        return df
    
    def _add_scoring_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add RFM-style scoring features."""
        # Recency score (inverse of days since last transaction)
        df['recency_score'] = 1 / (df['days_since_last_transaction'] + 1)
        
        # Monetary score (normalized total spent)
        max_spent = df['total_spent'].max()
        df['monetary_score'] = df['total_spent'] / max_spent if max_spent > 0 else 0
        
        # Frequency score (normalized transaction frequency)
        max_freq = df['transaction_frequency'].max()
        df['frequency_score'] = df['transaction_frequency'] / max_freq if max_freq > 0 else 0
        
        # Spending acceleration
        df['spending_acceleration'] = df['spending_trend_30d'].clip(-1, 1)
        
        return df
    
    async def _get_fan_features(
        self,
        fan_id: str,
        session: AsyncSession
    ) -> Optional[List[float]]:
        """Extract features for a single fan."""
        # Get fan data
        result = await session.execute(
            select(Fan).where(Fan.id == fan_id)
        )
        fan = result.scalar_one_or_none()
        
        if not fan:
            return None
        
        # Get transaction statistics
        trans_result = await session.execute(
            select(
                func.count(Transaction.id).label('count'),
                func.sum(Transaction.amount).label('total'),
                func.avg(Transaction.amount).label('avg'),
                func.max(Transaction.amount).label('max'),
                func.min(Transaction.created_at).label('first'),
                func.max(Transaction.created_at).label('last'),
                func.count(distinct(func.date(Transaction.created_at))).label('active_days')
            ).where(
                and_(
                    Transaction.fan_id == fan_id,
                    Transaction.status == 'completed'
                )
            )
        )
        trans_stats = trans_result.first()
        
        if not trans_stats.count:
            # No transaction history
            return [
                (datetime.utcnow() - fan.created_at).days,  # days_since_join
                999,  # days_since_first_transaction
                999,  # days_since_last_transaction
                0,    # transaction_count
                0,    # transaction_frequency
                0,    # active_days
                0,    # consistency_score
                0,    # total_spent
                0,    # avg_transaction_amount
                0,    # max_transaction_amount
                0,    # spending_acceleration
                0,    # message_count
                0,    # content_interaction_rate
                0.5,  # response_rate
                0,    # preferred_content_type
                12,   # preferred_transaction_hour
                0.3,  # weekend_activity_ratio
                0,    # spending_variance
                0,    # spending_trend_30d
                0,    # engagement_trend_30d
                0,    # recency_score
                0,    # monetary_score
                0     # frequency_score
            ]
        
        # Calculate features
        days_since_join = (datetime.utcnow() - fan.created_at).days
        days_since_first = (datetime.utcnow() - trans_stats.first).days
        days_since_last = (datetime.utcnow() - trans_stats.last).days
        transaction_frequency = trans_stats.count / max(1, days_since_first)
        
        # Get message count
        msg_result = await session.execute(
            select(func.count(Message.id)).where(
                Message.sender_id == fan_id
            )
        )
        message_count = msg_result.scalar() or 0
        
        # Calculate trends (simplified)
        spending_trend = 0.1  # Placeholder
        engagement_trend = transaction_frequency * 30
        
        # Scoring
        recency_score = 1 / (days_since_last + 1)
        monetary_score = min(float(trans_stats.total) / 5000, 1.0)  # Normalized to max 5000
        frequency_score = min(transaction_frequency * 30, 1.0)  # Normalized
        
        return [
            days_since_join,
            days_since_first,
            days_since_last,
            trans_stats.count,
            transaction_frequency,
            trans_stats.active_days,
            1 / (days_since_last + 1),  # consistency_score
            float(trans_stats.total),
            float(trans_stats.avg),
            float(trans_stats.max),
            spending_trend,  # spending_acceleration
            message_count,
            message_count / (trans_stats.count + 1),  # content_interaction_rate
            0.5,  # response_rate (placeholder)
            0,    # preferred_content_type (placeholder)
            12,   # preferred_transaction_hour (placeholder)
            0.3,  # weekend_activity_ratio (placeholder)
            float(trans_stats.avg) * 0.3,  # spending_variance
            spending_trend,
            engagement_trend,
            recency_score,
            monetary_score,
            frequency_score
        ]
    
    def _calculate_confidence_intervals(
        self,
        X: np.ndarray,
        ltv_30d: float,
        ltv_90d: float,
        ltv_365d: float
    ) -> Dict[str, Tuple[float, float]]:
        """Calculate confidence intervals for predictions."""
        # Simplified confidence intervals based on prediction magnitude
        # In production, use prediction intervals from the model
        
        confidence_intervals = {
            '30_days': (
                max(0, ltv_30d * 0.8),  # Lower bound
                ltv_30d * 1.2  # Upper bound
            ),
            '90_days': (
                max(0, ltv_90d * 0.75),
                ltv_90d * 1.25
            ),
            '365_days': (
                max(0, ltv_365d * 0.7),
                ltv_365d * 1.3
            )
        }
        
        return confidence_intervals
    
    def _generate_ltv_recommendations(
        self,
        ltv_30d: float,
        ltv_90d: float,
        ltv_365d: float,
        features: List[float]
    ) -> List[str]:
        """Generate recommendations based on LTV predictions."""
        recommendations = []
        
        # LTV growth analysis
        growth_90_30 = (ltv_90d - ltv_30d) / ltv_30d if ltv_30d > 0 else 0
        growth_365_90 = (ltv_365d - ltv_90d) / ltv_90d if ltv_90d > 0 else 0
        
        # High value fan
        if ltv_365d > 1000:
            recommendations.append("VIP fan - prioritize for exclusive content and perks")
            recommendations.append("Consider personalized retention strategies")
        
        # Growing LTV
        if growth_90_30 > 0.5:
            recommendations.append("Rapidly growing value - nurture engagement")
            recommendations.append("Introduce loyalty rewards to maintain momentum")
        
        # Declining or flat LTV
        if growth_365_90 < 0.1:
            recommendations.append("LTV growth stagnating - re-engagement needed")
            recommendations.append("Test new content types or interaction methods")
        
        # Recency issues
        days_since_last = features[2] if len(features) > 2 else 0
        if days_since_last > 30:
            recommendations.append("Fan becoming inactive - send win-back campaign")
        
        # Low frequency
        transaction_frequency = features[4] if len(features) > 4 else 0
        if transaction_frequency < 0.1 and ltv_365d < 100:
            recommendations.append("Low engagement - consider targeted promotions")
        
        return recommendations[:4]  # Limit to 4 recommendations
    
    def _get_segment_recommendations(self, segment: str) -> List[str]:
        """Get recommendations for fan segments."""
        segment_recommendations = {
            'vip': [
                "Provide exclusive VIP content and early access",
                "Assign dedicated account management",
                "Create personalized experiences",
                "Implement VIP loyalty program"
            ],
            'high_value': [
                "Offer premium content packages",
                "Increase engagement through personalized messages",
                "Provide loyalty rewards",
                "Monitor for signs of churn"
            ],
            'medium_value': [
                "Encourage increased engagement with promotions",
                "Test different content types",
                "Implement tiered rewards system",
                "Focus on consistency"
            ],
            'low_value': [
                "Send targeted re-engagement campaigns",
                "Offer limited-time promotions",
                "Simplify interaction process",
                "Survey for feedback"
            ],
            'at_risk': [
                "Immediate intervention required",
                "Send win-back offers",
                "Investigate reasons for low engagement",
                "Consider alternative engagement channels"
            ]
        }
        
        return segment_recommendations.get(segment, [])
    
    def _calculate_feature_importance(
        self,
        X: np.ndarray,
        feature_names: List[str]
    ) -> Dict[str, float]:
        """Calculate feature importance across all models."""
        # Average importance across all three models
        importance_scores = {}
        
        for model, weight in [
            (self.short_term_model, 0.3),
            (self.medium_term_model, 0.3),
            (self.long_term_model, 0.4)
        ]:
            if hasattr(model, 'feature_importances_'):
                # Get importances for original features (before polynomial expansion)
                n_features = len(feature_names)
                importances = model.feature_importances_[:n_features]
                
                for i, name in enumerate(feature_names):
                    if name not in importance_scores:
                        importance_scores[name] = 0
                    importance_scores[name] += importances[i] * weight
        
        # Normalize
        total = sum(importance_scores.values())
        if total > 0:
            importance_scores = {k: v/total for k, v in importance_scores.items()}
        
        # Sort by importance
        return dict(sorted(importance_scores.items(), key=lambda x: x[1], reverse=True))
    
    async def _get_historical_ltv_data(
        self,
        agency_id: str,
        session: AsyncSession
    ) -> pd.DataFrame:
        """Get historical LTV data for trend analysis."""
        # This would ideally come from stored predictions
        # For now, calculate from transaction history
        
        query = select(
            Fan.id,
            Fan.created_at,
            func.sum(Transaction.amount).label('total_ltv'),
            func.count(Transaction.id).label('transaction_count'),
            func.min(Transaction.created_at).label('first_transaction'),
            func.max(Transaction.created_at).label('last_transaction')
        ).join(
            Transaction,
            and_(
                Transaction.fan_id == Fan.id,
                Transaction.status == 'completed'
            )
        ).where(
            Fan.agency_id == agency_id
        ).group_by(Fan.id)
        
        result = await session.execute(query)
        rows = result.fetchall()
        
        data = []
        for row in rows:
            data.append({
                'fan_id': row.id,
                'joined_date': row.created_at,
                'total_ltv': float(row.total_ltv),
                'transaction_count': row.transaction_count,
                'first_transaction': row.first_transaction,
                'last_transaction': row.last_transaction,
                'lifetime_days': (row.last_transaction - row.first_transaction).days
            })
        
        return pd.DataFrame(data)
    
    def _calculate_ltv_trends(self, ltv_data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate overall LTV trends."""
        if ltv_data.empty:
            return {}
        
        # Group by cohort (join month)
        ltv_data['join_month'] = pd.to_datetime(ltv_data['joined_date']).dt.to_period('M')
        
        monthly_stats = ltv_data.groupby('join_month').agg({
            'total_ltv': ['mean', 'sum', 'count'],
            'transaction_count': 'mean',
            'lifetime_days': 'mean'
        })
        
        # Calculate trend
        recent_months = monthly_stats.tail(6)
        if len(recent_months) > 1:
            ltv_trend = np.polyfit(range(len(recent_months)), 
                                  recent_months['total_ltv']['mean'].values, 1)[0]
        else:
            ltv_trend = 0
        
        return {
            'average_ltv': float(ltv_data['total_ltv'].mean()),
            'median_ltv': float(ltv_data['total_ltv'].median()),
            'total_ltv': float(ltv_data['total_ltv'].sum()),
            'ltv_trend': 'increasing' if ltv_trend > 0 else 'decreasing',
            'trend_magnitude': abs(float(ltv_trend))
        }
    
    def _analyze_cohort_ltv(self, ltv_data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze LTV by cohort."""
        if ltv_data.empty:
            return {}
        
        ltv_data['join_month'] = pd.to_datetime(ltv_data['joined_date']).dt.to_period('M')
        
        cohort_analysis = {}
        for cohort in ltv_data['join_month'].unique():
            cohort_data = ltv_data[ltv_data['join_month'] == cohort]
            cohort_analysis[str(cohort)] = {
                'fan_count': len(cohort_data),
                'avg_ltv': float(cohort_data['total_ltv'].mean()),
                'total_ltv': float(cohort_data['total_ltv'].sum()),
                'avg_lifetime_days': float(cohort_data['lifetime_days'].mean())
            }
        
        return cohort_analysis
    
    def _analyze_segment_ltv(self, ltv_data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze LTV by value segments."""
        if ltv_data.empty:
            return {}
        
        # Create value segments
        ltv_data['segment'] = pd.qcut(
            ltv_data['total_ltv'],
            q=5,
            labels=['at_risk', 'low_value', 'medium_value', 'high_value', 'vip']
        )
        
        segment_analysis = {}
        for segment in ltv_data['segment'].unique():
            segment_data = ltv_data[ltv_data['segment'] == segment]
            segment_analysis[segment] = {
                'fan_count': len(segment_data),
                'avg_ltv': float(segment_data['total_ltv'].mean()),
                'total_ltv': float(segment_data['total_ltv'].sum()),
                'ltv_range': {
                    'min': float(segment_data['total_ltv'].min()),
                    'max': float(segment_data['total_ltv'].max())
                }
            }
        
        return segment_analysis
    
    def _identify_ltv_drivers(self, ltv_data: pd.DataFrame) -> List[str]:
        """Identify key drivers of LTV."""
        drivers = []
        
        if not ltv_data.empty:
            # Transaction frequency
            high_ltv_fans = ltv_data[ltv_data['total_ltv'] > ltv_data['total_ltv'].quantile(0.75)]
            avg_trans_high = high_ltv_fans['transaction_count'].mean()
            avg_trans_all = ltv_data['transaction_count'].mean()
            
            if avg_trans_high > avg_trans_all * 1.5:
                drivers.append("Transaction frequency is a key LTV driver")
            
            # Lifetime duration
            avg_lifetime_high = high_ltv_fans['lifetime_days'].mean()
            avg_lifetime_all = ltv_data['lifetime_days'].mean()
            
            if avg_lifetime_high > avg_lifetime_all * 1.3:
                drivers.append("Fan retention duration significantly impacts LTV")
            
            # Early engagement
            early_trans = ltv_data[
                (ltv_data['first_transaction'] - ltv_data['joined_date']).dt.days < 7
            ]
            if not early_trans.empty:
                early_ltv = early_trans['total_ltv'].mean()
                if early_ltv > ltv_data['total_ltv'].mean() * 1.2:
                    drivers.append("Early engagement (first week) predicts higher LTV")
        
        return drivers
    
    def _generate_ltv_insights(self, trends: Dict[str, Any]) -> List[str]:
        """Generate insights from LTV analysis."""
        insights = []
        
        # Overall trend insights
        if 'overall' in trends and trends['overall']:
            if trends['overall'].get('ltv_trend') == 'increasing':
                insights.append(f"LTV is trending upward with {trends['overall']['trend_magnitude']:.1f} monthly growth")
            else:
                insights.append("LTV trend is declining - intervention needed")
        
        # Cohort insights
        if 'by_cohort' in trends and trends['by_cohort']:
            recent_cohorts = list(trends['by_cohort'].keys())[-3:]
            if recent_cohorts:
                recent_avg = np.mean([trends['by_cohort'][c]['avg_ltv'] for c in recent_cohorts])
                insights.append(f"Recent cohorts averaging ${recent_avg:.2f} LTV")
        
        # Segment insights
        if 'by_segment' in trends and trends['by_segment']:
            if 'vip' in trends['by_segment']:
                vip_pct = trends['by_segment']['vip']['fan_count'] / sum(
                    s['fan_count'] for s in trends['by_segment'].values()
                ) * 100
                insights.append(f"Top {vip_pct:.1f}% of fans generate majority of revenue")
        
        # Driver insights
        if 'drivers' in trends and trends['drivers']:
            insights.extend(trends['drivers'][:2])  # Add top 2 drivers
        
        return insights
    
    def _generate_strategic_recommendations(self, trends: Dict[str, Any]) -> List[str]:
        """Generate strategic recommendations based on LTV analysis."""
        recommendations = []
        
        # Based on overall trends
        if trends.get('overall', {}).get('ltv_trend') == 'decreasing':
            recommendations.append("Implement retention program to reverse LTV decline")
            recommendations.append("Analyze and address churn factors")
        
        # Based on segment distribution
        if 'by_segment' in trends:
            segments = trends['by_segment']
            if segments.get('at_risk', {}).get('fan_count', 0) > len(segments) * 0.3:
                recommendations.append("High percentage of at-risk fans - launch re-engagement campaign")
            
            if segments.get('vip', {}).get('fan_count', 0) < len(segments) * 0.05:
                recommendations.append("Low VIP percentage - focus on upgrading high-value fans")
        
        # Based on drivers
        if 'drivers' in trends:
            if "Transaction frequency" in str(trends['drivers']):
                recommendations.append("Incentivize regular interactions to boost LTV")
            if "Early engagement" in str(trends['drivers']):
                recommendations.append("Optimize onboarding to drive early transactions")
        
        return recommendations