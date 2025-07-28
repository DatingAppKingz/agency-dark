"""
Add encrypted API keys tables

This migration creates:
1. Enhanced api_keys table with encryption
2. API key audit logs table
3. Indexes for performance
"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from core.config import get_settings
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


async def run_migration():
    """Run the encrypted API keys migration"""
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            logger.info("Starting encrypted API keys migration...")
            
            # Create api_keys table
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    
                    -- Key identification
                    name VARCHAR(100) NOT NULL,
                    key_prefix VARCHAR(8) NOT NULL,
                    key_hash VARCHAR(128) NOT NULL,
                    
                    -- Encrypted data
                    encrypted_data TEXT NOT NULL,
                    
                    -- Permissions
                    scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
                    
                    -- Properties
                    environment VARCHAR(20) DEFAULT 'live',
                    expires_at TIMESTAMP WITH TIME ZONE,
                    
                    -- Usage tracking
                    last_used_at TIMESTAMP WITH TIME ZONE,
                    usage_count INTEGER DEFAULT 0,
                    
                    -- Status
                    is_active BOOLEAN DEFAULT TRUE,
                    revoked_at TIMESTAMP WITH TIME ZONE,
                    revocation_reason VARCHAR(100),
                    
                    -- Rotation
                    rotated_at TIMESTAMP WITH TIME ZONE,
                    rotation_count INTEGER DEFAULT 0,
                    
                    -- Metadata
                    metadata JSONB,
                    
                    -- Timestamps
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_api_key_lookup 
                    ON api_keys(key_prefix, is_active);
                CREATE INDEX IF NOT EXISTS idx_api_key_user_active 
                    ON api_keys(user_id, is_active);
                CREATE INDEX IF NOT EXISTS idx_api_key_expiry 
                    ON api_keys(expires_at, is_active);
                CREATE INDEX IF NOT EXISTS idx_api_key_hash 
                    ON api_keys(key_hash) WHERE is_active = TRUE;
            """))
            
            # Create api_key_audits table
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS api_key_audits (
                    id SERIAL PRIMARY KEY,
                    api_key_id INTEGER NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
                    user_id UUID REFERENCES users(id),
                    
                    -- Audit info
                    action VARCHAR(50) NOT NULL,
                    details JSONB,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    
                    -- Timestamp
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_api_key_audit_key 
                    ON api_key_audits(api_key_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_api_key_audit_user 
                    ON api_key_audits(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_api_key_audit_action 
                    ON api_key_audits(action, created_at DESC);
            """))
            
            # Create function for updating updated_at
            await db.execute(text("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """))
            
            # Create trigger for api_keys
            await db.execute(text("""
                DROP TRIGGER IF EXISTS update_api_keys_updated_at ON api_keys;
                
                CREATE TRIGGER update_api_keys_updated_at 
                BEFORE UPDATE ON api_keys
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            """))
            
            # Create view for active API keys
            await db.execute(text("""
                CREATE OR REPLACE VIEW active_api_keys AS
                SELECT 
                    ak.id,
                    ak.user_id,
                    ak.name,
                    ak.key_prefix,
                    ak.scopes,
                    ak.environment,
                    ak.expires_at,
                    ak.last_used_at,
                    ak.usage_count,
                    ak.created_at,
                    u.email as user_email,
                    u.full_name as user_name,
                    CASE 
                        WHEN ak.expires_at < CURRENT_TIMESTAMP THEN 'expired'
                        WHEN ak.rotated_at IS NULL AND 
                             ak.created_at < CURRENT_TIMESTAMP - INTERVAL '90 days' THEN 'needs_rotation'
                        WHEN ak.rotated_at IS NOT NULL AND 
                             ak.rotated_at < CURRENT_TIMESTAMP - INTERVAL '90 days' THEN 'needs_rotation'
                        ELSE 'active'
                    END as status
                FROM api_keys ak
                JOIN users u ON ak.user_id = u.id
                WHERE ak.is_active = TRUE;
            """))
            
            # Create materialized view for API key statistics
            await db.execute(text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_api_key_stats AS
                SELECT 
                    u.id as user_id,
                    u.email,
                    COUNT(DISTINCT ak.id) as total_keys,
                    COUNT(DISTINCT CASE WHEN ak.is_active THEN ak.id END) as active_keys,
                    COUNT(DISTINCT CASE WHEN ak.expires_at < CURRENT_TIMESTAMP THEN ak.id END) as expired_keys,
                    SUM(ak.usage_count) as total_usage,
                    MAX(ak.last_used_at) as last_api_activity,
                    COUNT(DISTINCT aka.id) as total_audit_events,
                    COUNT(DISTINCT CASE WHEN aka.action = 'failed_verification' THEN aka.id END) as failed_attempts
                FROM users u
                LEFT JOIN api_keys ak ON u.id = ak.user_id
                LEFT JOIN api_key_audits aka ON ak.id = aka.api_key_id
                GROUP BY u.id, u.email;
                
                CREATE INDEX IF NOT EXISTS idx_mv_api_key_stats_user 
                    ON mv_api_key_stats(user_id);
                CREATE INDEX IF NOT EXISTS idx_mv_api_key_stats_usage 
                    ON mv_api_key_stats(total_usage DESC);
            """))
            
            await db.commit()
            logger.info("Encrypted API keys migration completed successfully")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await db.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())