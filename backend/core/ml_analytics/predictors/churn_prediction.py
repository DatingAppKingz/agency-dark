"""
Churn prediction using machine learning classification.
"""
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.utils.class_weight import compute_class_weight
import logging
import joblib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from core.ml_analytics.models import (
    MLModel, Prediction, FeatureStore,
    PredictionType, ModelStatus
)
from core.domain.models import Fan, Transaction, User

logger = logging.getLogger(__name__)


class ChurnPredictor:
    """Predict fan churn using Random Forest classification."""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.model_metadata = None
        self.feature_names = [
            'days_since_last_transaction',
            'total_spent',
            'transaction_count',
            'avg_transaction_amount',
            'days_active',
            'transaction_frequency',
            'recency_score',
            'monetary_score',
            'engagement_trend',
            'spending_trend',
            'days_since_join',
            'lifetime_value_percentile'
        ]
        self.threshold = 0.5  # Classification threshold
    
    async def train(
        self,
        agency_id: str,
        session: AsyncSession,
        lookback_days: int = 180,
        churn_days: int = 30,
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """Train churn prediction model."""
        logger.info(f"Training churn prediction model for agency {agency_id}")
        
        # Fetch and prepare training data
        X, y, fan_ids = await self._prepare_training_data(
            agency_id, session, lookback_days, churn_days
        )
        
        if len(X) < 100:
            raise ValueError("Insufficient data for training (need at least 100 fans)")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Handle class imbalance
        class_weights = compute_class_weight(
            'balanced',
            classes=np.unique(y_train),
            y=y_train
        )
        class_weight_dict = {i: w for i, w in enumerate(class_weights)}
        
        # Train model
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=20,
            min_samples_leaf=10,
            class_weight=class_weight_dict,
            random_state=42,
            n_jobs=-1
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate model
        metrics = self._evaluate_model(
            X_train_scaled, y_train,
            X_test_scaled, y_test
        )
        
        # Feature importance
        feature_importance = dict(zip(
            self.feature_names,
            self.model.feature_importances_
        ))
        
        # Store metadata
        self.model_metadata = {
            'agency_id': agency_id,
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'churn_rate': float(y.mean()),
            'feature_importance': feature_importance,
            'metrics': metrics,
            'churn_days': churn_days,
            'lookback_days': lookback_days,
            'trained_at': datetime.utcnow().isoformat()
        }
        
        return {
            'success': True,
            'metrics': metrics,
            'training_samples': len(X_train),
            'churn_rate': float(y.mean()),
            'feature_importance': feature_importance,
            'model_metadata': self.model_metadata
        }
    
    async def predict(
        self,
        fan_ids: List[str],
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Predict churn probability for specific fans."""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        predictions = []
        
        for fan_id in fan_ids:
            # Get fan features
            features = await self._get_fan_features(fan_id, session)
            if features is None:
                continue
            
            # Scale features
            X = np.array([features])
            X_scaled = self.scaler.transform(X)
            
            # Get prediction probabilities
            proba = self.model.predict_proba(X_scaled)[0]
            churn_probability = proba[1]  # Probability of churn
            
            # Get individual feature contributions
            feature_contributions = self._get_feature_contributions(X[0])
            
            predictions.append({
                'fan_id': fan_id,
                'churn_probability': float(churn_probability),
                'churn_prediction': churn_probability > self.threshold,
                'confidence_score': float(max(proba)),
                'risk_level': self._get_risk_level(churn_probability),
                'feature_contributions': feature_contributions,
                'recommended_actions': self._get_recommendations(churn_probability, feature_contributions)
            })
        
        return predictions
    
    async def predict_all_fans(
        self,
        agency_id: str,
        session: AsyncSession,
        min_probability: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Predict churn for all active fans in agency."""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
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
        
        # Batch predict
        high_risk_fans = []
        
        for fan in fans:
            features = await self._get_fan_features(str(fan.id), session)
            if features is None:
                continue
            
            X = np.array([features])
            X_scaled = self.scaler.transform(X)
            
            proba = self.model.predict_proba(X_scaled)[0]
            churn_probability = proba[1]
            
            if churn_probability >= min_probability:
                feature_contributions = self._get_feature_contributions(X[0])
                
                high_risk_fans.append({
                    'fan_id': str(fan.id),
                    'fan_username': fan.username,
                    'churn_probability': float(churn_probability),
                    'risk_level': self._get_risk_level(churn_probability),
                    'days_since_last_transaction': features[0],
                    'total_spent': features[1],
                    'top_risk_factors': self._get_top_risk_factors(feature_contributions),
                    'recommended_actions': self._get_recommendations(churn_probability, feature_contributions)
                })
        
        # Sort by churn probability
        high_risk_fans.sort(key=lambda x: x['churn_probability'], reverse=True)
        
        return high_risk_fans
    
    async def analyze_churn_patterns(
        self,
        agency_id: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Analyze churn patterns and trends."""
        # Get historical churn data
        churn_data = await self._get_historical_churn_data(agency_id, session)
        
        # Calculate churn metrics
        monthly_churn_rate = self._calculate_monthly_churn_rate(churn_data)
        churn_by_cohort = self._analyze_cohort_churn(churn_data)
        churn_by_value_segment = self._analyze_value_segment_churn(churn_data)
        
        # Get feature importance from model
        feature_importance = None
        if self.model and hasattr(self.model, 'feature_importances_'):
            feature_importance = dict(zip(
                self.feature_names,
                self.model.feature_importances_
            ))
            feature_importance = dict(sorted(
                feature_importance.items(),
                key=lambda x: x[1],
                reverse=True
            ))
        
        return {
            'churn_metrics': {
                'current_monthly_rate': monthly_churn_rate[-1] if monthly_churn_rate else 0,
                'average_monthly_rate': np.mean(monthly_churn_rate) if monthly_churn_rate else 0,
                'churn_trend': 'increasing' if len(monthly_churn_rate) > 1 and monthly_churn_rate[-1] > monthly_churn_rate[-2] else 'decreasing'
            },
            'cohort_analysis': churn_by_cohort,
            'value_segment_analysis': churn_by_value_segment,
            'top_churn_indicators': feature_importance,
            'insights': self._generate_churn_insights(
                monthly_churn_rate,
                churn_by_cohort,
                churn_by_value_segment,
                feature_importance
            )
        }
    
    def save_model(self, path: str):
        """Save trained model and scaler."""
        if self.model is None:
            raise ValueError("No model to save")
        
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'metadata': self.model_metadata,
            'feature_names': self.feature_names,
            'threshold': self.threshold,
            'version': '1.0'
        }, path)
    
    def load_model(self, path: str):
        """Load trained model and scaler."""
        data = joblib.load(path)
        self.model = data['model']
        self.scaler = data['scaler']
        self.model_metadata = data['metadata']
        self.feature_names = data.get('feature_names', self.feature_names)
        self.threshold = data.get('threshold', 0.5)
    
    async def _prepare_training_data(
        self,
        agency_id: str,
        session: AsyncSession,
        lookback_days: int,
        churn_days: int
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Prepare training data with features and labels."""
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        churn_threshold = datetime.utcnow() - timedelta(days=churn_days)
        
        # Get all fans with transaction history
        query = select(Fan).where(
            and_(
                Fan.agency_id == agency_id,
                Fan.created_at < cutoff_date
            )
        )
        
        result = await session.execute(query)
        fans = result.scalars().all()
        
        X = []
        y = []
        fan_ids = []
        
        for fan in fans:
            # Get fan features
            features = await self._get_fan_features_for_date(
                str(fan.id),
                session,
                cutoff_date
            )
            
            if features is None:
                continue
            
            # Determine if fan churned
            last_transaction_query = select(func.max(Transaction.created_at)).where(
                and_(
                    Transaction.fan_id == fan.id,
                    Transaction.status == 'completed'
                )
            )
            last_transaction_result = await session.execute(last_transaction_query)
            last_transaction_date = last_transaction_result.scalar()
            
            if last_transaction_date:
                churned = last_transaction_date < churn_threshold
            else:
                churned = True
            
            X.append(features)
            y.append(1 if churned else 0)
            fan_ids.append(str(fan.id))
        
        return np.array(X), np.array(y), fan_ids
    
    async def _get_fan_features(
        self,
        fan_id: str,
        session: AsyncSession,
        as_of_date: Optional[datetime] = None
    ) -> Optional[List[float]]:
        """Extract features for a single fan."""
        if as_of_date is None:
            as_of_date = datetime.utcnow()
        
        # Get fan
        result = await session.execute(
            select(Fan).where(Fan.id == fan_id)
        )
        fan = result.scalar_one_or_none()
        
        if not fan:
            return None
        
        # Get transaction history
        transaction_query = select(Transaction).where(
            and_(
                Transaction.fan_id == fan_id,
                Transaction.status == 'completed',
                Transaction.created_at <= as_of_date
            )
        ).order_by(Transaction.created_at.desc())
        
        result = await session.execute(transaction_query)
        transactions = result.scalars().all()
        
        if not transactions:
            # No transaction history
            days_since_join = (as_of_date - fan.created_at).days
            return [
                999,  # days_since_last_transaction (never)
                0,    # total_spent
                0,    # transaction_count
                0,    # avg_transaction_amount
                0,    # days_active
                0,    # transaction_frequency
                0,    # recency_score
                0,    # monetary_score
                0,    # engagement_trend
                0,    # spending_trend
                days_since_join,
                0     # lifetime_value_percentile
            ]
        
        # Calculate features
        days_since_last = (as_of_date - transactions[0].created_at).days
        total_spent = sum(t.amount for t in transactions)
        transaction_count = len(transactions)
        avg_transaction = total_spent / transaction_count if transaction_count > 0 else 0
        
        # Days active (first to last transaction)
        first_transaction_date = transactions[-1].created_at
        last_transaction_date = transactions[0].created_at
        days_active = (last_transaction_date - first_transaction_date).days + 1
        
        # Transaction frequency (transactions per 30 days)
        if days_active > 0:
            transaction_frequency = (transaction_count / days_active) * 30
        else:
            transaction_frequency = 0
        
        # Recency score (inverse of days since last transaction)
        recency_score = 1 / (days_since_last + 1)
        
        # Monetary score (percentile rank)
        monetary_score = min(total_spent / 1000, 1.0)  # Normalized to 0-1
        
        # Engagement trend (recent vs older transactions)
        recent_cutoff = as_of_date - timedelta(days=30)
        recent_transactions = [t for t in transactions if t.created_at > recent_cutoff]
        older_transactions = [t for t in transactions if t.created_at <= recent_cutoff]
        
        if older_transactions:
            recent_freq = len(recent_transactions)
            older_freq = len(older_transactions) / (days_active / 30) if days_active > 30 else len(older_transactions)
            engagement_trend = (recent_freq - older_freq) / (older_freq + 1)
        else:
            engagement_trend = 0
        
        # Spending trend
        if older_transactions:
            recent_spending = sum(t.amount for t in recent_transactions)
            older_spending = sum(t.amount for t in older_transactions) / max(1, len(older_transactions))
            recent_avg = recent_spending / max(1, len(recent_transactions))
            spending_trend = (recent_avg - older_spending) / (older_spending + 1)
        else:
            spending_trend = 0
        
        # Days since join
        days_since_join = (as_of_date - fan.created_at).days
        
        # Lifetime value percentile (simplified)
        ltv_percentile = min(total_spent / 5000, 1.0)  # Normalized
        
        return [
            days_since_last,
            total_spent,
            transaction_count,
            avg_transaction,
            days_active,
            transaction_frequency,
            recency_score,
            monetary_score,
            engagement_trend,
            spending_trend,
            days_since_join,
            ltv_percentile
        ]
    
    async def _get_fan_features_for_date(
        self,
        fan_id: str,
        session: AsyncSession,
        as_of_date: datetime
    ) -> Optional[List[float]]:
        """Get fan features as of a specific date."""
        return await self._get_fan_features(fan_id, session, as_of_date)
    
    def _evaluate_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray
    ) -> Dict[str, float]:
        """Evaluate model performance."""
        # Training metrics
        train_pred = self.model.predict(X_train)
        train_proba = self.model.predict_proba(X_train)[:, 1]
        
        # Test metrics
        test_pred = self.model.predict(X_test)
        test_proba = self.model.predict_proba(X_test)[:, 1]
        
        # Cross-validation
        cv_scores = cross_val_score(self.model, X_train, y_train, cv=5, scoring='roc_auc')
        
        return {
            'train_accuracy': float(accuracy_score(y_train, train_pred)),
            'test_accuracy': float(accuracy_score(y_test, test_pred)),
            'precision': float(precision_score(y_test, test_pred, zero_division=0)),
            'recall': float(recall_score(y_test, test_pred, zero_division=0)),
            'f1_score': float(f1_score(y_test, test_pred, zero_division=0)),
            'roc_auc': float(roc_auc_score(y_test, test_proba)),
            'cv_auc_mean': float(cv_scores.mean()),
            'cv_auc_std': float(cv_scores.std())
        }
    
    def _get_risk_level(self, probability: float) -> str:
        """Categorize churn risk level."""
        if probability >= 0.8:
            return 'critical'
        elif probability >= 0.6:
            return 'high'
        elif probability >= 0.4:
            return 'medium'
        elif probability >= 0.2:
            return 'low'
        else:
            return 'minimal'
    
    def _get_feature_contributions(self, features: np.ndarray) -> Dict[str, float]:
        """Get individual feature contributions to prediction."""
        if not hasattr(self.model, 'feature_importances_'):
            return {}
        
        # Simple approximation using feature importance * feature value
        contributions = {}
        for i, (name, importance) in enumerate(zip(self.feature_names, self.model.feature_importances_)):
            # Normalize feature value
            if features[i] != 0:
                contribution = importance * abs(features[i])
                contributions[name] = float(contribution)
        
        # Sort by contribution
        return dict(sorted(contributions.items(), key=lambda x: x[1], reverse=True))
    
    def _get_top_risk_factors(self, contributions: Dict[str, float], n: int = 3) -> List[str]:
        """Get top risk factors from feature contributions."""
        sorted_factors = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
        
        risk_factors = []
        for factor, _ in sorted_factors[:n]:
            if factor == 'days_since_last_transaction':
                risk_factors.append('Long time since last purchase')
            elif factor == 'transaction_frequency':
                risk_factors.append('Declining purchase frequency')
            elif factor == 'engagement_trend':
                risk_factors.append('Decreasing engagement')
            elif factor == 'spending_trend':
                risk_factors.append('Reduced spending')
            elif factor == 'recency_score':
                risk_factors.append('Low recent activity')
            else:
                risk_factors.append(factor.replace('_', ' ').title())
        
        return risk_factors
    
    def _get_recommendations(self, probability: float, contributions: Dict[str, float]) -> List[str]:
        """Generate recommendations based on churn risk."""
        recommendations = []
        
        if probability >= 0.6:
            recommendations.append("Immediate intervention required")
            recommendations.append("Send personalized retention offer")
        
        # Specific recommendations based on risk factors
        top_factors = list(contributions.keys())[:3]
        
        if 'days_since_last_transaction' in top_factors:
            recommendations.append("Send re-engagement campaign")
        
        if 'spending_trend' in top_factors:
            recommendations.append("Offer exclusive discount or promotion")
        
        if 'engagement_trend' in top_factors:
            recommendations.append("Share new, exclusive content")
        
        if 'transaction_frequency' in top_factors:
            recommendations.append("Create urgency with limited-time offers")
        
        if probability < 0.4:
            recommendations.append("Continue regular engagement")
            recommendations.append("Monitor for changes")
        
        return recommendations[:4]  # Limit to 4 recommendations
    
    async def _get_historical_churn_data(
        self,
        agency_id: str,
        session: AsyncSession
    ) -> pd.DataFrame:
        """Get historical churn data for analysis."""
        # This is a simplified version - in production, you'd track actual churn events
        query = select(
            Fan.id,
            Fan.created_at,
            func.max(Transaction.created_at).label('last_transaction_date'),
            func.sum(Transaction.amount).label('total_spent'),
            func.count(Transaction.id).label('transaction_count')
        ).join(
            Transaction,
            and_(
                Transaction.fan_id == Fan.id,
                Transaction.status == 'completed'
            ),
            isouter=True
        ).where(
            Fan.agency_id == agency_id
        ).group_by(Fan.id)
        
        result = await session.execute(query)
        data = result.fetchall()
        
        df = pd.DataFrame([
            {
                'fan_id': row.id,
                'joined_date': row.created_at,
                'last_transaction_date': row.last_transaction_date,
                'total_spent': row.total_spent or 0,
                'transaction_count': row.transaction_count or 0
            }
            for row in data
        ])
        
        # Calculate churn (30 days of inactivity)
        if not df.empty:
            df['churned'] = df['last_transaction_date'].apply(
                lambda x: (datetime.utcnow() - x).days > 30 if x else True
            )
        
        return df
    
    def _calculate_monthly_churn_rate(self, churn_data: pd.DataFrame) -> List[float]:
        """Calculate monthly churn rates."""
        if churn_data.empty:
            return []
        
        # Group by month and calculate churn rate
        churn_rates = []
        
        # Simplified - calculate for last 6 months
        for i in range(6):
            month_start = datetime.utcnow() - timedelta(days=30 * (i + 1))
            month_end = datetime.utcnow() - timedelta(days=30 * i)
            
            active_start = len(churn_data[
                (churn_data['joined_date'] <= month_start) &
                ((churn_data['last_transaction_date'] >= month_start) | churn_data['last_transaction_date'].isna())
            ])
            
            if active_start > 0:
                churned_count = len(churn_data[
                    (churn_data['last_transaction_date'] >= month_start) &
                    (churn_data['last_transaction_date'] < month_end)
                ])
                churn_rate = churned_count / active_start
                churn_rates.append(churn_rate)
        
        return churn_rates[::-1]  # Reverse to chronological order
    
    def _analyze_cohort_churn(self, churn_data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze churn by cohort."""
        if churn_data.empty:
            return {}
        
        # Group by join month
        churn_data['join_month'] = pd.to_datetime(churn_data['joined_date']).dt.to_period('M')
        
        cohort_analysis = {}
        for cohort in churn_data['join_month'].unique():
            cohort_fans = churn_data[churn_data['join_month'] == cohort]
            if len(cohort_fans) > 0:
                cohort_analysis[str(cohort)] = {
                    'total_fans': len(cohort_fans),
                    'churned_fans': len(cohort_fans[cohort_fans['churned']]),
                    'churn_rate': len(cohort_fans[cohort_fans['churned']]) / len(cohort_fans)
                }
        
        return cohort_analysis
    
    def _analyze_value_segment_churn(self, churn_data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze churn by customer value segment."""
        if churn_data.empty:
            return {}
        
        # Define value segments
        churn_data['value_segment'] = pd.cut(
            churn_data['total_spent'],
            bins=[0, 100, 500, 1000, float('inf')],
            labels=['Low', 'Medium', 'High', 'VIP']
        )
        
        segment_analysis = {}
        for segment in ['Low', 'Medium', 'High', 'VIP']:
            segment_fans = churn_data[churn_data['value_segment'] == segment]
            if len(segment_fans) > 0:
                segment_analysis[segment] = {
                    'total_fans': len(segment_fans),
                    'churned_fans': len(segment_fans[segment_fans['churned']]),
                    'churn_rate': len(segment_fans[segment_fans['churned']]) / len(segment_fans),
                    'avg_lifetime_value': float(segment_fans['total_spent'].mean())
                }
        
        return segment_analysis
    
    def _generate_churn_insights(
        self,
        monthly_rates: List[float],
        cohort_analysis: Dict[str, Any],
        segment_analysis: Dict[str, Any],
        feature_importance: Optional[Dict[str, float]]
    ) -> List[str]:
        """Generate actionable insights from churn analysis."""
        insights = []
        
        # Monthly trend insights
        if len(monthly_rates) >= 2:
            trend = "increasing" if monthly_rates[-1] > monthly_rates[-2] else "decreasing"
            avg_rate = np.mean(monthly_rates)
            insights.append(f"Churn rate is {trend}, current: {monthly_rates[-1]:.1%}, average: {avg_rate:.1%}")
        
        # Segment insights
        if segment_analysis:
            highest_churn_segment = max(
                segment_analysis.items(),
                key=lambda x: x[1].get('churn_rate', 0)
            )
            insights.append(f"{highest_churn_segment[0]} value customers have highest churn rate ({highest_churn_segment[1]['churn_rate']:.1%})")
        
        # Feature importance insights
        if feature_importance:
            top_factor = list(feature_importance.keys())[0]
            insights.append(f"Top churn indicator: {top_factor.replace('_', ' ')}")
        
        # Recommendations
        if monthly_rates and monthly_rates[-1] > 0.1:
            insights.append("High churn rate detected - implement retention campaign")
        
        return insights
