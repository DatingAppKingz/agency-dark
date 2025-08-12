-- OAuth Tables Optimization for Production
-- Run this after initial OAuth tables are created
-- Adds indexes, partitioning, and performance optimizations

-- ============================================================================
-- INDEXES FOR TOKEN LOOKUPS
-- ============================================================================

-- Index for fast token validation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_tokens_token_hash 
ON oauth_tokens USING btree (token_hash) 
WHERE revoked_at IS NULL AND expires_at > NOW();

-- Index for refresh token lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_tokens_refresh_token_hash 
ON oauth_tokens USING btree (refresh_token_hash) 
WHERE refresh_token_hash IS NOT NULL AND revoked_at IS NULL;

-- Index for user's active tokens
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_tokens_user_active 
ON oauth_tokens USING btree (user_id, client_id) 
WHERE revoked_at IS NULL AND expires_at > NOW();

-- Index for client's active tokens
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_tokens_client_active 
ON oauth_tokens USING btree (client_id, created_at DESC) 
WHERE revoked_at IS NULL;

-- Index for token cleanup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_tokens_cleanup 
ON oauth_tokens USING btree (expires_at) 
WHERE revoked_at IS NULL;

-- ============================================================================
-- INDEXES FOR AUTHORIZATION CODES
-- ============================================================================

-- Index for authorization code lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_auth_codes_code_hash 
ON oauth_authorization_codes USING btree (code_hash) 
WHERE used_at IS NULL AND expires_at > NOW();

-- Index for PKCE validation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_auth_codes_pkce 
ON oauth_authorization_codes USING btree (code_hash, code_challenge) 
WHERE code_challenge IS NOT NULL AND used_at IS NULL;

-- ============================================================================
-- INDEXES FOR CLIENT QUERIES
-- ============================================================================

-- Index for client authentication
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_clients_auth 
ON oauth_clients USING btree (client_id, client_secret_hash) 
WHERE is_active = true;

-- Index for client redirect URI validation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_client_redirect_uris 
ON oauth_client_redirect_uris USING btree (client_id, uri_hash);

-- Index for client scopes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_client_scopes 
ON oauth_client_scopes USING btree (client_id, scope);

-- ============================================================================
-- INDEXES FOR CONSENT MANAGEMENT
-- ============================================================================

-- Index for user consent lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_consents_lookup 
ON oauth_consents USING btree (user_id, client_id) 
WHERE revoked_at IS NULL;

-- Index for consent expiration
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_consents_expiry 
ON oauth_consents USING btree (expires_at) 
WHERE revoked_at IS NULL AND expires_at IS NOT NULL;

-- ============================================================================
-- INDEXES FOR AUDIT LOGS
-- ============================================================================

-- Index for audit log queries by user
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_audit_user 
ON oauth_audit_logs USING btree (user_id, created_at DESC);

-- Index for audit log queries by client
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_audit_client 
ON oauth_audit_logs USING btree (client_id, created_at DESC);

-- Index for security event monitoring
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_audit_security 
ON oauth_audit_logs USING btree (event_type, created_at DESC) 
WHERE event_type IN ('failed_authentication', 'suspicious_activity', 'token_theft');

-- ============================================================================
-- PARTITIONING FOR LARGE TABLES
-- ============================================================================

-- Partition oauth_tokens by month for better performance and maintenance
DO $$
BEGIN
    -- Check if partitioning doesn't already exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_class 
        WHERE relname = 'oauth_tokens_partitioned' 
        AND relkind = 'p'
    ) THEN
        -- Create partitioned table
        CREATE TABLE oauth_tokens_partitioned (
            LIKE oauth_tokens INCLUDING ALL
        ) PARTITION BY RANGE (created_at);
        
        -- Create partitions for the next 12 months
        FOR i IN 0..11 LOOP
            EXECUTE format(
                'CREATE TABLE oauth_tokens_%s PARTITION OF oauth_tokens_partitioned 
                FOR VALUES FROM (%L) TO (%L)',
                to_char(CURRENT_DATE + (i || ' months')::interval, 'YYYY_MM'),
                date_trunc('month', CURRENT_DATE + (i || ' months')::interval),
                date_trunc('month', CURRENT_DATE + ((i+1) || ' months')::interval)
            );
        END LOOP;
    END IF;
