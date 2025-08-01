"""Create sync conflict logs table manually."""

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
        result = await conn.execute(text("SELECT to_regclass('sync_conflict_logs')"))
        exists = result.scalar() is not None
        
        if exists:
            print('Table sync_conflict_logs already exists')
        else:
            print('Creating sync_conflict_logs table...')
            # Create table
            await conn.execute(text('''
                CREATE TABLE sync_conflict_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    sync_job_id VARCHAR,
                    api_key_id INTEGER REFERENCES api_keys(id),
                    agency_id UUID NOT NULL REFERENCES agencies(id),
                    conflict_type VARCHAR NOT NULL,
                    entity_type VARCHAR NOT NULL,
                    local_id VARCHAR NOT NULL,
                    remote_id VARCHAR NOT NULL,
                    field_conflicts JSONB,
                    local_data_snapshot JSONB,
                    remote_data_snapshot JSONB,
                    resolution_action VARCHAR NOT NULL,
                    resolved_data JSONB,
                    merge_conflicts JSONB,
                    manual_review_required BOOLEAN DEFAULT FALSE,
                    resolved_by UUID REFERENCES users(id),
                    resolved_at TIMESTAMP,
                    auto_resolved BOOLEAN DEFAULT FALSE,
                    resolution_notes TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            '''))
            
            # Create indexes
            await conn.execute(text('CREATE INDEX ix_sync_conflict_logs_sync_job_id ON sync_conflict_logs(sync_job_id)'))
            await conn.execute(text('CREATE INDEX ix_sync_conflict_logs_agency_id ON sync_conflict_logs(agency_id)'))
            await conn.execute(text('CREATE INDEX ix_sync_conflict_logs_api_key_id ON sync_conflict_logs(api_key_id)'))
            await conn.execute(text('CREATE INDEX ix_sync_conflict_logs_entity_type ON sync_conflict_logs(entity_type)'))
            await conn.execute(text('CREATE INDEX ix_sync_conflict_logs_conflict_type ON sync_conflict_logs(conflict_type)'))
            await conn.execute(text('CREATE INDEX ix_sync_conflict_logs_manual_review_required ON sync_conflict_logs(manual_review_required)'))
            await conn.execute(text('CREATE INDEX ix_sync_conflict_logs_created_at ON sync_conflict_logs(created_at)'))
            
            print('Table created successfully')
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_migration())