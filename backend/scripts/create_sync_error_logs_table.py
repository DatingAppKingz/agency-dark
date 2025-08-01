"""Create sync error logs table manually."""

import asyncio
import sys
sys.path.append('.')

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from core.config import settings

async def run_migration():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        # Check if table already exists
        result = await conn.execute(text("SELECT to_regclass('sync_error_logs')"))
        exists = result.scalar() is not None
        
        if exists:
            print('Table sync_error_logs already exists')
        else:
            print('Creating sync_error_logs table...')
            # Create table
            await conn.execute(text('''
                CREATE TABLE sync_error_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    error_type VARCHAR(50) NOT NULL,
                    error_message TEXT NOT NULL,
                    error_code VARCHAR(50),
                    retry_count INTEGER DEFAULT 0,
                    sync_job_id VARCHAR,
                    api_key_id INTEGER REFERENCES api_keys(id),
                    agency_id UUID REFERENCES agencies(id),
                    service_id VARCHAR(100),
                    item_id VARCHAR,
                    batch_number INTEGER,
                    operation_type VARCHAR(50),
                    stack_trace TEXT,
                    context_data JSONB,
                    recovery_strategy VARCHAR(50),
                    recovery_successful BOOLEAN,
                    recovery_metadata JSONB,
                    occurred_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    resolved_at TIMESTAMP
                )
            '''))
            
            # Create indexes
            await conn.execute(text('CREATE INDEX ix_sync_error_logs_error_type ON sync_error_logs(error_type)'))
            await conn.execute(text('CREATE INDEX ix_sync_error_logs_error_code ON sync_error_logs(error_code)'))
            await conn.execute(text('CREATE INDEX ix_sync_error_logs_sync_job_id ON sync_error_logs(sync_job_id)'))
            await conn.execute(text('CREATE INDEX ix_sync_error_logs_agency_id ON sync_error_logs(agency_id)'))
            await conn.execute(text('CREATE INDEX ix_sync_error_logs_service_id ON sync_error_logs(service_id)'))
            await conn.execute(text('CREATE INDEX ix_sync_error_logs_occurred_at_desc ON sync_error_logs(occurred_at DESC)'))
            await conn.execute(text('CREATE INDEX ix_sync_error_logs_error_type_occurred_at ON sync_error_logs(error_type, occurred_at)'))
            await conn.execute(text('CREATE INDEX ix_sync_error_logs_api_key_error_type ON sync_error_logs(api_key_id, error_type)'))
            
            print('Table created successfully')
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_migration())