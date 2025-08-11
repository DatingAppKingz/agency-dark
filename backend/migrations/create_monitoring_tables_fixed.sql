-- Create monitoring tables needed by the monitoring service
-- These tables store metrics, alerts, and health checks

-- Drop and recreate enum types
DROP TYPE IF EXISTS metric_type CASCADE;
CREATE TYPE metric_type AS ENUM (
    'api_throughput',
    'api_request_count',
    'api_response_time',
    'api_error_rate',
    'cache_hit_rate',
    'cache_memory_usage',
    'cache_operations',
    'database_connections',
    'database_query_time',
    'database_transactions',
    'system_cpu',
    'system_memory',
    'system_disk',
    'business_metric',
    'custom'
);

DROP TYPE IF EXISTS alert_severity CASCADE;
CREATE TYPE alert_severity AS ENUM (
    'info',
    'warning',
    'error',
    'critical'
);

DROP TYPE IF EXISTS health_status CASCADE;
CREATE TYPE health_status AS ENUM (
    'healthy',
    'degraded',
    'unhealthy',
    'unknown'
);

-- Metrics table
CREATE TABLE IF NOT EXISTS metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_type metric_type NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    value FLOAT NOT NULL,
    unit VARCHAR(50),
    tags JSONB DEFAULT '{}',
    entity_type VARCHAR(100),
    entity_id VARCHAR(255),
    hostname VARCHAR(255),
    service_name VARCHAR(100),
    environment VARCHAR(50),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alert rules table
CREATE TABLE IF NOT EXISTS alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    metric_type metric_type NOT NULL,
    condition VARCHAR(50) NOT NULL,
    threshold FLOAT NOT NULL,
    query TEXT,
    aggregation VARCHAR(50),
    time_window_minutes INTEGER DEFAULT 5,
    severity alert_severity DEFAULT 'warning',
    tags JSONB DEFAULT '{}',
    notification_channels JSONB DEFAULT '[]',
    cooldown_minutes INTEGER DEFAULT 30,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alert history table
CREATE TABLE IF NOT EXISTS alert_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_rule_id UUID REFERENCES alert_rules(id) ON DELETE CASCADE,
    triggered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    severity alert_severity NOT NULL,
    metric_value FLOAT NOT NULL,
    threshold FLOAT NOT NULL,
    message TEXT,
    notification_sent BOOLEAN DEFAULT false,
    acknowledged BOOLEAN DEFAULT false,
    acknowledged_by UUID,
    acknowledged_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Service health table
CREATE TABLE IF NOT EXISTS service_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(100) NOT NULL,
    status health_status NOT NULL DEFAULT 'unknown',
    check_name VARCHAR(255) NOT NULL,
    response_time_ms INTEGER,
    details JSONB DEFAULT '{}',
    dependencies JSONB DEFAULT '[]',
    checked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_healthy_at TIMESTAMP,
    previous_status health_status,
    status_changed_at TIMESTAMP,
    consecutive_failures INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(service_name, check_name)
);

-- Webhook deliveries table
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID,
    event VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    status_code INTEGER,
    response_body TEXT,
    response_time_ms INTEGER,
    is_successful BOOLEAN DEFAULT false,
    attempt_count INTEGER DEFAULT 1,
    error_message TEXT,
    next_retry_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance metrics aggregation table
CREATE TABLE IF NOT EXISTS metrics_aggregated (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_type metric_type NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    period VARCHAR(20) NOT NULL,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    avg_value FLOAT,
    min_value FLOAT,
    max_value FLOAT,
    sum_value FLOAT,
    count_value INTEGER,
    p50_value FLOAT,
    p95_value FLOAT,
    p99_value FLOAT,
    tags JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_type, metric_name, period, period_start)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_type_name ON metrics(metric_type, metric_name);
CREATE INDEX IF NOT EXISTS idx_metrics_entity ON metrics(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_metrics_service ON metrics(service_name);
CREATE INDEX IF NOT EXISTS idx_metrics_tags ON metrics USING gin(tags);

CREATE INDEX IF NOT EXISTS idx_alert_rules_active ON alert_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_alert_rules_metric_type ON alert_rules(metric_type);

CREATE INDEX IF NOT EXISTS idx_alert_history_rule ON alert_history(alert_rule_id);
CREATE INDEX IF NOT EXISTS idx_alert_history_triggered ON alert_history(triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_history_unresolved ON alert_history(resolved_at) WHERE resolved_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_service_health_service ON service_health(service_name);
CREATE INDEX IF NOT EXISTS idx_service_health_status ON service_health(status);
CREATE INDEX IF NOT EXISTS idx_service_health_checked ON service_health(checked_at DESC);

CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook ON webhook_deliveries(webhook_id);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_retry ON webhook_deliveries(next_retry_at) WHERE next_retry_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_failed ON webhook_deliveries(is_successful) WHERE is_successful = false;

CREATE INDEX IF NOT EXISTS idx_metrics_agg_period ON metrics_aggregated(period, period_start DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_agg_type ON metrics_aggregated(metric_type, metric_name);