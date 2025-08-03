"""
Analytics data export service.
"""
import logging
import csv
import json
import io
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from core.config import settings
from models.analytics import MetricSnapshot
from modules.analytics.domain.models import RevenueTransaction, ContentPerformance, FanSpendingHistory
from modules.analytics.domain.schemas import (
    ExportFormat,
    ExportRequest,
    ExportResponse
)
from core.domain.models import ModelProfile, Fan


logger = logging.getLogger(__name__)


class AnalyticsExporter:
    """Handles export of analytics data to various formats."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def export_data(
        self,
        model_id: str,
        request: ExportRequest
    ) -> ExportResponse:
        """
        Export analytics data based on request.
        
        Args:
            model_id: Model ID
            request: Export request details
            
        Returns:
            Export response with file information
        """
        export_id = str(uuid.uuid4())
        
        # Get data based on export type
        if request.export_type == "revenue":
            data = await self._get_revenue_data(model_id, request)
        elif request.export_type == "subscribers":
            data = await self._get_subscriber_data(model_id, request)
        elif request.export_type == "content":
            data = await self._get_content_data(model_id, request)
        elif request.export_type == "fans":
            data = await self._get_fan_data(model_id, request)
        else:
            raise ValueError(f"Unknown export type: {request.export_type}")
        
        # Generate file based on format
        if request.format == ExportFormat.CSV:
            file_content = self._generate_csv(data)
            file_extension = "csv"
            content_type = "text/csv"
        elif request.format == ExportFormat.JSON:
            file_content = self._generate_json(data, request.include_metadata)
            file_extension = "json"
            content_type = "application/json"
        else:
            raise ValueError(f"Unsupported format: {request.format}")
        
        # Save file (in production, this would upload to S3 or similar)
        file_name = f"export_{export_id}.{file_extension}"
        file_path = f"/tmp/{file_name}"  # Temporary storage
        
        with open(file_path, 'w') as f:
            f.write(file_content)
        
        # Generate response
        return ExportResponse(
            export_id=export_id,
            file_url=f"/api/v1/analytics/exports/{export_id}/download",
            file_size=len(file_content.encode()),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            format=request.format
        )
    
    async def _get_revenue_data(
        self,
        model_id: str,
        request: ExportRequest
    ) -> List[Dict[str, Any]]:
        """Get revenue data for export."""
        start_dt = datetime.combine(request.period_start, datetime.min.time())
        end_dt = datetime.combine(request.period_end, datetime.max.time())
        
        result = await self.db.execute(
            select(RevenueTransaction)
            .where(
                and_(
                    RevenueTransaction.model_id == model_id,
                    RevenueTransaction.transaction_date >= start_dt,
                    RevenueTransaction.transaction_date <= end_dt
                )
            )
            .order_by(RevenueTransaction.transaction_date.desc())
        )
        
        transactions = result.scalars().all()
        
        # Get fan details
        fan_ids = list(set(tx.fan_id for tx in transactions))
        fans_result = await self.db.execute(
            select(Fan).where(Fan.id.in_(fan_ids))
        )
        fans_by_id = {f.id: f for f in fans_result.scalars().all()}
        
        # Build export data
        data = []
        for tx in transactions:
            fan = fans_by_id.get(tx.fan_id)
            data.append({
                'transaction_id': str(tx.id),
                'date': tx.transaction_date.isoformat(),
                'fan_username': fan.username if fan else 'Unknown',
                'type': tx.transaction_type,
                'amount': float(tx.amount),
                'currency': tx.currency,
                'source': tx.source,
                'content_type': tx.content_type,
                'content_id': tx.content_id
            })
        
        return data
    
    async def _get_subscriber_data(
        self,
        model_id: str,
        request: ExportRequest
    ) -> List[Dict[str, Any]]:
        """Get subscriber data for export."""
        start_dt = datetime.combine(request.period_start, datetime.min.time())
        end_dt = datetime.combine(request.period_end, datetime.max.time())
        
        result = await self.db.execute(
            select(MetricSnapshot)
            .where(
                and_(
                    MetricSnapshot.model_id == model_id,
                    MetricSnapshot.timestamp >= start_dt,
                    MetricSnapshot.timestamp <= end_dt
                )
            )
            .order_by(MetricSnapshot.timestamp)
        )
        
        snapshots = result.scalars().all()
        
        data = []
        for snapshot in snapshots:
            data.append({
                'timestamp': snapshot.timestamp.isoformat(),
                'total_subscribers': snapshot.total_subscribers,
                'paying_subscribers': snapshot.paying_subscribers,
                'non_paying_fans': snapshot.non_paying_fans,
                'new_subscribers': snapshot.new_subscribers,
                'lost_subscribers': snapshot.lost_subscribers,
                'conversion_rate': float(snapshot.conversion_rate)
            })
        
        return data
    
    async def _get_content_data(
        self,
        model_id: str,
        request: ExportRequest
    ) -> List[Dict[str, Any]]:
        """Get content performance data for export."""
        start_dt = datetime.combine(request.period_start, datetime.min.time())
        end_dt = datetime.combine(request.period_end, datetime.max.time())
        
        result = await self.db.execute(
            select(ContentPerformance)
            .where(
                and_(
                    ContentPerformance.model_id == model_id,
                    ContentPerformance.published_at >= start_dt,
                    ContentPerformance.published_at <= end_dt
                )
            )
            .order_by(ContentPerformance.published_at.desc())
        )
        
        content = result.scalars().all()
        
        data = []
        for item in content:
            data.append({
                'content_id': item.content_id,
                'type': item.content_type,
                'title': item.title or 'Untitled',
                'published_at': item.published_at.isoformat(),
                'categories': ', '.join(item.categories or []),
                'views': item.views,
                'likes': item.likes,
                'comments': item.comments,
                'engagement_rate': round(
                    (item.likes + item.comments) / max(1, item.views) * 100, 2
                ),
                'total_revenue': float(item.total_revenue),
                'is_ppv': item.is_ppv,
                'ppv_price': float(item.ppv_price) if item.ppv_price else None
            })
        
        return data
    
    async def _get_fan_data(
        self,
        model_id: str,
        request: ExportRequest
    ) -> List[Dict[str, Any]]:
        """Get fan spending data for export."""
        start_dt = datetime.combine(request.period_start, datetime.min.time())
        end_dt = datetime.combine(request.period_end, datetime.max.time())
        
        # Get fans with spending in the period
        result = await self.db.execute(
            select(Fan)
            .where(Fan.model_id == model_id)
            .order_by(Fan.total_spent.desc())
        )
        
        fans = result.scalars().all()
        
        # Get spending history for each fan
        data = []
        for fan in fans:
            # Get spending in the period
            spending_result = await self.db.execute(
                select(FanSpendingHistory)
                .where(
                    and_(
                        FanSpendingHistory.fan_id == fan.id,
                        FanSpendingHistory.period_start >= start_dt,
                        FanSpendingHistory.period_end <= end_dt
                    )
                )
            )
            
            spending_records = spending_result.scalars().all()
            
            # Aggregate spending
            total_in_period = sum(s.total_amount for s in spending_records)
            subscription_amount = sum(s.subscription_amount for s in spending_records)
            tip_amount = sum(s.tip_amount for s in spending_records)
            ppv_amount = sum(s.ppv_amount for s in spending_records)
            
            if total_in_period > 0:
                data.append({
                    'fan_id': str(fan.id),
                    'username': fan.username,
                    'display_name': fan.display_name,
                    'total_spent_lifetime': float(fan.total_spent),
                    'total_spent_period': float(total_in_period),
                    'subscription_amount': float(subscription_amount),
                    'tip_amount': float(tip_amount),
                    'ppv_amount': float(ppv_amount),
                    'is_subscriber': fan.is_subscriber,
                    'is_paying': fan.is_paying,
                    'subscribed_at': fan.subscribed_at.isoformat() if fan.subscribed_at else None
                })
        
        return data
    
    def _generate_csv(self, data: List[Dict[str, Any]]) -> str:
        """Generate CSV file content."""
        if not data:
            return ""
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue()
    
    def _generate_json(
        self,
        data: List[Dict[str, Any]],
        include_metadata: bool
    ) -> str:
        """Generate JSON file content."""
        if include_metadata:
            export_data = {
                'metadata': {
                    'export_date': datetime.utcnow().isoformat(),
                    'record_count': len(data),
                    'fields': list(data[0].keys()) if data else []
                },
                'data': data
            }
        else:
            export_data = data
        
        return json.dumps(export_data, indent=2, default=str)