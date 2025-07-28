"""
Advanced reporting service with complex analytics and insights
"""
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date, timedelta
from uuid import UUID
import pandas as pd
import numpy as np
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from modules.reporting.domain.models import CustomReport, ScheduledReport
from modules.analytics.domain.models import Analytics
from modules.messaging.domain.models import Message
from modules.payments.domain.models import Payment
from modules.fans.domain.models import Fan
from modules.models.domain.models import Model
from core.database import get_db
from core.logging import get_logger
from core.performance import cached, CacheKeyBuilder

logger = get_logger(__name__)


class AdvancedReportingService:
    """Service for advanced reporting and analytics"""
    
    @staticmethod
    @cached(ttl=3600, namespace="reports")
    async def generate_cohort_analysis(
        db: AsyncSession,
        agency_id: UUID,
        start_date: date,
        end_date: date,
        cohort_type: str = "monthly"
    ) -> Dict[str, Any]:
        """
        Generate cohort analysis report
        
        Args:
            db: Database session
            agency_id: Agency ID
            start_date: Start date for analysis
            end_date: End date for analysis
            cohort_type: Type of cohort (daily, weekly, monthly)
            
        Returns:
            Cohort analysis data
        """
        # Get fans with their first activity date
        fans_query = (
            select(
                Fan.id,
                Fan.created_at,
                Fan.model_id,
                func.min(Payment.created_at).label("first_payment_date")
            )
            .join(Model, Fan.model_id == Model.id)
            .outerjoin(Payment, Fan.id == Payment.fan_id)
            .where(
                and_(
                    Model.agency_id == agency_id,
                    Fan.created_at >= start_date,
                    Fan.created_at <= end_date
                )
            )
            .group_by(Fan.id, Fan.created_at, Fan.model_id)
        )
        
        result = await db.execute(fans_query)
        fans_data = result.all()
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(fans_data)
        
        if df.empty:
            return {"cohorts": [], "retention": {}}
        
        # Assign cohorts based on creation date
        if cohort_type == "monthly":
            df['cohort'] = pd.to_datetime(df['created_at']).dt.to_period('M')
        elif cohort_type == "weekly":
            df['cohort'] = pd.to_datetime(df['created_at']).dt.to_period('W')
        else:  # daily
            df['cohort'] = pd.to_datetime(df['created_at']).dt.date
        
        # Calculate retention for each cohort
        cohort_groups = df.groupby('cohort')
        retention_data = []
        
        for cohort, group in cohort_groups:
            cohort_size = len(group)
            retention_rates = {}
            
            # Calculate retention for different periods
            for period in range(0, 13):  # 0-12 periods
                if cohort_type == "monthly":
                    period_date = pd.Period(cohort).to_timestamp() + pd.DateOffset(months=period)
                elif cohort_type == "weekly":
                    period_date = pd.Period(cohort).to_timestamp() + pd.DateOffset(weeks=period)
                else:
                    period_date = pd.Timestamp(cohort) + pd.DateOffset(days=period)
                
                # Get active fans in this period
                active_query = (
                    select(func.count(distinct(Payment.fan_id)))
                    .where(
                        and_(
                            Payment.fan_id.in_(group['id'].tolist()),
                            Payment.created_at >= period_date,
                            Payment.created_at < period_date + timedelta(days=30)
                        )
                    )
                )
                
                active_count = await db.scalar(active_query)
                retention_rate = (active_count / cohort_size * 100) if cohort_size > 0 else 0
                retention_rates[f"period_{period}"] = round(retention_rate, 2)
            
            retention_data.append({
                "cohort": str(cohort),
                "size": cohort_size,
                "retention": retention_rates
            })
        
        # Calculate average retention curve
        avg_retention = {}
        for period in range(0, 13):
            period_key = f"period_{period}"
            rates = [c["retention"].get(period_key, 0) for c in retention_data]
            avg_retention[period_key] = round(np.mean(rates), 2) if rates else 0
        
        return {
            "cohorts": retention_data,
            "average_retention": avg_retention,
            "summary": {
                "total_cohorts": len(retention_data),
                "total_fans": len(df),
                "average_cohort_size": round(len(df) / len(retention_data), 2) if retention_data else 0
            }
        }
    
    @staticmethod
    async def generate_revenue_attribution_report(
        db: AsyncSession,
        agency_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Generate revenue attribution report showing revenue sources
        
        Args:
            db: Database session
            agency_id: Agency ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Revenue attribution data
        """
        # Get payments with attribution data
        payments_query = (
            select(
                Payment.amount,
                Payment.payment_type,
                Payment.created_at,
                Message.message_type,
                Fan.source,
                Model.id.label("model_id"),
                Model.display_name.label("model_name")
            )
            .join(Fan, Payment.fan_id == Fan.id)
            .join(Model, Payment.model_id == Model.id)
            .outerjoin(Message, Payment.message_id == Message.id)
            .where(
                and_(
                    Model.agency_id == agency_id,
                    Payment.created_at >= start_date,
                    Payment.created_at <= end_date,
                    Payment.status == "completed"
                )
            )
        )
        
        result = await db.execute(payments_query)
        payments = result.all()
        
        # Analyze revenue by different dimensions
        attribution = {
            "by_payment_type": {},
            "by_message_type": {},
            "by_fan_source": {},
            "by_model": {},
            "by_time_of_day": {},
            "by_day_of_week": {}
        }
        
        total_revenue = 0
        
        for payment in payments:
            amount = float(payment.amount)
            total_revenue += amount
            
            # By payment type
            payment_type = payment.payment_type
            if payment_type not in attribution["by_payment_type"]:
                attribution["by_payment_type"][payment_type] = {"amount": 0, "count": 0}
            attribution["by_payment_type"][payment_type]["amount"] += amount
            attribution["by_payment_type"][payment_type]["count"] += 1
            
            # By message type
            message_type = payment.message_type or "direct"
            if message_type not in attribution["by_message_type"]:
                attribution["by_message_type"][message_type] = {"amount": 0, "count": 0}
            attribution["by_message_type"][message_type]["amount"] += amount
            attribution["by_message_type"][message_type]["count"] += 1
            
            # By fan source
            fan_source = payment.source or "organic"
            if fan_source not in attribution["by_fan_source"]:
                attribution["by_fan_source"][fan_source] = {"amount": 0, "count": 0}
            attribution["by_fan_source"][fan_source]["amount"] += amount
            attribution["by_fan_source"][fan_source]["count"] += 1
            
            # By model
            model_key = f"{payment.model_id}:{payment.model_name}"
            if model_key not in attribution["by_model"]:
                attribution["by_model"][model_key] = {"amount": 0, "count": 0}
            attribution["by_model"][model_key]["amount"] += amount
            attribution["by_model"][model_key]["count"] += 1
            
            # By time of day
            hour = payment.created_at.hour
            hour_key = f"{hour:02d}:00"
            if hour_key not in attribution["by_time_of_day"]:
                attribution["by_time_of_day"][hour_key] = {"amount": 0, "count": 0}
            attribution["by_time_of_day"][hour_key]["amount"] += amount
            attribution["by_time_of_day"][hour_key]["count"] += 1
            
            # By day of week
            day_of_week = payment.created_at.strftime("%A")
            if day_of_week not in attribution["by_day_of_week"]:
                attribution["by_day_of_week"][day_of_week] = {"amount": 0, "count": 0}
            attribution["by_day_of_week"][day_of_week]["amount"] += amount
            attribution["by_day_of_week"][day_of_week]["count"] += 1
        
        # Calculate percentages and averages
        for category in attribution.values():
            for key, data in category.items():
                data["percentage"] = round((data["amount"] / total_revenue * 100), 2) if total_revenue > 0 else 0
                data["average"] = round(data["amount"] / data["count"], 2) if data["count"] > 0 else 0
        
        return {
            "total_revenue": total_revenue,
            "attribution": attribution,
            "insights": AdvancedReportingService._generate_attribution_insights(attribution)
        }
    
    @staticmethod
    def _generate_attribution_insights(attribution: Dict[str, Any]) -> List[str]:
        """Generate insights from attribution data"""
        insights = []
        
        # Find best performing payment type
        best_payment_type = max(
            attribution["by_payment_type"].items(),
            key=lambda x: x[1]["amount"],
            default=(None, {})
        )
        if best_payment_type[0]:
            insights.append(
                f"Top revenue source: {best_payment_type[0]} "
                f"({best_payment_type[1]['percentage']}% of revenue)"
            )
        
        # Find best time of day
        best_hour = max(
            attribution["by_time_of_day"].items(),
            key=lambda x: x[1]["amount"],
            default=(None, {})
        )
        if best_hour[0]:
            insights.append(f"Peak revenue hour: {best_hour[0]}")
        
        # Find best day of week
        best_day = max(
            attribution["by_day_of_week"].items(),
            key=lambda x: x[1]["amount"],
            default=(None, {})
        )
        if best_day[0]:
            insights.append(f"Best performing day: {best_day[0]}")
        
        return insights
    
    @staticmethod
    async def generate_predictive_analytics(
        db: AsyncSession,
        agency_id: UUID,
        model_id: Optional[UUID] = None,
        prediction_days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate predictive analytics using historical data
        
        Args:
            db: Database session
            agency_id: Agency ID
            model_id: Optional specific model ID
            prediction_days: Number of days to predict
            
        Returns:
            Predictive analytics data
        """
        # Get historical revenue data
        historical_days = 90
        end_date = date.today()
        start_date = end_date - timedelta(days=historical_days)
        
        query = (
            select(
                func.date(Payment.created_at).label("date"),
                func.sum(Payment.amount).label("revenue"),
                func.count(Payment.id).label("transaction_count")
            )
            .join(Model, Payment.model_id == Model.id)
            .where(
                and_(
                    Model.agency_id == agency_id,
                    Payment.created_at >= start_date,
                    Payment.created_at <= end_date,
                    Payment.status == "completed"
                )
            )
            .group_by(func.date(Payment.created_at))
            .order_by(func.date(Payment.created_at))
        )
        
        if model_id:
            query = query.where(Model.id == model_id)
        
        result = await db.execute(query)
        historical_data = result.all()
        
        if len(historical_data) < 30:
            return {
                "error": "Insufficient historical data for predictions",
                "required_days": 30,
                "available_days": len(historical_data)
            }
        
        # Convert to DataFrame
        df = pd.DataFrame(historical_data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Calculate trends
        df['revenue_ma7'] = df['revenue'].rolling(window=7).mean()
        df['revenue_ma30'] = df['revenue'].rolling(window=30).mean()
        
        # Simple linear regression for trend
        from sklearn.linear_model import LinearRegression
        
        X = np.arange(len(df)).reshape(-1, 1)
        y = df['revenue'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Generate predictions
        future_dates = pd.date_range(
            start=end_date + timedelta(days=1),
            periods=prediction_days,
            freq='D'
        )
        
        future_X = np.arange(len(df), len(df) + prediction_days).reshape(-1, 1)
        predictions = model.predict(future_X)
        
        # Calculate confidence intervals (simplified)
        std_dev = np.std(y)
        lower_bound = predictions - (1.96 * std_dev)
        upper_bound = predictions + (1.96 * std_dev)
        
        # Prepare prediction data
        prediction_data = []
        for i, date in enumerate(future_dates):
            prediction_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "predicted_revenue": round(max(0, predictions[i]), 2),
                "lower_bound": round(max(0, lower_bound[i]), 2),
                "upper_bound": round(max(0, upper_bound[i]), 2)
            })
        
        # Calculate key metrics
        current_monthly_revenue = df.tail(30)['revenue'].sum()
        predicted_monthly_revenue = sum(predictions[:30])
        growth_rate = ((predicted_monthly_revenue - current_monthly_revenue) / current_monthly_revenue * 100) if current_monthly_revenue > 0 else 0
        
        return {
            "predictions": prediction_data,
            "summary": {
                "current_monthly_revenue": round(current_monthly_revenue, 2),
                "predicted_monthly_revenue": round(predicted_monthly_revenue, 2),
                "predicted_growth_rate": round(growth_rate, 2),
                "trend_direction": "increasing" if model.coef_[0] > 0 else "decreasing",
                "confidence_level": 95
            },
            "historical_summary": {
                "average_daily_revenue": round(df['revenue'].mean(), 2),
                "revenue_volatility": round(df['revenue'].std(), 2),
                "best_day_revenue": round(df['revenue'].max(), 2),
                "worst_day_revenue": round(df['revenue'].min(), 2)
            }
        }
    
    @staticmethod
    async def generate_comparative_analysis(
        db: AsyncSession,
        agency_id: UUID,
        period1_start: date,
        period1_end: date,
        period2_start: date,
        period2_end: date,
        metrics: List[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comparative analysis between two periods
        
        Args:
            db: Database session
            agency_id: Agency ID
            period1_start: First period start date
            period1_end: First period end date
            period2_start: Second period start date
            period2_end: Second period end date
            metrics: List of metrics to compare
            
        Returns:
            Comparative analysis data
        """
        if not metrics:
            metrics = ["revenue", "transactions", "fans", "messages", "conversion_rate"]
        
        comparison = {}
        
        for metric in metrics:
            period1_value = await AdvancedReportingService._get_metric_value(
                db, agency_id, metric, period1_start, period1_end
            )
            period2_value = await AdvancedReportingService._get_metric_value(
                db, agency_id, metric, period2_start, period2_end
            )
            
            # Calculate change
            if period1_value > 0:
                change_percent = ((period2_value - period1_value) / period1_value) * 100
            else:
                change_percent = 100 if period2_value > 0 else 0
            
            comparison[metric] = {
                "period1": {
                    "value": period1_value,
                    "start": period1_start.isoformat(),
                    "end": period1_end.isoformat()
                },
                "period2": {
                    "value": period2_value,
                    "start": period2_start.isoformat(),
                    "end": period2_end.isoformat()
                },
                "change": {
                    "absolute": period2_value - period1_value,
                    "percentage": round(change_percent, 2),
                    "direction": "increase" if period2_value > period1_value else "decrease"
                }
            }
        
        # Generate insights
        insights = []
        
        # Find biggest improvements
        improvements = [
            (metric, data["change"]["percentage"])
            for metric, data in comparison.items()
            if data["change"]["percentage"] > 0
        ]
        improvements.sort(key=lambda x: x[1], reverse=True)
        
        if improvements:
            best_metric = improvements[0]
            insights.append(
                f"Biggest improvement: {best_metric[0]} "
                f"(+{best_metric[1]:.1f}%)"
            )
        
        # Find biggest declines
        declines = [
            (metric, data["change"]["percentage"])
            for metric, data in comparison.items()
            if data["change"]["percentage"] < 0
        ]
        declines.sort(key=lambda x: x[1])
        
        if declines:
            worst_metric = declines[0]
            insights.append(
                f"Biggest decline: {worst_metric[0]} "
                f"({worst_metric[1]:.1f}%)"
            )
        
        return {
            "comparison": comparison,
            "insights": insights,
            "summary": {
                "metrics_improved": len(improvements),
                "metrics_declined": len(declines),
                "overall_trend": "positive" if len(improvements) > len(declines) else "negative"
            }
        }
    
    @staticmethod
    async def _get_metric_value(
        db: AsyncSession,
        agency_id: UUID,
        metric: str,
        start_date: date,
        end_date: date
    ) -> float:
        """Get metric value for a specific period"""
        if metric == "revenue":
            query = (
                select(func.sum(Payment.amount))
                .join(Model, Payment.model_id == Model.id)
                .where(
                    and_(
                        Model.agency_id == agency_id,
                        Payment.created_at >= start_date,
                        Payment.created_at <= end_date,
                        Payment.status == "completed"
                    )
                )
            )
            result = await db.scalar(query)
            return float(result or 0)
        
        elif metric == "transactions":
            query = (
                select(func.count(Payment.id))
                .join(Model, Payment.model_id == Model.id)
                .where(
                    and_(
                        Model.agency_id == agency_id,
                        Payment.created_at >= start_date,
                        Payment.created_at <= end_date,
                        Payment.status == "completed"
                    )
                )
            )
            return await db.scalar(query) or 0
        
        elif metric == "fans":
            query = (
                select(func.count(distinct(Fan.id)))
                .join(Model, Fan.model_id == Model.id)
                .where(
                    and_(
                        Model.agency_id == agency_id,
                        Fan.created_at >= start_date,
                        Fan.created_at <= end_date
                    )
                )
            )
            return await db.scalar(query) or 0
        
        elif metric == "messages":
            query = (
                select(func.count(Message.id))
                .join(Model, Message.model_id == Model.id)
                .where(
                    and_(
                        Model.agency_id == agency_id,
                        Message.created_at >= start_date,
                        Message.created_at <= end_date
                    )
                )
            )
            return await db.scalar(query) or 0
        
        elif metric == "conversion_rate":
            # Get unique fans who made purchases
            purchasing_fans_query = (
                select(func.count(distinct(Payment.fan_id)))
                .join(Model, Payment.model_id == Model.id)
                .where(
                    and_(
                        Model.agency_id == agency_id,
                        Payment.created_at >= start_date,
                        Payment.created_at <= end_date,
                        Payment.status == "completed"
                    )
                )
            )
            purchasing_fans = await db.scalar(purchasing_fans_query) or 0
            
            # Get total active fans
            total_fans_query = (
                select(func.count(distinct(Fan.id)))
                .join(Model, Fan.model_id == Model.id)
                .where(
                    and_(
                        Model.agency_id == agency_id,
                        Fan.last_activity >= start_date,
                        Fan.last_activity <= end_date
                    )
                )
            )
            total_fans = await db.scalar(total_fans_query) or 0
            
            return (purchasing_fans / total_fans * 100) if total_fans > 0 else 0
        
        return 0