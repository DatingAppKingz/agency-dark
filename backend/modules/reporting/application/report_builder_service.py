"""
Custom report builder service for creating dynamic reports.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.sql import Select

from core.exceptions import BadRequestError, NotFoundError
from core.redis import redis_client
from modules.reporting.domain.models import (
    ReportTemplate, ReportSchedule, GeneratedReport,
    ReportWidget, ReportStatus
)
from modules.reporting.domain.schemas import (
    ReportTemplateCreate, ReportTemplateUpdate,
    ReportWidgetConfig, ReportGenerateRequest
)

logger = logging.getLogger(__name__)


class ReportBuilderService:
    """Service for building and managing custom reports."""
    
    def __init__(self):
        self.cache_prefix = "report:"
        self.widget_types = {
            "metric": self._build_metric_widget,
            "chart": self._build_chart_widget,
            "table": self._build_table_widget,
            "text": self._build_text_widget,
            "comparison": self._build_comparison_widget
        }
        
    async def create_report_template(
        self,
        data: ReportTemplateCreate,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> ReportTemplate:
        """Create a new report template."""
        # Validate widgets
        for widget in data.widgets:
            if widget.type not in self.widget_types:
                raise BadRequestError(f"Invalid widget type: {widget.type}")
        
        # Create template
        template = ReportTemplate(
            agency_id=agency_id,
            created_by_id=user_id,
            name=data.name,
            description=data.description,
            report_type=data.report_type,
            layout=data.layout,
            filters=data.filters.dict() if data.filters else {},
            is_public=data.is_public
        )
        
        db.add(template)
        await db.flush()
        
        # Add widgets
        for i, widget_data in enumerate(data.widgets):
            widget = ReportWidget(
                template_id=template.id,
                widget_type=widget_data.type,
                title=widget_data.title,
                config=widget_data.config,
                position=widget_data.position or i,
                size=widget_data.size
            )
            db.add(widget)
        
        await db.commit()
        await db.refresh(template)
        
        logger.info(f"Created report template '{template.name}' for agency {agency_id}")
        return template
    
    async def update_report_template(
        self,
        template_id: UUID,
        data: ReportTemplateUpdate,
        agency_id: UUID,
        db: AsyncSession
    ) -> ReportTemplate:
        """Update a report template."""
        # Get template
        result = await db.execute(
            select(ReportTemplate).where(
                ReportTemplate.id == template_id,
                ReportTemplate.agency_id == agency_id
            )
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise NotFoundError("Report template not found")
        
        # Update fields
        update_data = data.dict(exclude_unset=True)
        
        if "widgets" in update_data:
            # Handle widget updates
            widgets_data = update_data.pop("widgets")
            
            # Delete existing widgets
            await db.execute(
                ReportWidget.__table__.delete().where(
                    ReportWidget.template_id == template_id
                )
            )
            
            # Add new widgets
            for i, widget_data in enumerate(widgets_data):
                widget = ReportWidget(
                    template_id=template.id,
                    widget_type=widget_data["type"],
                    title=widget_data["title"],
                    config=widget_data["config"],
                    position=widget_data.get("position", i),
                    size=widget_data.get("size", "medium")
                )
                db.add(widget)
        
        for field, value in update_data.items():
            setattr(template, field, value)
        
        await db.commit()
        await db.refresh(template)
        
        return template
    
    async def generate_report(
        self,
        template_id: UUID,
        request: ReportGenerateRequest,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> GeneratedReport:
        """Generate a report from template."""
        # Get template with widgets
        result = await db.execute(
            select(ReportTemplate)
            .options(selectinload(ReportTemplate.widgets))
            .where(
                ReportTemplate.id == template_id,
                or_(
                    ReportTemplate.agency_id == agency_id,
                    ReportTemplate.is_public == True
                )
            )
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise NotFoundError("Report template not found")
        
        # Create generated report record
        generated_report = GeneratedReport(
            id=uuid4(),
            template_id=template_id,
            agency_id=agency_id,
            generated_by_id=user_id,
            parameters={
                "date_from": request.date_from.isoformat() if request.date_from else None,
                "date_to": request.date_to.isoformat() if request.date_to else None,
                "model_id": str(request.model_id) if request.model_id else None,
                "filters": request.filters
            },
            status=ReportStatus.GENERATING
        )
        
        db.add(generated_report)
        await db.commit()
        
        try:
            # Generate report data
            report_data = await self._generate_report_data(
                template, request, agency_id, db
            )
            
            # Update report with data
            generated_report.report_data = report_data
            generated_report.status = ReportStatus.COMPLETED
            generated_report.completed_at = datetime.utcnow()
            
            # Cache report
            await self._cache_report(generated_report)
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            generated_report.status = ReportStatus.FAILED
            generated_report.error_message = str(e)
        
        await db.commit()
        return generated_report
    
    async def _generate_report_data(
        self,
        template: ReportTemplate,
        request: ReportGenerateRequest,
        agency_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate the actual report data."""
        report_data = {
            "template": {
                "name": template.name,
                "description": template.description,
                "type": template.report_type
            },
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "parameters": {
                    "date_from": request.date_from.isoformat() if request.date_from else None,
                    "date_to": request.date_to.isoformat() if request.date_to else None,
                    "model_id": str(request.model_id) if request.model_id else None
                }
            },
            "widgets": []
        }
        
        # Generate data for each widget
        for widget in sorted(template.widgets, key=lambda w: w.position):
            widget_data = await self._generate_widget_data(
                widget, request, agency_id, db
            )
            report_data["widgets"].append({
                "id": str(widget.id),
                "type": widget.widget_type,
                "title": widget.title,
                "size": widget.size,
                "position": widget.position,
                "data": widget_data
            })
        
        return report_data
    
    async def _generate_widget_data(
        self,
        widget: ReportWidget,
        request: ReportGenerateRequest,
        agency_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate data for a specific widget."""
        handler = self.widget_types.get(widget.widget_type)
        if not handler:
            raise BadRequestError(f"Unknown widget type: {widget.widget_type}")
        
        return await handler(widget, request, agency_id, db)
    
    async def _build_metric_widget(
        self,
        widget: ReportWidget,
        request: ReportGenerateRequest,
        agency_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Build data for metric widget."""
        config = widget.config
        metric_type = config.get("metric_type", "revenue")
        
        # Build query based on metric type
        if metric_type == "revenue":
            from modules.financial.domain.models import Transaction
            
            query = select(func.sum(Transaction.amount)).where(
                Transaction.agency_id == agency_id,
                Transaction.status == "completed"
            )
            
            if request.date_from:
                query = query.where(Transaction.created_at >= request.date_from)
            if request.date_to:
                query = query.where(Transaction.created_at <= request.date_to)
            if request.model_id:
                query = query.where(Transaction.model_id == request.model_id)
            
            result = await db.execute(query)
            value = result.scalar() or 0
            
            # Get comparison if requested
            comparison = None
            if config.get("show_comparison"):
                comparison = await self._calculate_comparison(
                    query, request, db, config.get("comparison_period", "previous_period")
                )
            
            return {
                "value": float(value),
                "format": "currency",
                "comparison": comparison
            }
        
        elif metric_type == "fans":
            from modules.analytics.domain.models import Fan
            
            query = select(func.count(Fan.id)).join(
                Fan.model
            ).where(
                Fan.model.has(agency_id=agency_id)
            )
            
            if request.model_id:
                query = query.where(Fan.model_id == request.model_id)
            
            result = await db.execute(query)
            value = result.scalar() or 0
            
            return {
                "value": value,
                "format": "number"
            }
        
        else:
            return {"value": 0, "format": "number"}
    
    async def _build_chart_widget(
        self,
        widget: ReportWidget,
        request: ReportGenerateRequest,
        agency_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Build data for chart widget."""
        config = widget.config
        chart_type = config.get("chart_type", "line")
        data_source = config.get("data_source", "revenue")
        
        if data_source == "revenue":
            from modules.analytics.domain.models import RevenueAnalytics
            
            query = select(
                RevenueAnalytics.date,
                RevenueAnalytics.total_revenue
            ).where(
                RevenueAnalytics.agency_id == agency_id
            )
            
            if request.date_from:
                query = query.where(RevenueAnalytics.date >= request.date_from)
            if request.date_to:
                query = query.where(RevenueAnalytics.date <= request.date_to)
            if request.model_id:
                query = query.where(RevenueAnalytics.model_id == request.model_id)
            
            query = query.order_by(RevenueAnalytics.date)
            
            result = await db.execute(query)
            data = result.all()
            
            return {
                "chart_type": chart_type,
                "labels": [d.date.isoformat() for d in data],
                "datasets": [{
                    "label": "Revenue",
                    "data": [float(d.total_revenue) for d in data]
                }]
            }
        
        return {"chart_type": chart_type, "labels": [], "datasets": []}
    
    async def _build_table_widget(
        self,
        widget: ReportWidget,
        request: ReportGenerateRequest,
        agency_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Build data for table widget."""
        config = widget.config
        table_type = config.get("table_type", "transactions")
        
        if table_type == "top_fans":
            from modules.analytics.domain.models import Fan
            
            query = select(
                Fan.username,
                Fan.display_name,
                Fan.total_spent,
                Fan.lifetime_value,
                Fan.last_activity
            ).join(
                Fan.model
            ).where(
                Fan.model.has(agency_id=agency_id)
            )
            
            if request.model_id:
                query = query.where(Fan.model_id == request.model_id)
            
            query = query.order_by(Fan.total_spent.desc()).limit(10)
            
            result = await db.execute(query)
            fans = result.all()
            
            return {
                "columns": ["Username", "Display Name", "Total Spent", "Lifetime Value", "Last Activity"],
                "rows": [
                    [
                        f.username,
                        f.display_name or "-",
                        f"${f.total_spent:.2f}",
                        f"${f.lifetime_value:.2f}",
                        f.last_activity.strftime("%Y-%m-%d") if f.last_activity else "-"
                    ]
                    for f in fans
                ]
            }
        
        return {"columns": [], "rows": []}
    
    async def _build_text_widget(
        self,
        widget: ReportWidget,
        request: ReportGenerateRequest,
        agency_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Build data for text widget."""
        config = widget.config
        return {
            "content": config.get("content", ""),
            "format": config.get("format", "plain")
        }
    
    async def _build_comparison_widget(
        self,
        widget: ReportWidget,
        request: ReportGenerateRequest,
        agency_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Build data for comparison widget."""
        config = widget.config
        metrics = config.get("metrics", [])
        
        comparison_data = []
        for metric in metrics:
            # Get current value
            current = await self._get_metric_value(
                metric, request, agency_id, db
            )
            
            # Get previous value
            previous_request = ReportGenerateRequest(
                date_from=request.date_from - timedelta(days=30) if request.date_from else None,
                date_to=request.date_from - timedelta(days=1) if request.date_from else None,
                model_id=request.model_id,
                filters=request.filters
            )
            
            previous = await self._get_metric_value(
                metric, previous_request, agency_id, db
            )
            
            # Calculate change
            change = 0
            change_percent = 0
            if previous > 0:
                change = current - previous
                change_percent = (change / previous) * 100
            
            comparison_data.append({
                "metric": metric["name"],
                "current": current,
                "previous": previous,
                "change": change,
                "change_percent": change_percent
            })
        
        return {"comparisons": comparison_data}
    
    async def _get_metric_value(
        self,
        metric: Dict[str, Any],
        request: ReportGenerateRequest,
        agency_id: UUID,
        db: AsyncSession
    ) -> float:
        """Get a single metric value."""
        metric_type = metric.get("type")
        
        if metric_type == "revenue":
            from modules.financial.domain.models import Transaction
            
            query = select(func.sum(Transaction.amount)).where(
                Transaction.agency_id == agency_id,
                Transaction.status == "completed"
            )
            
            if request.date_from:
                query = query.where(Transaction.created_at >= request.date_from)
            if request.date_to:
                query = query.where(Transaction.created_at <= request.date_to)
            if request.model_id:
                query = query.where(Transaction.model_id == request.model_id)
            
            result = await db.execute(query)
            return float(result.scalar() or 0)
        
        return 0
    
    async def _calculate_comparison(
        self,
        base_query: Select,
        request: ReportGenerateRequest,
        db: AsyncSession,
        comparison_type: str
    ) -> Dict[str, Any]:
        """Calculate comparison data."""
        # This is simplified - would need proper date range calculation
        return {
            "previous_value": 0,
            "change": 0,
            "change_percent": 0,
            "trend": "neutral"
        }
    
    async def _cache_report(self, report: GeneratedReport):
        """Cache generated report."""
        cache_key = f"{self.cache_prefix}{report.id}"
        await redis_client.setex(
            cache_key,
            3600,  # 1 hour
            json.dumps(report.report_data, default=str)
        )
    
    async def get_report_templates(
        self,
        agency_id: UUID,
        skip: int = 0,
        limit: int = 20,
        db: AsyncSession = None
    ) -> List[ReportTemplate]:
        """Get available report templates."""
        query = select(ReportTemplate).where(
            or_(
                ReportTemplate.agency_id == agency_id,
                ReportTemplate.is_public == True
            )
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_generated_reports(
        self,
        agency_id: UUID,
        skip: int = 0,
        limit: int = 20,
        db: AsyncSession = None
    ) -> List[GeneratedReport]:
        """Get generated reports."""
        query = select(GeneratedReport).where(
            GeneratedReport.agency_id == agency_id
        ).order_by(
            GeneratedReport.created_at.desc()
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def duplicate_template(
        self,
        template_id: UUID,
        new_name: str,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> ReportTemplate:
        """Duplicate an existing template."""
        # Get original template
        result = await db.execute(
            select(ReportTemplate)
            .options(selectinload(ReportTemplate.widgets))
            .where(
                ReportTemplate.id == template_id,
                or_(
                    ReportTemplate.agency_id == agency_id,
                    ReportTemplate.is_public == True
                )
            )
        )
        original = result.scalar_one_or_none()
        
        if not original:
            raise NotFoundError("Report template not found")
        
        # Create duplicate
        duplicate = ReportTemplate(
            agency_id=agency_id,
            created_by_id=user_id,
            name=new_name,
            description=original.description,
            report_type=original.report_type,
            layout=original.layout,
            filters=original.filters,
            is_public=False
        )
        
        db.add(duplicate)
        await db.flush()
        
        # Duplicate widgets
        for widget in original.widgets:
            new_widget = ReportWidget(
                template_id=duplicate.id,
                widget_type=widget.widget_type,
                title=widget.title,
                config=widget.config,
                position=widget.position,
                size=widget.size
            )
            db.add(new_widget)
        
        await db.commit()
        return duplicate