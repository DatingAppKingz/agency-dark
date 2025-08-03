"""
Analytics export service for generating CSV, Excel, and PDF reports.
"""
import logging
from typing import List, Dict, Any, Optional, BinaryIO
from datetime import datetime, timedelta
from uuid import UUID
import io
import csv
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, LineChart, Reference
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from core.exceptions import BadRequestError
from core.redis import redis_client
from modules.analytics.domain.models import (\n    ModelAnalytics,\n    FanAnalytics,\n    RevenueAnalytics,\n    EngagementAnalytics,\n    ContentAnalytics\n)
from modules.messaging.domain.models import BulkMessage, MessageSchedule
from modules.financial.domain.models import Transaction, Commission

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting analytics data in various formats."""
    
    def __init__(self):
        self.cache_prefix = "export:"
        self.cache_ttl = 3600  # 1 hour
        
    async def export_analytics(
        self,
        export_type: str,
        format: str,
        agency_id: UUID,
        model_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        db: AsyncSession = None
    ) -> BinaryIO:
        """Export analytics data in specified format."""
        # Validate format
        valid_formats = ['csv', 'excel', 'pdf', 'json']
        if format not in valid_formats:
            raise BadRequestError(f"Invalid format. Choose from: {valid_formats}")
        
        # Get data based on export type
        data = await self._get_export_data(
            export_type, agency_id, model_id, date_from, date_to, filters, db
        )
        
        # Generate export based on format
        if format == 'csv':
            return self._export_csv(data, export_type)
        elif format == 'excel':
            return self._export_excel(data, export_type)
        elif format == 'pdf':
            return self._export_pdf(data, export_type)
        elif format == 'json':
            return self._export_json(data, export_type)
    
    async def _get_export_data(
        self,
        export_type: str,
        agency_id: UUID,
        model_id: Optional[UUID],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        filters: Optional[Dict[str, Any]],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get data for export based on type."""
        if not date_from:
            date_from = datetime.utcnow() - timedelta(days=30)
        if not date_to:
            date_to = datetime.utcnow()
        
        data = {
            "metadata": {
                "export_type": export_type,
                "agency_id": str(agency_id),
                "model_id": str(model_id) if model_id else None,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "generated_at": datetime.utcnow().isoformat()
            }
        }
        
        if export_type == "revenue":
            data["revenue"] = await self._get_revenue_data(
                agency_id, model_id, date_from, date_to, db
            )
        elif export_type == "engagement":
            data["engagement"] = await self._get_engagement_data(
                agency_id, model_id, date_from, date_to, db
            )
        elif export_type == "fans":
            data["fans"] = await self._get_fan_data(
                agency_id, model_id, date_from, date_to, filters, db
            )
        elif export_type == "content":
            data["content"] = await self._get_content_data(
                agency_id, model_id, date_from, date_to, db
            )
        elif export_type == "messages":
            data["messages"] = await self._get_message_data(
                agency_id, model_id, date_from, date_to, db
            )
        elif export_type == "financial":
            data["financial"] = await self._get_financial_data(
                agency_id, model_id, date_from, date_to, db
            )
        elif export_type == "comprehensive":
            # Get all data types
            data["revenue"] = await self._get_revenue_data(
                agency_id, model_id, date_from, date_to, db
            )
            data["engagement"] = await self._get_engagement_data(
                agency_id, model_id, date_from, date_to, db
            )
            data["fans"] = await self._get_fan_data(
                agency_id, model_id, date_from, date_to, filters, db
            )
        else:
            raise BadRequestError(f"Invalid export type: {export_type}")
        
        return data
    
    async def _get_revenue_data(
        self,
        agency_id: UUID,
        model_id: Optional[UUID],
        date_from: datetime,
        date_to: datetime,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get revenue analytics data."""
        query = select(RevenueAnalytics).where(
            RevenueAnalytics.agency_id == agency_id,
            RevenueAnalytics.date >= date_from,
            RevenueAnalytics.date <= date_to
        )
        
        if model_id:
            query = query.where(RevenueAnalytics.model_id == model_id)
        
        query = query.order_by(RevenueAnalytics.date)
        
        result = await db.execute(query)
        analytics = result.scalars().all()
        
        return [
            {
                "date": a.date.isoformat(),
                "total_revenue": float(a.total_revenue or 0),
                "subscription_revenue": float(a.subscription_revenue or 0),
                "tip_revenue": float(a.tip_revenue or 0),
                "ppv_revenue": float(a.ppv_revenue or 0),
                "message_revenue": float(a.message_revenue or 0),
                "transaction_count": a.transaction_count,
                "model_name": a.model.display_name if a.model else None
            }
            for a in analytics
        ]
    
    async def _get_engagement_data(
        self,
        agency_id: UUID,
        model_id: Optional[UUID],
        date_from: datetime,
        date_to: datetime,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get engagement analytics data."""
        query = select(EngagementAnalytics).where(
            EngagementAnalytics.agency_id == agency_id,
            EngagementAnalytics.date >= date_from,
            EngagementAnalytics.date <= date_to
        )
        
        if model_id:
            query = query.where(EngagementAnalytics.model_id == model_id)
        
        result = await db.execute(query)
        analytics = result.scalars().all()
        
        return [
            {
                "date": a.date.isoformat(),
                "messages_sent": a.messages_sent,
                "messages_received": a.messages_received,
                "avg_response_time": a.avg_response_time,
                "unique_conversations": a.unique_conversations,
                "media_sent": a.media_sent,
                "likes_received": a.likes_received,
                "comments_received": a.comments_received
            }
            for a in analytics
        ]
    
    async def _get_fan_data(
        self,
        agency_id: UUID,
        model_id: Optional[UUID],
        date_from: datetime,
        date_to: datetime,
        filters: Optional[Dict[str, Any]],
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get fan analytics data."""
        from modules.analytics.domain.models import Fan
        
        query = select(Fan).join(
            Fan.model
        ).where(
            Fan.model.has(agency_id=agency_id),
            Fan.created_at >= date_from,
            Fan.created_at <= date_to
        )
        
        if model_id:
            query = query.where(Fan.model_id == model_id)
        
        # Apply filters
        if filters:
            if filters.get("subscription_status"):
                query = query.where(Fan.subscription_status.in_(filters["subscription_status"]))
            if filters.get("spent_min"):
                query = query.where(Fan.total_spent >= filters["spent_min"])
            if filters.get("spent_max"):
                query = query.where(Fan.total_spent <= filters["spent_max"])
        
        result = await db.execute(query)
        fans = result.scalars().all()
        
        return [
            {
                "fan_id": str(f.id),
                "username": f.username,
                "display_name": f.display_name,
                "subscription_status": f.subscription_status,
                "subscribed_at": f.subscribed_at.isoformat() if f.subscribed_at else None,
                "total_spent": float(f.total_spent or 0),
                "message_count": f.message_count,
                "last_activity": f.last_activity.isoformat() if f.last_activity else None,
                "lifetime_value": float(f.lifetime_value or 0),
                "tags": f.tags or []
            }
            for f in fans
        ]
    
    async def _get_content_data(
        self,
        agency_id: UUID,
        model_id: Optional[UUID],
        date_from: datetime,
        date_to: datetime,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get content analytics data."""
        query = select(ContentAnalytics).where(
            ContentAnalytics.agency_id == agency_id,
            ContentAnalytics.created_at >= date_from,
            ContentAnalytics.created_at <= date_to
        )
        
        if model_id:
            query = query.where(ContentAnalytics.model_id == model_id)
        
        result = await db.execute(query)
        content = result.scalars().all()
        
        return [
            {
                "content_id": str(c.id),
                "type": c.content_type,
                "title": c.title,
                "posted_at": c.posted_at.isoformat(),
                "views": c.views,
                "likes": c.likes,
                "comments": c.comments,
                "revenue_generated": float(c.revenue_generated or 0),
                "engagement_rate": c.engagement_rate
            }
            for c in content
        ]
    
    async def _get_message_data(
        self,
        agency_id: UUID,
        model_id: Optional[UUID],
        date_from: datetime,
        date_to: datetime,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get messaging analytics data."""
        # Bulk messages
        bulk_query = select(BulkMessage).where(
            BulkMessage.agency_id == agency_id,
            BulkMessage.created_at >= date_from,
            BulkMessage.created_at <= date_to
        )
        
        if model_id:
            bulk_query = bulk_query.where(BulkMessage.model_id == model_id)
        
        bulk_result = await db.execute(bulk_query)
        bulk_messages = bulk_result.scalars().all()
        
        # Scheduled messages
        schedule_query = select(MessageSchedule).where(
            MessageSchedule.agency_id == agency_id,
            MessageSchedule.created_at >= date_from,
            MessageSchedule.created_at <= date_to
        )
        
        if model_id:
            schedule_query = schedule_query.where(MessageSchedule.model_id == model_id)
        
        schedule_result = await db.execute(schedule_query)
        scheduled_messages = schedule_result.scalars().all()
        
        return {
            "bulk_campaigns": [
                {
                    "campaign_name": b.campaign_name,
                    "status": b.status,
                    "total_recipients": b.total_recipients,
                    "sent_count": b.sent_count,
                    "failed_count": b.failed_count,
                    "created_at": b.created_at.isoformat(),
                    "completed_at": b.completed_at.isoformat() if b.completed_at else None
                }
                for b in bulk_messages
            ],
            "scheduled_messages": [
                {
                    "scheduled_for": s.scheduled_for.isoformat(),
                    "status": s.status,
                    "is_recurring": s.is_recurring,
                    "platform": s.platform,
                    "created_at": s.created_at.isoformat()
                }
                for s in scheduled_messages
            ]
        }
    
    async def _get_financial_data(
        self,
        agency_id: UUID,
        model_id: Optional[UUID],
        date_from: datetime,
        date_to: datetime,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get financial data including transactions and commissions."""
        # Transactions
        trans_query = select(Transaction).where(
            Transaction.agency_id == agency_id,
            Transaction.created_at >= date_from,
            Transaction.created_at <= date_to
        )
        
        if model_id:
            trans_query = trans_query.where(Transaction.model_id == model_id)
        
        trans_result = await db.execute(trans_query)
        transactions = trans_result.scalars().all()
        
        # Commissions
        comm_query = select(Commission).where(
            Commission.agency_id == agency_id,
            Commission.created_at >= date_from,
            Commission.created_at <= date_to
        )
        
        if model_id:
            comm_query = comm_query.where(Commission.model_id == model_id)
        
        comm_result = await db.execute(comm_query)
        commissions = comm_result.scalars().all()
        
        return {
            "transactions": [
                {
                    "transaction_id": str(t.id),
                    "type": t.transaction_type,
                    "amount": float(t.amount),
                    "currency": t.currency,
                    "status": t.status,
                    "created_at": t.created_at.isoformat()
                }
                for t in transactions
            ],
            "commissions": [
                {
                    "commission_id": str(c.id),
                    "gross_amount": float(c.gross_amount),
                    "commission_rate": float(c.commission_rate),
                    "commission_amount": float(c.commission_amount),
                    "net_amount": float(c.net_amount),
                    "status": c.status,
                    "created_at": c.created_at.isoformat()
                }
                for c in commissions
            ],
            "summary": {
                "total_revenue": sum(float(t.amount) for t in transactions),
                "total_commissions": sum(float(c.commission_amount) for c in commissions),
                "transaction_count": len(transactions)
            }
        }
    
    def _export_csv(self, data: Dict[str, Any], export_type: str) -> BinaryIO:
        """Export data as CSV."""
        output = io.StringIO()
        
        # Get the main data array
        main_data = None
        if "revenue" in data:
            main_data = data["revenue"]
        elif "engagement" in data:
            main_data = data["engagement"]
        elif "fans" in data:
            main_data = data["fans"]
        elif "content" in data:
            main_data = data["content"]
        
        if not main_data:
            raise BadRequestError("No data to export")
        
        # Write CSV
        if main_data:
            fieldnames = list(main_data[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(main_data)
        
        # Convert to bytes
        output.seek(0)
        return io.BytesIO(output.getvalue().encode('utf-8'))
    
    def _export_excel(self, data: Dict[str, Any], export_type: str) -> BinaryIO:
        """Export data as Excel with formatting and charts."""
        wb = Workbook()
        
        # Remove default sheet
        wb.remove(wb.active)
        
        # Add metadata sheet
        metadata_sheet = wb.create_sheet("Metadata")
        metadata_sheet.append(["Export Information"])
        for key, value in data["metadata"].items():
            metadata_sheet.append([key.replace("_", " ").title(), value])
        
        # Add data sheets
        if "revenue" in data and data["revenue"]:
            self._add_revenue_sheet(wb, data["revenue"])
        
        if "engagement" in data and data["engagement"]:
            self._add_engagement_sheet(wb, data["engagement"])
        
        if "fans" in data and data["fans"]:
            self._add_fans_sheet(wb, data["fans"])
        
        if "financial" in data:
            self._add_financial_sheet(wb, data["financial"])
        
        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output
    
    def _add_revenue_sheet(self, wb: Workbook, revenue_data: List[Dict[str, Any]]):
        """Add revenue sheet with chart to Excel workbook."""
        ws = wb.create_sheet("Revenue")
        
        # Headers
        headers = ["Date", "Total Revenue", "Subscriptions", "Tips", "PPV", "Messages"]
        ws.append(headers)
        
        # Style headers
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.font = Font(color="FFFFFF", bold=True)
        
        # Add data
        for row in revenue_data:
            ws.append([
                row["date"],
                row["total_revenue"],
                row["subscription_revenue"],
                row["tip_revenue"],
                row["ppv_revenue"],
                row["message_revenue"]
            ])
        
        # Add chart
        chart = LineChart()
        chart.title = "Revenue Over Time"
        chart.y_axis.title = "Revenue ($)"
        chart.x_axis.title = "Date"
        
        data_ref = Reference(ws, min_col=2, min_row=1, max_col=6, max_row=len(revenue_data) + 1)
        chart.add_data(data_ref, titles_from_data=True)
        
        dates = Reference(ws, min_col=1, min_row=2, max_row=len(revenue_data) + 1)
        chart.set_categories(dates)
        
        ws.add_chart(chart, "H2")
        
        # Auto-fit columns
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            ws.column_dimensions[column_letter].width = min(max_length + 2, 50)
    
    def _add_engagement_sheet(self, wb: Workbook, engagement_data: List[Dict[str, Any]]):
        """Add engagement sheet to Excel workbook."""
        ws = wb.create_sheet("Engagement")
        
        # Headers
        headers = list(engagement_data[0].keys()) if engagement_data else []
        ws.append(headers)
        
        # Style headers
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.font = Font(color="FFFFFF", bold=True)
        
        # Add data
        for row in engagement_data:
            ws.append(list(row.values()))
    
    def _add_fans_sheet(self, wb: Workbook, fans_data: List[Dict[str, Any]]):
        """Add fans sheet to Excel workbook."""
        ws = wb.create_sheet("Fans")
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(fans_data)
        
        # Write headers
        headers = df.columns.tolist()
        ws.append(headers)
        
        # Style headers
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.font = Font(color="FFFFFF", bold=True)
        
        # Add data
        for _, row in df.iterrows():
            ws.append(row.tolist())
        
        # Add summary statistics
        ws.append([])
        ws.append(["Summary Statistics"])
        ws.append(["Total Fans", len(fans_data)])
        ws.append(["Average Lifetime Value", df["lifetime_value"].mean() if "lifetime_value" in df else 0])
        ws.append(["Total Revenue", df["total_spent"].sum() if "total_spent" in df else 0])
    
    def _add_financial_sheet(self, wb: Workbook, financial_data: Dict[str, Any]):
        """Add financial sheet to Excel workbook."""
        ws = wb.create_sheet("Financial")
        
        # Summary section
        ws.append(["Financial Summary"])
        ws.append(["Total Revenue", financial_data["summary"]["total_revenue"]])
        ws.append(["Total Commissions", financial_data["summary"]["total_commissions"]])
        ws.append(["Transaction Count", financial_data["summary"]["transaction_count"]])
        ws.append([])
        
        # Transactions section
        if financial_data["transactions"]:
            ws.append(["Transactions"])
            trans_headers = list(financial_data["transactions"][0].keys())
            ws.append(trans_headers)
            
            for trans in financial_data["transactions"]:
                ws.append(list(trans.values()))
    
    def _export_pdf(self, data: Dict[str, Any], export_type: str) -> BinaryIO:
        """Export data as PDF report."""
        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1976D2')
        )
        elements.append(Paragraph(f"{export_type.title()} Analytics Report", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Metadata
        metadata_data = [
            ["Report Information", ""],
            ["Generated At", data["metadata"]["generated_at"]],
            ["Date Range", f"{data['metadata']['date_from']} to {data['metadata']['date_to']}"],
            ["Export Type", data["metadata"]["export_type"]]
        ]
        
        metadata_table = Table(metadata_data, colWidths=[2*inch, 4*inch])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(metadata_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Add data sections
        if "revenue" in data and data["revenue"]:
            elements.append(Paragraph("Revenue Analytics", styles['Heading2']))
            revenue_table_data = [
                ["Date", "Total", "Subscriptions", "Tips", "PPV", "Messages"]
            ]
            for row in data["revenue"][:10]:  # Limit rows for PDF
                revenue_table_data.append([
                    row["date"],
                    f"${row['total_revenue']:.2f}",
                    f"${row['subscription_revenue']:.2f}",
                    f"${row['tip_revenue']:.2f}",
                    f"${row['ppv_revenue']:.2f}",
                    f"${row['message_revenue']:.2f}"
                ])
            
            revenue_table = Table(revenue_table_data)
            revenue_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(revenue_table)
        
        doc.build(elements)
        output.seek(0)
        return output
    
    def _export_json(self, data: Dict[str, Any], export_type: str) -> BinaryIO:
        """Export data as JSON."""
        json_str = json.dumps(data, indent=2, default=str)
        return io.BytesIO(json_str.encode('utf-8'))