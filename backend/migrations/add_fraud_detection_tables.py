"""
Add fraud detection tables

This migration creates:
1. fraud_checks table for storing fraud check results
2. user_activities table for behavioral tracking
3. fraud_rules table for custom rules
4. Indexes for performance
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
    """Run the fraud detection tables migration"""
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            logger.info("Starting fraud detection tables migration...")
            
            # Create fraud_checks table
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS fraud_checks (
                    id SERIAL PRIMARY KEY,
                    
                    -- Check context
                    user_id VARCHAR(255),
                    ip_address VARCHAR(45),
                    action VARCHAR(100) NOT NULL,
                    
                    -- Results
                    score FLOAT NOT NULL,
                    risk_level VARCHAR(20) NOT NULL,
                    confidence FLOAT,
                    
                    -- Details
                    indicators JSONB NOT NULL DEFAULT '[]'::jsonb,
                    recommendations JSONB DEFAULT '[]'::jsonb,
                    
                    -- Actions taken
                    blocked BOOLEAN DEFAULT FALSE,
                    verification_required BOOLEAN DEFAULT FALSE,
                    
                    -- Metadata
                    metadata JSONB,
                    
                    -- Timestamp
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_fraud_checks_user 
                    ON fraud_checks(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_fraud_checks_ip 
                    ON fraud_checks(ip_address, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_fraud_checks_action 
                    ON fraud_checks(action, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_fraud_checks_risk 
                    ON fraud_checks(risk_level, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_fraud_checks_score 
                    ON fraud_checks(score DESC, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_fraud_checks_blocked 
                    ON fraud_checks(blocked, created_at DESC) WHERE blocked = TRUE;
                CREATE INDEX IF NOT EXISTS idx_fraud_checks_created 
                    ON fraud_checks(created_at DESC);
                
                -- Index for JSONB queries
                CREATE INDEX IF NOT EXISTS idx_fraud_checks_indicators 
                    ON fraud_checks USING gin(indicators);
            """))
            
            # Create user_activities table for behavioral tracking
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS user_activities (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    
                    -- Activity details
                    activity_type VARCHAR(100) NOT NULL,
                    activity_data JSONB,
                    
                    -- Context
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    device_fingerprint VARCHAR(255),
                    
                    -- Location
                    country_code VARCHAR(2),
                    city VARCHAR(100),
                    latitude FLOAT,
                    longitude FLOAT,
                    
                    -- Timestamp
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_user_activities_user 
                    ON user_activities(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_user_activities_type 
                    ON user_activities(activity_type, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_user_activities_ip 
                    ON user_activities(ip_address, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_user_activities_created 
                    ON user_activities(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_user_activities_location 
                    ON user_activities(country_code, city);
            """))
            
            # Create fraud_rules table for custom rules
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS fraud_rules (
                    id SERIAL PRIMARY KEY,
                    
                    -- Rule definition
                    name VARCHAR(100) NOT NULL UNIQUE,
                    description TEXT,
                    rule_type VARCHAR(50) NOT NULL,
                    
                    -- Conditions
                    conditions JSONB NOT NULL,
                    
                    -- Actions
                    score_impact FLOAT DEFAULT 0,
                    risk_level VARCHAR(20),
                    action VARCHAR(50) NOT NULL DEFAULT 'flag',
                    
                    -- Control
                    enabled BOOLEAN DEFAULT TRUE,
                    priority INTEGER DEFAULT 0,
                    
                    -- Metadata
                    metadata JSONB,
                    
                    -- Audit
                    created_by UUID REFERENCES users(id),
                    updated_by UUID REFERENCES users(id),
                    
                    -- Timestamps
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_fraud_rules_type 
                    ON fraud_rules(rule_type, enabled);
                CREATE INDEX IF NOT EXISTS idx_fraud_rules_priority 
                    ON fraud_rules(priority DESC, enabled);
            """))
            
            # Create trigger for updated_at
            await db.execute(text("""
                CREATE OR REPLACE FUNCTION update_fraud_rules_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
                
                DROP TRIGGER IF EXISTS update_fraud_rules_updated_at ON fraud_rules;
                
                CREATE TRIGGER update_fraud_rules_updated_at 
                BEFORE UPDATE ON fraud_rules
                FOR EACH ROW EXECUTE FUNCTION update_fraud_rules_updated_at();
            """))
            
            # Create view for fraud statistics
            await db.execute(text("""
                CREATE OR REPLACE VIEW fraud_statistics AS
                SELECT 
                    DATE_TRUNC('hour', created_at) as hour,
                    action,
                    risk_level,
                    COUNT(*) as check_count,
                    AVG(score) as avg_score,
                    MAX(score) as max_score,
                    COUNT(CASE WHEN blocked THEN 1 END) as blocked_count,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(DISTINCT ip_address) as unique_ips
                FROM fraud_checks
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
                GROUP BY DATE_TRUNC('hour', created_at), action, risk_level
                ORDER BY hour DESC, check_count DESC;
            """))
            
            # Create materialized view for user risk profiles
            await db.execute(text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_user_risk_profiles AS
                SELECT 
                    fc.user_id,
                    u.email,
                    u.created_at as user_created,
                    COUNT(DISTINCT fc.id) as total_checks,
                    AVG(fc.score) as avg_risk_score,
                    MAX(fc.score) as max_risk_score,
                    COUNT(CASE WHEN fc.blocked THEN 1 END) as blocked_count,
                    COUNT(CASE WHEN fc.risk_level = 'high' THEN 1 END) as high_risk_count,
                    COUNT(CASE WHEN fc.risk_level = 'critical' THEN 1 END) as critical_risk_count,
                    
                    -- Recent activity
                    MAX(fc.created_at) as last_check,
                    COUNT(CASE WHEN fc.created_at >= NOW() - INTERVAL '7 days' THEN 1 END) as checks_last_week,
                    
                    -- Common indicators
                    (
                        SELECT jsonb_agg(DISTINCT jsonb_array_elements(indicators)->>'type')
                        FROM fraud_checks fc2
                        WHERE fc2.user_id = fc.user_id
                    ) as common_indicators,
                    
                    -- Risk classification
                    CASE 
                        WHEN AVG(fc.score) >= 70 THEN 'high_risk'
                        WHEN AVG(fc.score) >= 40 THEN 'medium_risk'
                        WHEN AVG(fc.score) >= 20 THEN 'low_risk'
                        ELSE 'minimal_risk'
                    END as risk_classification
                    
                FROM fraud_checks fc
                LEFT JOIN users u ON fc.user_id = u.id::text
                WHERE fc.user_id IS NOT NULL
                GROUP BY fc.user_id, u.email, u.created_at;
                
                CREATE INDEX IF NOT EXISTS idx_mv_user_risk_profiles_user 
                    ON mv_user_risk_profiles(user_id);
                CREATE INDEX IF NOT EXISTS idx_mv_user_risk_profiles_risk 
                    ON mv_user_risk_profiles(risk_classification);
                CREATE INDEX IF NOT EXISTS idx_mv_user_risk_profiles_score 
                    ON mv_user_risk_profiles(avg_risk_score DESC);
            """))
            
            # Insert default fraud rules
            await db.execute(text("""
                INSERT INTO fraud_rules (name, description, rule_type, conditions, score_impact, action)
                VALUES 
                    (
                        'rapid_withdrawal_attempts',
                        'Multiple withdrawal attempts in short time',
                        'velocity',
                        '{"action": "withdrawal", "count": 5, "window_seconds": 3600}'::jsonb,
                        30,
                        'flag'
                    ),
                    (
                        'new_user_high_transaction',
                        'High value transaction from new user',
                        'behavioral',
                        '{"user_age_days": 7, "amount_threshold": 1000}'::jsonb,
                        25,
                        'flag'
                    ),
                    (
                        'multiple_country_login',
                        'Login from multiple countries in short time',
                        'geo_anomaly',
                        '{"country_count": 3, "window_hours": 24}'::jsonb,
                        40,
                        'block'
                    ),
                    (
                        'suspicious_api_pattern',
                        'Unusual API usage pattern',
                        'api_abuse',
                        '{"endpoint_diversity": 10, "request_rate": 100, "window_minutes": 5}'::jsonb,
                        35,
                        'flag'
                    )
                ON CONFLICT (name) DO NOTHING;
            """))
            
            await db.commit()
            logger.info("Fraud detection tables migration completed successfully")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await db.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())