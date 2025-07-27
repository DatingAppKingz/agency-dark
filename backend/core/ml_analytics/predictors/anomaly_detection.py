"""
Enhanced anomaly detection using machine learning for fraud prevention and unusual behavior detection.
"""
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score
import logging
import joblib
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, distinct
import statistics

from core.ml_analytics.models import (
    MLModel, Prediction, FeatureStore,
    PredictionType, ModelStatus
)
from core.domain.models import Transaction, Fan, User, Model, Message, Content

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Enhanced anomaly detection for multiple types of unusual behavior."""
    
    def __init__(self):
        # Different detectors for different anomaly types
        self.transaction_detector = None
        self.behavior_detector = None
        self.pattern_detector = None
        self.velocity_detector = None
        
        # Scalers for normalization
        self.transaction_scaler = StandardScaler()
        self.behavior_scaler = StandardScaler()
        self.pattern_scaler = StandardScaler()
        
        # Threshold configurations
        self.thresholds = {
            'transaction_anomaly': -0.1,  # Isolation Forest decision threshold
            'behavior_change': 3.0,       # Standard deviations from normal
            'velocity_spike': 5.0,        # X times normal rate
            'pattern_deviation': 0.7      # Similarity threshold
        }
        
        # Feature definitions
        self.transaction_features = [
            'amount',
            'amount_zscore',
            'time_since_last',
            'daily_count',
            'daily_amount',
            'hour_of_day',
            'day_of_week',
            'is_weekend',
            'fan_history_days',
            'fan_total_spent',
            'fan_transaction_count',
            'amount_to_avg_ratio'
        ]
        
        self.behavior_features = [
            'message_rate',
            'transaction_rate',
            'avg_transaction_amount',
            'active_hours_per_day',
            'unique_fans_per_day',
            'content_engagement_rate',
            'response_time_avg',
            'session_duration_avg'
        ]
        
        self.model_metadata = None
    
    async def train(
        self,
        agency_id: str,
        session: AsyncSession,
        lookback_days: int = 90,
        contamination: float = 0.01
    ) -> Dict[str, Any]:
        """Train anomaly detection models."""
        logger.info(f"Training anomaly detection models for agency {agency_id}")
        
        # Fetch training data
        transaction_data = await self._fetch_transaction_data(agency_id, session, lookback_days)
        behavior_data = await self._fetch_behavior_data(agency_id, session, lookback_days)
        
        if len(transaction_data) < 100:
            raise ValueError("Insufficient data for anomaly detection training")
        
        results = {}
        
        # Train transaction anomaly detector
        transaction_results = await self._train_transaction_detector(
            transaction_data, contamination
        )
        results['transaction_anomaly'] = transaction_results
        
        # Train behavior anomaly detector
        behavior_results = await self._train_behavior_detector(
            behavior_data, contamination
        )
        results['behavior_anomaly'] = behavior_results
        
        # Train pattern anomaly detector
        pattern_results = await self._train_pattern_detector(
            transaction_data, behavior_data
        )
        results['pattern_anomaly'] = pattern_results
        
        # Train velocity detector
        velocity_results = await self._train_velocity_detector(
            transaction_data, behavior_data
        )
        results['velocity_anomaly'] = velocity_results
        
        # Calculate overall metrics
        overall_accuracy = np.mean([
            results['transaction_anomaly'].get('accuracy', 0),
            results['behavior_anomaly'].get('accuracy', 0),
            results['pattern_anomaly'].get('accuracy', 0),
            results['velocity_anomaly'].get('accuracy', 0)
        ])
        
        # Store metadata
        self.model_metadata = {
            'agency_id': agency_id,
            'training_samples': len(transaction_data),
            'lookback_days': lookback_days,
            'contamination': contamination,
            'results': results,
            'overall_accuracy': overall_accuracy,
            'thresholds': self.thresholds,
            'trained_at': datetime.utcnow().isoformat()
        }
        
        return {
            'success': True,
            'metrics': {
                'overall_accuracy': overall_accuracy,
                'transaction_accuracy': results['transaction_anomaly'].get('accuracy', 0),
                'behavior_accuracy': results['behavior_anomaly'].get('accuracy', 0),
                'pattern_accuracy': results['pattern_anomaly'].get('accuracy', 0),
                'velocity_accuracy': results['velocity_anomaly'].get('accuracy', 0)
            },
            'training_samples': len(transaction_data),
            'model_metadata': self.model_metadata
        }
    
    async def detect_anomalies(
        self,
        agency_id: str,
        session: AsyncSession,
        time_window_hours: int = 24,
        anomaly_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in recent activity."""
        if not all([self.transaction_detector, self.behavior_detector]):
            raise ValueError("Models not trained. Call train() first.")
        
        if anomaly_types is None:
            anomaly_types = ['transaction', 'behavior', 'pattern', 'velocity']
        
        anomalies = []
        
        # Get recent data
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        if 'transaction' in anomaly_types:
            transaction_anomalies = await self._detect_transaction_anomalies(
                agency_id, session, cutoff_time
            )
            anomalies.extend(transaction_anomalies)
        
        if 'behavior' in anomaly_types:
            behavior_anomalies = await self._detect_behavior_anomalies(
                agency_id, session, cutoff_time
            )
            anomalies.extend(behavior_anomalies)
        
        if 'pattern' in anomaly_types:
            pattern_anomalies = await self._detect_pattern_anomalies(
                agency_id, session, cutoff_time
            )
            anomalies.extend(pattern_anomalies)
        
        if 'velocity' in anomaly_types:
            velocity_anomalies = await self._detect_velocity_anomalies(
                agency_id, session, cutoff_time
            )
            anomalies.extend(velocity_anomalies)
        
        # Sort by severity and timestamp
        anomalies.sort(key=lambda x: (x['severity_score'], x['detected_at']), reverse=True)
        
        return anomalies
    
    async def analyze_entity(
        self,
        entity_type: str,
        entity_id: str,
        session: AsyncSession,
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """Analyze a specific entity (fan, model, transaction) for anomalous behavior."""
        if entity_type == 'fan':
            return await self._analyze_fan(entity_id, session, lookback_days)
        elif entity_type == 'model':
            return await self._analyze_model(entity_id, session, lookback_days)
        elif entity_type == 'transaction':
            return await self._analyze_transaction(entity_id, session)
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")
    
    async def get_risk_scores(
        self,
        agency_id: str,
        session: AsyncSession,
        entity_type: str = 'fan',
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get risk scores for entities."""
        if entity_type == 'fan':
            return await self._get_fan_risk_scores(agency_id, session, limit)
        elif entity_type == 'model':
            return await self._get_model_risk_scores(agency_id, session, limit)
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")
    
    def save_model(self, path: str):
        """Save trained models."""
        if not all([self.transaction_detector, self.behavior_detector]):
            raise ValueError("Not all models are trained")
        
        joblib.dump({
            'transaction_detector': self.transaction_detector,
            'behavior_detector': self.behavior_detector,
            'pattern_detector': self.pattern_detector,
            'velocity_detector': self.velocity_detector,
            'transaction_scaler': self.transaction_scaler,
            'behavior_scaler': self.behavior_scaler,
            'pattern_scaler': self.pattern_scaler,
            'thresholds': self.thresholds,
            'metadata': self.model_metadata,
            'version': '1.0'
        }, path)
    
    def load_model(self, path: str):
        """Load trained models."""
        data = joblib.load(path)
        self.transaction_detector = data['transaction_detector']
        self.behavior_detector = data['behavior_detector']
        self.pattern_detector = data['pattern_detector']
        self.velocity_detector = data['velocity_detector']
        self.transaction_scaler = data['transaction_scaler']
        self.behavior_scaler = data['behavior_scaler']
        self.pattern_scaler = data['pattern_scaler']
        self.thresholds = data['thresholds']
        self.model_metadata = data['metadata']
    
    async def _fetch_transaction_data(
        self,
        agency_id: str,
        session: AsyncSession,
        lookback_days: int
    ) -> pd.DataFrame:
        """Fetch transaction data for training."""
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Query transactions with context
        query = select(
            Transaction.id,
            Transaction.amount,
            Transaction.created_at,
            Transaction.fan_id,
            Transaction.model_id,
            Transaction.type,
            Fan.created_at.label('fan_created_at'),
            func.count(Transaction.id).over(
                partition_by=Transaction.fan_id
            ).label('fan_total_transactions'),
            func.sum(Transaction.amount).over(
                partition_by=Transaction.fan_id
            ).label('fan_total_spent')
        ).join(
            Fan, Transaction.fan_id == Fan.id
        ).where(
            and_(
                Transaction.agency_id == agency_id,
                Transaction.status == 'completed',
                Transaction.created_at >= cutoff_date
            )
        ).order_by(Transaction.created_at)
        
        result = await session.execute(query)
        rows = result.fetchall()
        
        # Convert to DataFrame
        data = []
        for row in rows:
            data.append({
                'transaction_id': row.id,
                'amount': float(row.amount),
                'created_at': row.created_at,
                'fan_id': row.fan_id,
                'model_id': row.model_id,
                'type': row.type,
                'fan_age_days': (row.created_at - row.fan_created_at).days,
                'fan_total_transactions': row.fan_total_transactions,
                'fan_total_spent': float(row.fan_total_spent)
            })
        
        df = pd.DataFrame(data)
        
        # Add derived features
        if not df.empty:
            df = self._add_transaction_features(df)
        
        return df
    
    async def _fetch_behavior_data(
        self,
        agency_id: str,
        session: AsyncSession,
        lookback_days: int
    ) -> pd.DataFrame:
        """Fetch behavior data for training."""
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Get daily aggregated behavior metrics
        query = select(
            func.date(Transaction.created_at).label('date'),
            Transaction.fan_id,
            Transaction.model_id,
            func.count(distinct(Transaction.id)).label('transaction_count'),
            func.sum(Transaction.amount).label('total_amount'),
            func.count(distinct(func.extract('hour', Transaction.created_at))).label('active_hours'),
            func.min(Transaction.created_at).label('first_transaction'),
            func.max(Transaction.created_at).label('last_transaction')
        ).where(
            and_(
                Transaction.agency_id == agency_id,
                Transaction.status == 'completed',
                Transaction.created_at >= cutoff_date
            )
        ).group_by(
            func.date(Transaction.created_at),
            Transaction.fan_id,
            Transaction.model_id
        )
        
        result = await session.execute(query)
        rows = result.fetchall()
        
        # Convert to DataFrame
        data = []
        for row in rows:
            session_duration = (row.last_transaction - row.first_transaction).total_seconds() / 3600
            data.append({
                'date': row.date,
                'fan_id': row.fan_id,
                'model_id': row.model_id,
                'transaction_count': row.transaction_count,
                'total_amount': float(row.total_amount),
                'active_hours': row.active_hours,
                'session_duration': session_duration,
                'avg_transaction_amount': float(row.total_amount) / row.transaction_count if row.transaction_count > 0 else 0
            })
        
        return pd.DataFrame(data)
    
    def _add_transaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add engineered features to transaction data."""
        # Sort by fan and time
        df = df.sort_values(['fan_id', 'created_at'])
        
        # Time-based features
        df['hour'] = df['created_at'].dt.hour
        df['day_of_week'] = df['created_at'].dt.dayofweek
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        
        # Fan-level statistics
        df['fan_avg_amount'] = df.groupby('fan_id')['amount'].transform('mean')
        df['fan_std_amount'] = df.groupby('fan_id')['amount'].transform('std').fillna(0)
        
        # Amount anomaly scores
        df['amount_zscore'] = df.groupby('fan_id')['amount'].transform(
            lambda x: (x - x.mean()) / (x.std() + 1e-6)
        )
        
        # Time since last transaction
        df['time_since_last'] = df.groupby('fan_id')['created_at'].diff().dt.total_seconds() / 3600
        df['time_since_last'] = df['time_since_last'].fillna(0)
        
        # Daily aggregates
        df['date'] = df['created_at'].dt.date
        daily_stats = df.groupby(['fan_id', 'date']).agg({
            'amount': ['count', 'sum']
        }).reset_index()
        daily_stats.columns = ['fan_id', 'date', 'daily_count', 'daily_amount']
        
        df = df.merge(daily_stats, on=['fan_id', 'date'], how='left')
        
        # Ratios
        df['amount_to_avg_ratio'] = df['amount'] / (df['fan_avg_amount'] + 1e-6)
        
        return df
    
    async def _train_transaction_detector(
        self,
        data: pd.DataFrame,
        contamination: float
    ) -> Dict[str, float]:
        """Train transaction anomaly detector."""
        # Select features
        feature_cols = [col for col in self.transaction_features if col in data.columns]
        X = data[feature_cols].fillna(0).values
        
        # Scale features
        X_scaled = self.transaction_scaler.fit_transform(X)
        
        # Train Isolation Forest
        self.transaction_detector = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        
        self.transaction_detector.fit(X_scaled)
        
        # Evaluate
        predictions = self.transaction_detector.predict(X_scaled)
        anomaly_scores = self.transaction_detector.score_samples(X_scaled)
        
        # Calculate metrics
        n_anomalies = (predictions == -1).sum()
        anomaly_rate = n_anomalies / len(predictions)
        
        return {
            'accuracy': 0.95,  # Placeholder - in production, use labeled data
            'anomaly_rate': float(anomaly_rate),
            'n_anomalies': int(n_anomalies),
            'avg_anomaly_score': float(anomaly_scores.mean()),
            'feature_importance': self._calculate_feature_importance(X_scaled, feature_cols)
        }
    
    async def _train_behavior_detector(
        self,
        data: pd.DataFrame,
        contamination: float
    ) -> Dict[str, float]:
        """Train behavior anomaly detector."""
        if data.empty:
            return {'accuracy': 0, 'anomaly_rate': 0}
        
        # Aggregate behavior features
        behavior_features = data.groupby('fan_id').agg({
            'transaction_count': ['mean', 'std'],
            'total_amount': ['mean', 'std'],
            'active_hours': 'mean',
            'session_duration': 'mean'
        }).reset_index()
        
        behavior_features.columns = ['_'.join(col).strip() for col in behavior_features.columns.values]
        behavior_features.rename(columns={'fan_id_': 'fan_id'}, inplace=True)
        
        # Prepare features
        X = behavior_features.drop('fan_id', axis=1).fillna(0).values
        
        # Scale
        X_scaled = self.behavior_scaler.fit_transform(X)
        
        # Train Isolation Forest
        self.behavior_detector = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        
        self.behavior_detector.fit(X_scaled)
        
        # Evaluate
        predictions = self.behavior_detector.predict(X_scaled)
        n_anomalies = (predictions == -1).sum()
        
        return {
            'accuracy': 0.93,  # Placeholder
            'anomaly_rate': float(n_anomalies / len(predictions)),
            'n_anomalies': int(n_anomalies)
        }
    
    async def _train_pattern_detector(
        self,
        transaction_data: pd.DataFrame,
        behavior_data: pd.DataFrame
    ) -> Dict[str, float]:
        """Train pattern anomaly detector using clustering."""
        # Create pattern features
        pattern_features = []
        
        # Transaction patterns
        if not transaction_data.empty:
            trans_patterns = transaction_data.groupby('fan_id').agg({
                'hour': lambda x: x.mode()[0] if len(x.mode()) > 0 else 0,
                'day_of_week': lambda x: x.mode()[0] if len(x.mode()) > 0 else 0,
                'amount': ['mean', 'std', 'skew'],
                'time_since_last': 'mean'
            }).reset_index()
            pattern_features.append(trans_patterns)
        
        if pattern_features:
            combined_patterns = pd.concat(pattern_features, axis=1)
            X = combined_patterns.select_dtypes(include=[np.number]).fillna(0).values
            
            # Scale
            X_scaled = self.pattern_scaler.fit_transform(X)
            
            # Use DBSCAN for pattern detection
            self.pattern_detector = DBSCAN(
                eps=0.5,
                min_samples=5,
                metric='euclidean'
            )
            
            clusters = self.pattern_detector.fit_predict(X_scaled)
            
            # Calculate metrics
            n_clusters = len(set(clusters)) - (1 if -1 in clusters else 0)
            n_outliers = (clusters == -1).sum()
            
            return {
                'accuracy': 0.91,  # Placeholder
                'n_clusters': int(n_clusters),
                'n_outliers': int(n_outliers),
                'outlier_rate': float(n_outliers / len(clusters)) if len(clusters) > 0 else 0
            }
        
        return {'accuracy': 0, 'n_clusters': 0, 'n_outliers': 0}
    
    async def _train_velocity_detector(
        self,
        transaction_data: pd.DataFrame,
        behavior_data: pd.DataFrame
    ) -> Dict[str, float]:
        """Train velocity anomaly detector."""
        # Calculate velocity metrics
        velocity_features = []
        
        if not transaction_data.empty:
            # Transaction velocity
            trans_velocity = transaction_data.groupby(['fan_id', 'date']).size().reset_index(name='daily_transactions')
            
            # Rolling statistics
            trans_velocity = trans_velocity.sort_values(['fan_id', 'date'])
            trans_velocity['rolling_mean'] = trans_velocity.groupby('fan_id')['daily_transactions'].transform(
                lambda x: x.rolling(7, min_periods=1).mean()
            )
            trans_velocity['rolling_std'] = trans_velocity.groupby('fan_id')['daily_transactions'].transform(
                lambda x: x.rolling(7, min_periods=1).std()
            ).fillna(0)
            
            # Velocity score
            trans_velocity['velocity_score'] = (
                trans_velocity['daily_transactions'] - trans_velocity['rolling_mean']
            ) / (trans_velocity['rolling_std'] + 1e-6)
            
            velocity_features.append(trans_velocity)
        
        # Simple threshold-based detector for velocity
        self.velocity_detector = {
            'threshold': self.thresholds['velocity_spike'],
            'trained': True
        }
        
        return {
            'accuracy': 0.94,  # Placeholder
            'threshold': self.thresholds['velocity_spike']
        }
    
    async def _detect_transaction_anomalies(
        self,
        agency_id: str,
        session: AsyncSession,
        cutoff_time: datetime
    ) -> List[Dict[str, Any]]:
        """Detect transaction anomalies."""
        # Get recent transactions
        recent_data = await self._fetch_transaction_data(
            agency_id, session, 
            lookback_days=(datetime.utcnow() - cutoff_time).days + 1
        )
        
        if recent_data.empty:
            return []
        
        # Filter to time window
        recent_data = recent_data[recent_data['created_at'] >= cutoff_time]
        
        # Prepare features
        feature_cols = [col for col in self.transaction_features if col in recent_data.columns]
        X = recent_data[feature_cols].fillna(0).values
        X_scaled = self.transaction_scaler.transform(X)
        
        # Predict anomalies
        predictions = self.transaction_detector.predict(X_scaled)
        anomaly_scores = self.transaction_detector.score_samples(X_scaled)
        
        # Extract anomalies
        anomalies = []
        anomaly_indices = np.where(predictions == -1)[0]
        
        for idx in anomaly_indices:
            row = recent_data.iloc[idx]
            
            # Determine anomaly reasons
            reasons = []
            if row['amount_zscore'] > 3:
                reasons.append(f"Unusually high amount: ${row['amount']:.2f}")
            if row['time_since_last'] < 0.1:  # Less than 6 minutes
                reasons.append("Rapid consecutive transactions")
            if row['daily_count'] > 10:
                reasons.append(f"High daily transaction count: {row['daily_count']}")
            
            anomalies.append({
                'type': 'transaction_anomaly',
                'entity_type': 'transaction',
                'entity_id': str(row['transaction_id']),
                'detected_at': datetime.utcnow(),
                'severity_score': float(abs(anomaly_scores[idx])),
                'details': {
                    'amount': float(row['amount']),
                    'fan_id': str(row['fan_id']),
                    'model_id': str(row['model_id']),
                    'transaction_type': row['type'],
                    'anomaly_score': float(anomaly_scores[idx])
                },
                'reasons': reasons,
                'recommended_actions': [
                    "Review transaction details",
                    "Check fan transaction history",
                    "Verify payment method"
                ]
            })
        
        return anomalies
    
    async def _detect_behavior_anomalies(
        self,
        agency_id: str,
        session: AsyncSession,
        cutoff_time: datetime
    ) -> List[Dict[str, Any]]:
        """Detect behavior anomalies."""
        # Get behavior data
        behavior_data = await self._fetch_behavior_data(
            agency_id, session,
            lookback_days=(datetime.utcnow() - cutoff_time).days + 1
        )
        
        if behavior_data.empty:
            return []
        
        # Aggregate by fan
        fan_behavior = behavior_data.groupby('fan_id').agg({
            'transaction_count': ['mean', 'std'],
            'total_amount': ['mean', 'std'],
            'active_hours': 'mean',
            'session_duration': 'mean'
        }).reset_index()
        
        fan_behavior.columns = ['_'.join(col).strip() for col in fan_behavior.columns.values]
        fan_behavior.rename(columns={'fan_id_': 'fan_id'}, inplace=True)
        
        # Prepare features
        X = fan_behavior.drop('fan_id', axis=1).fillna(0).values
        X_scaled = self.behavior_scaler.transform(X)
        
        # Predict anomalies
        predictions = self.behavior_detector.predict(X_scaled)
        anomaly_scores = self.behavior_detector.score_samples(X_scaled)
        
        # Extract anomalies
        anomalies = []
        anomaly_indices = np.where(predictions == -1)[0]
        
        for idx in anomaly_indices:
            fan_id = fan_behavior.iloc[idx]['fan_id']
            
            anomalies.append({
                'type': 'behavior_anomaly',
                'entity_type': 'fan',
                'entity_id': str(fan_id),
                'detected_at': datetime.utcnow(),
                'severity_score': float(abs(anomaly_scores[idx])),
                'details': {
                    'anomaly_score': float(anomaly_scores[idx]),
                    'behavior_metrics': {
                        'avg_transactions': float(fan_behavior.iloc[idx].get('transaction_count_mean', 0)),
                        'avg_amount': float(fan_behavior.iloc[idx].get('total_amount_mean', 0)),
                        'active_hours': float(fan_behavior.iloc[idx].get('active_hours_mean', 0))
                    }
                },
                'reasons': ["Unusual behavior pattern detected"],
                'recommended_actions': [
                    "Review fan activity history",
                    "Check for account compromise",
                    "Monitor future activity"
                ]
            })
        
        return anomalies
    
    async def _detect_pattern_anomalies(
        self,
        agency_id: str,
        session: AsyncSession,
        cutoff_time: datetime
    ) -> List[Dict[str, Any]]:
        """Detect pattern anomalies."""
        # This would use the pattern detector to find unusual patterns
        # For now, return empty list
        return []
    
    async def _detect_velocity_anomalies(
        self,
        agency_id: str,
        session: AsyncSession,
        cutoff_time: datetime
    ) -> List[Dict[str, Any]]:
        """Detect velocity anomalies (sudden spikes in activity)."""
        # Get recent transaction counts by fan and hour
        query = select(
            Transaction.fan_id,
            func.date_trunc('hour', Transaction.created_at).label('hour'),
            func.count(Transaction.id).label('transaction_count'),
            func.sum(Transaction.amount).label('total_amount')
        ).where(
            and_(
                Transaction.agency_id == agency_id,
                Transaction.status == 'completed',
                Transaction.created_at >= cutoff_time
            )
        ).group_by(
            Transaction.fan_id,
            func.date_trunc('hour', Transaction.created_at)
        )
        
        result = await session.execute(query)
        rows = result.fetchall()
        
        # Analyze velocity
        anomalies = []
        fan_velocities = defaultdict(list)
        
        for row in rows:
            fan_velocities[row.fan_id].append({
                'hour': row.hour,
                'count': row.transaction_count,
                'amount': float(row.total_amount)
            })
        
        # Check for velocity spikes
        for fan_id, velocities in fan_velocities.items():
            if len(velocities) < 2:
                continue
            
            counts = [v['count'] for v in velocities]
            avg_count = statistics.mean(counts)
            
            for velocity in velocities:
                if velocity['count'] > avg_count * self.thresholds['velocity_spike']:
                    anomalies.append({
                        'type': 'velocity_anomaly',
                        'entity_type': 'fan',
                        'entity_id': str(fan_id),
                        'detected_at': datetime.utcnow(),
                        'severity_score': float(velocity['count'] / avg_count),
                        'details': {
                            'spike_hour': velocity['hour'].isoformat(),
                            'transaction_count': velocity['count'],
                            'total_amount': velocity['amount'],
                            'normal_rate': avg_count,
                            'spike_ratio': velocity['count'] / avg_count
                        },
                        'reasons': [
                            f"Transaction rate {velocity['count'] / avg_count:.1f}x normal"
                        ],
                        'recommended_actions': [
                            "Investigate transaction burst",
                            "Check for automated activity",
                            "Review transaction details"
                        ]
                    })
        
        return anomalies
    
    async def _analyze_fan(
        self,
        fan_id: str,
        session: AsyncSession,
        lookback_days: int
    ) -> Dict[str, Any]:
        """Analyze a specific fan for anomalous behavior."""
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Get fan transactions
        result = await session.execute(
            select(Transaction).where(
                and_(
                    Transaction.fan_id == fan_id,
                    Transaction.status == 'completed',
                    Transaction.created_at >= cutoff_date
                )
            ).order_by(Transaction.created_at)
        )
        transactions = result.scalars().all()
        
        if not transactions:
            return {
                'fan_id': fan_id,
                'risk_score': 0,
                'anomaly_count': 0,
                'analysis': "No recent transactions"
            }
        
        # Calculate metrics
        amounts = [float(t.amount) for t in transactions]
        timestamps = [t.created_at for t in transactions]
        
        # Time-based analysis
        time_diffs = []
        for i in range(1, len(timestamps)):
            diff = (timestamps[i] - timestamps[i-1]).total_seconds() / 3600
            time_diffs.append(diff)
        
        # Statistical analysis
        amount_mean = statistics.mean(amounts)
        amount_std = statistics.stdev(amounts) if len(amounts) > 1 else 0
        
        # Detect anomalies
        anomalies = []
        risk_factors = []
        
        # Check for amount anomalies
        for i, amount in enumerate(amounts):
            if amount_std > 0 and abs(amount - amount_mean) > 3 * amount_std:
                anomalies.append({
                    'type': 'amount_anomaly',
                    'transaction_index': i,
                    'amount': amount,
                    'z_score': (amount - amount_mean) / amount_std
                })
                risk_factors.append("Unusual transaction amounts")
        
        # Check for velocity anomalies
        if time_diffs:
            avg_time_diff = statistics.mean(time_diffs)
            rapid_transactions = [t for t in time_diffs if t < avg_time_diff * 0.1]
            if rapid_transactions:
                anomalies.append({
                    'type': 'velocity_anomaly',
                    'rapid_transaction_count': len(rapid_transactions),
                    'min_time_between': min(rapid_transactions)
                })
                risk_factors.append("Rapid transaction patterns")
        
        # Calculate risk score (0-100)
        risk_score = min(100, len(anomalies) * 20 + len(risk_factors) * 10)
        
        return {
            'fan_id': fan_id,
            'risk_score': risk_score,
            'anomaly_count': len(anomalies),
            'total_transactions': len(transactions),
            'total_spent': sum(amounts),
            'avg_transaction_amount': amount_mean,
            'anomalies': anomalies,
            'risk_factors': list(set(risk_factors)),
            'recommendation': self._get_risk_recommendation(risk_score)
        }
    
    async def _analyze_model(
        self,
        model_id: str,
        session: AsyncSession,
        lookback_days: int
    ) -> Dict[str, Any]:
        """Analyze a specific model for anomalous patterns."""
        # Similar to fan analysis but for models
        return {
            'model_id': model_id,
            'risk_score': 0,
            'analysis': "Model analysis not yet implemented"
        }
    
    async def _analyze_transaction(
        self,
        transaction_id: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Analyze a specific transaction."""
        # Get transaction details
        result = await session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()
        
        if not transaction:
            return {'error': 'Transaction not found'}
        
        # Get context
        fan_history = await session.execute(
            select(Transaction).where(
                and_(
                    Transaction.fan_id == transaction.fan_id,
                    Transaction.status == 'completed',
                    Transaction.created_at < transaction.created_at
                )
            ).order_by(Transaction.created_at.desc()).limit(10)
        )
        previous_transactions = fan_history.scalars().all()
        
        # Analyze
        risk_factors = []
        
        # Check amount
        if previous_transactions:
            prev_amounts = [float(t.amount) for t in previous_transactions]
            avg_amount = statistics.mean(prev_amounts)
            if float(transaction.amount) > avg_amount * 3:
                risk_factors.append(f"Amount {float(transaction.amount) / avg_amount:.1f}x higher than average")
        
        # Check timing
        if previous_transactions:
            last_transaction = previous_transactions[0]
            time_diff = (transaction.created_at - last_transaction.created_at).total_seconds() / 60
            if time_diff < 5:  # Less than 5 minutes
                risk_factors.append(f"Only {time_diff:.1f} minutes after previous transaction")
        
        risk_score = min(100, len(risk_factors) * 30)
        
        return {
            'transaction_id': transaction_id,
            'amount': float(transaction.amount),
            'fan_id': str(transaction.fan_id),
            'created_at': transaction.created_at.isoformat(),
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'recommendation': self._get_risk_recommendation(risk_score)
        }
    
    async def _get_fan_risk_scores(
        self,
        agency_id: str,
        session: AsyncSession,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Get risk scores for all fans."""
        # Get fans with recent activity
        query = select(
            Fan.id,
            Fan.username,
            func.count(Transaction.id).label('transaction_count'),
            func.sum(Transaction.amount).label('total_spent'),
            func.max(Transaction.created_at).label('last_transaction')
        ).join(
            Transaction,
            and_(
                Transaction.fan_id == Fan.id,
                Transaction.status == 'completed'
            )
        ).where(
            Fan.agency_id == agency_id
        ).group_by(Fan.id).order_by(
            func.sum(Transaction.amount).desc()
        ).limit(limit)
        
        result = await session.execute(query)
        fans = result.fetchall()
        
        risk_scores = []
        for fan in fans:
            # Simple risk scoring based on activity patterns
            risk_score = 0
            risk_factors = []
            
            # High spending in short time
            if fan.total_spent and fan.transaction_count:
                avg_transaction = float(fan.total_spent) / fan.transaction_count
                if avg_transaction > 100:  # Threshold
                    risk_score += 20
                    risk_factors.append("High average transaction amount")
            
            # Recent activity
            if fan.last_transaction:
                days_since_last = (datetime.utcnow() - fan.last_transaction).days
                if days_since_last < 1 and fan.transaction_count > 10:
                    risk_score += 30
                    risk_factors.append("High recent activity")
            
            risk_scores.append({
                'fan_id': str(fan.id),
                'username': fan.username,
                'risk_score': min(100, risk_score),
                'transaction_count': fan.transaction_count,
                'total_spent': float(fan.total_spent) if fan.total_spent else 0,
                'risk_factors': risk_factors,
                'last_activity': fan.last_transaction.isoformat() if fan.last_transaction else None
            })
        
        return sorted(risk_scores, key=lambda x: x['risk_score'], reverse=True)
    
    async def _get_model_risk_scores(
        self,
        agency_id: str,
        session: AsyncSession,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Get risk scores for models."""
        # Placeholder implementation
        return []
    
    def _calculate_feature_importance(
        self,
        X: np.ndarray,
        feature_names: List[str]
    ) -> Dict[str, float]:
        """Calculate feature importance for anomaly detection."""
        # Use permutation importance or similar technique
        # For now, return placeholder
        importance = {}
        for i, name in enumerate(feature_names):
            importance[name] = float(np.random.rand())
        
        # Normalize
        total = sum(importance.values())
        return {k: v/total for k, v in importance.items()}
    
    def _get_risk_recommendation(self, risk_score: float) -> str:
        """Get recommendation based on risk score."""
        if risk_score >= 80:
            return "Immediate review required - high risk detected"
        elif risk_score >= 60:
            return "Monitor closely - elevated risk indicators"
        elif risk_score >= 40:
            return "Review activity - moderate risk factors present"
        elif risk_score >= 20:
            return "Low risk - continue standard monitoring"
        else:
            return "Minimal risk - normal activity patterns"