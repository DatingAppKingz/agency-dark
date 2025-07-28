"""
Anomaly Detection Model for fraud prevention and unusual behavior detection
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import DBSCAN
from sklearn.neighbors import LocalOutlierFactor
import scipy.stats as stats

from .base import BaseMLModel


class AnomalyDetectionModel(BaseMLModel):
    """
    Multi-algorithm anomaly detection for fraud prevention
    Combines multiple approaches for robust detection
    """
    
    def __init__(self, version: str = "1.0.0"):
        super().__init__("anomaly_detection", version)
        self.scaler = StandardScaler()
        self.models = {}
        self.threshold_percentile = 95
        self.pca_model = PCA(n_components=0.95)  # Keep 95% variance
        self.anomaly_rules = []
        self.baseline_stats = {}
        
    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess transaction/activity data for anomaly detection
        
        Expected columns:
        - user_id
        - timestamp
        - amount (for financial transactions)
        - transaction_type
        - ip_address
        - device_id
        - location_country
        - location_city
        """
        df = data.copy()
        
        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Extract time-based features
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        df['is_night'] = df['hour'].between(22, 6).astype(int)
        
        # User behavior features
        user_stats = df.groupby('user_id').agg({
            'amount': ['mean', 'std', 'count'],
            'timestamp': ['min', 'max']
        })
        user_stats.columns = ['avg_amount', 'std_amount', 'transaction_count', 'first_seen', 'last_seen']
        user_stats['account_age_days'] = (datetime.now() - user_stats['first_seen']).dt.days
        
        # Merge user stats
        df = df.merge(user_stats, left_on='user_id', right_index=True, how='left')
        
        # Calculate deviations from user normal behavior
        df['amount_z_score'] = (df['amount'] - df['avg_amount']) / (df['std_amount'] + 1e-8)
        df['amount_ratio'] = df['amount'] / (df['avg_amount'] + 1e-8)
        
        # Velocity features (transactions in time windows)
        for window in [1, 24]:  # 1 hour and 24 hour windows
            df[f'transactions_{window}h'] = df.groupby('user_id')['timestamp'].transform(
                lambda x: x.rolling(f'{window}H').count()
            )
            df[f'amount_sum_{window}h'] = df.groupby('user_id')['amount'].transform(
                lambda x: x.rolling(f'{window}H').sum()
            )
        
        # Location features
        if 'location_country' in df.columns:
            # Count unique locations
            df['unique_countries'] = df.groupby('user_id')['location_country'].transform('nunique')
            df['unique_cities'] = df.groupby('user_id')['location_city'].transform('nunique')
            
            # Flag location changes
            df['location_changed'] = (
                df.groupby('user_id')['location_country'].shift() != df['location_country']
            ).astype(int)
        
        # Device features
        if 'device_id' in df.columns:
            df['unique_devices'] = df.groupby('user_id')['device_id'].transform('nunique')
            df['device_changed'] = (
                df.groupby('user_id')['device_id'].shift() != df['device_id']
            ).astype(int)
        
        # IP address features
        if 'ip_address' in df.columns:
            # Extract IP octets for pattern analysis
            ip_parts = df['ip_address'].str.split('.', expand=True).astype(float)
            df['ip_class_a'] = ip_parts[0]
            df['ip_class_b'] = ip_parts[1]
            
            # Count unique IPs
            df['unique_ips'] = df.groupby('user_id')['ip_address'].transform('nunique')
        
        # Transaction pattern features
        df['time_since_last'] = df.groupby('user_id')['timestamp'].diff().dt.total_seconds() / 3600
        df['is_rapid_succession'] = (df['time_since_last'] < 0.017).astype(int)  # Less than 1 minute
        
        # Handle missing values
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        df[numeric_columns] = df[numeric_columns].fillna(0)
        
        # Remove infinite values
        df = df.replace([np.inf, -np.inf], 0)
        
        return df
    
    def train(self, data: pd.DataFrame, contamination: float = 0.01, **kwargs) -> Dict[str, Any]:
        """
        Train anomaly detection models
        
        Args:
            data: Historical transaction data
            contamination: Expected proportion of anomalies in the dataset
        """
        # Preprocess data
        df = self.preprocess_data(data)
        
        # Define features for anomaly detection
        feature_cols = [
            'amount', 'amount_z_score', 'amount_ratio',
            'hour', 'day_of_week', 'is_weekend', 'is_night',
            'transactions_1h', 'transactions_24h',
            'amount_sum_1h', 'amount_sum_24h',
            'transaction_count', 'account_age_days'
        ]
        
        # Add optional features if available
        optional_features = [
            'unique_countries', 'unique_cities', 'location_changed',
            'unique_devices', 'device_changed',
            'unique_ips', 'ip_class_a', 'ip_class_b',
            'time_since_last', 'is_rapid_succession'
        ]
        
        feature_cols.extend([f for f in optional_features if f in df.columns])
        self.feature_names = feature_cols
        
        # Prepare training data
        X = df[feature_cols].values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Apply PCA for dimensionality reduction
        X_pca = self.pca_model.fit_transform(X_scaled)
        
        # Train multiple anomaly detection models
        self.models = {
            'isolation_forest': IsolationForest(
                contamination=contamination,
                random_state=42,
                n_estimators=100
            ),
            'lof': LocalOutlierFactor(
                contamination=contamination,
                novelty=True,
                n_neighbors=20
            ),
            'isolation_forest_pca': IsolationForest(
                contamination=contamination,
                random_state=42,
                n_estimators=100
            )
        }
        
        # Train models
        self.models['isolation_forest'].fit(X_scaled)
        self.models['lof'].fit(X_scaled)
        self.models['isolation_forest_pca'].fit(X_pca)
        
        # Calculate baseline statistics for rule-based detection
        self._calculate_baseline_stats(df)
        
        # Define rule-based anomalies
        self._define_anomaly_rules()
        
        # Store training metadata
        self.training_metadata = {
            'training_samples': len(X),
            'n_features': len(feature_cols),
            'n_components_pca': self.pca_model.n_components_,
            'contamination': contamination,
            'training_date': datetime.now().isoformat(),
            'feature_names': feature_cols
        }
        
        self.is_trained = True
        return self.training_metadata
    
    def _calculate_baseline_stats(self, df: pd.DataFrame):
        """Calculate baseline statistics for rule-based detection"""
        self.baseline_stats = {
            'amount': {
                'mean': df['amount'].mean(),
                'std': df['amount'].std(),
                'p99': df['amount'].quantile(0.99),
                'p999': df['amount'].quantile(0.999)
            },
            'velocity': {
                'transactions_1h_p95': df['transactions_1h'].quantile(0.95),
                'transactions_24h_p95': df['transactions_24h'].quantile(0.95),
                'amount_sum_1h_p95': df['amount_sum_1h'].quantile(0.95),
                'amount_sum_24h_p95': df['amount_sum_24h'].quantile(0.95)
            }
        }
    
    def _define_anomaly_rules(self):
        """Define rule-based anomaly detection criteria"""
        self.anomaly_rules = [
            {
                'name': 'extreme_amount',
                'condition': lambda row: row['amount'] > self.baseline_stats['amount']['p999'],
                'severity': 'high',
                'description': 'Transaction amount exceeds 99.9th percentile'
            },
            {
                'name': 'high_velocity_1h',
                'condition': lambda row: row['transactions_1h'] > self.baseline_stats['velocity']['transactions_1h_p95'],
                'severity': 'medium',
                'description': 'High transaction frequency in 1 hour'
            },
            {
                'name': 'rapid_location_change',
                'condition': lambda row: row.get('location_changed', 0) == 1 and row.get('time_since_last', float('inf')) < 1,
                'severity': 'high',
                'description': 'Location changed within 1 hour'
            },
            {
                'name': 'multiple_devices',
                'condition': lambda row: row.get('unique_devices', 0) > 3,
                'severity': 'medium',
                'description': 'Using multiple devices'
            }
        ]
    
    def predict(self, data: pd.DataFrame) -> np.ndarray:
        """
        Predict anomalies in new data
        Returns: Array of 1 (anomaly) or 0 (normal)
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        df = self.preprocess_data(data)
        X = df[self.feature_names].values
        X_scaled = self.scaler.transform(X)
        X_pca = self.pca_model.transform(X_scaled)
        
        # Get predictions from each model
        predictions = {
            'isolation_forest': self.models['isolation_forest'].predict(X_scaled),
            'lof': self.models['lof'].predict(X_scaled),
            'isolation_forest_pca': self.models['isolation_forest_pca'].predict(X_pca)
        }
        
        # Convert to binary (1 for anomaly, 0 for normal)
        for name in predictions:
            predictions[name] = (predictions[name] == -1).astype(int)
        
        # Ensemble voting
        ensemble_predictions = (
            predictions['isolation_forest'] + 
            predictions['lof'] + 
            predictions['isolation_forest_pca']
        ) >= 2  # Majority voting
        
        return ensemble_predictions.astype(int)
    
    def get_anomaly_scores(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Get detailed anomaly scores and explanations
        """
        df = self.preprocess_data(data)
        X = df[self.feature_names].values
        X_scaled = self.scaler.transform(X)
        X_pca = self.pca_model.transform(X_scaled)
        
        # Get anomaly scores from each model
        scores = pd.DataFrame()
        scores['isolation_forest_score'] = self.models['isolation_forest'].score_samples(X_scaled)
        scores['lof_score'] = self.models['lof'].score_samples(X_scaled)
        scores['isolation_forest_pca_score'] = self.models['isolation_forest_pca'].score_samples(X_pca)
        
        # Normalize scores to [0, 1] where 1 is most anomalous
        for col in scores.columns:
            scores[col] = 1 - (scores[col] - scores[col].min()) / (scores[col].max() - scores[col].min())
        
        # Calculate ensemble score
        scores['ensemble_score'] = scores.mean(axis=1)
        
        # Apply rule-based detection
        rule_violations = []
        for idx, row in df.iterrows():
            violations = []
            for rule in self.anomaly_rules:
                if rule['condition'](row):
                    violations.append({
                        'rule': rule['name'],
                        'severity': rule['severity'],
                        'description': rule['description']
                    })
            rule_violations.append(violations)
        
        scores['rule_violations'] = rule_violations
        scores['n_rule_violations'] = scores['rule_violations'].apply(len)
        
        # Calculate final anomaly score
        scores['anomaly_score'] = scores['ensemble_score'] * 0.7 + (scores['n_rule_violations'] / 10) * 0.3
        scores['anomaly_score'] = scores['anomaly_score'].clip(0, 1)
        
        # Determine anomaly level
        conditions = [
            (scores['anomaly_score'] < 0.3),
            (scores['anomaly_score'] < 0.5),
            (scores['anomaly_score'] < 0.7),
            (scores['anomaly_score'] >= 0.7)
        ]
        choices = ['normal', 'low_risk', 'medium_risk', 'high_risk']
        scores['risk_level'] = np.select(conditions, choices)
        
        # Add original data columns
        result = pd.concat([
            df[['user_id', 'timestamp', 'amount', 'transaction_type']],
            scores
        ], axis=1)
        
        return result
    
    def explain_anomaly(self, data_point: pd.Series) -> Dict[str, Any]:
        """
        Provide detailed explanation for why a transaction is anomalous
        """
        df = pd.DataFrame([data_point]).reset_index(drop=True)
        scores = self.get_anomaly_scores(df).iloc[0]
        
        explanation = {
            'anomaly_score': scores['anomaly_score'],
            'risk_level': scores['risk_level'],
            'model_scores': {
                'isolation_forest': scores['isolation_forest_score'],
                'local_outlier_factor': scores['lof_score'],
                'isolation_forest_pca': scores['isolation_forest_pca_score']
            },
            'rule_violations': scores['rule_violations'],
            'contributing_factors': []
        }
        
        # Identify contributing factors
        if data_point.get('amount_z_score', 0) > 3:
            explanation['contributing_factors'].append({
                'factor': 'unusual_amount',
                'detail': f"Amount is {data_point['amount_z_score']:.1f} standard deviations from user average"
            })
        
        if data_point.get('transactions_1h', 0) > 10:
            explanation['contributing_factors'].append({
                'factor': 'high_frequency',
                'detail': f"{int(data_point['transactions_1h'])} transactions in the last hour"
            })
        
        if data_point.get('location_changed', 0) == 1:
            explanation['contributing_factors'].append({
                'factor': 'location_change',
                'detail': "Transaction from different location than previous"
            })
        
        return explanation
    
    def evaluate(self, data: pd.DataFrame, y_true: np.ndarray) -> Dict[str, float]:
        """Evaluate model performance"""
        y_pred = self.predict(data)
        
        # Calculate metrics
        tp = np.sum((y_true == 1) & (y_pred == 1))
        tn = np.sum((y_true == 0) & (y_pred == 0))
        fp = np.sum((y_true == 0) & (y_pred == 1))
        fn = np.sum((y_true == 1) & (y_pred == 0))
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'true_positives': int(tp),
            'true_negatives': int(tn),
            'false_positives': int(fp),
            'false_negatives': int(fn),
            'total_anomalies_detected': int(np.sum(y_pred)),
            'total_true_anomalies': int(np.sum(y_true))
        }