"""
Optimized query builders for common database operations.
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import json
from sqlalchemy import select, func, and_, or_, case, text
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.models import (
    ModelProfile, User, Agency, Fan, 
    Notification, AuditLog
)
from modules.financial.domain.models import (
    FinancialTransaction, BillingCycle, Payout,
    TransactionType, PayoutStatus
)
from modules.analytics.domain.models import (
    MetricSnapshot, RevenueTransaction,
    ContentPerformance, FanSpendingHistory
)


class OptimizedQueries:
    """Collection of optimized database queries."""
    
    @staticmethod
    def get_model_with_relations():
        """Get model profile with commonly needed relations."""
        return (
            select(ModelProfile)
            .options(
                selectinload(ModelProfile.agency),
                selectinload(ModelProfile.user),
                selectinload(ModelProfile.chatters)
            )
        )
    
    @staticmethod
    def get_active_models_for_agency(agency_id: str):
        """Get active models for an agency with optimized loading."""
        return (
            select(ModelProfile)
            .where(
                and_(
                    ModelProfile.agency_id == agency_id,
                    ModelProfile.is_active == True
                )
            )
            .options(selectinload(ModelProfile.user))
            .order_by(ModelProfile.total_earnings.desc())
        )
    
    @staticmethod
    def get_model_financial_summary(
        model_id: str,
        start_date: datetime,
        end_date: datetime
    ):
        """Get financial summary for a model using aggregation."""
        return (
            select(
                func.sum(
                    case(
                        (FinancialTransaction.type == TransactionType.REVENUE, 
                         FinancialTransaction.amount),
                        else_=0
                    )
                ).label('total_revenue'),
                func.sum(
                    case(
                        (FinancialTransaction.type == TransactionType.COMMISSION,
                         FinancialTransaction.amount),
                        else_=0
                    )
                ).label('total_commission'),
                func.sum(
                    case(
                        (FinancialTransaction.type == TransactionType.PAYOUT,
                         FinancialTransaction.amount),
                        else_=0
                    )
                ).label('total_payouts'),
                func.count(
                    case(
                        (FinancialTransaction.type == TransactionType.REVENUE, 1)
                    )
                ).label('revenue_count')
            )
            .where(
                and_(
                    FinancialTransaction.model_id == model_id,
                    FinancialTransaction.transaction_date >= start_date,
                    FinancialTransaction.transaction_date <= end_date
                )
            )
        )
    
    @staticmethod
    def get_top_performing_models(
        agency_id: str,
        limit: int = 10,
        period_days: int = 30
    ):
        """Get top performing models by revenue."""
        cutoff_date = datetime.utcnow() - timedelta(days=period_days)
        
        return text("""
            WITH model_revenue AS (
                SELECT 
                    m.id,
                    m.onlyfans_username,
                    m.display_name,
                    m.total_earnings,
                    COALESCE(SUM(ft.amount) FILTER (WHERE ft.type = 'revenue'), 0) as period_revenue,
                    COUNT(DISTINCT f.id) FILTER (WHERE f.is_paying = true) as paying_fans
                FROM model_profiles m
                LEFT JOIN financial_transactions ft ON ft.model_id = m.id
                    AND ft.transaction_date >= :cutoff_date
                    AND ft.type = 'revenue'
                LEFT JOIN fans f ON f.model_id = m.id
                WHERE m.agency_id = :agency_id
                    AND m.is_active = true
                GROUP BY m.id, m.onlyfans_username, m.display_name, m.total_earnings
            )
            SELECT * FROM model_revenue
            ORDER BY period_revenue DESC
            LIMIT :limit
        """)
    
    @staticmethod
    def get_fan_value_segments(model_id: str):
        """Get fan segmentation by lifetime value."""
        return text("""
            WITH fan_values AS (
                SELECT 
                    f.id,
                    f.username,
                    f.is_paying,
                    f.total_spent,
                    f.last_active_at,
                    CASE 
                        WHEN f.total_spent >= 1000 THEN 'whale'
                        WHEN f.total_spent >= 500 THEN 'high_value'
                        WHEN f.total_spent >= 100 THEN 'medium_value'
                        WHEN f.total_spent > 0 THEN 'low_value'
                        ELSE 'free'
                    END as segment,
                    COUNT(rt.id) as transaction_count,
                    MAX(rt.transaction_date) as last_transaction
                FROM fans f
                LEFT JOIN revenue_transactions rt ON rt.fan_id = f.id
                WHERE f.model_id = :model_id
                GROUP BY f.id, f.username, f.is_paying, f.total_spent, f.last_active_at
            )
            SELECT 
                segment,
                COUNT(*) as fan_count,
                SUM(total_spent) as segment_revenue,
                AVG(total_spent) as avg_fan_value,
                COUNT(*) FILTER (WHERE last_active_at >= CURRENT_DATE - INTERVAL '30 days') as active_30d
            FROM fan_values
            GROUP BY segment
            ORDER BY 
                CASE segment
                    WHEN 'whale' THEN 1
                    WHEN 'high_value' THEN 2
                    WHEN 'medium_value' THEN 3
                    WHEN 'low_value' THEN 4
                    ELSE 5
                END
        """)
    
    @staticmethod
    def get_revenue_trends(
        model_id: str,
        days: int = 30,
        granularity: str = 'daily'
    ):
        """Get revenue trends with configurable granularity."""
        date_trunc = 'day' if granularity == 'daily' else 'week'
        
        return text(f"""
            WITH date_series AS (
                SELECT generate_series(
                    CURRENT_DATE - INTERVAL '{days} days',
                    CURRENT_DATE,
                    INTERVAL '1 {date_trunc}'
                )::date as period
            ),
            revenue_by_period AS (
                SELECT 
                    DATE_TRUNC('{date_trunc}', rt.transaction_date)::date as period,
                    COUNT(DISTINCT rt.fan_id) as unique_fans,
                    COUNT(*) as transaction_count,
                    SUM(rt.amount) as revenue,
                    AVG(rt.amount) as avg_transaction,
                    SUM(rt.amount) FILTER (WHERE rt.transaction_type = 'subscription') as subscription_revenue,
                    SUM(rt.amount) FILTER (WHERE rt.transaction_type = 'tip') as tip_revenue,
                    SUM(rt.amount) FILTER (WHERE rt.transaction_type LIKE 'ppv%') as ppv_revenue
                FROM revenue_transactions rt
                WHERE rt.model_id = :model_id
                    AND rt.transaction_date >= CURRENT_DATE - INTERVAL '{days} days'
                GROUP BY DATE_TRUNC('{date_trunc}', rt.transaction_date)
            )
            SELECT 
                ds.period,
                COALESCE(rbp.unique_fans, 0) as unique_fans,
                COALESCE(rbp.transaction_count, 0) as transaction_count,
                COALESCE(rbp.revenue, 0) as revenue,
                COALESCE(rbp.avg_transaction, 0) as avg_transaction,
                COALESCE(rbp.subscription_revenue, 0) as subscription_revenue,
                COALESCE(rbp.tip_revenue, 0) as tip_revenue,
                COALESCE(rbp.ppv_revenue, 0) as ppv_revenue
            FROM date_series ds
            LEFT JOIN revenue_by_period rbp ON ds.period = rbp.period
            ORDER BY ds.period
        """)
    
    @staticmethod
    def get_pending_payouts(
        limit: Optional[int] = None,
        recipient_type: Optional[str] = None
    ):
        """Get pending payouts with related data."""
        query = (
            select(Payout)
            .where(
                Payout.status.in_([
                    PayoutStatus.PENDING,
                    PayoutStatus.PROCESSING
                ])
            )
            .options(
                joinedload(Payout.billing_cycle),
                joinedload(Payout.recipient)
            )
            .order_by(Payout.scheduled_at.asc())
        )
        
        if recipient_type:
            query = query.where(Payout.recipient_type == recipient_type)
        
        if limit:
            query = query.limit(limit)
        
        return query
    
    @staticmethod
    def calculate_model_balance(model_id: str):
        """Calculate current balance for a model."""
        return text("""
            SELECT calculate_model_balance(:model_id) as balance
        """)
    
    @staticmethod
    def get_content_performance_summary(
        model_id: str,
        days: int = 30
    ):
        """Get content performance summary."""
        return text("""
            WITH recent_content AS (
                SELECT 
                    content_type,
                    COUNT(*) as content_count,
                    SUM(views) as total_views,
                    SUM(likes) as total_likes,
                    SUM(total_revenue) as total_revenue,
                    AVG(CASE WHEN views > 0 THEN (likes::float / views * 100) ELSE 0 END) as avg_engagement_rate
                FROM content_performance
                WHERE model_id = :model_id
                    AND published_at >= CURRENT_DATE - INTERVAL ':days days'
                GROUP BY content_type
            )
            SELECT 
                content_type,
                content_count,
                total_views,
                total_likes,
                total_revenue,
                ROUND(avg_engagement_rate, 2) as avg_engagement_rate,
                CASE WHEN content_count > 0 THEN ROUND(total_revenue / content_count, 2) ELSE 0 END as avg_revenue_per_content
            FROM recent_content
            ORDER BY total_revenue DESC
        """)
    
    @staticmethod
    def get_agency_dashboard_metrics(agency_id: str):
        """Get optimized agency dashboard metrics."""
        return text("""
            WITH agency_metrics AS (
                SELECT 
                    -- Model metrics
                    COUNT(DISTINCT m.id) as total_models,
                    COUNT(DISTINCT m.id) FILTER (WHERE m.is_active = true) as active_models,
                    
                    -- Fan metrics
                    COUNT(DISTINCT f.id) as total_fans,
                    COUNT(DISTINCT f.id) FILTER (WHERE f.is_paying = true) as paying_fans,
                    
                    -- Revenue metrics (last 30 days)
                    COALESCE(SUM(ft.amount) FILTER (
                        WHERE ft.type = 'revenue' 
                        AND ft.transaction_date >= CURRENT_DATE - INTERVAL '30 days'
                    ), 0) as revenue_30d,
                    
                    -- Revenue metrics (last 7 days)
                    COALESCE(SUM(ft.amount) FILTER (
                        WHERE ft.type = 'revenue' 
                        AND ft.transaction_date >= CURRENT_DATE - INTERVAL '7 days'
                    ), 0) as revenue_7d,
                    
                    -- Revenue metrics (today)
                    COALESCE(SUM(ft.amount) FILTER (
                        WHERE ft.type = 'revenue' 
                        AND ft.transaction_date >= CURRENT_DATE
                    ), 0) as revenue_today,
                    
                    -- Commission metrics
                    COALESCE(SUM(ft.commission_amount) FILTER (
                        WHERE ft.type = 'revenue' 
                        AND ft.transaction_date >= CURRENT_DATE - INTERVAL '30 days'
                    ), 0) as commission_30d
                    
                FROM model_profiles m
                LEFT JOIN fans f ON f.model_id = m.id
                LEFT JOIN financial_transactions ft ON ft.model_id = m.id
                WHERE m.agency_id = :agency_id
            )
            SELECT * FROM agency_metrics
        """)


class BatchOperations:
    """Optimized batch database operations."""
    
    @staticmethod
    async def batch_update_model_stats(
        session: AsyncSession,
        model_stats: List[Dict[str, Any]]
    ):
        """Batch update model statistics."""
        if not model_stats:
            return
        
        # Build bulk update query
        values = []
        for stat in model_stats:
            values.append(f"""(
                '{stat['model_id']}'::uuid,
                {stat.get('subscriber_count', 0)},
                {stat.get('paying_subscriber_count', 0)},
                {stat.get('total_earnings', 0)}
            )""")
        
        query = f"""
            UPDATE model_profiles AS m
            SET 
                subscriber_count = v.subscriber_count,
                paying_subscriber_count = v.paying_subscriber_count,
                total_earnings = v.total_earnings,
                last_sync_at = NOW()
            FROM (VALUES {','.join(values)}) AS v(
                model_id, subscriber_count, paying_subscriber_count, total_earnings
            )
            WHERE m.id = v.model_id
        """
        
        await session.execute(text(query))
    
    @staticmethod
    async def batch_create_transactions(
        session: AsyncSession,
        transactions: List[Dict[str, Any]]
    ):
        """Batch create financial transactions."""
        if not transactions:
            return
        
        # Prepare bulk insert
        values = []
        for txn in transactions:
            values.append({
                'agency_id': txn['agency_id'],
                'model_id': txn['model_id'],
                'user_id': txn.get('user_id'),
                'type': txn['type'],
                'amount': txn['amount'],
                'currency': txn.get('currency', 'USD'),
                'external_reference': txn.get('external_reference'),
                'description': txn.get('description'),
                'commission_rate': txn.get('commission_rate'),
                'commission_amount': txn.get('commission_amount'),
                'transaction_date': txn['transaction_date'],
                'metadata': json.dumps(txn.get('metadata', {}))
            })
        
        # Use PostgreSQL's INSERT with ON CONFLICT
        stmt = text("""
            INSERT INTO financial_transactions (
                id, agency_id, model_id, user_id, type, amount, currency,
                external_reference, description, commission_rate, commission_amount,
                transaction_date, metadata, created_at
            )
            VALUES (
                gen_random_uuid(), :agency_id, :model_id, :user_id, :type, :amount, :currency,
                :external_reference, :description, :commission_rate, :commission_amount,
                :transaction_date, :metadata::jsonb, NOW()
            )
            ON CONFLICT (external_reference) 
            WHERE external_reference IS NOT NULL
            DO NOTHING
        """)
        
        await session.execute(stmt, values)
    
    @staticmethod
    async def vacuum_old_data(
        session: AsyncSession,
        days_to_keep: int = 90
    ):
        """Clean up old data for performance."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Delete old notifications
        await session.execute(
            text("""
                DELETE FROM notifications 
                WHERE created_at < :cutoff_date 
                AND read = true
            """),
            {"cutoff_date": cutoff_date}
        )
        
        # Delete old audit logs
        await session.execute(
            text("""
                DELETE FROM audit_logs 
                WHERE created_at < :cutoff_date
                AND action NOT IN ('user_created', 'model_created', 'payout_completed')
            """),
            {"cutoff_date": cutoff_date}
        )
        
        # Archive old analytics cache
        await session.execute(
            text("""
                DELETE FROM analytics_cache 
                WHERE expires_at < NOW()
            """)
        )
        
        await session.commit()