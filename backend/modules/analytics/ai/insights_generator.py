"""
AI-powered insights generator for analytics
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
from uuid import UUID
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from ..domain.models import Analytics, MetricSnapshot
from modules.fans.domain.models import Fan
from modules.payments.domain.models import Payment

logger = get_logger(__name__)


class InsightsGenerator:
    """Generate AI-powered insights from analytics data"""
    
    def __init__(self):
        self.prediction_models = {}
        self.insight_templates = self._init_insight_templates()
        
    def _init_insight_templates(self) -> Dict[str, str]:
        """Initialize insight message templates"""
        return {
            "revenue_trend_up": "Revenue is trending up by {percentage:.1f}% over the last {period}. At this rate, you could reach ${projected_amount:,.0f} by {target_date}.",
            "revenue_trend_down": "Revenue has decreased by {percentage:.1f}% over the last {period}. Consider {recommendation} to reverse this trend.",
            "high_engagement_time": "Your fans are most active between {start_time} and {end_time}. Schedule content during these hours for maximum engagement.",
            "top_fan_segment": "Your top {count} fans generate {percentage:.0f}% of your revenue. Consider creating exclusive content for this VIP segment.",
            "churn_risk": "{count} fans haven't engaged in {days} days and are at risk of churning. Send them personalized messages to re-engage.",
            "growth_opportunity": "Fans who {action} are {multiplier:.1f}x more likely to become high-value subscribers. Focus on encouraging this behavior.",
            "content_performance": "{content_type} content generates {percentage:.0f}% more revenue than average. Consider creating more of this type.",
            "optimal_pricing": "Based on conversion data, pricing content at ${price:.0f} could increase revenue by {percentage:.0f}%.",
            "retention_insight": "Fans who receive responses within {time} are {percentage:.0f}% more likely to remain subscribed.",
            "milestone_approaching": "You're {percentage:.0f}% of the way to reaching {milestone}. Keep up the momentum!"
        }
        
    async def generate_insights(
        self,
        agency_id: UUID,
        model_id: Optional[UUID],
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate comprehensive AI insights"""
        insights = {
            "recommendations": [],
            "predictions": [],
            "opportunities": [],
            "alerts": [],
            "summary": {}
        }
        
        # Gather data for analysis
        data = await self._gather_analytics_data(
            agency_id, model_id, time_range, db
        )
        
        # Generate different types of insights
        revenue_insights = await self._analyze_revenue_trends(data, db)
        engagement_insights = await self._analyze_engagement_patterns(data, db)
        fan_insights = await self._analyze_fan_behavior(data, db)
        content_insights = await self._analyze_content_performance(data, db)
        
        # Combine insights
        insights["recommendations"].extend(revenue_insights.get("recommendations", []))
        insights["recommendations"].extend(engagement_insights.get("recommendations", []))
        insights["recommendations"].extend(fan_insights.get("recommendations", []))
        insights["recommendations"].extend(content_insights.get("recommendations", []))
        
        # Generate predictions
        predictions = await self._generate_predictions(data, db)
        insights["predictions"] = predictions
        
        # Identify opportunities
        opportunities = await self._identify_opportunities(data, db)
        insights["opportunities"] = opportunities
        
        # Generate alerts
        alerts = await self._generate_alerts(data, db)
        insights["alerts"] = alerts
        
        # Create summary
        insights["summary"] = await self._create_summary(insights)
        
        # Sort by priority
        insights["recommendations"].sort(key=lambda x: x.get("priority", 0), reverse=True)
        
        return insights
        
    async def _gather_analytics_data(
        self,
        agency_id: UUID,
        model_id: Optional[UUID],
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Gather all necessary analytics data"""
        # Base query filters
        filters = [
            Analytics.agency_id == str(agency_id),
            Analytics.date >= time_range["start_date"],
            Analytics.date <= time_range["end_date"]
        ]
        
        if model_id:
            filters.append(Analytics.model_id == model_id)
            
        # Get analytics data
        analytics_query = select(Analytics).where(and_(*filters))
        analytics_result = await db.execute(analytics_query)
        analytics_data = analytics_result.scalars().all()
        
        # Get metric snapshots
        snapshot_filters = filters.copy()
        if model_id:
            snapshot_query = select(MetricSnapshot).where(
                and_(
                    MetricSnapshot.model_id == model_id,
                    MetricSnapshot.timestamp >= time_range["start_date"],
                    MetricSnapshot.timestamp <= time_range["end_date"]
                )
            )
            snapshot_result = await db.execute(snapshot_query)
            snapshots = snapshot_result.scalars().all()
        else:
            snapshots = []
            
        # Get fan data
        fan_filters = [Fan.model_id == model_id] if model_id else []
        fan_query = select(Fan).where(and_(*fan_filters)) if fan_filters else select(Fan)
        fan_result = await db.execute(fan_query)
        fans = fan_result.scalars().all()
        
        # Get payment data
        payment_filters = filters.copy()
        payment_query = select(Payment).where(
            and_(
                Payment.status == "completed",
                Payment.created_at >= time_range["start_date"],
                Payment.created_at <= time_range["end_date"]
            )
        )
        
        if model_id:
            payment_query = payment_query.where(Payment.model_id == model_id)
            
        payment_result = await db.execute(payment_query)
        payments = payment_result.scalars().all()
        
        return {
            "analytics": analytics_data,
            "snapshots": snapshots,
            "fans": fans,
            "payments": payments,
            "time_range": time_range
        }
        
    async def _analyze_revenue_trends(
        self,
        data: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Analyze revenue trends and patterns"""
        insights = {"recommendations": []}
        payments = data["payments"]
        
        if not payments:
            return insights
            
        # Calculate daily revenue
        daily_revenue = {}
        for payment in payments:
            date_key = payment.created_at.date()
            daily_revenue[date_key] = daily_revenue.get(date_key, 0) + float(payment.amount)
            
        # Sort by date
        sorted_dates = sorted(daily_revenue.keys())
        revenue_values = [daily_revenue[d] for d in sorted_dates]
        
        if len(revenue_values) >= 7:
            # Calculate trend
            x = np.arange(len(revenue_values)).reshape(-1, 1)
            y = np.array(revenue_values)
            
            model = LinearRegression()
            model.fit(x, y)
            
            # Calculate trend metrics
            trend_slope = model.coef_[0]
            avg_revenue = np.mean(revenue_values)
            trend_percentage = (trend_slope / avg_revenue) * 100 if avg_revenue > 0 else 0
            
            # Generate insight
            if trend_percentage > 5:
                # Positive trend
                projected_revenue = model.predict([[len(revenue_values) + 30]])[0]
                insight = {
                    "type": "revenue_trend",
                    "title": "Revenue Growth Detected",
                    "message": self.insight_templates["revenue_trend_up"].format(
                        percentage=trend_percentage,
                        period=f"{len(revenue_values)} days",
                        projected_amount=projected_revenue * 30,
                        target_date=(datetime.now() + timedelta(days=30)).strftime("%B %d")
                    ),
                    "priority": 8,
                    "sentiment": "positive",
                    "data": {
                        "trend_percentage": trend_percentage,
                        "current_avg": avg_revenue,
                        "projected_monthly": projected_revenue * 30
                    }
                }
                insights["recommendations"].append(insight)
                
            elif trend_percentage < -5:
                # Negative trend
                recommendations = [
                    "increasing engagement with top fans",
                    "creating exclusive content offers",
                    "running a limited-time promotion"
                ]
                
                insight = {
                    "type": "revenue_trend",
                    "title": "Revenue Decline Alert",
                    "message": self.insight_templates["revenue_trend_down"].format(
                        percentage=abs(trend_percentage),
                        period=f"{len(revenue_values)} days",
                        recommendation=np.random.choice(recommendations)
                    ),
                    "priority": 9,
                    "sentiment": "warning",
                    "data": {
                        "trend_percentage": trend_percentage,
                        "current_avg": avg_revenue
                    }
                }
                insights["recommendations"].append(insight)
                
        # Analyze payment patterns
        payment_types = {}
        for payment in payments:
            ptype = payment.payment_type
            payment_types[ptype] = payment_types.get(ptype, 0) + float(payment.amount)
            
        # Find best performing payment type
        if payment_types:
            best_type = max(payment_types.items(), key=lambda x: x[1])
            total_revenue = sum(payment_types.values())
            
            if best_type[1] / total_revenue > 0.5:
                insight = {
                    "type": "payment_optimization",
                    "title": "Payment Type Insight",
                    "message": f"{best_type[0].title()} generates {(best_type[1]/total_revenue)*100:.0f}% of your revenue. Focus on optimizing this payment method.",
                    "priority": 6,
                    "sentiment": "info",
                    "data": {
                        "dominant_type": best_type[0],
                        "percentage": (best_type[1]/total_revenue)*100
                    }
                }
                insights["recommendations"].append(insight)
                
        return insights
        
    async def _analyze_engagement_patterns(
        self,
        data: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Analyze engagement patterns"""
        insights = {"recommendations": []}
        analytics = data["analytics"]
        
        # Analyze message patterns
        message_events = [a for a in analytics if a.event_type in ["message_sent", "message_received"]]
        
        if message_events:
            # Group by hour
            hourly_activity = {}
            for event in message_events:
                hour = event.created_at.hour
                hourly_activity[hour] = hourly_activity.get(hour, 0) + 1
                
            # Find peak hours
            if hourly_activity:
                sorted_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)
                peak_hours = sorted_hours[:3]
                
                if peak_hours[0][1] > len(message_events) * 0.2:
                    # Significant peak detected
                    peak_start = min(h[0] for h in peak_hours)
                    peak_end = max(h[0] for h in peak_hours)
                    
                    insight = {
                        "type": "engagement_pattern",
                        "title": "Peak Activity Hours",
                        "message": self.insight_templates["high_engagement_time"].format(
                            start_time=f"{peak_start}:00",
                            end_time=f"{peak_end + 1}:00"
                        ),
                        "priority": 7,
                        "sentiment": "info",
                        "data": {
                            "peak_hours": [h[0] for h in peak_hours],
                            "activity_percentage": (peak_hours[0][1] / len(message_events)) * 100
                        }
                    }
                    insights["recommendations"].append(insight)
                    
        # Analyze response times
        response_events = [a for a in analytics if a.event_type == "message_sent" and a.data.get("response_time")]
        
        if response_events:
            response_times = [a.data["response_time"] for a in response_events]
            avg_response_time = np.mean(response_times)
            
            if avg_response_time < 300:  # Less than 5 minutes
                insight = {
                    "type": "response_performance",
                    "title": "Excellent Response Time",
                    "message": f"Your average response time of {avg_response_time/60:.1f} minutes is excellent! This quick engagement helps retain fans.",
                    "priority": 5,
                    "sentiment": "positive",
                    "data": {
                        "avg_response_time_minutes": avg_response_time / 60
                    }
                }
                insights["recommendations"].append(insight)
                
        return insights
        
    async def _analyze_fan_behavior(
        self,
        data: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Analyze fan behavior and segments"""
        insights = {"recommendations": []}
        fans = data["fans"]
        payments = data["payments"]
        
        if not fans:
            return insights
            
        # Calculate fan value distribution
        fan_values = {}
        for payment in payments:
            if payment.fan_id:
                fan_id = str(payment.fan_id)
                fan_values[fan_id] = fan_values.get(fan_id, 0) + float(payment.amount)
                
        if fan_values:
            # Sort fans by value
            sorted_fans = sorted(fan_values.items(), key=lambda x: x[1], reverse=True)
            total_revenue = sum(fan_values.values())
            
            # Calculate top fan contribution
            top_20_percent = int(len(sorted_fans) * 0.2) or 1
            top_fans_revenue = sum(f[1] for f in sorted_fans[:top_20_percent])
            
            if top_fans_revenue / total_revenue > 0.5:
                insight = {
                    "type": "fan_segmentation",
                    "title": "VIP Fan Opportunity",
                    "message": self.insight_templates["top_fan_segment"].format(
                        count=top_20_percent,
                        percentage=(top_fans_revenue / total_revenue) * 100
                    ),
                    "priority": 8,
                    "sentiment": "opportunity",
                    "data": {
                        "vip_count": top_20_percent,
                        "revenue_percentage": (top_fans_revenue / total_revenue) * 100,
                        "avg_vip_value": top_fans_revenue / top_20_percent
                    }
                }
                insights["recommendations"].append(insight)
                
        # Analyze churn risk
        inactive_fans = []
        for fan in fans:
            if fan.last_activity:
                days_inactive = (datetime.utcnow() - fan.last_activity).days
                if days_inactive > 30 and fan.is_paying:
                    inactive_fans.append(fan)
                    
        if inactive_fans:
            insight = {
                "type": "churn_risk",
                "title": "Fan Retention Alert",
                "message": self.insight_templates["churn_risk"].format(
                    count=len(inactive_fans),
                    days=30
                ),
                "priority": 9,
                "sentiment": "warning",
                "data": {
                    "at_risk_count": len(inactive_fans),
                    "potential_revenue_loss": sum(f.total_spent for f in inactive_fans) / 12  # Monthly estimate
                }
            }
            insights["recommendations"].append(insight)
            
        return insights
        
    async def _analyze_content_performance(
        self,
        data: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Analyze content performance patterns"""
        insights = {"recommendations": []}
        
        # Analyze content engagement metrics
        content_events = [a for a in data["analytics"] if a.event_type in ["photo_unlock", "video_play", "post_purchase"]]
        
        if content_events:
            content_revenue = {}
            
            for event in content_events:
                content_type = event.data.get("content_type", "unknown")
                revenue = float(event.value) if event.value else 0
                content_revenue[content_type] = content_revenue.get(content_type, 0) + revenue
                
            if content_revenue:
                # Find best performing content type
                best_type = max(content_revenue.items(), key=lambda x: x[1])
                avg_revenue = np.mean(list(content_revenue.values()))
                
                if best_type[1] > avg_revenue * 1.5:
                    insight = {
                        "type": "content_performance",
                        "title": "High-Performing Content Type",
                        "message": self.insight_templates["content_performance"].format(
                            content_type=best_type[0].title(),
                            percentage=((best_type[1] - avg_revenue) / avg_revenue) * 100
                        ),
                        "priority": 7,
                        "sentiment": "positive",
                        "data": {
                            "best_type": best_type[0],
                            "revenue_uplift": ((best_type[1] - avg_revenue) / avg_revenue) * 100
                        }
                    }
                    insights["recommendations"].append(insight)
                    
        return insights
        
    async def _generate_predictions(
        self,
        data: Dict[str, Any],
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Generate predictive insights"""
        predictions = []
        
        # Revenue prediction
        payments = data["payments"]
        if len(payments) >= 30:  # Need sufficient data
            daily_revenue = {}
            for payment in payments:
                date_key = payment.created_at.date()
                daily_revenue[date_key] = daily_revenue.get(date_key, 0) + float(payment.amount)
                
            # Prepare data for prediction
            sorted_dates = sorted(daily_revenue.keys())
            revenue_values = [daily_revenue[d] for d in sorted_dates]
            
            # Simple moving average prediction
            if len(revenue_values) >= 7:
                recent_avg = np.mean(revenue_values[-7:])
                monthly_projection = recent_avg * 30
                
                predictions.append({
                    "type": "revenue_forecast",
                    "title": "30-Day Revenue Forecast",
                    "value": monthly_projection,
                    "confidence": 0.75,
                    "formatted_value": f"${monthly_projection:,.0f}",
                    "based_on": "7-day moving average"
                })
                
        # Fan growth prediction
        fans = data["fans"]
        if fans:
            # Count new fans by date
            new_fans_by_date = {}
            for fan in fans:
                if fan.created_at:
                    date_key = fan.created_at.date()
                    if date_key >= data["time_range"]["start_date"]:
                        new_fans_by_date[date_key] = new_fans_by_date.get(date_key, 0) + 1
                        
            if len(new_fans_by_date) >= 7:
                recent_growth = list(new_fans_by_date.values())[-7:]
                avg_daily_growth = np.mean(recent_growth)
                monthly_growth = int(avg_daily_growth * 30)
                
                predictions.append({
                    "type": "fan_growth_forecast",
                    "title": "Expected New Fans (30 days)",
                    "value": monthly_growth,
                    "confidence": 0.7,
                    "formatted_value": f"{monthly_growth:,}",
                    "based_on": "Recent growth rate"
                })
                
        return predictions
        
    async def _identify_opportunities(
        self,
        data: Dict[str, Any],
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Identify growth opportunities"""
        opportunities = []
        
        # Analyze conversion opportunities
        fans = data["fans"]
        if fans:
            non_paying = [f for f in fans if not f.is_paying]
            paying = [f for f in fans if f.is_paying]
            
            if non_paying and paying:
                conversion_rate = len(paying) / (len(paying) + len(non_paying)) * 100
                
                if conversion_rate < 30:
                    opportunities.append({
                        "type": "conversion_optimization",
                        "title": "Conversion Rate Opportunity",
                        "description": f"Your current conversion rate is {conversion_rate:.1f}%. Industry average is 35-40%.",
                        "potential_impact": "high",
                        "suggested_actions": [
                            "Create limited-time welcome offers",
                            "Send personalized content previews",
                            "Implement tiered pricing options"
                        ],
                        "estimated_revenue_increase": len(non_paying) * 0.1 * 20  # 10% conversion at $20 avg
                    })
                    
        # Analyze pricing opportunities
        payments = data["payments"]
        if payments:
            amounts = [float(p.amount) for p in payments]
            if amounts:
                median_amount = np.median(amounts)
                percentile_75 = np.percentile(amounts, 75)
                
                if percentile_75 > median_amount * 1.5:
                    opportunities.append({
                        "type": "pricing_optimization",
                        "title": "Premium Pricing Opportunity",
                        "description": f"25% of your fans pay ${percentile_75:.0f}+. Consider premium tiers.",
                        "potential_impact": "medium",
                        "suggested_actions": [
                            "Create VIP subscription tier",
                            "Offer exclusive high-value content",
                            "Implement personalized pricing"
                        ],
                        "estimated_revenue_increase": len(payments) * 0.25 * (percentile_75 - median_amount)
                    })
                    
        return opportunities
        
    async def _generate_alerts(
        self,
        data: Dict[str, Any],
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Generate alerts for important conditions"""
        alerts = []
        
        # Check for sudden revenue drops
        payments = data["payments"]
        if payments:
            # Group by date
            daily_revenue = {}
            for payment in payments:
                date_key = payment.created_at.date()
                daily_revenue[date_key] = daily_revenue.get(date_key, 0) + float(payment.amount)
                
            if len(daily_revenue) >= 3:
                sorted_dates = sorted(daily_revenue.keys())
                recent_revenues = [daily_revenue[d] for d in sorted_dates[-3:]]
                
                if recent_revenues[-1] < recent_revenues[0] * 0.5:
                    alerts.append({
                        "type": "revenue_drop",
                        "severity": "high",
                        "title": "Significant Revenue Drop",
                        "message": "Revenue has dropped by more than 50% in the last 3 days.",
                        "timestamp": datetime.utcnow().isoformat(),
                        "action_required": True
                    })
                    
        # Check for high churn rate
        analytics = data["analytics"]
        recent_unsubs = [a for a in analytics if a.event_type == "fan_unsubscribed" 
                        and (datetime.utcnow() - a.created_at).days <= 7]
        recent_subs = [a for a in analytics if a.event_type == "fan_subscribed" 
                      and (datetime.utcnow() - a.created_at).days <= 7]
        
        if recent_subs and len(recent_unsubs) > len(recent_subs) * 0.3:
            alerts.append({
                "type": "high_churn",
                "severity": "medium",
                "title": "Elevated Churn Rate",
                "message": f"Churn rate is {(len(recent_unsubs)/len(recent_subs))*100:.0f}% this week.",
                "timestamp": datetime.utcnow().isoformat(),
                "action_required": True
            })
            
        return alerts
        
    async def _create_summary(
        self,
        insights: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create executive summary of insights"""
        high_priority = [r for r in insights["recommendations"] if r.get("priority", 0) >= 8]
        positive_insights = [r for r in insights["recommendations"] if r.get("sentiment") == "positive"]
        
        return {
            "total_insights": len(insights["recommendations"]),
            "high_priority_count": len(high_priority),
            "positive_trends": len(positive_insights),
            "alerts_count": len(insights["alerts"]),
            "opportunities_count": len(insights["opportunities"]),
            "key_takeaway": high_priority[0]["message"] if high_priority else "No critical insights at this time."
        }
