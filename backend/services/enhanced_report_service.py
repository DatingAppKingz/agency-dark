"""Enhanced report service with chart generation."""

from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import asyncio

from core.logger import get_logger
from core.application.reports_service import ReportsService
from services.report_chart_generator import get_report_chart_generator
from models.user import User
from models.agency import Agency

logger = get_logger(__name__)


class EnhancedReportService:
    """Enhanced report service with integrated chart generation."""
    
    def __init__(self):
        self.reports_service = ReportsService()
        self.chart_generator = get_report_chart_generator()
    
    async def generate_comprehensive_revenue_report(
        self,
        db: AsyncSession,
        agency_id: int,
        start_date: date,
        end_date: date,
        include_charts: bool = True,
        chart_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive revenue report with charts.
        
        Args:
            db: Database session
            agency_id: Agency ID
            start_date: Report start date
            end_date: Report end date
            include_charts: Whether to include charts
            chart_types: List of chart types to generate
            
        Returns:
            Comprehensive report with data and charts
        """
        try:
            # Get base revenue report
            revenue_data = await self.reports_service.generate_revenue_report(
                db, agency_id, start_date, end_date, group_by='day'
            )
            
            report = {
                'agency_id': agency_id,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'data': revenue_data,
                'generated_at': datetime.utcnow().isoformat()
            }
            
            # Generate charts if requested
            if include_charts and revenue_data.get('data'):
                chart_types = chart_types or ['line', 'bar']
                charts = {}
                
                for chart_type in chart_types:
                    if chart_type == 'line':
                        charts['revenue_trend'] = await self.chart_generator.generate_revenue_chart(
                            revenue_data['data'],
                            chart_type='line',
                            title='Revenue Trend'
                        )
                    elif chart_type == 'bar':
                        charts['revenue_comparison'] = await self.chart_generator.generate_revenue_chart(
                            revenue_data['data'],
                            chart_type='bar',
                            title='Daily Revenue Comparison'
                        )
                    elif chart_type == 'area':
                        charts['revenue_area'] = await self.chart_generator.generate_revenue_chart(
                            revenue_data['data'],
                            chart_type='area',
                            title='Revenue Overview'
                        )
                
                report['charts'] = charts
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating comprehensive revenue report: {e}")
            raise
    
    async def generate_performance_dashboard(
        self,
        db: AsyncSession,
        agency_id: int,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Generate performance dashboard with multiple metrics and visualizations."""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=period_days)
            
            # Gather various metrics in parallel
            tasks = [
                self._get_revenue_metrics(db, agency_id, start_date, end_date),
                self._get_user_metrics(db, agency_id, start_date, end_date),
                self._get_content_metrics(db, agency_id, start_date, end_date),
                self._get_engagement_metrics(db, agency_id, start_date, end_date)
            ]
            
            results = await asyncio.gather(*tasks)
            revenue_metrics, user_metrics, content_metrics, engagement_metrics = results
            
            # Generate charts
            charts = {}
            
            # Revenue trend chart
            if revenue_metrics.get('daily_revenue'):
                charts['revenue_trend'] = await self.chart_generator.generate_trend_chart(
                    revenue_metrics['daily_revenue'],
                    date_field='date',
                    value_field='revenue',
                    title=f'Revenue Trend - Last {period_days} Days'
                )
            
            # User growth chart
            if user_metrics.get('daily_signups'):
                charts['user_growth'] = await self.chart_generator.generate_trend_chart(
                    user_metrics['daily_signups'],
                    date_field='date',
                    value_field='signups',
                    title='User Growth'
                )
            
            # Content performance comparison
            if content_metrics.get('content_types'):
                charts['content_distribution'] = await self.chart_generator.generate_comparison_chart(
                    content_metrics['content_types'],
                    x_field='type',
                    y_fields=['count', 'engagement'],
                    title='Content Performance by Type'
                )
            
            # Engagement heatmap
            if engagement_metrics.get('hourly_activity'):
                charts['activity_heatmap'] = await self.chart_generator.generate_heatmap(
                    engagement_metrics['hourly_activity'],
                    title='User Activity Heatmap'
                )
            
            # Conversion funnel
            if engagement_metrics.get('conversion_funnel'):
                charts['conversion_funnel'] = await self.chart_generator.generate_funnel_chart(
                    engagement_metrics['conversion_funnel'],
                    title='User Conversion Funnel'
                )
            
            return {
                'agency_id': agency_id,
                'period': {
                    'days': period_days,
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'metrics': {
                    'revenue': revenue_metrics,
                    'users': user_metrics,
                    'content': content_metrics,
                    'engagement': engagement_metrics
                },
                'charts': charts,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating performance dashboard: {e}")
            raise
    
    async def generate_model_performance_report(
        self,
        db: AsyncSession,
        model_id: int,
        period_days: int = 30,
        include_charts: bool = True
    ) -> Dict[str, Any]:
        """Generate detailed performance report for a specific model."""
        try:
            # Get model performance data
            performance_data = await self.reports_service.generate_model_performance_report(
                db, model_id, period_days
            )
            
            report = {
                'model_id': model_id,
                'period_days': period_days,
                'data': performance_data,
                'generated_at': datetime.utcnow().isoformat()
            }
            
            if include_charts:
                charts = {}
                
                # Earnings trend
                if performance_data.get('daily_earnings'):
                    charts['earnings_trend'] = await self.chart_generator.generate_trend_chart(
                        performance_data['daily_earnings'],
                        date_field='date',
                        value_field='earnings',
                        title='Daily Earnings Trend'
                    )
                
                # Engagement metrics
                if performance_data.get('engagement_metrics'):
                    charts['engagement_pie'] = await self.chart_generator.generate_performance_chart(
                        performance_data['engagement_metrics'],
                        metric='response_rate',
                        title='Message Response Rate'
                    )
                
                # Content performance
                if performance_data.get('content_performance'):
                    charts['content_bar'] = await self.chart_generator.generate_comparison_chart(
                        performance_data['content_performance'],
                        x_field='content_type',
                        y_fields=['views', 'likes', 'tips'],
                        title='Content Performance Comparison'
                    )
                
                report['charts'] = charts
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating model performance report: {e}")
            raise
    
    async def generate_financial_summary_report(
        self,
        db: AsyncSession,
        agency_id: int,
        year: int,
        month: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate financial summary report with visualizations."""
        try:
            # Determine date range
            if month:
                start_date = date(year, month, 1)
                if month == 12:
                    end_date = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = date(year, month + 1, 1) - timedelta(days=1)
            else:
                start_date = date(year, 1, 1)
                end_date = date(year, 12, 31)
            
            # Get financial data
            financial_data = await self.reports_service.generate_financial_report(
                db, agency_id, start_date, end_date
            )
            
            charts = {}
            
            # Monthly revenue comparison (for yearly reports)
            if not month and financial_data.get('monthly_breakdown'):
                charts['monthly_revenue'] = await self.chart_generator.generate_comparison_chart(
                    financial_data['monthly_breakdown'],
                    x_field='month',
                    y_fields=['revenue', 'expenses', 'profit'],
                    title=f'Monthly Financial Overview - {year}'
                )
            
            # Expense distribution
            if financial_data.get('expense_breakdown'):
                charts['expense_distribution'] = await self.chart_generator.generate_performance_chart(
                    {'expense_distribution': financial_data['expense_breakdown']},
                    metric='expense_distribution',
                    title='Expense Distribution'
                )
            
            # Revenue sources
            if financial_data.get('revenue_sources'):
                charts['revenue_sources'] = await self.chart_generator.generate_comparison_chart(
                    financial_data['revenue_sources'],
                    x_field='source',
                    y_fields=['amount'],
                    title='Revenue by Source',
                    chart_type='bar'
                )
            
            return {
                'agency_id': agency_id,
                'period': {
                    'year': year,
                    'month': month,
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'financial_data': financial_data,
                'charts': charts,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating financial summary report: {e}")
            raise
    
    async def _get_revenue_metrics(
        self,
        db: AsyncSession,
        agency_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get revenue metrics for dashboard."""
        # Implementation would query revenue data
        # This is a placeholder - actual implementation would use SQLAlchemy queries
        return {
            'total_revenue': 125000.50,
            'growth_rate': 15.5,
            'daily_revenue': [
                {'date': (start_date + timedelta(days=i)).isoformat(), 
                 'revenue': 4000 + (i * 100)}
                for i in range((end_date - start_date).days + 1)
            ]
        }
    
    async def _get_user_metrics(
        self,
        db: AsyncSession,
        agency_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get user metrics for dashboard."""
        return {
            'total_users': 1250,
            'new_users': 125,
            'daily_signups': [
                {'date': (start_date + timedelta(days=i)).isoformat(), 
                 'signups': 4 + (i % 5)}
                for i in range((end_date - start_date).days + 1)
            ]
        }
    
    async def _get_content_metrics(
        self,
        db: AsyncSession,
        agency_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get content metrics for dashboard."""
        return {
            'total_content': 5420,
            'content_types': [
                {'type': 'Photos', 'count': 3200, 'engagement': 85.5},
                {'type': 'Videos', 'count': 1800, 'engagement': 92.3},
                {'type': 'Posts', 'count': 420, 'engagement': 78.9}
            ]
        }
    
    async def _get_engagement_metrics(
        self,
        db: AsyncSession,
        agency_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get engagement metrics for dashboard."""
        # Generate hourly activity heatmap data
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        hourly_activity = {}
        for day in days:
            hourly_activity[day] = {str(h): 50 + (h * 5) for h in range(24)}
        
        return {
            'avg_engagement_rate': 82.5,
            'total_interactions': 45320,
            'hourly_activity': hourly_activity,
            'conversion_funnel': {
                'Visitors': 10000,
                'Registered': 2500,
                'Subscribed': 800,
                'Active': 600,
                'Premium': 250
            }
        }


# Singleton instance
_enhanced_report_service = None


def get_enhanced_report_service() -> EnhancedReportService:
    """Get singleton instance of enhanced report service."""
    global _enhanced_report_service
    if _enhanced_report_service is None:
        _enhanced_report_service = EnhancedReportService()
    return _enhanced_report_service