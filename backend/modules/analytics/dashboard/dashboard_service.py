"""
Main dashboard service for analytics
"""
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.redis import redis_client
from core.logging import get_logger
from core.database import get_db

from .widget_manager import WidgetManager
from .models import DashboardWidget, DashboardLayout
from ..realtime.engine import realtime_engine
from ..application.service import AnalyticsService

logger = get_logger(__name__)


class DashboardService:
    """Main service for dashboard operations"""
    
    def __init__(self):
        self.widget_manager = WidgetManager()
        
    async def get_dashboard_data(
        self,
        agency_id: UUID,
        user_id: UUID,
        model_id: Optional[UUID] = None,
        time_range: Optional[Dict[str, Any]] = None,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """Get complete dashboard data"""
        if db is None:
            async with get_db() as db:
                return await self._get_dashboard_data(
                    agency_id, user_id, model_id, time_range, db
                )
        else:
            return await self._get_dashboard_data(
                agency_id, user_id, model_id, time_range, db
            )
            
    async def _get_dashboard_data(
        self,
        agency_id: UUID,
        user_id: UUID,
        model_id: Optional[UUID],
        time_range: Optional[Dict[str, Any]],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Internal method to get dashboard data"""
        # Set default time range if not provided
        if not time_range:
            time_range = {
                "period": "week",
                "start_date": date.today() - timedelta(days=7),
                "end_date": date.today()
            }
            
        # Get user's layout
        layout = await self.widget_manager.load_layout(
            agency_id, user_id, db=db
        )
        
        if not layout:
            # Create default layout
            layout = await self._create_default_layout(
                agency_id, user_id, model_id, db
            )
            
        # Get widgets data
        widgets_data = await self._load_widgets_data(
            layout, time_range, db
        )
        
        # Get summary metrics
        summary = await self._get_summary_metrics(
            agency_id, model_id, time_range, db
        )
        
        # Get real-time metrics
        realtime = await realtime_engine.get_realtime_metrics(
            agency_id=str(agency_id),
            model_id=str(model_id) if model_id else None,
            time_range=300  # Last 5 minutes
        )
        
        return {
            "layout": {
                "id": layout.id,
                "name": layout.name,
                "grid_size": layout.grid_size,
                "theme": layout.theme
            },
            "widgets": widgets_data,
            "summary": summary,
            "realtime": realtime,
            "time_range": time_range,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    async def create_custom_dashboard(
        self,
        agency_id: UUID,
        user_id: UUID,
        name: str,
        widgets: List[Dict[str, Any]],
        db: AsyncSession
    ) -> DashboardLayout:
        """Create a custom dashboard layout"""
        # Create widgets
        created_widgets = []
        
        for widget_config in widgets:
            widget = await self.widget_manager.create_widget(
                agency_id=agency_id,
                widget_type=widget_config["type"],
                config=widget_config,
                db=db
            )
            created_widgets.append({
                "widget_id": widget.id,
                "position": widget_config.get("position"),
                "size": widget_config.get("size")
            })
            
        # Save layout
        layout = await self.widget_manager.save_layout(
            agency_id=agency_id,
            user_id=user_id,
            layout_name=name,
            widgets=created_widgets,
            db=db
        )
        
        return layout
        
    async def update_widget_position(
        self,
        widget_id: str,
        position: Dict[str, int],
        size: Dict[str, int],
        db: AsyncSession
    ) -> bool:
        """Update widget position and size"""
        widget = await self.widget_manager.update_widget(
            widget_id=widget_id,
            updates={"position": position, "size": size},
            db=db
        )
        
        return widget is not None
        
    async def export_dashboard(
        self,
        agency_id: UUID,
        user_id: UUID,
        format: str = "pdf",
        db: AsyncSession = None
    ) -> bytes:
        """Export dashboard to specified format"""
        if db is None:
            async with get_db() as db:
                return await self._export_dashboard(
                    agency_id, user_id, format, db
                )
        else:
            return await self._export_dashboard(
                agency_id, user_id, format, db
            )
            
    async def _export_dashboard(
        self,
        agency_id: UUID,
        user_id: UUID,
        format: str,
        db: AsyncSession
    ) -> bytes:
        """Internal method to export dashboard"""
        # Get dashboard data
        dashboard_data = await self._get_dashboard_data(
            agency_id, user_id, None, None, db
        )
        
        if format == "json":
            # Export as JSON
            return json.dumps(dashboard_data, indent=2).encode()
        elif format == "pdf":
            # Generate PDF report
            from ..reporting.export_service import ExportService
            export_service = ExportService()
            
            return await export_service.export_dashboard_pdf(
                dashboard_data, db
            )
        elif format == "excel":
            # Generate Excel report
            from ..reporting.export_service import ExportService
            export_service = ExportService()
            
            return await export_service.export_dashboard_excel(
                dashboard_data, db
            )
        else:
            raise ValueError(f"Unsupported export format: {format}")
            
    async def get_widget_detail(
        self,
        widget_id: str,
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get detailed data for a specific widget"""
        widget = await db.get(DashboardWidget, widget_id)
        
        if not widget:
            raise ValueError(f"Widget {widget_id} not found")
            
        # Get widget data with extended options
        data = await self.widget_manager.get_widget_data(
            widget, time_range, db
        )
        
        # Add drill-down data if applicable
        if widget.config.get("supports_drilldown"):
            data["drilldown"] = await self._get_drilldown_data(
                widget, data, db
            )
            
        return {
            "widget": {
                "id": widget.id,
                "type": widget.widget_type,
                "title": widget.title,
                "config": widget.config
            },
            "data": data,
            "time_range": time_range,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    async def _create_default_layout(
        self,
        agency_id: UUID,
        user_id: UUID,
        model_id: Optional[UUID],
        db: AsyncSession
    ) -> DashboardLayout:
        """Create default dashboard layout"""
        # Define default widgets
        default_widgets = [
            {
                "type": "realtime_stats",
                "position": {"x": 0, "y": 0},
                "size": {"width": 12, "height": 2}
            },
            {
                "type": "revenue_overview",
                "position": {"x": 0, "y": 2},
                "size": {"width": 6, "height": 4}
            },
            {
                "type": "fan_growth",
                "position": {"x": 6, "y": 2},
                "size": {"width": 6, "height": 4}
            },
            {
                "type": "top_fans",
                "position": {"x": 0, "y": 6},
                "size": {"width": 4, "height": 6}
            },
            {
                "type": "message_analytics",
                "position": {"x": 4, "y": 6},
                "size": {"width": 4, "height": 6}
            },
            {
                "type": "ai_insights",
                "position": {"x": 8, "y": 6},
                "size": {"width": 4, "height": 6}
            }
        ]
        
        # Create widgets
        widget_refs = []
        
        for widget_config in default_widgets:
            widget = await self.widget_manager.create_widget(
                agency_id=agency_id,
                widget_type=widget_config["type"],
                config={
                    "model_id": str(model_id) if model_id else None,
                    **widget_config
                },
                db=db
            )
            
            widget_refs.append({
                "widget_id": widget.id,
                "position": widget_config["position"],
                "size": widget_config["size"]
            })
            
        # Create layout
        layout = await self.widget_manager.save_layout(
            agency_id=agency_id,
            user_id=user_id,
            layout_name="Default Dashboard",
            widgets=widget_refs,
            db=db
        )
        
        # Set as default
        layout.is_default = True
        await db.commit()
        
        return layout
        
    async def _load_widgets_data(
        self,
        layout: DashboardLayout,
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Load data for all widgets in layout"""
        widgets_data = []
        
        # Load widgets concurrently
        tasks = []
        
        for widget_ref in layout.widgets:
            widget_id = widget_ref["widget_id"]
            widget = await db.get(DashboardWidget, widget_id)
            
            if widget and widget.is_active:
                task = self.widget_manager.get_widget_data(
                    widget, time_range, db
                )
                tasks.append((widget, task))
                
        # Wait for all widget data
        results = await asyncio.gather(
            *[task for _, task in tasks],
            return_exceptions=True
        )
        
        # Combine results
        for i, (widget, _) in enumerate(tasks):
            result = results[i]
            
            if isinstance(result, Exception):
                logger.error(f"Error loading widget {widget.id}: {result}")
                data = {"error": str(result)}
            else:
                data = result
                
            widget_info = {
                "id": widget.id,
                "type": widget.widget_type,
                "title": widget.title,
                "position": widget.position,
                "size": widget.size,
                "data": data
            }
            
            widgets_data.append(widget_info)
            
        return widgets_data
        
    async def _get_summary_metrics(
        self,
        agency_id: UUID,
        model_id: Optional[UUID],
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get summary metrics for dashboard header"""
        # Get key metrics
        analytics_service = AnalyticsService(db)
        if model_id:
            analytics = await analytics_service.get_model_analytics(
                model_id, time_range["start_date"], time_range["end_date"], db
            )
        else:
            analytics = await analytics_service.get_agency_analytics(
                agency_id, time_range["start_date"], time_range["end_date"], db
            )
            
        # Calculate changes
        previous_period = {
            "start_date": time_range["start_date"] - (time_range["end_date"] - time_range["start_date"]),
            "end_date": time_range["start_date"]
        }
        
        if model_id:
            previous_analytics = await analytics_service.get_model_analytics(
                model_id, previous_period["start_date"], previous_period["end_date"], db
            )
        else:
            previous_analytics = await analytics_service.get_agency_analytics(
                agency_id, previous_period["start_date"], previous_period["end_date"], db
            )
            
        # Calculate percentage changes
        def calc_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return ((current - previous) / previous) * 100
            
        return {
            "revenue": {
                "current": analytics.get("total_revenue", 0),
                "previous": previous_analytics.get("total_revenue", 0),
                "change": calc_change(
                    analytics.get("total_revenue", 0),
                    previous_analytics.get("total_revenue", 0)
                )
            },
            "fans": {
                "total": analytics.get("total_fans", 0),
                "new": analytics.get("new_fans", 0),
                "churned": analytics.get("churned_fans", 0),
                "growth_rate": analytics.get("fan_growth_rate", 0)
            },
            "engagement": {
                "messages": analytics.get("total_messages", 0),
                "response_rate": analytics.get("response_rate", 0),
                "avg_response_time": analytics.get("avg_response_time", "N/A")
            },
            "performance": {
                "arpu": analytics.get("arpu", 0),  # Average Revenue Per User
                "ltv": analytics.get("ltv", 0),  # Lifetime Value
                "conversion_rate": analytics.get("conversion_rate", 0)
            }
        }
        
    async def _get_drilldown_data(
        self,
        widget: DashboardWidget,
        data: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get drill-down data for widget"""
        # Implementation depends on widget type
        if widget.widget_type == "revenue_overview":
            # Get revenue breakdown by source
            return {
                "by_source": await self._get_revenue_by_source(
                    widget.agency_id, widget.config.get("model_id"), db
                ),
                "by_type": await self._get_revenue_by_type(
                    widget.agency_id, widget.config.get("model_id"), db
                ),
                "top_transactions": await self._get_top_transactions(
                    widget.agency_id, widget.config.get("model_id"), db
                )
            }
        elif widget.widget_type == "fan_growth":
            # Get fan cohort analysis
            return {
                "cohorts": await self._get_fan_cohorts(
                    widget.agency_id, widget.config.get("model_id"), db
                ),
                "retention": await self._get_fan_retention(
                    widget.agency_id, widget.config.get("model_id"), db
                )
            }
        else:
            return {}
            
    async def _get_revenue_by_source(
        self,
        agency_id: str,
        model_id: Optional[str],
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get revenue breakdown by source"""
        # Implementation for revenue by source
        return []
        
    async def _get_revenue_by_type(
        self,
        agency_id: str,
        model_id: Optional[str],
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get revenue breakdown by type"""
        # Implementation for revenue by type
        return []
        
    async def _get_top_transactions(
        self,
        agency_id: str,
        model_id: Optional[str],
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get top transactions"""
        # Implementation for top transactions
        return []
        
    async def _get_fan_cohorts(
        self,
        agency_id: str,
        model_id: Optional[str],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get fan cohort analysis"""
        # Implementation for cohort analysis
        return {}
        
    async def _get_fan_retention(
        self,
        agency_id: str,
        model_id: Optional[str],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get fan retention analysis"""
        # Implementation for retention analysis
        return {}


# Global service instance
dashboard_service = DashboardService()
