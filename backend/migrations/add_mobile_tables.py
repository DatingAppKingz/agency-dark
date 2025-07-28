"""
Add mobile application tables

This migration creates:
1. mobile_devices table for device tracking
2. mobile_sessions table for session management
3. mobile_push_logs table for push notification history
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
    """Run the mobile tables migration"""
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            logger.info("Starting mobile tables migration...")
            
            # Create mobile_devices table
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS mobile_devices (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    
                    -- Device identification
                    device_id VARCHAR(255) NOT NULL,
                    device_name VARCHAR(255),
                    platform VARCHAR(50) NOT NULL,
                    platform_version VARCHAR(50),
                    app_version VARCHAR(50),
                    
                    -- Push notifications
                    push_token VARCHAR(500),
                    push_enabled BOOLEAN DEFAULT TRUE,
                    
                    -- Biometric authentication
                    biometric_enabled BOOLEAN DEFAULT FALSE,
                    biometric_type VARCHAR(50),
                    
                    -- Status
                    is_active BOOLEAN DEFAULT TRUE,
                    is_trusted BOOLEAN DEFAULT FALSE,
                    
                    -- Timestamps
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Constraints
                    CONSTRAINT unique_user_device UNIQUE (user_id, device_id)
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_mobile_device_user 
                    ON mobile_devices(user_id);
                CREATE INDEX IF NOT EXISTS idx_mobile_device_active 
                    ON mobile_devices(is_active, user_id);
                CREATE INDEX IF NOT EXISTS idx_mobile_device_push 
                    ON mobile_devices(push_token) WHERE push_enabled = TRUE;
            """))
            
            # Create mobile_sessions table
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS mobile_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    device_id UUID NOT NULL REFERENCES mobile_devices(id) ON DELETE CASCADE,
                    
                    -- Session tokens
                    refresh_token TEXT UNIQUE,
                    
                    -- Session info
                    ip_address VARCHAR(45),
                    location_country VARCHAR(2),
                    location_city VARCHAR(100),
                    
                    -- Session lifecycle
                    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    ended_at TIMESTAMP WITH TIME ZONE,
                    
                    -- Status
                    is_active BOOLEAN DEFAULT TRUE,
                    ended_reason VARCHAR(50),
                    
                    -- Metadata
                    metadata JSONB
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_mobile_session_user 
                    ON mobile_sessions(user_id, is_active);
                CREATE INDEX IF NOT EXISTS idx_mobile_session_device 
                    ON mobile_sessions(device_id, is_active);
                CREATE INDEX IF NOT EXISTS idx_mobile_session_token 
                    ON mobile_sessions(refresh_token);
                CREATE INDEX IF NOT EXISTS idx_mobile_session_active 
                    ON mobile_sessions(is_active, expires_at);
            """))
            
            # Create mobile_push_logs table
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS mobile_push_logs (
                    id SERIAL PRIMARY KEY,
                    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                    device_id UUID REFERENCES mobile_devices(id) ON DELETE SET NULL,
                    
                    -- Notification details
                    notification_type VARCHAR(50) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    body TEXT,
                    data JSONB,
                    
                    -- Delivery status
                    status VARCHAR(50) NOT NULL, -- sent, delivered, failed, opened
                    error_message TEXT,
                    
                    -- Tracking
                    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    delivered_at TIMESTAMP WITH TIME ZONE,
                    opened_at TIMESTAMP WITH TIME ZONE,
                    
                    -- FCM details
                    fcm_message_id VARCHAR(255),
                    fcm_response JSONB
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_push_log_user 
                    ON mobile_push_logs(user_id, sent_at DESC);
                CREATE INDEX IF NOT EXISTS idx_push_log_device 
                    ON mobile_push_logs(device_id, sent_at DESC);
                CREATE INDEX IF NOT EXISTS idx_push_log_status 
                    ON mobile_push_logs(status, sent_at DESC);
                CREATE INDEX IF NOT EXISTS idx_push_log_type 
                    ON mobile_push_logs(notification_type, sent_at DESC);
            """))
            
            # Create mobile_app_settings table
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS mobile_app_settings (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    
                    -- Notification preferences
                    notifications_enabled BOOLEAN DEFAULT TRUE,
                    message_notifications BOOLEAN DEFAULT TRUE,
                    transaction_notifications BOOLEAN DEFAULT TRUE,
                    marketing_notifications BOOLEAN DEFAULT FALSE,
                    
                    -- App preferences
                    theme VARCHAR(20) DEFAULT 'system', -- light, dark, system
                    language VARCHAR(10) DEFAULT 'en',
                    
                    -- Privacy settings
                    show_online_status BOOLEAN DEFAULT TRUE,
                    show_read_receipts BOOLEAN DEFAULT TRUE,
                    
                    -- Data usage
                    auto_download_media BOOLEAN DEFAULT TRUE,
                    cellular_data_usage VARCHAR(20) DEFAULT 'normal', -- low, normal, high
                    
                    -- Timestamps
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Constraints
                    CONSTRAINT unique_user_settings UNIQUE (user_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_mobile_settings_user 
                    ON mobile_app_settings(user_id);
            """))
            
            # Create trigger for updated_at
            await db.execute(text("""
                CREATE OR REPLACE FUNCTION update_mobile_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
                
                DROP TRIGGER IF EXISTS update_mobile_devices_updated ON mobile_devices;
                DROP TRIGGER IF EXISTS update_mobile_settings_updated ON mobile_app_settings;
                
                CREATE TRIGGER update_mobile_settings_updated 
                BEFORE UPDATE ON mobile_app_settings
                FOR EACH ROW EXECUTE FUNCTION update_mobile_updated_at();
            """))
            
            # Create view for active mobile users
            await db.execute(text("""
                CREATE OR REPLACE VIEW mobile_active_users AS
                SELECT 
                    u.id as user_id,
                    u.email,
                    u.full_name,
                    COUNT(DISTINCT md.id) as device_count,
                    COUNT(DISTINCT ms.id) as active_sessions,
                    MAX(ms.last_activity) as last_active,
                    ARRAY_AGG(DISTINCT md.platform) as platforms,
                    bool_or(md.push_enabled) as push_enabled,
                    bool_or(md.biometric_enabled) as biometric_enabled
                FROM users u
                JOIN mobile_devices md ON u.id = md.user_id AND md.is_active = TRUE
                LEFT JOIN mobile_sessions ms ON md.id = ms.device_id AND ms.is_active = TRUE
                GROUP BY u.id, u.email, u.full_name;
            """))
            
            # Create materialized view for push notification stats
            await db.execute(text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_push_notification_stats AS
                SELECT 
                    DATE_TRUNC('day', sent_at) as day,
                    notification_type,
                    status,
                    COUNT(*) as count,
                    COUNT(DISTINCT user_id) as unique_users,
                    AVG(CASE 
                        WHEN delivered_at IS NOT NULL 
                        THEN EXTRACT(EPOCH FROM (delivered_at - sent_at))
                        ELSE NULL 
                    END) as avg_delivery_time_seconds,
                    COUNT(CASE WHEN opened_at IS NOT NULL THEN 1 END)::FLOAT / 
                        NULLIF(COUNT(CASE WHEN delivered_at IS NOT NULL THEN 1 END), 0) as open_rate
                FROM mobile_push_logs
                WHERE sent_at >= NOW() - INTERVAL '30 days'
                GROUP BY DATE_TRUNC('day', sent_at), notification_type, status
                ORDER BY day DESC, notification_type;
                
                CREATE INDEX IF NOT EXISTS idx_mv_push_stats_day 
                    ON mv_push_notification_stats(day DESC);
                CREATE INDEX IF NOT EXISTS idx_mv_push_stats_type 
                    ON mv_push_notification_stats(notification_type);
            """))
            
            await db.commit()
            logger.info("Mobile tables migration completed successfully")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await db.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())