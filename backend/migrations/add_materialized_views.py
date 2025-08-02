"""
Add materialized views for performance optimization

This migration creates materialized views for:
- Model performance aggregations
- Agency dashboard metrics
- Financial summaries
- Top performer rankings
- Analytics rollups
"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from core.config import get_settings
from core.database_utils.materialized_views import materialized_view_manager
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


async def create_required_tables(db: AsyncSession):
    """Ensure required tables exist before creating materialized views"""
    
    # Create model_financial_summary table if it doesn't exist
    financial_summary_table = text("""
        CREATE TABLE IF NOT EXISTS model_financial_summary (
            id SERIAL PRIMARY KEY,
            model_id INTEGER NOT NULL UNIQUE REFERENCES models(id),
            revenue_total DECIMAL(10, 2) DEFAULT 0,
            revenue_last_7_days DECIMAL(10, 2) DEFAULT 0,
            revenue_last_30_days DECIMAL(10, 2) DEFAULT 0,
            revenue_growth_pct DECIMAL(5, 2) DEFAULT 0,
            tips_total DECIMAL(10, 2) DEFAULT 0,
            subscriptions_active INTEGER DEFAULT 0,
            subscriptions_total INTEGER DEFAULT 0,
            avg_subscription_price DECIMAL(10, 2) DEFAULT 0,
            messages_revenue DECIMAL(10, 2) DEFAULT 0,
            last_activity TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_model_financial_model 
            ON model_financial_summary(model_id);
        CREATE INDEX IF NOT EXISTS idx_model_financial_revenue 
            ON model_financial_summary(revenue_total DESC);
    """)
    
    await db.execute(financial_summary_table)
    
    # Create transactions table if it doesn't exist
    transactions_table = text("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            model_id INTEGER NOT NULL REFERENCES models(id),
            user_id INTEGER REFERENCES users(id),
            type VARCHAR(50) NOT NULL CHECK (type IN ('subscription', 'tip', 'message', 'other')),
            amount DECIMAL(10, 2) NOT NULL,
            currency VARCHAR(3) DEFAULT 'USD',
            status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
            payment_method VARCHAR(50),
            external_id VARCHAR(255),
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_transactions_model 
            ON transactions(model_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_transactions_type 
            ON transactions(type, status, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_transactions_status 
            ON transactions(status, created_at DESC);
    """)
    
    await db.execute(transactions_table)
    
    # Create messages table enhancements
    messages_enhancement = text("""
        ALTER TABLE messages 
        ADD COLUMN IF NOT EXISTS is_replied BOOLEAN DEFAULT FALSE;
        
        CREATE INDEX IF NOT EXISTS idx_messages_replied 
            ON messages(recipient_id, is_replied, created_at DESC);
    """)
    
    try:
        await db.execute(messages_enhancement)
    except Exception as e:
        logger.warning(f"Could not enhance messages table: {e}")
    
    await db.commit()
    logger.info("Required tables created/verified")


async def populate_sample_financial_data(db: AsyncSession):
    """Populate sample financial summary data for existing models"""
    
    # Check if data already exists
    check_query = text("SELECT COUNT(*) FROM model_financial_summary")
    count = await db.scalar(check_query)
    
    if count > 0:
        logger.info("Financial summary data already exists")
        return
    
    # Populate financial summary for each model
    populate_query = text("""
        INSERT INTO model_financial_summary (
            model_id,
            revenue_total,
            revenue_last_7_days,
            revenue_last_30_days,
            revenue_growth_pct,
            tips_total,
            subscriptions_active,
            avg_subscription_price,
            last_activity
        )
        SELECT 
            m.id,
            ROUND(RANDOM() * 50000 + 5000, 2) as revenue_total,
            ROUND(RANDOM() * 5000 + 500, 2) as revenue_last_7_days,
            ROUND(RANDOM() * 20000 + 2000, 2) as revenue_last_30_days,
            ROUND(RANDOM() * 50 - 10, 2) as revenue_growth_pct,
            ROUND(RANDOM() * 10000 + 1000, 2) as tips_total,
            FLOOR(RANDOM() * 500 + 50) as subscriptions_active,
            ROUND(RANDOM() * 40 + 10, 2) as avg_subscription_price,
            CURRENT_TIMESTAMP - INTERVAL '1 day' * FLOOR(RANDOM() * 7)
        FROM models m
        WHERE NOT EXISTS (
            SELECT 1 FROM model_financial_summary fs 
            WHERE fs.model_id = m.id
        )
    """)
    
    await db.execute(populate_query)
    await db.commit()
    logger.info("Sample financial data populated")


async def create_performance_indexes(db: AsyncSession):
    """Create additional indexes for materialized view performance"""
    
    indexes = [
        # Analytics indexes
        "CREATE INDEX IF NOT EXISTS idx_analytics_model_event_time ON analytics(model_id, event_type, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_analytics_session_time ON analytics(session_id, timestamp DESC)",
        
        # Models indexes
        "CREATE INDEX IF NOT EXISTS idx_models_agency_status ON models(agency_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_models_created ON models(created_at DESC)",
        
        # Messages indexes
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation_time ON messages(conversation_id, created_at DESC)",
        
        # Bookings indexes
        "CREATE INDEX IF NOT EXISTS idx_bookings_date_status ON bookings(booking_date DESC, status)"
    ]
    
    for index_query in indexes:
        try:
            await db.execute(text(index_query))
            logger.info(f"Created index: {index_query.split(' ')[-1]}")
        except Exception as e:
            logger.warning(f"Could not create index: {e}")
    
    await db.commit()


async def grant_permissions(db: AsyncSession):
    """Grant necessary permissions for materialized views"""
    
    # Grant SELECT permissions to application role
    grant_query = text("""
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN 
                SELECT matviewname 
                FROM pg_matviews 
                WHERE schemaname = 'public'
            LOOP
                EXECUTE format('GRANT SELECT ON %I TO %I', r.matviewname, current_user);
            END LOOP;
        END $$;
    """)
    
    try:
        await db.execute(grant_query)
        await db.commit()
        logger.info("Permissions granted for materialized views")
    except Exception as e:
        logger.warning(f"Could not grant permissions: {e}")


async def run_migration():
    """Run the materialized views migration"""
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            logger.info("Starting materialized views migration...")
            
            # 1. Create required tables
            await create_required_tables(db)
            
            # 2. Populate sample data
            await populate_sample_financial_data(db)
            
            # 3. Create performance indexes
            await create_performance_indexes(db)
            
            # 4. Create all materialized views
            await materialized_view_manager.create_all_views(db)
            
            # 5. Grant permissions
            await grant_permissions(db)
            
            # 6. Initial refresh of all views
            logger.info("Performing initial refresh of materialized views...")
            refresh_results = await materialized_view_manager.refresh_all_views(db)
            
            # Log results
            for view_name, duration in refresh_results.items():
                if duration is not None:
                    logger.info(f"Refreshed {view_name} in {duration:.2f} seconds")
                else:
                    logger.error(f"Failed to refresh {view_name}")
            
            logger.info("Materialized views migration completed successfully")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await db.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())