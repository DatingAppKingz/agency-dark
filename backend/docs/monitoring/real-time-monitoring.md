# Real-time Monitoring System

## Overview

The Real-time Monitoring System provides comprehensive observability into the AgencyDark platform, tracking system health, performance metrics, and alerting on anomalies.

## Components

### 1. System Metrics Collection
- **CPU Monitoring**: Usage percentage, load average, per-core metrics
- **Memory Monitoring**: RAM usage, swap usage, process memory
- **Disk Monitoring**: Space usage, I/O statistics
- **Network Monitoring**: Bandwidth, connections, packet statistics

### 2. Application Metrics
- **API Performance**: Request counts, response times, error rates
- **Database Performance**: Connection pool, query times, slow queries
- **Cache Performance**: Hit rates, memory usage, operations
- **WebSocket Metrics**: Active connections, message throughput

### 3. Health Check System
- **Service Health**: API, database, cache, disk, memory status
- **Dependency Checks**: External service availability
- **Response Time Tracking**: Service latency monitoring
- **Status History**: Health state transitions

### 4. Alert Management
- **Rule-based Alerts**: Configurable thresholds and conditions
- **Multi-severity Levels**: Info, Warning, Error, Critical
- **Alert Cooldowns**: Prevent alert spam
- **Notification Channels**: Email, SMS, Slack, webhooks
- **Alert Lifecycle**: Active → Acknowledged → Resolved

### 5. Performance Profiling
- **Request Profiling**: Detailed timing breakdown
- **Resource Usage**: CPU and memory per request
- **Query Analysis**: Slow query detection
- **Cache Performance**: Hit/miss tracking

## Architecture

```
┌─────────────────────┐
│   Application       │
│   Middleware        │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ Monitoring Service  │
├─────────────────────┤
│ • Orchestration     │
│ • Health Checks     │
│ • Alert Evaluation  │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│    Collectors       │
├─────────────────────┤
│ • System Collector  │
│ • API Collector     │
│ • DB Collector      │
│ • Cache Collector   │
└─────────────────────┘
```

## API Endpoints

### System Status
```
GET /api/v1/monitoring/status
```
Returns overall system health and service status.

### Query Metrics
```
GET /api/v1/monitoring/metrics
```
Query metrics with filters:
- `metric_type`: Type of metric
- `metric_name`: Specific metric name
- `service_name`: Service to filter by
- `start_time`: Start of time range
- `end_time`: End of time range

### Health Checks
```
GET /api/v1/monitoring/health
```
Get detailed health check results for all services.

### Alerts
```
GET /api/v1/monitoring/alerts
```
List alerts with filters:
- `status`: active, acknowledged, resolved
- `severity`: info, warning, error, critical
- `start_date`: Filter by trigger date
- `end_date`: Filter by trigger date

### Performance Analysis
```
GET /api/v1/monitoring/performance/endpoints
GET /api/v1/monitoring/performance/endpoints/{endpoint}
GET /api/v1/monitoring/performance/database
GET /api/v1/monitoring/performance/cache
```

## Configuration

### Alert Rules

Create custom alert rules:

```json
POST /api/v1/monitoring/alert-rules
{
  "name": "High API Error Rate",
  "description": "Alert when API errors exceed 5%",
  "metric_type": "api_error_rate",
  "condition": "greater_than",
  "threshold": 5.0,
  "time_window_minutes": 5,
  "severity": "warning",
  "notification_channels": [
    {
      "type": "email",
      "recipients": ["ops@agency.com"]
    }
  ]
}
```

### Default Alert Rules

The system comes with pre-configured alert rules:
- High CPU Usage (>80%)
- Critical CPU Usage (>95%)
- High Memory Usage (>85%)
- Low Disk Space (>90%)
- High API Error Rate (>5%)
- Database Connection Pool Full (>80)
- Low Cache Hit Rate (<70%)

## Monitoring Middleware

The monitoring middleware automatically tracks:
- Request duration
- Database query time
- Cache operation time
- External API call time
- Resource usage

Example request tracking:
```python
# Automatically tracked by middleware
- Total request time: 150ms
  - Database queries: 80ms (3 queries)
  - Cache operations: 5ms (2 hits, 1 miss)
  - Processing time: 65ms
```

## Dashboards

Create custom monitoring dashboards:

```json
POST /api/v1/monitoring/dashboards
{
  "name": "API Performance Dashboard",
  "layout": {
    "columns": 2,
    "rows": 3
  },
  "widgets": [
    {
      "type": "line_chart",
      "metric": "api_request_count",
      "position": {"x": 0, "y": 0, "w": 1, "h": 1}
    },
    {
      "type": "gauge",
      "metric": "api_error_rate",
      "position": {"x": 1, "y": 0, "w": 1, "h": 1}
    }
  ],
  "refresh_interval_seconds": 30
}
```

## Best Practices

### 1. Metric Collection
- Keep collection intervals reasonable (60s for system metrics)
- Use appropriate metric types and naming conventions
- Tag metrics for better filtering

### 2. Alert Configuration
- Set realistic thresholds based on baseline performance
- Use appropriate time windows to avoid false positives
- Configure cooldown periods to prevent alert fatigue
- Test alert rules before enabling

### 3. Performance Monitoring
- Monitor slow endpoints regularly
- Set up alerts for performance degradation
- Use performance profiles to identify bottlenecks
- Track trends over time

### 4. Resource Management
- Monitor metric storage growth
- Set up data retention policies
- Archive old metrics periodically
- Use aggregation for long-term storage

## Integration

### With ML Analytics
The monitoring system integrates with ML Analytics for:
- Anomaly detection in metrics
- Predictive alerting
- Capacity planning

### With Reporting
Export monitoring data for:
- Performance reports
- SLA compliance
- Incident analysis
- Capacity planning

## Troubleshooting

### High Memory Usage
1. Check cache memory metrics
2. Review database connection pool
3. Analyze request patterns
4. Look for memory leaks in performance profiles

### Slow API Response
1. Check endpoint performance metrics
2. Review database slow queries
3. Analyze cache hit rates
4. Check external API latencies

### Alert Storms
1. Review alert rule configurations
2. Adjust thresholds based on baselines
3. Increase cooldown periods
4. Group related alerts

## Security Considerations

- Metrics data is isolated by agency
- Alert rules require admin permissions
- Dashboard sharing is controlled
- Sensitive data is not logged in metrics

## Future Enhancements

1. **Distributed Tracing**: Track requests across services
2. **Log Aggregation**: Centralized log management
3. **Custom Metrics**: User-defined metrics via SDK
4. **Mobile Alerts**: Push notifications for critical alerts
5. **AI-powered Insights**: Automatic root cause analysis