"""
Revenue forecasting using time series analysis.
"""
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error, r2_score
import logging
import json
import joblib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.ml_analytics.models import (
    MLModel, Prediction, ModelTrainingJob,
    PredictionType, ModelStatus
)
from core.domain.models import Transaction

logger = logging.getLogger(__name__)


class RevenueForecastPredictor:
    """Revenue forecasting using Facebook Prophet."""
    
    def __init__(self):
        self.model = None
        self.model_metadata = None
        self.feature_columns = [
            'ds',  # Date
            'y',   # Revenue
            'day_of_week',
            'month',
            'quarter',
            'is_weekend',
            'is_month_start',
            'is_month_end'
        ]
    
    async def train(
        self,
        agency_id: str,
        session: AsyncSession,
        lookback_days: int = 365,
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """Train revenue forecasting model."""
        logger.info(f"Training revenue forecast model for agency {agency_id}")
        
        # Fetch historical revenue data
        df = await self._fetch_revenue_data(agency_id, session, lookback_days)
        
        if len(df) < 30:
            raise ValueError("Insufficient data for training (need at least 30 days)")
        
        # Prepare features
        df = self._prepare_features(df)
        
        # Split data
        split_date = df['ds'].max() - timedelta(days=int(len(df) * test_size))
        train_df = df[df['ds'] <= split_date]
        test_df = df[df['ds'] > split_date]
        
        # Initialize and train Prophet model
        self.model = Prophet(
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=True,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10
        )
        
        # Add custom seasonalities
        self.model.add_seasonality(name='monthly', period=30.5, fourier_order=5)
        self.model.add_seasonality(name='quarterly', period=91.25, fourier_order=3)
        
        # Add regressors
        for col in ['is_weekend', 'is_month_start', 'is_month_end']:
            if col in train_df.columns:
                self.model.add_regressor(col)
        
        # Fit model
        self.model.fit(train_df)
        
        # Evaluate on test set
        metrics = await self._evaluate_model(test_df)
        
        # Store model metadata
        self.model_metadata = {
            'agency_id': agency_id,
            'training_samples': len(train_df),
            'test_samples': len(test_df),
            'training_period': {
                'start': train_df['ds'].min().isoformat(),
                'end': train_df['ds'].max().isoformat()
            },
            'metrics': metrics,
            'features': list(train_df.columns),
            'trained_at': datetime.utcnow().isoformat()
        }
        
        return {
            'success': True,
            'metrics': metrics,
            'training_samples': len(train_df),
            'model_metadata': self.model_metadata
        }
    
    async def predict(
        self,
        horizon_days: int = 30,
        include_history: bool = False
    ) -> pd.DataFrame:
        """Generate revenue forecasts."""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        # Create future dataframe
        future = self.model.make_future_dataframe(
            periods=horizon_days,
            include_history=include_history
        )
        
        # Add regressor features
        future = self._add_regressor_features(future)
        
        # Generate forecast
        forecast = self.model.predict(future)
        
        # Select relevant columns
        forecast_df = forecast[[
            'ds', 'yhat', 'yhat_lower', 'yhat_upper',
            'trend', 'weekly', 'yearly'
        ]].copy()
        
        # Rename columns
        forecast_df.columns = [
            'date', 'forecast', 'lower_bound', 'upper_bound',
            'trend', 'weekly_seasonality', 'yearly_seasonality'
        ]
        
        # Add metadata
        forecast_df['confidence_interval'] = forecast_df['upper_bound'] - forecast_df['lower_bound']
        forecast_df['prediction_date'] = datetime.utcnow()
        
        return forecast_df
    
    async def predict_specific_dates(
        self,
        dates: List[datetime]
    ) -> List[Dict[str, Any]]:
        """Predict revenue for specific dates."""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        # Create dataframe with specific dates
        future = pd.DataFrame({'ds': dates})
        future = self._add_regressor_features(future)
        
        # Generate predictions
        forecast = self.model.predict(future)
        
        # Format results
        predictions = []
        for idx, row in forecast.iterrows():
            predictions.append({
                'date': row['ds'].isoformat(),
                'predicted_revenue': float(row['yhat']),
                'lower_bound': float(row['yhat_lower']),
                'upper_bound': float(row['yhat_upper']),
                'confidence_score': 1 - (row['yhat_upper'] - row['yhat_lower']) / (2 * row['yhat'])
            })
        
        return predictions
    
    async def analyze_trends(
        self,
        df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """Analyze revenue trends and patterns."""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        # Get forecast data
        if df is None:
            df = await self.predict(horizon_days=90, include_history=True)
        
        # Calculate trend metrics
        recent_trend = df.tail(30)['trend'].mean()
        previous_trend = df.iloc[-60:-30]['trend'].mean()
        trend_change = ((recent_trend - previous_trend) / previous_trend) * 100
        
        # Identify seasonality patterns
        weekly_pattern = self._analyze_weekly_pattern(df)
        monthly_pattern = self._analyze_monthly_pattern(df)
        
        # Detect anomalies
        anomalies = self._detect_anomalies(df)
        
        return {
            'trend_analysis': {
                'current_trend': recent_trend,
                'trend_change_percentage': trend_change,
                'trend_direction': 'increasing' if trend_change > 0 else 'decreasing'
            },
            'seasonality': {
                'weekly_pattern': weekly_pattern,
                'monthly_pattern': monthly_pattern,
                'best_days': self._get_best_days(weekly_pattern),
                'best_periods': self._get_best_periods(monthly_pattern)
            },
            'anomalies': anomalies,
            'insights': self._generate_insights(trend_change, weekly_pattern, anomalies)
        }
    
    def save_model(self, path: str):
        """Save trained model to disk."""
        if self.model is None:
            raise ValueError("No model to save")
        
        joblib.dump({
            'model': self.model,
            'metadata': self.model_metadata,
            'version': '1.0'
        }, path)
    
    def load_model(self, path: str):
        """Load trained model from disk."""
        data = joblib.load(path)
        self.model = data['model']
        self.model_metadata = data['metadata']
    
    async def _fetch_revenue_data(
        self,
        agency_id: str,
        session: AsyncSession,
        lookback_days: int
    ) -> pd.DataFrame:
        """Fetch historical revenue data."""
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Query daily revenue
        query = select(
            func.date_trunc('day', Transaction.created_at).label('date'),
            func.sum(Transaction.amount).label('revenue'),
            func.count(Transaction.id).label('transaction_count')
        ).where(
            Transaction.agency_id == agency_id,
            Transaction.status == 'completed',
            Transaction.created_at >= cutoff_date
        ).group_by(
            func.date_trunc('day', Transaction.created_at)
        ).order_by('date')
        
        result = await session.execute(query)
        rows = result.fetchall()
        
        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'ds': row.date,
                'y': float(row.revenue or 0),
                'transaction_count': row.transaction_count
            }
            for row in rows
        ])
        
        # Fill missing dates with 0
        if not df.empty:
            date_range = pd.date_range(
                start=df['ds'].min(),
                end=df['ds'].max(),
                freq='D'
            )
            df = df.set_index('ds').reindex(date_range, fill_value=0).reset_index()
            df.columns = ['ds', 'y', 'transaction_count']
        
        return df
    
    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for Prophet model."""
        df = df.copy()
        
        # Add time-based features
        df['day_of_week'] = df['ds'].dt.dayofweek
        df['month'] = df['ds'].dt.month
        df['quarter'] = df['ds'].dt.quarter
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        df['is_month_start'] = (df['ds'].dt.day <= 3).astype(int)
        df['is_month_end'] = (df['ds'].dt.day >= 28).astype(int)
        
        # Handle outliers
        df = self._handle_outliers(df)
        
        # Log transform for better predictions
        df['y'] = np.log1p(df['y'])
        
        return df
    
    def _add_regressor_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add regressor features to future dataframe."""
        df = df.copy()
        
        df['day_of_week'] = df['ds'].dt.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        df['is_month_start'] = (df['ds'].dt.day <= 3).astype(int)
        df['is_month_end'] = (df['ds'].dt.day >= 28).astype(int)
        
        return df
    
    def _handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle outliers in revenue data."""
        # Calculate IQR
        Q1 = df['y'].quantile(0.25)
        Q3 = df['y'].quantile(0.75)
        IQR = Q3 - Q1
        
        # Define bounds
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        # Cap outliers
        df.loc[df['y'] < lower_bound, 'y'] = lower_bound
        df.loc[df['y'] > upper_bound, 'y'] = upper_bound
        
        return df
    
    async def _evaluate_model(self, test_df: pd.DataFrame) -> Dict[str, float]:
        """Evaluate model performance on test set."""
        # Generate predictions for test period
        forecast = self.model.predict(test_df)
        
        # Transform back from log scale
        y_true = np.expm1(test_df['y'].values)
        y_pred = np.expm1(forecast['yhat'].values)
        
        # Calculate metrics
        mape = mean_absolute_percentage_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        r2 = r2_score(y_true, y_pred)
        
        # Calculate coverage of prediction intervals
        coverage = np.mean(
            (y_true >= np.expm1(forecast['yhat_lower'].values)) &
            (y_true <= np.expm1(forecast['yhat_upper'].values))
        )
        
        return {
            'mape': float(mape),
            'rmse': float(rmse),
            'r2': float(r2),
            'coverage': float(coverage),
            'mean_absolute_error': float(np.mean(np.abs(y_true - y_pred)))
        }
    
    def _analyze_weekly_pattern(self, df: pd.DataFrame) -> Dict[str, float]:
        """Analyze weekly revenue patterns."""
        if 'date' in df.columns:
            df['day_of_week'] = pd.to_datetime(df['date']).dt.dayofweek
        elif 'ds' in df.columns:
            df['day_of_week'] = df['ds'].dt.dayofweek
        
        # Calculate average revenue by day of week
        weekly_avg = df.groupby('day_of_week')['forecast'].mean()
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return {days[i]: float(weekly_avg.get(i, 0)) for i in range(7)}
    
    def _analyze_monthly_pattern(self, df: pd.DataFrame) -> Dict[str, float]:
        """Analyze monthly revenue patterns."""
        if 'date' in df.columns:
            df['day_of_month'] = pd.to_datetime(df['date']).dt.day
        elif 'ds' in df.columns:
            df['day_of_month'] = df['ds'].dt.day
        
        # Group by day of month
        monthly_pattern = df.groupby('day_of_month')['forecast'].mean()
        
        return {
            'start_of_month': float(monthly_pattern[1:7].mean()),
            'mid_month': float(monthly_pattern[14:21].mean()),
            'end_of_month': float(monthly_pattern[25:].mean())
        }
    
    def _detect_anomalies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect anomalies in revenue data."""
        anomalies = []
        
        if 'forecast' in df.columns and 'lower_bound' in df.columns:
            # Find points outside prediction intervals
            outliers = df[
                (df.get('actual', df['forecast']) < df['lower_bound']) |
                (df.get('actual', df['forecast']) > df['upper_bound'])
            ]
            
            for _, row in outliers.iterrows():
                anomalies.append({
                    'date': row.get('date', row.get('ds')).isoformat(),
                    'expected': float(row['forecast']),
                    'actual': float(row.get('actual', row['forecast'])),
                    'deviation': float(abs(row.get('actual', row['forecast']) - row['forecast'])),
                    'type': 'above_expected' if row.get('actual', row['forecast']) > row['forecast'] else 'below_expected'
                })
        
        return anomalies
    
    def _get_best_days(self, weekly_pattern: Dict[str, float]) -> List[str]:
        """Get best performing days of the week."""
        sorted_days = sorted(weekly_pattern.items(), key=lambda x: x[1], reverse=True)
        return [day for day, _ in sorted_days[:3]]
    
    def _get_best_periods(self, monthly_pattern: Dict[str, float]) -> List[str]:
        """Get best performing periods of the month."""
        sorted_periods = sorted(monthly_pattern.items(), key=lambda x: x[1], reverse=True)
        return [period for period, _ in sorted_periods]
    
    def _generate_insights(self, trend_change: float, weekly_pattern: Dict[str, float], anomalies: List) -> List[str]:
        """Generate actionable insights."""
        insights = []
        
        # Trend insights
        if abs(trend_change) > 10:
            direction = "increasing" if trend_change > 0 else "decreasing"
            insights.append(f"Revenue trend is {direction} by {abs(trend_change):.1f}% over the last 30 days")
        
        # Weekly pattern insights
        best_day = max(weekly_pattern.items(), key=lambda x: x[1])[0]
        worst_day = min(weekly_pattern.items(), key=lambda x: x[1])[0]
        insights.append(f"{best_day} typically has the highest revenue")
        insights.append(f"Consider promotions on {worst_day} to boost revenue")
        
        # Anomaly insights
        if anomalies:
            recent_anomalies = [a for a in anomalies if (datetime.now() - datetime.fromisoformat(a['date'])).days < 30]
            if recent_anomalies:
                insights.append(f"Detected {len(recent_anomalies)} unusual revenue days in the past month")
        
        return insights
