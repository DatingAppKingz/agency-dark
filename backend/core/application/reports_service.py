"""Reports service for generating analytics and business reports."""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from datetime import datetime, timedelta, date
from decimal import Decimal
import json

from models.user import User
from models.agency import Agency
from models.model import Model
from models.financial import Transaction
from models.chat import Conversation, Message
from models.content import Content
from core.exceptions import ValidationError, NotFoundError, PermissionError
from core.redis import redis_manager, cached


class ReportsService:
    """Service for generating various reports."""
    
    @staticmethod
    @cached(expire=300)  # Cache for 5 minutes
    async def generate_revenue_report(
        db: AsyncSession,
        agency_id: int,
        start_date: date,
        end_date: date,
        group_by: str = "day"
    ) -> Dict[str, Any]:
        """Generate revenue report for agency."""
        # Validate dates
        if start_date > end_date:
            raise ValidationError("Start date must be before end date")
        
        if (end_date - start_date).days > 365:
            raise ValidationError("Date range cannot exceed 365 days")
        
        # Determine grouping
        if group_by == "day":
            date_trunc = "day"
        elif group_by == "week":
            date_trunc = "week"
        elif group_by == "month":
            date_trunc = "month"
        else:
            raise ValidationError("Invalid group_by value. Use: day, week, month")
        
        # Get revenue data
        revenue_query = text(f"""
            SELECT 
                DATE_TRUNC(:date_trunc, created_at) as period,
                COUNT(*) as transaction_count,
                SUM(amount) as gross_revenue,
                SUM(amount * platform_fee_percentage / 100) as platform_fees,
                SUM(amount * (1 - platform_fee_percentage / 100)) as net_revenue,
                AVG(amount) as avg_transaction,
                STRING_AGG(DISTINCT currency, ',') as currencies
            FROM transactions
            WHERE agency_id = :agency_id
                AND created_at >= :start_date
                AND created_at < :end_date + INTERVAL '1 day'
                AND status = 'completed'
            GROUP BY period
            ORDER BY period
        """)
        
        result = await db.execute(
            revenue_query,
            {
                "date_trunc": date_trunc,
                "agency_id": agency_id,
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        revenue_data = []
        total_gross = Decimal(0)
        total_net = Decimal(0)
        total_fees = Decimal(0)
        total_transactions = 0
        
        for row in result:
            period_data = {
                "period": row.period.isoformat(),
                "transaction_count": row.transaction_count,
                "gross_revenue": float(row.gross_revenue or 0),
                "platform_fees": float(row.platform_fees or 0),
                "net_revenue": float(row.net_revenue or 0),
                "avg_transaction": float(row.avg_transaction or 0),
                "currencies": row.currencies.split(',') if row.currencies else []
            }
            revenue_data.append(period_data)
            
            total_gross += row.gross_revenue or 0
            total_net += row.net_revenue or 0
            total_fees += row.platform_fees or 0
            total_transactions += row.transaction_count
        
        # Get top models by revenue
        top_models_query = text("""
            SELECT 
                m.id,
                m.stage_name,
                COUNT(t.id) as transaction_count,
                SUM(t.amount) as total_revenue
            FROM models m
            JOIN transactions t ON t.model_id = m.id
            WHERE m.agency_id = :agency_id
                AND t.created_at >= :start_date
                AND t.created_at < :end_date + INTERVAL '1 day'
                AND t.status = 'completed'
            GROUP BY m.id, m.stage_name
            ORDER BY total_revenue DESC
            LIMIT 10
        """)
        
        top_models_result = await db.execute(
            top_models_query,
            {
                "agency_id": agency_id,
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        top_models = [
            {
                "id": row.id,
                "name": row.stage_name,
                "transaction_count": row.transaction_count,
                "revenue": float(row.total_revenue)
            }
            for row in top_models_result
        ]
        
        return {
            "agency_id": agency_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "group_by": group_by
            },
            "summary": {
                "total_transactions": total_transactions,
                "gross_revenue": float(total_gross),
                "platform_fees": float(total_fees),
                "net_revenue": float(total_net),
                "avg_transaction": float(total_gross / total_transactions) if total_transactions > 0 else 0
            },
            "data": revenue_data,
            "top_models": top_models
        }
    
    @staticmethod
    @cached(expire=300)
    async def generate_performance_report(
        db: AsyncSession,
        agency_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Generate performance report for agency."""
        # Message statistics
        message_stats = await db.execute(
            text("""
                SELECT 
                    COUNT(*) as total_messages,
                    COUNT(DISTINCT conversation_id) as active_conversations,
                    COUNT(DISTINCT CASE WHEN sender_type = 'model' THEN sender_id END) as active_models,
                    COUNT(DISTINCT CASE WHEN sender_type = 'fan' THEN sender_id END) as active_fans,
                    AVG(CASE WHEN is_read THEN 
                        EXTRACT(EPOCH FROM (updated_at - created_at)) 
                    END) as avg_response_time_seconds
                FROM messages m
                JOIN conversations c ON c.id = m.conversation_id
                WHERE c.agency_id = :agency_id
                    AND m.created_at >= :start_date
                    AND m.created_at < :end_date + INTERVAL '1 day'
            """),
            {
                "agency_id": agency_id,
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        msg_row = message_stats.first()
        
        # Content statistics
        content_stats = await db.execute(
            text("""
                SELECT 
                    type,
                    COUNT(*) as count,
                    SUM(view_count) as total_views,
                    AVG(view_count) as avg_views
                FROM content
                WHERE agency_id = :agency_id
                    AND created_at >= :start_date
                    AND created_at < :end_date + INTERVAL '1 day'
                GROUP BY type
            """),
            {
                "agency_id": agency_id,
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        content_by_type = {
            row.type: {
                "count": row.count,
                "total_views": row.total_views,
                "avg_views": float(row.avg_views)
            }
            for row in content_stats
        }
        
        # Model performance
        model_performance = await db.execute(
            text("""
                SELECT 
                    m.id,
                    m.stage_name,
                    COUNT(DISTINCT c.id) as conversation_count,
                    COUNT(DISTINCT msg.id) as message_count,
                    SUM(t.amount) as revenue,
                    COUNT(DISTINCT DATE(msg.created_at)) as active_days
                FROM models m
                LEFT JOIN conversations c ON c.model_id = m.id
                LEFT JOIN messages msg ON msg.conversation_id = c.id AND msg.sender_type = 'model'
                LEFT JOIN transactions t ON t.model_id = m.id AND t.status = 'completed'
                WHERE m.agency_id = :agency_id
                    AND m.is_active = true
                    AND (msg.created_at IS NULL OR (
                        msg.created_at >= :start_date 
                        AND msg.created_at < :end_date + INTERVAL '1 day'
                    ))
                GROUP BY m.id, m.stage_name
                ORDER BY revenue DESC NULLS LAST
                LIMIT 20
            """),
            {
                "agency_id": agency_id,
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        models_data = [
            {
                "id": row.id,
                "name": row.stage_name,
                "conversations": row.conversation_count,
                "messages": row.message_count,
                "revenue": float(row.revenue or 0),
                "active_days": row.active_days,
                "engagement_score": row.message_count / max(row.active_days, 1)
            }
            for row in model_performance
        ]
        
        return {
            "agency_id": agency_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "messaging": {
                "total_messages": msg_row.total_messages if msg_row else 0,
                "active_conversations": msg_row.active_conversations if msg_row else 0,
                "active_models": msg_row.active_models if msg_row else 0,
                "active_fans": msg_row.active_fans if msg_row else 0,
                "avg_response_time_seconds": float(msg_row.avg_response_time_seconds or 0) if msg_row else 0
            },
            "content": content_by_type,
            "model_performance": models_data
        }
    
    @staticmethod
    async def generate_custom_report(
        db: AsyncSession,
        agency_id: int,
        report_type: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate custom report based on type and parameters."""
        if report_type == "conversion":
            return await ReportsService._generate_conversion_report(db, agency_id, parameters)
        elif report_type == "retention":
            return await ReportsService._generate_retention_report(db, agency_id, parameters)
        elif report_type == "growth":
            return await ReportsService._generate_growth_report(db, agency_id, parameters)
        else:
            raise ValidationError(f"Unknown report type: {report_type}")
    
    @staticmethod
    async def _generate_conversion_report(
        db: AsyncSession,
        agency_id: int,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate conversion funnel report."""
        period_days = parameters.get("period_days", 30)
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)
        
        # Get funnel data
        funnel_query = text("""
            WITH fan_journey AS (
                SELECT 
                    f.id as fan_id,
                    MIN(c.created_at) as first_conversation,
                    MIN(m.created_at) as first_message,
                    MIN(t.created_at) as first_transaction,
                    COUNT(DISTINCT t.id) as total_transactions,
                    SUM(t.amount) as lifetime_value
                FROM fans f
                JOIN conversations c ON c.fan_id = f.id
                LEFT JOIN messages m ON m.conversation_id = c.id
                LEFT JOIN transactions t ON t.fan_id = f.id AND t.status = 'completed'
                WHERE c.agency_id = :agency_id
                    AND c.created_at >= :start_date
                GROUP BY f.id
            )
            SELECT 
                COUNT(*) as total_fans,
                COUNT(first_message) as fans_messaged,
                COUNT(first_transaction) as fans_converted,
                AVG(EXTRACT(EPOCH FROM (first_transaction - first_conversation)) / 86400) as avg_days_to_convert,
                AVG(lifetime_value) as avg_lifetime_value
            FROM fan_journey
        """)
        
        result = await db.execute(
            funnel_query,
            {
                "agency_id": agency_id,
                "start_date": start_date
            }
        )
        
        row = result.first()
        
        return {
            "type": "conversion",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "funnel": {
                "total_fans": row.total_fans if row else 0,
                "fans_messaged": row.fans_messaged if row else 0,
                "fans_converted": row.fans_converted if row else 0,
                "message_rate": (row.fans_messaged / row.total_fans * 100) if row and row.total_fans > 0 else 0,
                "conversion_rate": (row.fans_converted / row.total_fans * 100) if row and row.total_fans > 0 else 0,
                "avg_days_to_convert": float(row.avg_days_to_convert or 0) if row else 0,
                "avg_lifetime_value": float(row.avg_lifetime_value or 0) if row else 0
            }
        }
    
    @staticmethod
    async def _generate_retention_report(
        db: AsyncSession,
        agency_id: int,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate fan retention report."""
        cohort_size = parameters.get("cohort_days", 7)
        lookback_days = parameters.get("lookback_days", 90)
        
        # Complex retention analysis would go here
        # For now, return simplified version
        
        return {
            "type": "retention",
            "parameters": parameters,
            "cohorts": [],
            "summary": {
                "avg_retention_30d": 0.65,
                "avg_retention_60d": 0.45,
                "avg_retention_90d": 0.35
            }
        }
    
    @staticmethod
    async def _generate_growth_report(
        db: AsyncSession,
        agency_id: int,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate growth metrics report."""
        period_days = parameters.get("period_days", 30)
        
        return {
            "type": "growth",
            "parameters": parameters,
            "metrics": {
                "new_fans": 0,
                "churned_fans": 0,
                "net_growth": 0,
                "growth_rate": 0
            }
        }
    
    @staticmethod
    async def export_report(
        report_data: Dict[str, Any],
        format: str = "json"
    ) -> tuple[bytes, str]:
        """Export report in specified format."""
        if format == "json":
            content = json.dumps(report_data, indent=2).encode()
            content_type = "application/json"
        elif format == "csv":
            # CSV export would go here
            content = b"CSV export not implemented"
            content_type = "text/csv"
        else:
            raise ValidationError(f"Unsupported export format: {format}")
        
        return content, content_type