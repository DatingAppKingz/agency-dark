"""
Add table partitioning for high-volume tables

This migration:
1. Creates partitioned versions of high-volume tables
2. Migrates existing data to partitioned tables
3. Sets up automatic partition management
"""
from typing import Optional
import asyncio
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.config import get_settings
from core.database_utils.partitioning import partition_manager
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


async def check_table_exists(db: AsyncSession, table_name: str) -> bool:
    """Check if a table exists"""
    query = text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = :table_name
        )
    """)
    result = await db.execute(query, {"table_name": table_name})
    return result.scalar()


async def create_partition_maintenance_function(db: AsyncSession):
    """Create a PL/pgSQL function for automatic partition maintenance"""
    create_function = text("""
        CREATE OR REPLACE FUNCTION maintain_partitions()
        RETURNS void AS $$
        DECLARE
            table_config RECORD;
            partition_date DATE;
            partition_name TEXT;
            start_date DATE;
            end_date DATE;
        BEGIN
            -- Configuration for each partitioned table
            FOR table_config IN 
                SELECT 'analytics' as table_name, 3 as future_months
                UNION ALL SELECT 'messages', 3
                UNION ALL SELECT 'bookings', 3
                UNION ALL SELECT 'audit_logs', 3
                UNION ALL SELECT 'model_analytics', 3
            LOOP
                -- Create future partitions
                FOR i IN 1..table_config.future_months LOOP
                    partition_date := DATE_TRUNC('month', CURRENT_DATE) + (i || ' months')::INTERVAL;
                    partition_name := table_config.table_name || '_' || 
                                    TO_CHAR(partition_date, 'YYYY_MM');
                    start_date := partition_date;
                    end_date := partition_date + INTERVAL '1 month';
                    
                    -- Check if partition exists
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_tables 
                        WHERE tablename = partition_name
                    ) THEN
                        EXECUTE format(
                            'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I ' ||
                            'FOR VALUES FROM (%L) TO (%L)',
                            partition_name, table_config.table_name,
                            start_date, end_date
                        );
                        RAISE NOTICE 'Created partition %', partition_name;
                    END IF;
                END LOOP;
            END LOOP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    await db.execute(create_function)
    logger.info("Created partition maintenance function")


async def create_partition_maintenance_job(db: AsyncSession):
    """Create a scheduled job for partition maintenance using pg_cron"""
    # First check if pg_cron extension is available
    check_extension = text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_extension WHERE extname = 'pg_cron'
        )
    """)
    
    result = await db.execute(check_extension)
    has_pg_cron = result.scalar()
    
    if has_pg_cron:
        # Schedule monthly partition maintenance
        schedule_job = text("""
            SELECT cron.schedule(
                'partition-maintenance',
                '0 2 1 * *',  -- Run at 2 AM on the 1st of each month
                $$SELECT maintain_partitions()$$
            )
        """)
        
        await db.execute(schedule_job)
        logger.info("Scheduled partition maintenance job with pg_cron")
    else:
        logger.warning("pg_cron extension not available - manual partition maintenance required")


async def migrate_existing_data(db: AsyncSession, table_name: str):
    """Migrate existing data to partitioned table"""
    old_table = f"{table_name}_old"
    
    # Check if old table exists (meaning we have data to migrate)
    if await check_table_exists(db, old_table):
        logger.info(f"Migrating data from {old_table} to {table_name}")
        
        # Get partition column based on table
        partition_columns = {
            "analytics": "timestamp",
            "messages": "created_at",
            "bookings": "booking_date",
            "audit_logs": "timestamp",
            "model_analytics": "date"
        }
        
        partition_column = partition_columns.get(table_name)
        
        if partition_column:
            # Migrate data in batches to avoid memory issues
            batch_size = 10000
            offset = 0
            
            while True:
                migrate_query = text(f"""
                    INSERT INTO {table_name}
                    SELECT * FROM {old_table}
                    ORDER BY {partition_column}
                    LIMIT :batch_size OFFSET :offset
                """)
                
                result = await db.execute(
                    migrate_query,
                    {"batch_size": batch_size, "offset": offset}
                )
                
                if result.rowcount == 0:
                    break
                
                offset += batch_size
                logger.info(f"Migrated {offset} rows for {table_name}")
                
                # Commit periodically to avoid long transactions
                await db.commit()
            
            # Drop old table after successful migration
            await db.execute(text(f"DROP TABLE IF EXISTS {old_table}"))
            logger.info(f"Completed migration for {table_name}")


async def setup_partition_triggers(db: AsyncSession):
    """Set up triggers for automatic routing to partitions"""
    # PostgreSQL 11+ handles this automatically with PARTITION BY
    # But we'll add a trigger to ensure partitions exist
    
    trigger_function = text("""
        CREATE OR REPLACE FUNCTION ensure_partition_exists()
        RETURNS TRIGGER AS $$
        DECLARE
            partition_date DATE;
            partition_name TEXT;
            start_date DATE;
            end_date DATE;
        BEGIN
            -- Determine partition based on table and date
            CASE TG_TABLE_NAME
                WHEN 'analytics' THEN 
                    partition_date := DATE_TRUNC('month', NEW.timestamp);
                WHEN 'messages' THEN 
                    partition_date := DATE_TRUNC('month', NEW.created_at);
                WHEN 'bookings' THEN 
                    partition_date := DATE_TRUNC('month', NEW.booking_date);
                WHEN 'audit_logs' THEN 
                    partition_date := DATE_TRUNC('month', NEW.timestamp);
                WHEN 'model_analytics' THEN 
                    partition_date := DATE_TRUNC('month', NEW.date);
            END CASE;
            
            partition_name := TG_TABLE_NAME || '_' || TO_CHAR(partition_date, 'YYYY_MM');
            start_date := partition_date;
            end_date := partition_date + INTERVAL '1 month';
            
            -- Create partition if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables WHERE tablename = partition_name
            ) THEN
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I ' ||
                    'FOR VALUES FROM (%L) TO (%L)',
                    partition_name, TG_TABLE_NAME, start_date, end_date
                );
            END IF;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    await db.execute(trigger_function)
    logger.info("Created partition existence trigger function")