END $$;

-- Partition audit logs by month
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class 
        WHERE relname = 'oauth_audit_logs_partitioned' 
        AND relkind = 'p'
    ) THEN
        CREATE TABLE oauth_audit_logs_partitioned (
            LIKE oauth_audit_logs INCLUDING ALL
        ) PARTITION BY RANGE (created_at);
        
        -- Create partitions for the next 6 months
        FOR i IN 0..5 LOOP
            EXECUTE format(
                'CREATE TABLE oauth_audit_logs_%s PARTITION OF oauth_audit_logs_partitioned 
                FOR VALUES FROM (%L) TO (%L)',
                to_char(CURRENT_DATE + (i || ' months')::interval, 'YYYY_MM'),
                date_trunc('month', CURRENT_DATE + (i || ' months')::interval),
                date_trunc('month', CURRENT_DATE + ((i+1) || ' months')::interval)
            );
        END LOOP;
    END IF;
END $$;

-- ============================================================================
-- MATERIALIZED VIEWS FOR ANALYTICS
-- ============================================================================

-- Materialized view for token statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS oauth_token_stats AS
SELECT 
    DATE(created_at) as date,
    client_id,
    COUNT(*) as tokens_issued,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(CASE WHEN revoked_at IS NOT NULL THEN 1 END) as tokens_revoked,
    AVG(EXTRACT(EPOCH FROM (COALESCE(revoked_at, expires_at) - created_at))) as avg_lifetime_seconds,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (COALESCE(revoked_at, expires_at) - created_at))) as median_lifetime_seconds,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (COALESCE(revoked_at, expires_at) - created_at))) as p95_lifetime_seconds
FROM oauth_tokens
WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY DATE(created_at), client_id;

CREATE UNIQUE INDEX ON oauth_token_stats (date, client_id);

-- Materialized view for client usage
CREATE MATERIALIZED VIEW IF NOT EXISTS oauth_client_usage AS
SELECT 
    c.client_id,
    c.name as client_name,
    COUNT(DISTINCT t.user_id) as unique_users,
    COUNT(t.id) as total_tokens,
    COUNT(CASE WHEN t.created_at >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) as tokens_last_week,
    COUNT(CASE WHEN t.created_at >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) as tokens_last_month,
    MAX(t.created_at) as last_used_at
FROM oauth_clients c
LEFT JOIN oauth_tokens t ON c.client_id = t.client_id
GROUP BY c.client_id, c.name;

CREATE UNIQUE INDEX ON oauth_client_usage (client_id);

-- ============================================================================
-- PERFORMANCE TUNING
-- ============================================================================

-- Update table statistics for query planner
ANALYZE oauth_tokens;
ANALYZE oauth_authorization_codes;
ANALYZE oauth_clients;
ANALYZE oauth_consents;
ANALYZE oauth_audit_logs;

-- Set appropriate autovacuum settings for high-write tables
ALTER TABLE oauth_tokens SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05,
    autovacuum_vacuum_cost_delay = 10
);

ALTER TABLE oauth_audit_logs SET (
    autovacuum_vacuum_scale_factor = 0.2,
    autovacuum_analyze_scale_factor = 0.1
);

-- ============================================================================
-- CLEANUP PROCEDURES
-- ============================================================================

-- Function to clean up expired tokens
CREATE OR REPLACE FUNCTION cleanup_expired_oauth_tokens()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM oauth_tokens 
    WHERE expires_at < NOW() - INTERVAL '7 days'
    OR (revoked_at IS NOT NULL AND revoked_at < NOW() - INTERVAL '30 days');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up old authorization codes
CREATE OR REPLACE FUNCTION cleanup_old_oauth_auth_codes()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM oauth_authorization_codes 
    WHERE expires_at < NOW() - INTERVAL '1 day'
    OR (used_at IS NOT NULL AND used_at < NOW() - INTERVAL '7 days');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to archive old audit logs
