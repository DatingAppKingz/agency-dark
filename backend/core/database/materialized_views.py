"""
Materialized Views Manager for Performance Optimization
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger

logger = get_logger(__name__)


class MaterializedView:
    """Base class for materialized views"""
    
    def __init__(self, name: str, query: str, indexes: List[str] = None):
        self.name = name
        self.query = query
        self.indexes = indexes or []
        self.last_refresh: Optional[datetime] = None
        self.refresh_duration: Optional[float] = None


class MaterializedViewManager:
    """Manages materialized views for performance optimization"""
    
    def __init__(self):
        self.views = {
            "model_performance_daily": MaterializedView(
                name="mv_model_performance_daily",
                query="""
                    SELECT 
                        m.id as model_id,
                        m.name as model_name,
                        m.agency_id,
                        DATE(a.timestamp) as date,
                        COUNT(DISTINCT CASE WHEN a.event_type = 'view' THEN a.session_id END) as unique_views,
                        COUNT(CASE WHEN a.event_type = 'view' THEN 1 END) as total_views,
                        COUNT(CASE WHEN a.event_type = 'like' THEN 1 END) as likes,
                        COUNT(CASE WHEN a.event_type = 'message' THEN 1 END) as messages,
                        COUNT(DISTINCT CASE WHEN a.event_type = 'message' THEN a.user_id END) as unique_messagers,
                        AVG(CASE WHEN a.event_type = 'session_duration' THEN CAST(a.event_data->>'duration' AS INTEGER) END) as avg_session_duration,
                        MAX(a.timestamp) as last_activity
                    FROM models m
                    LEFT JOIN analytics a ON m.id = a.model_id
                    WHERE a.timestamp >= CURRENT_DATE - INTERVAL '90 days'
                    GROUP BY m.id, m.name, m.agency_id, DATE(a.timestamp)
                """,
                indexes=[
                    "CREATE INDEX idx_mv_model_perf_model_date ON mv_model_performance_daily(model_id, date DESC)",
                    "CREATE INDEX idx_mv_model_perf_agency ON mv_model_performance_daily(agency_id, date DESC)",
                    "CREATE INDEX idx_mv_model_perf_date ON mv_model_performance_daily(date DESC)"
                ]
            ),
            
            "model_performance_monthly": MaterializedView(
                name="mv_model_performance_monthly",
                query="""
                    SELECT 
                        model_id,
                        model_name,
                        agency_id,
                        DATE_TRUNC('month', date) as month,
                        SUM(unique_views) as unique_views,
                        SUM(total_views) as total_views,
                        SUM(likes) as likes,
                        SUM(messages) as messages,
                        AVG(unique_messagers) as avg_daily_messagers,
                        AVG(avg_session_duration) as avg_session_duration,
                        COUNT(DISTINCT date) as active_days
                    FROM mv_model_performance_daily
                    GROUP BY model_id, model_name, agency_id, DATE_TRUNC('month', date)
                """,
                indexes=[
                    "CREATE INDEX idx_mv_model_monthly_model ON mv_model_performance_monthly(model_id, month DESC)",
                    "CREATE INDEX idx_mv_model_monthly_agency ON mv_model_performance_monthly(agency_id, month DESC)"
                ]
            ),
            
            "agency_dashboard_metrics": MaterializedView(
                name="mv_agency_dashboard_metrics",
                query="""
                    SELECT 
                        a.id as agency_id,
                        a.name as agency_name,
                        COUNT(DISTINCT m.id) as total_models,
                        COUNT(DISTINCT CASE WHEN m.status = 'active' THEN m.id END) as active_models,
                        COALESCE(SUM(f.revenue_total), 0) as total_revenue,
                        COALESCE(SUM(f.revenue_last_30_days), 0) as revenue_last_30_days,
                        COALESCE(SUM(f.tips_total), 0) as total_tips,
                        COALESCE(SUM(f.subscriptions_active), 0) as active_subscriptions,
                        COALESCE(AVG(f.avg_subscription_price), 0) as avg_subscription_price,
                        COALESCE(SUM(perf.total_views), 0) as total_views_last_30_days,
                        COALESCE(SUM(perf.messages), 0) as total_messages_last_30_days,
                        CURRENT_TIMESTAMP as last_updated
                    FROM agencies a
                    LEFT JOIN models m ON a.id = m.agency_id
                    LEFT JOIN model_financial_summary f ON m.id = f.model_id
                    LEFT JOIN (
                        SELECT model_id, SUM(total_views) as total_views, SUM(messages) as messages
                        FROM mv_model_performance_daily
                        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                        GROUP BY model_id
                    ) perf ON m.id = perf.model_id
                    GROUP BY a.id, a.name
                """,
                indexes=[
                    "CREATE INDEX idx_mv_agency_dash_id ON mv_agency_dashboard_metrics(agency_id)",
                    "CREATE INDEX idx_mv_agency_dash_revenue ON mv_agency_dashboard_metrics(total_revenue DESC)"
                ]
            ),
            
            "top_performers": MaterializedView(
                name="mv_top_performers",
                query="""
                    WITH performance_ranks AS (
                        SELECT 
                            m.id as model_id,
                            m.name as model_name,
                            m.agency_id,
                            a.name as agency_name,
                            COALESCE(f.revenue_last_30_days, 0) as revenue_30d,
                            COALESCE(f.revenue_growth_pct, 0) as revenue_growth,
                            COALESCE(p.total_views, 0) as views_30d,
                            COALESCE(p.engagement_rate, 0) as engagement_rate,
                            RANK() OVER (ORDER BY f.revenue_last_30_days DESC NULLS LAST) as revenue_rank,
                            RANK() OVER (ORDER BY f.revenue_growth_pct DESC NULLS LAST) as growth_rank,
                            RANK() OVER (ORDER BY p.total_views DESC NULLS LAST) as views_rank,
                            RANK() OVER (ORDER BY p.engagement_rate DESC NULLS LAST) as engagement_rank
                        FROM models m
                        JOIN agencies a ON m.agency_id = a.id
                        LEFT JOIN model_financial_summary f ON m.id = f.model_id
                        LEFT JOIN (
                            SELECT 
                                model_id,
                                SUM(total_views) as total_views,
                                CASE 
                                    WHEN SUM(total_views) > 0 
                                    THEN CAST(SUM(likes + messages) AS FLOAT) / SUM(total_views) * 100
                                    ELSE 0
                                END as engagement_rate
                            FROM mv_model_performance_daily
                            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                            GROUP BY model_id
                        ) p ON m.id = p.model_id
                        WHERE m.status = 'active'
                    )
                    SELECT 
                        model_id,
                        model_name,
                        agency_id,
                        agency_name,
                        revenue_30d,
                        revenue_growth,
                        views_30d,
                        engagement_rate,
                        revenue_rank,
                        growth_rank,
                        views_rank,
                        engagement_rank,
                        (revenue_rank + growth_rank + views_rank + engagement_rank) / 4.0 as overall_rank
                    FROM performance_ranks
                    WHERE revenue_rank <= 100 OR growth_rank <= 100 OR views_rank <= 100 OR engagement_rank <= 100
                    ORDER BY overall_rank
                """,
                indexes=[
                    "CREATE INDEX idx_mv_top_perf_overall ON mv_top_performers(overall_rank)",
                    "CREATE INDEX idx_mv_top_perf_agency ON mv_top_performers(agency_id, overall_rank)",
                    "CREATE INDEX idx_mv_top_perf_revenue ON mv_top_performers(revenue_rank)"
                ]
            ),
            
            "financial_summary": MaterializedView(
                name="mv_financial_summary",
                query="""
                    SELECT 
                        a.id as agency_id,
                        a.name as agency_name,
                        DATE_TRUNC('day', t.created_at) as date,
                        COUNT(DISTINCT CASE WHEN t.type = 'subscription' THEN t.id END) as subscription_count,
                        SUM(CASE WHEN t.type = 'subscription' THEN t.amount ELSE 0 END) as subscription_revenue,
                        COUNT(DISTINCT CASE WHEN t.type = 'tip' THEN t.id END) as tip_count,
                        SUM(CASE WHEN t.type = 'tip' THEN t.amount ELSE 0 END) as tip_revenue,
                        COUNT(DISTINCT CASE WHEN t.type = 'message' THEN t.id END) as paid_message_count,
                        SUM(CASE WHEN t.type = 'message' THEN t.amount ELSE 0 END) as message_revenue,
                        COUNT(DISTINCT t.model_id) as active_models,
                        SUM(t.amount) as total_revenue,
                        SUM(t.amount * (a.commission_rate / 100.0)) as agency_commission,
                        SUM(t.amount * (1 - a.commission_rate / 100.0)) as model_payout
                    FROM agencies a
                    JOIN models m ON a.id = m.agency_id
                    JOIN transactions t ON m.id = t.model_id
                    WHERE t.status = 'completed'
                        AND t.created_at >= CURRENT_DATE - INTERVAL '90 days'
                    GROUP BY a.id, a.name, DATE_TRUNC('day', t.created_at)
                """,
                indexes=[
                    "CREATE INDEX idx_mv_financial_agency_date ON mv_financial_summary(agency_id, date DESC)",
                    "CREATE INDEX idx_mv_financial_date ON mv_financial_summary(date DESC)",
                    "CREATE INDEX idx_mv_financial_revenue ON mv_financial_summary(total_revenue DESC)"
                ]
            ),
            
            "analytics_hourly_rollup": MaterializedView(
                name="mv_analytics_hourly_rollup",
                query="""
                    SELECT 
                        model_id,
                        DATE_TRUNC('hour', timestamp) as hour,
                        COUNT(DISTINCT CASE WHEN event_type = 'view' THEN session_id END) as unique_views,
                        COUNT(CASE WHEN event_type = 'view' THEN 1 END) as total_views,
                        COUNT(CASE WHEN event_type = 'like' THEN 1 END) as likes,
                        COUNT(CASE WHEN event_type = 'message' THEN 1 END) as messages,
                        COUNT(DISTINCT session_id) as unique_sessions,
                        COUNT(DISTINCT ip_address) as unique_ips,
                        AVG(CASE 
                            WHEN event_type = 'session_duration' 
                            THEN CAST(event_data->>'duration' AS INTEGER) 
                        END) as avg_session_duration,
                        MAX(timestamp) as last_event
                    FROM analytics
                    WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '7 days'
                    GROUP BY model_id, DATE_TRUNC('hour', timestamp)
                """,
                indexes=[
                    "CREATE INDEX idx_mv_analytics_hourly_model ON mv_analytics_hourly_rollup(model_id, hour DESC)",
                    "CREATE INDEX idx_mv_analytics_hourly_hour ON mv_analytics_hourly_rollup(hour DESC)"
                ]
            ),
            
            "model_engagement_scores": MaterializedView(
                name="mv_model_engagement_scores",
                query="""
                    WITH engagement_metrics AS (
                        SELECT 
                            m.id as model_id,
                            m.name as model_name,
                            m.agency_id,
                            COALESCE(views_7d.total_views, 0) as views_7d,
                            COALESCE(views_30d.total_views, 0) as views_30d,
                            COALESCE(engage_7d.engagement_rate, 0) as engagement_rate_7d,
                            COALESCE(engage_30d.engagement_rate, 0) as engagement_rate_30d,
                            COALESCE(msg_7d.response_rate, 0) as message_response_rate_7d,
                            COALESCE(retention.retention_rate, 0) as viewer_retention_30d,
                            COALESCE(f.revenue_last_7_days, 0) as revenue_7d,
                            COALESCE(f.revenue_last_30_days, 0) as revenue_30d
                        FROM models m
                        LEFT JOIN (
                            SELECT model_id, SUM(total_views) as total_views
                            FROM mv_model_performance_daily
                            WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                            GROUP BY model_id
                        ) views_7d ON m.id = views_7d.model_id
                        LEFT JOIN (
                            SELECT model_id, SUM(total_views) as total_views
                            FROM mv_model_performance_daily
                            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                            GROUP BY model_id
                        ) views_30d ON m.id = views_30d.model_id
                        LEFT JOIN (
                            SELECT 
                                model_id,
                                CASE 
                                    WHEN SUM(total_views) > 0 
                                    THEN CAST(SUM(likes + messages) AS FLOAT) / SUM(total_views) * 100
                                    ELSE 0
                                END as engagement_rate
                            FROM mv_model_performance_daily
                            WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                            GROUP BY model_id
                        ) engage_7d ON m.id = engage_7d.model_id
                        LEFT JOIN (
                            SELECT 
                                model_id,
                                CASE 
                                    WHEN SUM(total_views) > 0 
                                    THEN CAST(SUM(likes + messages) AS FLOAT) / SUM(total_views) * 100
                                    ELSE 0
                                END as engagement_rate
                            FROM mv_model_performance_daily
                            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                            GROUP BY model_id
                        ) engage_30d ON m.id = engage_30d.model_id
                        LEFT JOIN (
                            SELECT 
                                recipient_id as model_id,
                                CAST(COUNT(CASE WHEN is_replied THEN 1 END) AS FLOAT) / 
                                NULLIF(COUNT(*), 0) * 100 as response_rate
                            FROM messages
                            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                            GROUP BY recipient_id
                        ) msg_7d ON m.id = msg_7d.model_id
                        LEFT JOIN (
                            SELECT 
                                model_id,
                                CAST(COUNT(DISTINCT CASE 
                                    WHEN return_visit THEN session_id 
                                END) AS FLOAT) / NULLIF(COUNT(DISTINCT session_id), 0) * 100 as retention_rate
                            FROM (
                                SELECT 
                                    model_id,
                                    session_id,
                                    COUNT(*) OVER (PARTITION BY model_id, session_id) > 1 as return_visit
                                FROM analytics
                                WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
                                    AND event_type = 'view'
                            ) rv
                            GROUP BY model_id
                        ) retention ON m.id = retention.model_id
                        LEFT JOIN model_financial_summary f ON m.id = f.model_id
                        WHERE m.status = 'active'
                    )
                    SELECT 
                        model_id,
                        model_name,
                        agency_id,
                        views_7d,
                        views_30d,
                        engagement_rate_7d,
                        engagement_rate_30d,
                        message_response_rate_7d,
                        viewer_retention_30d,
                        revenue_7d,
                        revenue_30d,
                        -- Calculate composite engagement score (0-100)
                        (
                            (CASE WHEN views_30d > 0 THEN LEAST(views_30d / 10000.0, 1) ELSE 0 END * 20) +
                            (LEAST(engagement_rate_30d / 10.0, 1) * 25) +
                            (LEAST(message_response_rate_7d / 80.0, 1) * 25) +
                            (LEAST(viewer_retention_30d / 50.0, 1) * 20) +
                            (CASE WHEN revenue_30d > 0 THEN LEAST(revenue_30d / 5000.0, 1) ELSE 0 END * 10)
                        ) as engagement_score,
                        CURRENT_TIMESTAMP as calculated_at
                    FROM engagement_metrics
                """,
                indexes=[
                    "CREATE INDEX idx_mv_engagement_model ON mv_model_engagement_scores(model_id)",
                    "CREATE INDEX idx_mv_engagement_agency ON mv_model_engagement_scores(agency_id, engagement_score DESC)",
                    "CREATE INDEX idx_mv_engagement_score ON mv_model_engagement_scores(engagement_score DESC)"
                ]
            )
        }
    
    async def create_all_views(self, db: AsyncSession):
        """Create all materialized views"""
        logger.info("Creating materialized views...")
        
        for view_name, view in self.views.items():
            try:
                await self.create_view(db, view)
                logger.info(f"Created materialized view: {view.name}")
            except Exception as e:
                logger.error(f"Error creating view {view.name}: {e}")
                raise
        
        await db.commit()
        logger.info("All materialized views created successfully")
    
    async def create_view(self, db: AsyncSession, view: MaterializedView):
        """Create a single materialized view"""
        # Drop if exists
        drop_query = text(f"DROP MATERIALIZED VIEW IF EXISTS {view.name} CASCADE")
        await db.execute(drop_query)
        
        # Create materialized view
        create_query = text(f"CREATE MATERIALIZED VIEW {view.name} AS {view.query}")
        await db.execute(create_query)
        
        # Create indexes
        for index_query in view.indexes:
            await db.execute(text(index_query))
    
    async def refresh_view(self, db: AsyncSession, view_name: str, concurrent: bool = True):
        """Refresh a specific materialized view"""
        if view_name not in self.views:
            raise ValueError(f"Unknown view: {view_name}")
        
        view = self.views[view_name]
        start_time = datetime.utcnow()
        
        try:
            # Use CONCURRENTLY to avoid locking
            refresh_mode = "CONCURRENTLY" if concurrent else ""
            refresh_query = text(f"REFRESH MATERIALIZED VIEW {refresh_mode} {view.name}")
            
            await db.execute(refresh_query)
            await db.commit()
            
            view.last_refresh = datetime.utcnow()
            view.refresh_duration = (view.last_refresh - start_time).total_seconds()
            
            logger.info(f"Refreshed {view.name} in {view.refresh_duration:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Error refreshing view {view.name}: {e}")
            raise
    
    async def refresh_all_views(self, db: AsyncSession, concurrent: bool = True):
        """Refresh all materialized views"""
        logger.info("Refreshing all materialized views...")
        
        refresh_times = {}
        for view_name in self.views:
            try:
                await self.refresh_view(db, view_name, concurrent)
                refresh_times[view_name] = self.views[view_name].refresh_duration
            except Exception as e:
                logger.error(f"Failed to refresh {view_name}: {e}")
                refresh_times[view_name] = None
        
        return refresh_times
    
    async def get_view_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get statistics about materialized views"""
        stats_query = text("""
            SELECT 
                schemaname,
                matviewname,
                pg_size_pretty(pg_relation_size(schemaname||'.'||matviewname)) as size,
                obj_description(c.oid) as description
            FROM pg_matviews mv
            JOIN pg_class c ON c.relname = mv.matviewname
            WHERE schemaname = 'public'
            ORDER BY pg_relation_size(schemaname||'.'||matviewname) DESC
        """)
        
        result = await db.execute(stats_query)
        
        stats = {}
        for row in result:
            view_name = row.matviewname
            if view_name in [v.name for v in self.views.values()]:
                stats[view_name] = {
                    "size": row.size,
                    "last_refresh": self.views.get(view_name.replace("mv_", "")).last_refresh,
                    "refresh_duration": self.views.get(view_name.replace("mv_", "")).refresh_duration
                }
        
        return stats
    
    async def analyze_refresh_patterns(self, db: AsyncSession) -> Dict[str, Any]:
        """Analyze optimal refresh patterns for views"""
        patterns = {}
        
        for view_name, view in self.views.items():
            # Analyze data freshness requirements
            if "hourly" in view_name:
                patterns[view_name] = {
                    "recommended_interval": "15 minutes",
                    "priority": "high",
                    "reason": "Near real-time data required"
                }
            elif "daily" in view_name:
                patterns[view_name] = {
                    "recommended_interval": "1 hour",
                    "priority": "medium",
                    "reason": "Daily aggregations need hourly updates"
                }
            elif "monthly" in view_name:
                patterns[view_name] = {
                    "recommended_interval": "6 hours",
                    "priority": "low",
                    "reason": "Monthly data changes less frequently"
                }
            elif "financial" in view_name:
                patterns[view_name] = {
                    "recommended_interval": "30 minutes",
                    "priority": "high",
                    "reason": "Financial data needs timely updates"
                }
            else:
                patterns[view_name] = {
                    "recommended_interval": "2 hours",
                    "priority": "medium",
                    "reason": "Standard refresh interval"
                }
        
        return patterns
    
    async def drop_view(self, db: AsyncSession, view_name: str):
        """Drop a materialized view"""
        if view_name not in self.views:
            raise ValueError(f"Unknown view: {view_name}")
        
        view = self.views[view_name]
        drop_query = text(f"DROP MATERIALIZED VIEW IF EXISTS {view.name} CASCADE")
        await db.execute(drop_query)
        await db.commit()
        
        logger.info(f"Dropped materialized view: {view.name}")


# Global instance
materialized_view_manager = MaterializedViewManager()


# Utility functions
async def setup_materialized_views(db: AsyncSession):
    """Setup all materialized views"""
    await materialized_view_manager.create_all_views(db)


async def refresh_materialized_views(db: AsyncSession, view_name: Optional[str] = None):
    """Refresh materialized views"""
    if view_name:
        await materialized_view_manager.refresh_view(db, view_name)
    else:
        await materialized_view_manager.refresh_all_views(db)