async def add_partition_monitoring(db: AsyncSession):
    """Add views for monitoring partition health"""
    monitoring_view = text("""
        CREATE OR REPLACE VIEW partition_stats AS
        SELECT 
            parent.relname AS table_name,
            child.relname AS partition_name,
            pg_size_pretty(pg_relation_size(child.oid)) AS size,
            s.n_live_tup AS row_count,
            s.n_dead_tup AS dead_rows,
            s.last_vacuum,
            s.last_analyze,
            CASE 
                WHEN parent.relname LIKE '%\_____\___' THEN
                    TO_DATE(
                        SUBSTRING(child.relname FROM '(\d{4})_(\d{2})$'),
                        'YYYY_MM'
                    )
                ELSE NULL
            END AS partition_date
        FROM pg_inherits
        JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
        JOIN pg_class child ON pg_inherits.inhrelid = child.oid
        LEFT JOIN pg_stat_user_tables s ON s.relid = child.oid
        WHERE parent.relnamespace = 'public'::regnamespace
        ORDER BY parent.relname, child.relname;
        
        -- Create a summary view
        CREATE OR REPLACE VIEW partition_summary AS
        SELECT 
            table_name,
            COUNT(*) AS partition_count,
            SUM(row_count) AS total_rows,
            pg_size_pretty(SUM(pg_relation_size(partition_name::regclass))) AS total_size,
            MIN(partition_date) AS oldest_partition,
            MAX(partition_date) AS newest_partition
        FROM partition_stats
        GROUP BY table_name;
    """)
    
    await db.execute(monitoring_view)
    logger.info("Created partition monitoring views")


async def run_migration():
    """Run the partitioning migration"""
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            logger.info("Starting partitioning migration...")
            
            # 1. Create partition maintenance function
            await create_partition_maintenance_function(db)
            
            # 2. Initialize partitioning for all tables
            await partition_manager.initialize_partitioning(db)
            
            # 3. Migrate existing data if needed
            for table_name in partition_manager.partitioned_tables.keys():
                await migrate_existing_data(db, table_name)
            
            # 4. Set up triggers
            await setup_partition_triggers(db)
            
            # 5. Add monitoring views
            await add_partition_monitoring(db)
            
            # 6. Create maintenance job
            await create_partition_maintenance_job(db)
            
            # 7. Run initial partition maintenance
            await partition_manager.maintain_partitions(db)
            
            await db.commit()
            logger.info("Partitioning migration completed successfully")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await db.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())