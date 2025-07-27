"""
Time series calculations for analytics.

Provides advanced time series analysis including trends, 
forecasting, seasonality detection, and growth calculations.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import numpy as np
from scipy import stats
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import pandas as pd

from modules.analytics.domain.schemas import (
    TimeSeriesData,
    TrendAnalysis,
    Forecast,
    SeasonalPattern,
    GrowthMetrics
)


logger = logging.getLogger(__name__)


class TimeSeriesCalculator:
    """Performs time series calculations and analysis."""
    
    def __init__(self):
        """Initialize calculator."""
        pass
        
    def calculate_trend(
        self,
        data: List[TimeSeriesData],
        confidence_level: float = 0.95
    ) -> TrendAnalysis:
        """
        Calculate trend analysis for time series data.
        
        Args:
            data: Time series data points
            confidence_level: Confidence level for trend calculation
            
        Returns:
            Trend analysis results
        """
        if len(data) < 2:
            return TrendAnalysis(
                direction='neutral',
                slope=0.0,
                r_squared=0.0,
                confidence_interval=(0.0, 0.0)
            )
            
        # Extract values and timestamps
        values = [float(d.value) for d in data]
        timestamps = [d.timestamp.timestamp() for d in data]
        
        # Calculate linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(timestamps, values)
        
        # Determine trend direction
        if p_value < (1 - confidence_level):
            direction = 'increasing' if slope > 0 else 'decreasing'
        else:
            direction = 'neutral'
            
        # Calculate confidence interval
        t_stat = stats.t.ppf((1 + confidence_level) / 2, len(data) - 2)
        margin_of_error = t_stat * std_err
        confidence_interval = (slope - margin_of_error, slope + margin_of_error)
        
        # Calculate trend strength (normalized)
        if len(values) > 0 and max(values) != min(values):
            trend_strength = abs(slope) / (max(values) - min(values))
        else:
            trend_strength = 0.0
            
        return TrendAnalysis(
            direction=direction,
            slope=slope,
            r_squared=r_value ** 2,
            confidence_interval=confidence_interval,
            trend_strength=trend_strength,
            p_value=p_value
        )
        
    def calculate_growth_rate(
        self,
        data: List[TimeSeriesData],
        period: str = 'daily'
    ) -> GrowthMetrics:
        """
        Calculate various growth rate metrics.
        
        Args:
            data: Time series data points
            period: Period for growth calculation
            
        Returns:
            Growth metrics
        """
        if len(data) < 2:
            return GrowthMetrics(
                absolute_growth=0.0,
                percentage_growth=0.0,
                compound_growth_rate=0.0,
                average_growth_rate=0.0
            )
            
        values = [float(d.value) for d in data]
        
        # Absolute growth
        absolute_growth = values[-1] - values[0]
        
        # Percentage growth
        percentage_growth = 0.0
        if values[0] != 0:
            percentage_growth = ((values[-1] - values[0]) / values[0]) * 100
            
        # Compound Annual Growth Rate (CAGR)
        periods = len(data) - 1
        if periods > 0 and values[0] > 0:
            cagr = (pow(values[-1] / values[0], 1 / periods) - 1) * 100
        else:
            cagr = 0.0
            
        # Average growth rate
        growth_rates = []
        for i in range(1, len(values)):
            if values[i-1] != 0:
                rate = ((values[i] - values[i-1]) / values[i-1]) * 100
                growth_rates.append(rate)
                
        avg_growth = np.mean(growth_rates) if growth_rates else 0.0
        
        # Period-over-period growth
        pop_growth = {}
        if period == 'daily' and len(data) > 1:
            pop_growth['day_over_day'] = growth_rates[-1] if growth_rates else 0.0
        elif period == 'weekly' and len(data) > 7:
            week_ago_value = values[-8] if len(values) > 7 else values[0]
            if week_ago_value != 0:
                pop_growth['week_over_week'] = ((values[-1] - week_ago_value) / week_ago_value) * 100
        elif period == 'monthly' and len(data) > 30:
            month_ago_value = values[-31] if len(values) > 30 else values[0]
            if month_ago_value != 0:
                pop_growth['month_over_month'] = ((values[-1] - month_ago_value) / month_ago_value) * 100
                
        return GrowthMetrics(
            absolute_growth=absolute_growth,
            percentage_growth=percentage_growth,
            compound_growth_rate=cagr,
            average_growth_rate=avg_growth,
            period_over_period=pop_growth
        )
        
    def calculate_moving_average(
        self,
        data: List[TimeSeriesData],
        window: int = 7,
        method: str = 'simple'
    ) -> List[TimeSeriesData]:
        """
        Calculate moving average for smoothing.
        
        Args:
            data: Time series data points
            window: Window size for moving average
            method: Type of moving average ('simple', 'exponential', 'weighted')
            
        Returns:
            Smoothed time series data
        """
        if len(data) < window:
            return data
            
        values = [float(d.value) for d in data]
        timestamps = [d.timestamp for d in data]
        
        if method == 'simple':
            # Simple Moving Average
            ma_values = []
            for i in range(len(values)):
                if i < window - 1:
                    ma_values.append(values[i])
                else:
                    ma_values.append(np.mean(values[i-window+1:i+1]))
                    
        elif method == 'exponential':
            # Exponential Moving Average
            alpha = 2 / (window + 1)
            ma_values = [values[0]]
            for i in range(1, len(values)):
                ema = alpha * values[i] + (1 - alpha) * ma_values[-1]
                ma_values.append(ema)
                
        elif method == 'weighted':
            # Weighted Moving Average
            weights = np.arange(1, window + 1)
            ma_values = []
            for i in range(len(values)):
                if i < window - 1:
                    ma_values.append(values[i])
                else:
                    window_values = values[i-window+1:i+1]
                    weighted_avg = np.average(window_values, weights=weights)
                    ma_values.append(weighted_avg)
        else:
            ma_values = values
            
        # Create smoothed time series
        smoothed_data = []
        for i, (timestamp, value) in enumerate(zip(timestamps, ma_values)):
            smoothed_data.append(
                TimeSeriesData(
                    timestamp=timestamp,
                    value=value,
                    metadata={'method': method, 'window': window}
                )
            )
            
        return smoothed_data
        
    def forecast(
        self,
        data: List[TimeSeriesData],
        periods: int = 7,
        method: str = 'holt_winters',
        seasonality: Optional[int] = None
    ) -> Forecast:
        """
        Generate forecast for future periods.
        
        Args:
            data: Historical time series data
            periods: Number of periods to forecast
            method: Forecasting method ('linear', 'holt_winters', 'arima')
            seasonality: Seasonal period (e.g., 7 for weekly)
            
        Returns:
            Forecast results
        """
        if len(data) < 3:
            # Not enough data for forecasting
            return Forecast(
                predictions=[],
                confidence_intervals=[],
                method=method,
                accuracy_metrics={}
            )
            
        values = [float(d.value) for d in data]
        
        # Create pandas series for easier manipulation
        dates = pd.date_range(
            start=data[0].timestamp,
            periods=len(data),
            freq='D'  # Assuming daily data
        )
        ts = pd.Series(values, index=dates)
        
        predictions = []
        confidence_intervals = []
        
        if method == 'linear':
            # Simple linear extrapolation
            x = np.arange(len(values))
            slope, intercept = np.polyfit(x, values, 1)
            
            for i in range(periods):
                pred_value = slope * (len(values) + i) + intercept
                predictions.append(max(0, pred_value))  # Ensure non-negative
                
                # Simple confidence interval based on historical variance
                std_dev = np.std(values)
                confidence_intervals.append((
                    max(0, pred_value - 1.96 * std_dev),
                    pred_value + 1.96 * std_dev
                ))
                
        elif method == 'holt_winters':
            try:
                # Exponential smoothing with trend and seasonality
                if seasonality and len(values) >= 2 * seasonality:
                    model = ExponentialSmoothing(
                        ts,
                        seasonal_periods=seasonality,
                        trend='add',
                        seasonal='add'
                    )
                else:
                    # No seasonality or insufficient data
                    model = ExponentialSmoothing(
                        ts,
                        trend='add'
                    )
                    
                fit = model.fit()
                forecast = fit.forecast(periods)
                predictions = forecast.tolist()
                
                # Calculate prediction intervals
                residuals = ts - fit.fittedvalues
                std_error = np.std(residuals)
                
                for pred in predictions:
                    confidence_intervals.append((
                        max(0, pred - 1.96 * std_error),
                        pred + 1.96 * std_error
                    ))
                    
            except Exception as e:
                logger.error(f"Holt-Winters forecasting failed: {e}")
                # Fallback to linear
                return self.forecast(data, periods, 'linear')
                
        # Calculate accuracy metrics on historical data
        if len(values) > 10:
            # Use last 20% for validation
            split_point = int(len(values) * 0.8)
            train_data = data[:split_point]
            test_values = values[split_point:]
            
            # Generate predictions for test period
            test_forecast = self.forecast(
                train_data,
                len(test_values),
                method,
                seasonality
            )
            
            if test_forecast.predictions:
                # Calculate MAPE (Mean Absolute Percentage Error)
                mape = np.mean([
                    abs((actual - pred) / actual) * 100
                    for actual, pred in zip(test_values, test_forecast.predictions)
                    if actual != 0
                ])
                
                # Calculate RMSE
                rmse = np.sqrt(np.mean([
                    (actual - pred) ** 2
                    for actual, pred in zip(test_values, test_forecast.predictions)
                ]))
                
                accuracy_metrics = {
                    'mape': mape,
                    'rmse': rmse
                }
            else:
                accuracy_metrics = {}
        else:
            accuracy_metrics = {}
            
        # Generate future timestamps
        last_timestamp = data[-1].timestamp
        future_timestamps = [
            last_timestamp + timedelta(days=i+1)
            for i in range(periods)
        ]
        
        # Create forecast time series
        forecast_data = []
        for i, (timestamp, value, ci) in enumerate(
            zip(future_timestamps, predictions, confidence_intervals)
        ):
            forecast_data.append(
                TimeSeriesData(
                    timestamp=timestamp,
                    value=value,
                    metadata={
                        'is_forecast': True,
                        'confidence_interval': ci
                    }
                )
            )
            
        return Forecast(
            predictions=forecast_data,
            confidence_intervals=confidence_intervals,
            method=method,
            accuracy_metrics=accuracy_metrics
        )
        
    def detect_seasonality(
        self,
        data: List[TimeSeriesData],
        max_period: int = 30
    ) -> SeasonalPattern:
        """
        Detect seasonal patterns in time series data.
        
        Args:
            data: Time series data points
            max_period: Maximum period to check for seasonality
            
        Returns:
            Seasonal pattern analysis
        """
        if len(data) < max_period * 2:
            return SeasonalPattern(
                has_seasonality=False,
                period=None,
                strength=0.0,
                pattern=[]
            )
            
        values = np.array([float(d.value) for d in data])
        
        # Try different periods and find the best fit
        best_period = None
        best_strength = 0.0
        
        for period in range(2, min(max_period + 1, len(data) // 2)):
            try:
                # Use autocorrelation to detect periodicity
                autocorr = np.correlate(values, values, mode='full')
                autocorr = autocorr[len(autocorr)//2:]
                
                # Check correlation at this period
                if period < len(autocorr):
                    correlation = autocorr[period] / autocorr[0]
                    
                    if correlation > best_strength:
                        best_strength = correlation
                        best_period = period
                        
            except Exception as e:
                logger.debug(f"Seasonality detection failed for period {period}: {e}")
                
        # If strong seasonality found, extract pattern
        if best_strength > 0.5 and best_period:
            # Calculate average pattern
            pattern = []
            for i in range(best_period):
                period_values = [
                    values[j] for j in range(i, len(values), best_period)
                ]
                pattern.append(np.mean(period_values))
                
            # Normalize pattern
            pattern_mean = np.mean(pattern)
            if pattern_mean > 0:
                pattern = [p / pattern_mean for p in pattern]
                
            return SeasonalPattern(
                has_seasonality=True,
                period=best_period,
                strength=best_strength,
                pattern=pattern
            )
        else:
            return SeasonalPattern(
                has_seasonality=False,
                period=None,
                strength=0.0,
                pattern=[]
            )
            
    def decompose_time_series(
        self,
        data: List[TimeSeriesData],
        period: Optional[int] = None
    ) -> Dict[str, List[float]]:
        """
        Decompose time series into trend, seasonal, and residual components.
        
        Args:
            data: Time series data points
            period: Seasonal period (auto-detect if None)
            
        Returns:
            Dictionary with trend, seasonal, and residual components
        """
        if len(data) < 4:
            values = [float(d.value) for d in data]
            return {
                'trend': values,
                'seasonal': [0.0] * len(values),
                'residual': [0.0] * len(values)
            }
            
        values = [float(d.value) for d in data]
        
        # Create pandas series
        dates = pd.date_range(
            start=data[0].timestamp,
            periods=len(data),
            freq='D'
        )
        ts = pd.Series(values, index=dates)
        
        # Auto-detect period if not provided
        if not period:
            seasonal_result = self.detect_seasonality(data)
            period = seasonal_result.period if seasonal_result.has_seasonality else 7
            
        try:
            # Perform decomposition
            if len(data) >= 2 * period:
                decomposition = seasonal_decompose(
                    ts,
                    model='additive',
                    period=period,
                    extrapolate_trend='freq'
                )
                
                return {
                    'trend': decomposition.trend.fillna(method='bfill').fillna(method='ffill').tolist(),
                    'seasonal': decomposition.seasonal.fillna(0).tolist(),
                    'residual': decomposition.resid.fillna(0).tolist()
                }
            else:
                # Not enough data for decomposition
                return {
                    'trend': values,
                    'seasonal': [0.0] * len(values),
                    'residual': [0.0] * len(values)
                }
                
        except Exception as e:
            logger.error(f"Time series decomposition failed: {e}")
            return {
                'trend': values,
                'seasonal': [0.0] * len(values),
                'residual': [0.0] * len(values)
            }
            
    def calculate_volatility(
        self,
        data: List[TimeSeriesData],
        window: int = 30
    ) -> Dict[str, float]:
        """
        Calculate volatility metrics for time series.
        
        Args:
            data: Time series data points
            window: Rolling window for volatility calculation
            
        Returns:
            Volatility metrics
        """
        if len(data) < 2:
            return {
                'standard_deviation': 0.0,
                'coefficient_of_variation': 0.0,
                'rolling_volatility': []
            }
            
        values = [float(d.value) for d in data]
        
        # Standard deviation
        std_dev = np.std(values)
        
        # Coefficient of variation
        mean_value = np.mean(values)
        cv = (std_dev / mean_value * 100) if mean_value != 0 else 0.0
        
        # Rolling volatility
        rolling_vol = []
        for i in range(len(values)):
            if i < window - 1:
                rolling_vol.append(0.0)
            else:
                window_values = values[i-window+1:i+1]
                rolling_vol.append(np.std(window_values))
                
        return {
            'standard_deviation': std_dev,
            'coefficient_of_variation': cv,
            'rolling_volatility': rolling_vol,
            'mean': mean_value,
            'min': min(values),
            'max': max(values)
        }