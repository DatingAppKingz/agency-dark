"""
Database Partitioning Manager for High-Volume Tables
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import asyncio

from sqlalchemy import text, Table, Column, Integer, DateTime, String, JSON, ForeignKey, Index
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateTable

from core.database import Base
from core.logging import get_logger

logger = get_logger(__name__)


class PartitionManager:
    """Manages database table partitioning for performance optimization"""
    
    def __init__(self):
        self.partitioned_tables = {
            "analytics": {
                "base_table": "analytics",
                "partition_column": "timestamp",
                "partition_type": "RANGE",
                "interval": "monthly",
                "retention_months": 12
            },
            "messages": {
                "base_table": "messages",
                "partition_column": "created_at",
                "partition_type": "RANGE",
                "interval": "monthly",
                "retention_months": 6
            },
            "bookings": {
                "base_table": "bookings",
                "partition_column": "booking_date",
                "partition_type": "RANGE",
                "interval": "monthly",
                "retention_months": 24
            },
            "audit_logs": {
                "base_table": "audit_logs",
                "partition_column": "timestamp",
                "partition_type": "RANGE",
                "interval": "monthly",
                "retention_months": 3
            },
            "model_analytics": {
                "base_table": "model_analytics",
                "partition_column": "date",
                "partition_type": "RANGE",
                "interval": "monthly",
                "retention_months": 12
            }
        }
    
    async def initialize_partitioning(self, db: AsyncSession):
        """Initialize partitioning for all configured tables"""
        logger.info("Initializing database partitioning...")
        
        for table_name, config in self.partitioned_tables.items():
            try:
                await self._create_partitioned_table(db, table_name, config)
                await self._create_initial_partitions(db, table_name, config)
                logger.info(f"Initialized partitioning for {table_name}")
            except Exception as e:
                logger.error(f"Error initializing partitioning for {table_name}: {e}")
                raise
        
        await db.commit()
        logger.info("Database partitioning initialized successfully")
    
    async def _create_partitioned_table(
        self,
        db: AsyncSession,
        table_name: str,
        config: Dict[str, Any]
    ):
        """Create a partitioned table if it doesn't exist"""
        # Check if table already exists
        check_query = text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = :table_name
            )
        """)
        
        result = await db.execute(check_query, {"table_name": table_name})
        exists = result.scalar()
        
        if not exists:
            # Create partitioned table based on type
            if table_name == "analytics":
                await self._create_analytics_table(db)
            elif table_name == "messages":
                await self._create_messages_table(db)
            elif table_name == "bookings":
                await self._create_bookings_table(db)
            elif table_name == "audit_logs":
                await self._create_audit_logs_table(db)
            elif table_name == "model_analytics":
                await self._create_model_analytics_table(db)
    
    async def _create_analytics_table(self, db: AsyncSession):
        """Create partitioned analytics table"""
        create_query = text("""
            CREATE TABLE IF NOT EXISTS analytics (
                id BIGSERIAL,
                model_id INTEGER NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                event_data JSONB,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                session_id VARCHAR(100),
                user_agent TEXT,
                ip_address INET,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id, timestamp)
            ) PARTITION BY RANGE (timestamp);
            
            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_analytics_model_timestamp 
                ON analytics (model_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_analytics_event_type 
                ON analytics (event_type, timestamp);
            CREATE INDEX IF NOT EXISTS idx_analytics_session 
                ON analytics (session_id);
        """)
        
        await db.execute(create_query)
    
    async def _create_messages_table(self, db: AsyncSession):
        """Create partitioned messages table"""
        create_query = text("""
            CREATE TABLE IF NOT EXISTS messages (
                id BIGSERIAL,
                conversation_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                message_type VARCHAR(20) DEFAULT 'text',
                attachments JSONB,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id, created_at)
            ) PARTITION BY RANGE (created_at);
            
            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_messages_conversation 
                ON messages (conversation_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_messages_sender 
                ON messages (sender_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_messages_recipient_unread 
                ON messages (recipient_id, is_read, created_at);
        """)
        
        await db.execute(create_query)
    
    async def _create_bookings_table(self, db: AsyncSession):
        """Create partitioned bookings table"""
        create_query = text("""
            CREATE TABLE IF NOT EXISTS bookings (
                id BIGSERIAL,
                model_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                booking_date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                duration INTEGER NOT NULL,
                rate DECIMAL(10, 2) NOT NULL,
                total_amount DECIMAL(10, 2) NOT NULL,
                status VARCHAR(20) NOT NULL,
                location TEXT,
                notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id, booking_date)
            ) PARTITION BY RANGE (booking_date);
            
            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_bookings_model_date 
                ON bookings (model_id, booking_date);
            CREATE INDEX IF NOT EXISTS idx_bookings_client_date 
                ON bookings (client_id, booking_date);
            CREATE INDEX IF NOT EXISTS idx_bookings_status 
                ON bookings (status, booking_date);
        """)
        
        await db.execute(create_query)
    
    async def _create_audit_logs_table(self, db: AsyncSession):
        """Create partitioned audit logs table"""
        create_query = text("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id BIGSERIAL,
                user_id INTEGER NOT NULL,
                action VARCHAR(100) NOT NULL,
                resource_type VARCHAR(50) NOT NULL,
                resource_id INTEGER,
                changes JSONB,
                ip_address INET,
                user_agent TEXT,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id, timestamp)
            ) PARTITION BY RANGE (timestamp);
            
            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_audit_user_timestamp 
                ON audit_logs (user_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_audit_action 
                ON audit_logs (action, timestamp);
            CREATE INDEX IF NOT EXISTS idx_audit_resource 
                ON audit_logs (resource_type, resource_id, timestamp);
        """)
        
        await db.execute(create_query)
    
    async def _create_model_analytics_table(self, db: AsyncSession):
        """Create partitioned model analytics table"""
        create_query = text("""
            CREATE TABLE IF NOT EXISTS model_analytics (
                id BIGSERIAL,
                model_id INTEGER NOT NULL,
                date DATE NOT NULL,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                messages INTEGER DEFAULT 0,
                bookings INTEGER DEFAULT 0,
                revenue DECIMAL(10, 2) DEFAULT 0,
                unique_visitors INTEGER DEFAULT 0,
                avg_session_duration INTEGER DEFAULT 0,
                bounce_rate DECIMAL(5, 2) DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id, date)
            ) PARTITION BY RANGE (date);
            
            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_model_analytics_model_date 
                ON model_analytics (model_id, date);
            CREATE INDEX IF NOT EXISTS idx_model_analytics_date 
                ON model_analytics (date);
        """)
        
        await db.execute(create_query)
    
    async def _create_initial_partitions(
        self,
        db: AsyncSession,
        table_name: str,
        config: Dict[str, Any]
    ):
        """Create initial partitions for the table"""
        # Create partitions for past 3 months and next 3 months
        start_date = datetime.utcnow() - relativedelta(months=3)
        end_date = datetime.utcnow() + relativedelta(months=3)
        
        current_date = start_date.replace(day=1)
        while current_date <= end_date:
            await self._create_monthly_partition(
                db, table_name, current_date, config
            )
            current_date += relativedelta(months=1)
    
    async def _create_monthly_partition(
        self,
        db: AsyncSession,
        table_name: str,
        date: datetime,
        config: Dict[str, Any]
    ):
        """Create a monthly partition for a table"""
        partition_name = f"{table_name}_{date.year}_{date.month:02d}"
        start_date = date.replace(day=1)
        end_date = start_date + relativedelta(months=1)
        
        # Check if partition exists
        check_query = text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = :partition_name
            )
        """)
        
        result = await db.execute(check_query, {"partition_name": partition_name})
        exists = result.scalar()
        
        if not exists:
            create_query = text(f"""
                CREATE TABLE IF NOT EXISTS {partition_name} 
                PARTITION OF {table_name}
                FOR VALUES FROM ('{start_date.strftime('%Y-%m-%d')}') 
                TO ('{end_date.strftime('%Y-%m-%d')}')
            """)
            
            await db.execute(create_query)
            logger.info(f"Created partition {partition_name}")
    
    async def maintain_partitions(self, db: AsyncSession):
        """Maintain partitions - create new ones and drop old ones"""
        logger.info("Starting partition maintenance...")
        
        for table_name, config in self.partitioned_tables.items():
            try:
                # Create future partitions
                await self._create_future_partitions(db, table_name, config)
                
                # Drop old partitions based on retention policy
                await self._drop_old_partitions(db, table_name, config)
                
                # Analyze partitions for optimization
                await self._analyze_partitions(db, table_name)
                
            except Exception as e:
                logger.error(f"Error maintaining partitions for {table_name}: {e}")
        
        await db.commit()
        logger.info("Partition maintenance completed")
    
    async def _create_future_partitions(
        self,
        db: AsyncSession,
        table_name: str,
        config: Dict[str, Any]
    ):
        """Create partitions for future months"""
        # Create partitions for next 3 months
        current_date = datetime.utcnow().replace(day=1)
        
        for i in range(1, 4):
            future_date = current_date + relativedelta(months=i)
            await self._create_monthly_partition(
                db, table_name, future_date, config
            )
    
    async def _drop_old_partitions(
        self,
        db: AsyncSession,
        table_name: str,
        config: Dict[str, Any]
    ):
        """Drop partitions older than retention period"""
        retention_months = config.get("retention_months", 12)
        cutoff_date = datetime.utcnow() - relativedelta(months=retention_months)
        
        # List all partitions
        list_query = text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename LIKE :pattern
            ORDER BY tablename
        """)
        
        result = await db.execute(
            list_query, 
            {"pattern": f"{table_name}_%"}
        )
        
        for row in result:
            partition_name = row.tablename
            
            # Extract date from partition name
            try:
                parts = partition_name.split('_')
                year = int(parts[-2])
                month = int(parts[-1])
                partition_date = datetime(year, month, 1)
                
                if partition_date < cutoff_date.replace(day=1):
                    # Archive before dropping if needed
                    await self._archive_partition(db, partition_name)
                    
                    # Drop the partition
                    drop_query = text(f"DROP TABLE IF EXISTS {partition_name}")
                    await db.execute(drop_query)
                    logger.info(f"Dropped old partition {partition_name}")
                    
            except (ValueError, IndexError):
                logger.warning(f"Could not parse partition name: {partition_name}")
    
    async def _archive_partition(self, db: AsyncSession, partition_name: str):
        """Archive partition data before dropping (optional)"""
        # This could export to S3, another database, etc.
        # For now, we'll just log it
        logger.info(f"Archiving partition {partition_name} (not implemented)")
    
    async def _analyze_partitions(self, db: AsyncSession, table_name: str):
        """Analyze partitions for query optimization"""
        analyze_query = text(f"ANALYZE {table_name}")
        await db.execute(analyze_query)
    
    async def get_partition_info(
        self,
        db: AsyncSession,
        table_name: str
    ) -> List[Dict[str, Any]]:
        """Get information about table partitions"""
        info_query = text("""
            SELECT 
                inhrelid::regclass AS partition_name,
                pg_size_pretty(pg_relation_size(inhrelid)) AS size,
                pg_stat_user_tables.n_live_tup AS row_count,
                pg_stat_user_tables.last_vacuum,
                pg_stat_user_tables.last_analyze
            FROM pg_inherits
            JOIN pg_stat_user_tables ON pg_stat_user_tables.relid = pg_inherits.inhrelid
            WHERE inhparent = :table_name::regclass
            ORDER BY partition_name
        """)
        
        result = await db.execute(info_query, {"table_name": table_name})
        
        partitions = []
        for row in result:
            partitions.append({
                "name": str(row.partition_name),
                "size": row.size,
                "row_count": row.row_count,
                "last_vacuum": row.last_vacuum,
                "last_analyze": row.last_analyze
            })
        
        return partitions
    
    async def optimize_partition_constraints(self, db: AsyncSession):
        """Optimize partition constraints for better query planning"""
        for table_name in self.partitioned_tables.keys():
            # Enable constraint exclusion
            await db.execute(text("SET constraint_exclusion = partition"))
            
            # Update table statistics
            await db.execute(text(f"ANALYZE {table_name}"))
            
            logger.info(f"Optimized constraints for {table_name}")


# Global partition manager instance
partition_manager = PartitionManager()


# Utility functions
async def setup_partitioning(db: AsyncSession):
    """Setup database partitioning"""
    await partition_manager.initialize_partitioning(db)


async def maintain_partitions(db: AsyncSession):
    """Run partition maintenance"""
    await partition_manager.maintain_partitions(db)


async def get_partition_statistics(
    db: AsyncSession,
    table_name: str
) -> Dict[str, Any]:
    """Get partition statistics for a table"""
    partitions = await partition_manager.get_partition_info(db, table_name)
    
    total_size = 0
    total_rows = 0
    
    for partition in partitions:
        # Parse size (e.g., "123 MB" -> 123)
        size_str = partition["size"]
        if "MB" in size_str:
            total_size += float(size_str.replace(" MB", ""))
        elif "GB" in size_str:
            total_size += float(size_str.replace(" GB", "")) * 1024
        elif "KB" in size_str:
            total_size += float(size_str.replace(" KB", "")) / 1024
        
        total_rows += partition["row_count"] or 0
    
    return {
        "table": table_name,
        "partition_count": len(partitions),
        "total_size_mb": round(total_size, 2),
        "total_rows": total_rows,
        "partitions": partitions
    }