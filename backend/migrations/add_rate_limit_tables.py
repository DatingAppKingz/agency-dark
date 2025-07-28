"""
Add rate limiting tables for tracking violations and metrics

This migration creates:
1. rate_limit_violations table for tracking violations
2. system_metrics table for general system metrics
3. Indexes for performance
"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import get_settings
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


async def run_migration():
    """Run the rate limiting tables migration"""
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            logger.info("Starting rate limit tables migration...")
            
            # Create rate_limit_violations table
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS rate_limit_violations (
                    id SERIAL PRIMARY KEY,
                    
                    -- Identification
                    identifier VARCHAR(255) NOT NULL,
                    strategy VARCHAR(50) NOT NULL,
                    endpoint VARCHAR(255),
                    
                    -- Request details
                    method VARCHAR(10),
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    
                    -- Violation details
                    limit_exceeded INTEGER,
                    window_seconds INTEGER,
                    requests_made INTEGER,
                    
                    -- Response
                    blocked BOOLEAN DEFAULT FALSE,
                    block_duration INTEGER,
                    
                    -- Metadata
                    metadata JSONB,
                    
                    -- Timestamp
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_rate_violations_identifier 
                    ON rate_limit_violations(identifier, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_rate_violations_strategy 
                    ON rate_limit_violations(strategy, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_rate_violations_endpoint 
                    ON rate_limit_violations(endpoint, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_rate_violations_blocked 
                    ON rate_limit_violations(blocked, created_at DESC) WHERE blocked = TRUE;
                CREATE INDEX IF NOT EXISTS idx_rate_violations_created 
                    ON rate_limit_violations(created_at DESC);
            """))
            
            # Create system_metrics table (general purpose metrics)
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id SERIAL PRIMARY KEY,
                    
                    -- Metric info
                    metric_name VARCHAR(100) NOT NULL,
                    metric_value TEXT NOT NULL,
                    metric_type VARCHAR(50) DEFAULT 'gauge',
                    
                    -- Context
                    component VARCHAR(100),
                    environment VARCHAR(50),
                    
                    -- Additional data
                    metadata JSONB,
                    tags JSONB,
                    
                    -- Timestamp
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_system_metrics_name 
                    ON system_metrics(metric_name, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_system_metrics_component 
                    ON system_metrics(component, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_system_metrics_created 
                    ON system_metrics(created_at DESC);
                
                -- Create index for JSON queries
                CREATE INDEX IF NOT EXISTS idx_system_metrics_tags 
                    ON system_metrics USING gin(tags);
            """))
            
            # Create rate_limit_config table for dynamic configuration
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS rate_limit_configs (
                    id SERIAL PRIMARY KEY,
                    
                    -- Configuration target
                    strategy VARCHAR(50) NOT NULL,
                    endpoint VARCHAR(255),
                    identifier_pattern VARCHAR(255),
                    
                    -- Rate limit settings
                    requests INTEGER NOT NULL,
                    window_seconds INTEGER NOT NULL,
                    burst INTEGER,
                    block_duration INTEGER,
                    
                    -- Control
                    enabled BOOLEAN DEFAULT TRUE,
                    priority INTEGER DEFAULT 0,
                    
                    -- Metadata
                    description TEXT,
                    metadata JSONB,
                    
                    -- Audit
                    created_by UUID REFERENCES users(id),
                    updated_by UUID REFERENCES users(id),
                    
                    -- Timestamps
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    
                    -- Unique constraint
                    CONSTRAINT unique_rate_limit_config 
                        UNIQUE (strategy, endpoint, identifier_pattern)
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_rate_limit_config_lookup 
                    ON rate_limit_configs(strategy, endpoint, enabled);
                CREATE INDEX IF NOT EXISTS idx_rate_limit_config_priority 
                    ON rate_limit_configs(priority DESC, enabled);
                CREATE INDEX IF NOT EXISTS idx_rate_limit_config_expires 
                    ON rate_limit_configs(expires_at) WHERE expires_at IS NOT NULL;
            """))
            
            # Create trigger for updated_at
            await db.execute(text("""
                CREATE OR REPLACE FUNCTION update_rate_limit_config_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
                
                DROP TRIGGER IF EXISTS update_rate_limit_configs_updated_at ON rate_limit_configs;
                
                CREATE TRIGGER update_rate_limit_configs_updated_at 
                BEFORE UPDATE ON rate_limit_configs
                FOR EACH ROW EXECUTE FUNCTION update_rate_limit_config_updated_at();
            """))
            
            # Create view for rate limit statistics
            await db.execute(text("""
                CREATE OR REPLACE VIEW rate_limit_stats AS
                SELECT 
                    DATE_TRUNC('hour', created_at) as hour,
                    strategy,
                    endpoint,
                    COUNT(*) as total_violations,
                    COUNT(DISTINCT identifier) as unique_violators,
                    COUNT(CASE WHEN blocked THEN 1 END) as total_blocked,
                    AVG(requests_made) as avg_requests,
                    MAX(requests_made) as max_requests
                FROM rate_limit_violations
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
                GROUP BY DATE_TRUNC('hour', created_at), strategy, endpoint
                ORDER BY hour DESC, total_violations DESC;
            """))
            
            # Create materialized view for rate limit dashboard
            await db.execute(text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_rate_limit_dashboard AS
                SELECT 
                    strategy,
                    COUNT(*) as total_violations_24h,
                    COUNT(DISTINCT identifier) as unique_violators_24h,
                    COUNT(CASE WHEN blocked THEN 1 END) as blocked_24h,
                    
                    -- Top violators
                    (
                        SELECT jsonb_agg(jsonb_build_object(
                            'identifier', identifier,
                            'count', violation_count
                        ) ORDER BY violation_count DESC)
                        FROM (
                            SELECT identifier, COUNT(*) as violation_count
                            FROM rate_limit_violations v2
                            WHERE v2.strategy = v1.strategy
                                AND v2.created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                            GROUP BY identifier
                            ORDER BY violation_count DESC
                            LIMIT 10
                        ) top_violators
                    ) as top_violators,
                    
                    -- Top endpoints
                    (
                        SELECT jsonb_agg(jsonb_build_object(
                            'endpoint', endpoint,
                            'count', endpoint_count
                        ) ORDER BY endpoint_count DESC)
                        FROM (
                            SELECT endpoint, COUNT(*) as endpoint_count
                            FROM rate_limit_violations v3
                            WHERE v3.strategy = v1.strategy
                                AND v3.created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                                AND endpoint IS NOT NULL
                            GROUP BY endpoint
                            ORDER BY endpoint_count DESC
                            LIMIT 10
                        ) top_endpoints
                    ) as top_endpoints,
                    
                    -- Hourly trend (last 24 hours)
                    (
                        SELECT jsonb_agg(jsonb_build_object(
                            'hour', hour,
                            'count', hourly_count
                        ) ORDER BY hour)
                        FROM (
                            SELECT 
                                DATE_TRUNC('hour', created_at) as hour,
                                COUNT(*) as hourly_count
                            FROM rate_limit_violations v4
                            WHERE v4.strategy = v1.strategy
                                AND v4.created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                            GROUP BY DATE_TRUNC('hour', created_at)
                            ORDER BY hour
                        ) hourly
                    ) as hourly_trend
                    
                FROM rate_limit_violations v1
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                GROUP BY strategy;
                
                CREATE INDEX IF NOT EXISTS idx_mv_rate_limit_dashboard_strategy 
                    ON mv_rate_limit_dashboard(strategy);
            """))
            
            # Insert default rate limit configurations
            await db.execute(text("""
                INSERT INTO rate_limit_configs (strategy, endpoint, requests, window_seconds, burst, block_duration, description)
                VALUES 
                    -- Global defaults
                    ('ip', NULL, 100, 60, 20, 3600, 'Default IP rate limit'),
                    ('user', NULL, 1000, 3600, 100, 3600, 'Default user rate limit'),
                    ('api_key', NULL, 5000, 3600, 500, 3600, 'Default API key rate limit'),
                    
                    -- Auth endpoints
                    ('ip', '/api/v1/auth/login', 5, 300, NULL, 3600, 'Login rate limit'),
                    ('ip', '/api/v1/auth/register', 3, 3600, NULL, 7200, 'Registration rate limit'),
                    
                    -- Financial endpoints
                    ('user', '/api/v1/financial/withdrawals', 10, 86400, NULL, 86400, 'Withdrawal rate limit')
                ON CONFLICT (strategy, endpoint, identifier_pattern) DO NOTHING;
            """))
            
            await db.commit()
            logger.info("Rate limit tables migration completed successfully")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await db.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())