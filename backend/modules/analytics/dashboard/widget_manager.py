"""
Widget manager for dashboard customization
"""
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.redis import redis_client
from core.logging import get_logger
from .models import DashboardWidget, WidgetType, DashboardLayout
from .chart_generator import ChartGenerator

logger = get_logger(__name__)


class WidgetManager:
    """Manage dashboard widgets and layouts"""
    
    def __init__(self):
        self.chart_generator = ChartGenerator()
        self._widget_configs = self._init_widget_configs()
        
    def _init_widget_configs(self) -> Dict[str, Dict[str, Any]]:
        """Initialize available widget configurations"""
        return {
            "revenue_overview": {
                "type": WidgetType.CHART,
                "title": "Revenue Overview",
                "description": "Track revenue trends and breakdowns",
                "default_size": {"width": 6, "height": 4},
                "min_size": {"width": 4, "height": 3},
                "refresh_interval": 300,  # 5 minutes
                "data_source": "revenue_metrics",
                "chart_types": ["line", "bar", "area"]
            },
            "fan_growth": {
                "type": WidgetType.CHART,
                "title": "Fan Growth",
                "description": "Monitor subscriber growth and churn",
                "default_size": {"width": 6, "height": 4},
                "min_size": {"width": 4, "height": 3},
                "refresh_interval": 600,
                "data_source": "fan_metrics",
                "chart_types": ["line", "area"]
            },
            "engagement_heatmap": {
                "type": WidgetType.HEATMAP,
                "title": "Engagement Heatmap",
                "description": "Visualize peak activity times",
                "default_size": {"width": 8, "height": 4},
                "min_size": {"width": 6, "height": 3},
                "refresh_interval": 900,
                "data_source": "engagement_metrics"
            },
            "top_fans": {
                "type": WidgetType.TABLE,
                "title": "Top Fans",
                "description": "List of highest value fans",
                "default_size": {"width": 4, "height": 6},
                "min_size": {"width": 3, "height": 4},
                "refresh_interval": 1800,
                "data_source": "fan_rankings"
            },
            "realtime_stats": {
                "type": WidgetType.METRIC,
                "title": "Real-time Stats",
                "description": "Live metrics dashboard",
                "default_size": {"width": 12, "height": 2},
                "min_size": {"width": 8, "height": 2},
                "refresh_interval": 60,
                "data_source": "realtime_metrics"
            },
            "conversion_funnel": {
                "type": WidgetType.FUNNEL,
                "title": "Conversion Funnel",
                "description": "Track user journey conversions",
                "default_size": {"width": 6, "height": 5},
                "min_size": {"width": 4, "height": 4},
                "refresh_interval": 3600,
                "data_source": "funnel_metrics"
            },
            "message_analytics": {
                "type": WidgetType.MIXED,
                "title": "Message Analytics",
                "description": "Message volume and response metrics",
                "default_size": {"width": 6, "height": 4},
                "min_size": {"width": 4, "height": 3},
                "refresh_interval": 300,
                "data_source": "message_metrics"
            },
            "ai_insights": {
                "type": WidgetType.INSIGHTS,
                "title": "AI Insights",
                "description": "AI-powered recommendations and predictions",
                "default_size": {"width": 4, "height": 5},
                "min_size": {"width": 3, "height": 4},
                "refresh_interval": 1800,
                "data_source": "ai_analytics"
            }
        }
        
    async def create_widget(
        self,
        agency_id: UUID,
        widget_type: str,
        config: Dict[str, Any],
        db: AsyncSession
    ) -> DashboardWidget:
        """Create a new dashboard widget"""
        # Validate widget type
        if widget_type not in self._widget_configs:
            raise ValueError(f"Invalid widget type: {widget_type}")
            
        widget_config = self._widget_configs[widget_type]
        
        # Create widget
        widget = DashboardWidget(
            id=str(uuid4()),
            agency_id=str(agency_id),
            widget_type=widget_type,
            title=config.get("title", widget_config["title"]),
            config={
                **widget_config,
                **config,
                "created_at": datetime.utcnow().isoformat()
            },
            position=config.get("position", {"x": 0, "y": 0}),
            size=config.get("size", widget_config["default_size"]),
            is_active=True
        )
        
        db.add(widget)
        await db.commit()
        await db.refresh(widget)
        
        return widget
        
    async def update_widget(
        self,
        widget_id: str,
        updates: Dict[str, Any],
        db: AsyncSession
    ) -> DashboardWidget:
        """Update widget configuration"""
        widget = await db.get(DashboardWidget, widget_id)
        if not widget:
            raise ValueError(f"Widget {widget_id} not found")
            
        # Update fields
        for key, value in updates.items():
            if hasattr(widget, key):
                setattr(widget, key, value)
                
        widget.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(widget)
        
        return widget
        
    async def delete_widget(
        self,
        widget_id: str,
        db: AsyncSession
    ) -> bool:
        """Delete a widget"""
        widget = await db.get(DashboardWidget, widget_id)
        if not widget:
            return False
            
        await db.delete(widget)
        await db.commit()
        
        return True
        
    async def get_widget_data(
        self,
        widget: DashboardWidget,
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get data for a specific widget"""
        # Check cache first
        cache_key = f"widget_data:{widget.id}:{time_range.get('period', 'day')}"
        cached_data = await redis_client.get(cache_key)
        
        if cached_data:
            return json.loads(cached_data)
            
        # Generate fresh data
        data_source = widget.config.get("data_source")
        
        if data_source == "revenue_metrics":
            data = await self._get_revenue_data(widget, time_range, db)
        elif data_source == "fan_metrics":
            data = await self._get_fan_data(widget, time_range, db)
        elif data_source == "engagement_metrics":
            data = await self._get_engagement_data(widget, time_range, db)
        elif data_source == "fan_rankings":
            data = await self._get_top_fans_data(widget, time_range, db)
        elif data_source == "realtime_metrics":
            data = await self._get_realtime_data(widget)
        elif data_source == "funnel_metrics":
            data = await self._get_funnel_data(widget, time_range, db)
        elif data_source == "message_metrics":
            data = await self._get_message_data(widget, time_range, db)
        elif data_source == "ai_analytics":
            data = await self._get_ai_insights(widget, time_range, db)
        else:
            data = {"error": "Unknown data source"}
            
        # Cache data
        ttl = widget.config.get("refresh_interval", 300)
        await redis_client.setex(cache_key, ttl, json.dumps(data))
        
        return data
        
    async def save_layout(
        self,
        agency_id: UUID,
        user_id: UUID,
        layout_name: str,
        widgets: List[Dict[str, Any]],
        db: AsyncSession
    ) -> DashboardLayout:
        """Save dashboard layout"""
        # Check if layout exists
        existing = await db.execute(
            select(DashboardLayout).where(
                and_(
                    DashboardLayout.agency_id == str(agency_id),
                    DashboardLayout.user_id == str(user_id),
                    DashboardLayout.name == layout_name
                )
            )
        )
        layout = existing.scalar_one_or_none()
        
        if layout:
            # Update existing
            layout.widgets = widgets
            layout.updated_at = datetime.utcnow()
        else:
            # Create new
            layout = DashboardLayout(
                id=str(uuid4()),
                agency_id=str(agency_id),
                user_id=str(user_id),
                name=layout_name,
                widgets=widgets,
                is_default=False
            )
            db.add(layout)
            
        await db.commit()
        await db.refresh(layout)
        
        return layout
        
    async def load_layout(
        self,
        agency_id: UUID,
        user_id: UUID,
        layout_name: Optional[str] = None,
        db: AsyncSession
    ) -> Optional[DashboardLayout]:
        """Load dashboard layout"""
        query = select(DashboardLayout).where(
            and_(
                DashboardLayout.agency_id == str(agency_id),
                DashboardLayout.user_id == str(user_id)
            )
        )
        
        if layout_name:
            query = query.where(DashboardLayout.name == layout_name)
        else:
            # Get default layout
            query = query.where(DashboardLayout.is_default == True)
            
        result = await db.execute(query)
        return result.scalar_one_or_none()
        
    async def _get_revenue_data(
        self,
        widget: DashboardWidget,
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get revenue metrics data"""
        from modules.analytics.application.analytics_service import AnalyticsService
        
        service = AnalyticsService()
        
        # Get revenue data
        model_id = widget.config.get("model_id")
        if model_id:
            data = await service.get_model_revenue_analytics(
                UUID(model_id),
                time_range["start_date"],
                time_range["end_date"],
                db
            )
        else:
            data = await service.get_agency_revenue_analytics(
                UUID(widget.agency_id),
                time_range["start_date"],
                time_range["end_date"],
                db
            )
            
        # Generate chart data
        chart_type = widget.config.get("chart_type", "line")
        chart_data = await self.chart_generator.generate_chart(
            data=data,
            chart_type=chart_type,
            options=widget.config.get("chart_options", {})
        )
        
        return {
            "data": data,
            "chart": chart_data,
            "summary": {
                "total": data.get("total_revenue", 0),
                "growth": data.get("growth_rate", 0),
                "average_daily": data.get("average_daily_revenue", 0)
            }
        }
        
    async def _get_fan_data(
        self,
        widget: DashboardWidget,
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get fan metrics data"""
        # Implementation for fan data
        return {
            "total_fans": 0,
            "new_fans": 0,
            "churned_fans": 0,
            "growth_rate": 0,
            "chart": {}
        }
        
    async def _get_engagement_data(
        self,
        widget: DashboardWidget,
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get engagement heatmap data"""
        # Implementation for engagement heatmap
        return {
            "heatmap_data": [],
            "peak_hours": [],
            "peak_days": []
        }
        
    async def _get_top_fans_data(
        self,
        widget: DashboardWidget,
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get top fans ranking data"""
        # Implementation for top fans
        return {
            "fans": [],
            "total_count": 0
        }
        
    async def _get_realtime_data(
        self,
        widget: DashboardWidget
    ) -> Dict[str, Any]:
        """Get real-time metrics"""
        from ..realtime.engine import realtime_engine
        
        metrics = await realtime_engine.get_realtime_metrics(
            agency_id=widget.agency_id,
            model_id=widget.config.get("model_id"),
            time_range=300  # Last 5 minutes
        )
        
        return metrics
        
    async def _get_funnel_data(
        self,
        widget: DashboardWidget,
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get conversion funnel data"""
        # Implementation for funnel data
        return {
            "stages": [],
            "conversion_rates": [],
            "drop_off_points": []
        }
        
    async def _get_message_data(
        self,
        widget: DashboardWidget,
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get message analytics data"""
        # Implementation for message data
        return {
            "total_messages": 0,
            "response_rate": 0,
            "avg_response_time": 0,
            "message_volume": []
        }
        
    async def _get_ai_insights(
        self,
        widget: DashboardWidget,
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get AI-powered insights"""
        from ..ai.insights_generator import InsightsGenerator
        
        generator = InsightsGenerator()
        insights = await generator.generate_insights(
            agency_id=UUID(widget.agency_id),
            model_id=UUID(widget.config.get("model_id")) if widget.config.get("model_id") else None,
            time_range=time_range,
            db=db
        )
        
        return insights
