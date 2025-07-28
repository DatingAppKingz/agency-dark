"""
Churn Prediction Model for subscriber retention
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, 
    roc_auc_score, confusion_matrix, classification_report
)
import xgboost as xgb

from .base import ClassificationModel


class ChurnPredictionModel(ClassificationModel):
    """
    Advanced churn prediction model for identifying at-risk subscribers
    """
    
    def __init__(self, version: str = "1.0.0"):
        super().__init__("churn_prediction", version)
        self.scaler = StandardScaler()
        self.churn_window = 30  # Days to consider for churn
        self.models = {}
        
    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess subscriber data for churn prediction
        
        Expected columns:
        - subscriber_id
        - subscription_date
        - last_active_date
        - total_spent
        - message_count
        - content_views
        - login_frequency
        - days_since_last_activity
        """
        df = data.copy()
        
        # Calculate derived features
        if 'subscription_date' in df.columns and 'last_active_date' in df.columns:
            df['subscription_date'] = pd.to_datetime(df['subscription_date'])
            df['last_active_date'] = pd.to_datetime(df['last_active_date'])
            
            # Subscription duration
            df['subscription_days'] = (df['last_active_date'] - df['subscription_date']).dt.days
            
            # Activity patterns
            df['avg_daily_spend'] = df['total_spent'] / (df['subscription_days'] + 1)
            df['avg_daily_messages'] = df['message_count'] / (df['subscription_days'] + 1)
            df['avg_daily_content_views'] = df['content_views'] / (df['subscription_days'] + 1)
        
        # Engagement metrics
        df['engagement_score'] = (
            df['message_count'].fillna(0) * 0.3 +
            df['content_views'].fillna(0) * 0.3 +
            df['login_frequency'].fillna(0) * 0.4
        )
        
        # Monetary features
        df['spend_per_message'] = df['total_spent'] / (df['message_count'] + 1)
        df['spend_per_view'] = df['total_spent'] / (df['content_views'] + 1)
        
        # Recency features
        df['days_inactive'] = df['days_since_last_activity'].fillna(999)
        df['is_recently_active'] = (df['days_inactive'] <= 7).astype(int)
        df['activity_decline'] = df['days_inactive'] / (df['subscription_days'] + 1)
        
        # Behavioral segments
        df['is_high_spender'] = (df['total_spent'] > df['total_spent'].quantile(0.75)).astype(int)
        df['is_active_messager'] = (df['message_count'] > df['message_count'].quantile(0.75)).astype(int)
        df['is_content_consumer'] = (df['content_views'] > df['content_views'].quantile(0.75)).astype(int)
        
        # Interaction patterns
        df['message_to_view_ratio'] = df['message_count'] / (df['content_views'] + 1)
        df['login_regularity'] = df['login_frequency'] / (df['subscription_days'] + 1)
        
        # Handle missing values
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        df[numeric_columns] = df[numeric_columns].fillna(0)
        
        # Remove infinite values
        df = df.replace([np.inf, -np.inf], 0)
        
        return df
    
    def create_churn_labels(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create churn labels based on inactivity period
        """
        df = data.copy()
        
        # Define churn: No activity in the last 30 days
        df['churned'] = (df['days_since_last_activity'] > self.churn_window).astype(int)
        
        # Create churn risk categories
        conditions = [
            (df['days_since_last_activity'] <= 7),
            (df['days_since_last_activity'] <= 14),
            (df['days_since_last_activity'] <= 30),
            (df['days_since_last_activity'] > 30)
        ]
        choices = ['active', 'at_risk_low', 'at_risk_high', 'churned']
        df['churn_risk_category'] = np.select(conditions, choices, default='unknown')
        
        return df
    
    def train(self, data: pd.DataFrame, test_size: float = 0.2, **kwargs) -> Dict[str, Any]:
        """
        Train churn prediction model
        """
        # Preprocess data
        df = self.preprocess_data(data)
        df = self.create_churn_labels(df)
        
        # Define features to use
        feature_cols = [
            'subscription_days', 'total_spent', 'message_count', 'content_views',
            'login_frequency', 'days_inactive', 'avg_daily_spend', 'avg_daily_messages',
            'avg_daily_content_views', 'engagement_score', 'spend_per_message',
            'spend_per_view', 'is_recently_active', 'activity_decline',
            'is_high_spender', 'is_active_messager', 'is_content_consumer',
            'message_to_view_ratio', 'login_regularity'
        ]
        
        # Filter to existing columns
        feature_cols = [col for col in feature_cols if col in df.columns]
        self.feature_names = feature_cols
        
        # Prepare data
        X = df[feature_cols].values
        y = df['churned'].values
        
        # Calculate class weights
        self.class_weights = self.calculate_class_weights(y)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=test_size, random_state=42, stratify=y
        )
        
        # Train multiple models
        self.models = {
            'rf': RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                class_weight=self.class_weights,
                random_state=42,
                n_jobs=-1
            ),
            'gbm': GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            ),
            'xgb': xgb.XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                scale_pos_weight=self.class_weights[1]/self.class_weights[0],
                random_state=42,
                use_label_encoder=False,
                eval_metric='logloss'
            ),
            'lr': LogisticRegression(
                class_weight=self.class_weights,
                max_iter=1000,
                random_state=42
            )
        }
        
        # Train and evaluate each model
        model_scores = {}
        for name, model in self.models.items():
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            y_proba = model.predict_proba(X_test)[:, 1]
            
            model_scores[name] = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred),
                'recall': recall_score(y_test, y_pred),
                'f1': f1_score(y_test, y_pred),
                'roc_auc': roc_auc_score(y_test, y_proba)
            }
        
        # Select best model based on F1 score
        best_model = max(model_scores.items(), key=lambda x: x[1]['f1'])[0]
        self.model = self.models[best_model]
        
        # Store training metadata
        self.training_metadata = {
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'features_used': feature_cols,
            'class_distribution': {
                'not_churned': int(sum(y_train == 0)),
                'churned': int(sum(y_train == 1))
            },
            'model_scores': model_scores,
            'best_model': best_model,
            'training_date': datetime.now().isoformat()
        }
        
        self.is_trained = True
        self.classes_ = np.array([0, 1])
        
        return self.training_metadata
    
    def predict(self, data: pd.DataFrame) -> np.ndarray:
        """Predict churn for new data"""
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        df = self.preprocess_data(data)
        X = df[self.feature_names].values
        X_scaled = self.scaler.transform(X)
        
        return self.model.predict(X_scaled)
    
    def predict_proba(self, data: pd.DataFrame) -> np.ndarray:
        """Predict churn probability"""
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        df = self.preprocess_data(data)
        X = df[self.feature_names].values
        X_scaled = self.scaler.transform(X)
        
        return self.model.predict_proba(X_scaled)
    
    def get_risk_scores(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Get detailed risk scores and recommendations
        """
        df = data.copy()
        
        # Get predictions
        churn_proba = self.predict_proba(df)[:, 1]
        
        # Add risk scores
        df['churn_probability'] = churn_proba
        df['churn_risk_score'] = (churn_proba * 100).round(1)
        
        # Risk categories
        conditions = [
            (churn_proba < 0.3),
            (churn_proba < 0.5),
            (churn_proba < 0.7),
            (churn_proba >= 0.7)
        ]
        choices = ['low', 'medium', 'high', 'critical']
        df['risk_level'] = np.select(conditions, choices)
        
        # Add recommendations
        df['recommended_action'] = df.apply(self._get_recommendation, axis=1)
        
        # Calculate potential revenue loss
        df['potential_revenue_loss'] = df['avg_daily_spend'] * 30 * df['churn_probability']
        
        return df[['subscriber_id', 'churn_probability', 'churn_risk_score', 
                   'risk_level', 'recommended_action', 'potential_revenue_loss']]
    
    def _get_recommendation(self, row: pd.Series) -> str:
        """Get personalized retention recommendations"""
        risk_score = row.get('churn_probability', 0)
        
        if risk_score < 0.3:
            return "Monitor - Low risk"
        elif risk_score < 0.5:
            if row.get('days_inactive', 0) > 7:
                return "Send engagement campaign"
            else:
                return "Offer loyalty rewards"
        elif risk_score < 0.7:
            if row.get('is_high_spender', 0):
                return "Personal outreach - VIP retention"
            else:
                return "Offer discount or special content"
        else:
            if row.get('total_spent', 0) > 100:
                return "Urgent: Direct contact + exclusive offer"
            else:
                return "Win-back campaign with incentive"
    
    def evaluate(self, data: pd.DataFrame, y_true: np.ndarray) -> Dict[str, float]:
        """Evaluate model performance"""
        y_pred = self.predict(data)
        y_proba = self.predict_proba(data)[:, 1]
        
        cm = confusion_matrix(y_true, y_pred)
        
        return {
            'accuracy': float(accuracy_score(y_true, y_pred)),
            'precision': float(precision_score(y_true, y_pred)),
            'recall': float(recall_score(y_true, y_pred)),
            'f1_score': float(f1_score(y_true, y_pred)),
            'roc_auc': float(roc_auc_score(y_true, y_proba)),
            'true_negatives': int(cm[0, 0]),
            'false_positives': int(cm[0, 1]),
            'false_negatives': int(cm[1, 0]),
            'true_positives': int(cm[1, 1])
        }
    
    def get_cohort_analysis(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Analyze churn patterns by cohort
        """
        df = self.preprocess_data(data)
        df = self.create_churn_labels(df)
        
        # Create cohorts based on subscription month
        df['subscription_month'] = pd.to_datetime(df['subscription_date']).dt.to_period('M')
        
        # Calculate cohort metrics
        cohort_analysis = df.groupby('subscription_month').agg({
            'subscriber_id': 'count',
            'churned': ['sum', 'mean'],
            'total_spent': 'mean',
            'subscription_days': 'mean'
        }).round(2)
        
        cohort_analysis.columns = ['total_subscribers', 'churned_count', 
                                  'churn_rate', 'avg_revenue', 'avg_lifetime']
        
        return cohort_analysis