CREATE OR REPLACE FUNCTION archive_old_oauth_audit_logs()
RETURNS INTEGER AS $$
DECLARE
    archived_count INTEGER;
BEGIN
    -- Move old audit logs to archive table
    INSERT INTO oauth_audit_logs_archive
    SELECT * FROM oauth_audit_logs 
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    GET DIAGNOSTICS archived_count = ROW_COUNT;
    
    -- Delete archived logs from main table
    DELETE FROM oauth_audit_logs 
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    RETURN archived_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SCHEDULED MAINTENANCE
-- ============================================================================

-- Create pg_cron extension if not exists (requires superuser)
-- CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule cleanup jobs (uncomment if pg_cron is available)
-- SELECT cron.schedule('cleanup-expired-tokens', '0 2 * * *', 'SELECT cleanup_expired_oauth_tokens();');
-- SELECT cron.schedule('cleanup-auth-codes', '0 3 * * *', 'SELECT cleanup_old_oauth_auth_codes();');
-- SELECT cron.schedule('archive-audit-logs', '0 4 * * 0', 'SELECT archive_old_oauth_audit_logs();');
-- SELECT cron.schedule('refresh-token-stats', '*/15 * * * *', 'REFRESH MATERIALIZED VIEW CONCURRENTLY oauth_token_stats;');
-- SELECT cron.schedule('refresh-client-usage', '0 * * * *', 'REFRESH MATERIALIZED VIEW CONCURRENTLY oauth_client_usage;');

-- ============================================================================
-- MONITORING QUERIES
-- ============================================================================

-- Create function for monitoring token issuance rate
CREATE OR REPLACE FUNCTION get_token_issuance_rate(interval_minutes INTEGER DEFAULT 5)
RETURNS TABLE(
    minute TIMESTAMP,
    tokens_issued BIGINT,
    unique_users BIGINT,
    avg_response_time_ms NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        date_trunc('minute', created_at) as minute,
        COUNT(*) as tokens_issued,
        COUNT(DISTINCT user_id) as unique_users,
        AVG(EXTRACT(MILLISECONDS FROM (created_at - created_at))) as avg_response_time_ms
    FROM oauth_tokens
    WHERE created_at >= NOW() - (interval_minutes || ' minutes')::INTERVAL
    GROUP BY date_trunc('minute', created_at)
    ORDER BY minute DESC;
END;
$$ LANGUAGE plpgsql;

-- Create function for monitoring error rates
CREATE OR REPLACE FUNCTION get_oauth_error_rate(interval_minutes INTEGER DEFAULT 60)
RETURNS TABLE(
    error_type VARCHAR,
    error_count BIGINT,
    affected_users BIGINT,
    affected_clients BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        event_type as error_type,
        COUNT(*) as error_count,
        COUNT(DISTINCT user_id) as affected_users,
        COUNT(DISTINCT client_id) as affected_clients
    FROM oauth_audit_logs
    WHERE created_at >= NOW() - (interval_minutes || ' minutes')::INTERVAL
    AND event_type LIKE '%error%' OR event_type LIKE '%failed%'
    GROUP BY event_type
    ORDER BY error_count DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GRANT PERMISSIONS
-- ============================================================================

-- Grant appropriate permissions to application user
GRANT SELECT, INSERT, UPDATE ON oauth_tokens TO agencydark_app;
GRANT SELECT, INSERT, UPDATE ON oauth_authorization_codes TO agencydark_app;
GRANT SELECT ON oauth_clients TO agencydark_app;
GRANT SELECT, INSERT, UPDATE ON oauth_consents TO agencydark_app;
GRANT INSERT ON oauth_audit_logs TO agencydark_app;
GRANT SELECT ON oauth_token_stats TO agencydark_app;
GRANT SELECT ON oauth_client_usage TO agencydark_app;

-- Grant execute permissions on functions
GRANT EXECUTE ON FUNCTION get_token_issuance_rate TO agencydark_app;
GRANT EXECUTE ON FUNCTION get_oauth_error_rate TO agencydark_app;