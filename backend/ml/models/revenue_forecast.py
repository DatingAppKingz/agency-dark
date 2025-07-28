"""
Revenue Forecasting Model using Prophet and ensemble methods
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from .base import TimeSeriesModel


class RevenueForecastModel(TimeSeriesModel):
    """
    Advanced revenue forecasting model using ensemble methods
    Combines multiple approaches for robust predictions
    """
    
    def __init__(self, version: str = "1.0.0"):
        super().__init__("revenue_forecast", version)
        self.models = {}
        self.scaler = StandardScaler()
        self.forecast_horizon = 30  # days
        self.confidence_intervals = [0.80, 0.95]
        
    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess revenue data for training/prediction
        Expected columns: date, revenue, model_id (optional)
        """
        df = data.copy()
        
        # Ensure we have required columns
        if 'date' not in df.columns or 'revenue' not in df.columns:
            raise ValueError("Data must contain 'date' and 'revenue' columns")
        
        # Convert to datetime
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Handle missing values
        df['revenue'] = df['revenue'].fillna(0)
        
        # Create time series features
        df = self.create_features(df)
        
        # Add revenue-specific features
        df['revenue_log'] = np.log1p(df['revenue'])
        df['revenue_sqrt'] = np.sqrt(df['revenue'])
        
        # Moving averages specific to revenue
        df['revenue_ma7'] = df['revenue'].rolling(window=7, min_periods=1).mean()
        df['revenue_ma30'] = df['revenue'].rolling(window=30, min_periods=1).mean()
        
        # Growth rates
        df['daily_growth'] = df['revenue'].pct_change()
        df['weekly_growth'] = df['revenue'].pct_change(periods=7)
        df['monthly_growth'] = df['revenue'].pct_change(periods=30)
        
        # Seasonal decomposition features
        df['day_of_week_avg'] = df.groupby(df.index.dayofweek)['revenue'].transform('mean')
        df['month_avg'] = df.groupby(df.index.month)['revenue'].transform('mean')
        
        # Handle infinities and NaNs
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna(method='ffill').fillna(0)
        
        return df
    
    def train(self, data: pd.DataFrame, test_size: float = 0.2, **kwargs) -> Dict[str, Any]:
        """
        Train ensemble revenue forecasting model
        """
        # Preprocess data
        df = self.preprocess_data(data)
        
        # Define features to use
        feature_cols = [
            'day_of_week', 'day_of_month', 'month', 'quarter', 'year', 'is_weekend',
            'rolling_mean_7d', 'rolling_mean_14d', 'rolling_mean_30d',
            'rolling_std_7d', 'rolling_std_14d', 'rolling_std_30d',
            'lag_1d', 'lag_7d', 'lag_14d', 'lag_30d',
            'revenue_ma7', 'revenue_ma30',
            'day_of_week_avg', 'month_avg'
        ]
        
        # Remove any missing features
        feature_cols = [col for col in feature_cols if col in df.columns]
        self.feature_names = feature_cols
        
        # Prepare training data
        X = df[feature_cols].values
        y = df['revenue'].values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=test_size, shuffle=False
        )
        
        # Train multiple models
        self.models = {
            'rf': RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1
            ),
            'gbm': GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            ),
            'lr': LinearRegression()
        }
        
        # Train each model
        for name, model in self.models.items():
            model.fit(X_train, y_train)
        
        # Evaluate on test set
        predictions = self._ensemble_predict(X_test)
        metrics = self.evaluate(None, y_test, predictions)
        
        # Store training metadata
        self.training_metadata = {
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'features_used': feature_cols,
            'metrics': metrics,
            'training_date': datetime.now().isoformat(),
            'data_range': {
                'start': str(df.index.min()),
                'end': str(df.index.max())
            }
        }
        
        self.is_trained = True
        return self.training_metadata
    
    def _ensemble_predict(self, X: np.ndarray) -> np.ndarray:
        """Make ensemble predictions"""
        predictions = []
        weights = {'rf': 0.4, 'gbm': 0.4, 'lr': 0.2}
        
        for name, model in self.models.items():
            pred = model.predict(X)
            predictions.append(pred * weights[name])
        
        return np.sum(predictions, axis=0)
    
    def predict(self, data: pd.DataFrame) -> np.ndarray:
        """Make revenue predictions"""
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        df = self.preprocess_data(data)
        X = df[self.feature_names].values
        X_scaled = self.scaler.transform(X)
        
        return self._ensemble_predict(X_scaled)
    
    def forecast(self, 
                 historical_data: pd.DataFrame, 
                 periods: int = 30,
                 include_confidence: bool = True) -> pd.DataFrame:
        """
        Generate future revenue forecasts
        
        Args:
            historical_data: Historical revenue data
            periods: Number of days to forecast
            include_confidence: Include confidence intervals
            
        Returns:
            DataFrame with forecasts and confidence intervals
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before forecasting")
        
        # Prepare historical data
        df = self.preprocess_data(historical_data)
        last_date = df.index.max()
        
        # Generate future dates
        future_dates = pd.date_range(
            start=last_date + timedelta(days=1),
            periods=periods,
            freq='D'
        )
        
        # Create future dataframe
        future_df = pd.DataFrame(index=future_dates)
        future_df['revenue'] = 0  # Placeholder
        
        # Use last known values for initialization
        last_revenue = df['revenue'].iloc[-1]
        future_df['revenue'] = last_revenue
        
        forecasts = []
        
        # Iteratively forecast
        for i in range(periods):
            # Combine historical and forecasted data
            combined_df = pd.concat([df, future_df.iloc[:i+1]])
            combined_df = self.preprocess_data(combined_df)
            
            # Get features for prediction
            X = combined_df[self.feature_names].iloc[-1:].values
            X_scaled = self.scaler.transform(X)
            
            # Make prediction
            pred = self._ensemble_predict(X_scaled)[0]
            forecasts.append(pred)
            
            # Update future dataframe
            if i < periods - 1:
                future_df.iloc[i+1, future_df.columns.get_loc('revenue')] = pred
        
        # Create results dataframe
        results = pd.DataFrame({
            'date': future_dates,
            'forecast': forecasts
        })
        
        if include_confidence:
            # Calculate prediction intervals based on historical errors
            historical_predictions = self.predict(df)
            errors = df['revenue'].values - historical_predictions
            std_error = np.std(errors)
            
            for confidence in self.confidence_intervals:
                z_score = 1.96 if confidence == 0.95 else 1.28
                results[f'lower_{int(confidence*100)}'] = results['forecast'] - z_score * std_error
                results[f'upper_{int(confidence*100)}'] = results['forecast'] + z_score * std_error
            
            # Ensure non-negative forecasts
            for col in results.columns:
                if col != 'date':
                    results[col] = results[col].clip(lower=0)
        
        return results
    
    def evaluate(self, data: Optional[pd.DataFrame], y_true: np.ndarray, 
                 y_pred: Optional[np.ndarray] = None) -> Dict[str, float]:
        """Evaluate model performance"""
        if y_pred is None and data is not None:
            y_pred = self.predict(data)
        
        mae = mean_absolute_error(y_true, y_pred)
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_true, y_pred)
        mape = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100
        
        return {
            'mae': float(mae),
            'mse': float(mse),
            'rmse': float(rmse),
            'r2': float(r2),
            'mape': float(mape)
        }
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get aggregated feature importance across models"""
        if not self.is_trained:
            return {}
        
        importance_dict = {}
        
        # Get importance from tree-based models
        for name in ['rf', 'gbm']:
            if name in self.models:
                model = self.models[name]
                importances = model.feature_importances_
                for feat, imp in zip(self.feature_names, importances):
                    if feat not in importance_dict:
                        importance_dict[feat] = 0
                    importance_dict[feat] += imp
        
        # Normalize
        total = sum(importance_dict.values())
        if total > 0:
            importance_dict = {k: v/total for k, v in importance_dict.items()}
        
        # Sort by importance
        return dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))
    
    def detect_anomalies(self, data: pd.DataFrame, threshold: float = 3.0) -> pd.DataFrame:
        """
        Detect revenue anomalies using prediction errors
        
        Args:
            data: Revenue data to check
            threshold: Number of standard deviations for anomaly detection
            
        Returns:
            DataFrame with anomaly indicators
        """
        df = data.copy()
        predictions = self.predict(df)
        
        # Calculate residuals
        residuals = df['revenue'].values - predictions
        
        # Calculate z-scores
        mean_residual = np.mean(residuals)
        std_residual = np.std(residuals)
        z_scores = np.abs((residuals - mean_residual) / (std_residual + 1e-8))
        
        # Flag anomalies
        df['predicted_revenue'] = predictions
        df['residual'] = residuals
        df['z_score'] = z_scores
        df['is_anomaly'] = z_scores > threshold
        df['anomaly_severity'] = pd.cut(
            z_scores, 
            bins=[0, 2, 3, 5, np.inf],
            labels=['normal', 'mild', 'moderate', 'severe']
        )
        
        return df