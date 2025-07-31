# AgencyDark Monitoring Guide

This guide covers the complete monitoring setup for the AgencyDark platform.

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Setup Instructions](#setup-instructions)
5. [Dashboards](#dashboards)
6. [Alerts](#alerts)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

## Overview

The AgencyDark monitoring stack provides comprehensive observability for the platform, including:
- **Metrics**: Real-time performance and business metrics
- **Logs**: Centralized log aggregation and search
- **Traces**: Distributed tracing for request flow
- **Alerts**: Proactive notifications for issues
- **Dashboards**: Visual representation of system health

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Applications                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Backend  │  │ Frontend │  │ Database │  │  Redis   │  │
│  │   API    │  │   App    │  │   (PG)   │  │  Cache   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────┬─────────────┬─────────────┬──────────────┘
                  │             │             │
         Metrics  │     Logs    │    Traces   │
                  ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Monitoring Stack                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Prometheus│  │   Loki   │  │  Jaeger  │  │ Grafana  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│        │                                           ▲        │
│        ▼                                           │        │
│  ┌──────────┐                                     │        │
│  │  Alert   │────────────────────────────────────┘        │
│  │ Manager  │                                              │
│  └──────────┘                                              │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Prometheus
- **Purpose**: Metrics collection and storage
- **Port**: 9090
- **Configuration**: `/monitoring/prometheus/prometheus.yml`
- **Retention**: 30 days
- **Scrape Interval**: 15 seconds

### 2. Grafana
- **Purpose**: Visualization and dashboards
- **Port**: 3000
- **Default User**: admin
- **Dashboards Location**: `/monitoring/grafana/dashboards/`

### 3. Alertmanager
- **Purpose**: Alert routing and notifications
- **Port**: 9093
- **Configuration**: `/monitoring/alertmanager/alertmanager.yml`
- **Notification Channels**: Email, Slack, PagerDuty

### 4. Loki
- **Purpose**: Log aggregation
- **Port**: 3100
- **Retention**: 7 days
- **Storage**: Local filesystem

### 5. Jaeger
- **Purpose**: Distributed tracing
- **Port**: 16686 (UI)
- **Sampling Rate**: 0.1 (10%)

### 6. Exporters
- **Node Exporter**: System metrics (port 9100)
- **PostgreSQL Exporter**: Database metrics (port 9187)
- **Redis Exporter**: Cache metrics (port 9121)
- **Blackbox Exporter**: HTTP probes (port 9115)

## Setup Instructions

### Prerequisites
- Docker and Docker Compose installed
- 8GB RAM minimum for monitoring stack
- 50GB disk space for metrics storage

### Quick Setup
```bash
# Run the setup script
cd /opt/agencydark/agency-dark/backend
./scripts/setup_monitoring.sh

# Follow the prompts for:
# - SMTP password
# - Slack webhook (optional)
# - PagerDuty key (optional)
```

### Manual Setup

1. **Create directories**:
```bash
mkdir -p /opt/agencydark/monitoring/{prometheus,grafana,alertmanager,loki}
```

2. **Copy configuration files**:
```bash
cp -r ./monitoring/* /opt/agencydark/monitoring/
```

3. **Start the stack**:
```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

4. **Verify services**:
```bash
docker-compose -f docker-compose.monitoring.yml ps
```

### Configuration

#### Prometheus API Token
Generate and set in `.env`:
```bash
PROMETHEUS_API_TOKEN=$(openssl rand -hex 32)
```

#### Grafana Admin Password
Set in `docker-compose.monitoring.yml`:
```yaml
environment:
  - GF_SECURITY_ADMIN_PASSWORD=your_secure_password
```

#### Alert Notifications
Edit `/monitoring/alertmanager/alertmanager.yml`:
```yaml
global:
  smtp_auth_password: 'your_smtp_password'
  slack_api_url: 'your_slack_webhook'
```

## Dashboards

### 1. AgencyDark Overview
- **UID**: agencydark-overview
- **Metrics**: Request rate, response time, availability
- **Business Metrics**: Active users, transaction volume

### 2. API Performance
- **Metrics**: Endpoint latency, error rates, throughput
- **Breakdown**: By endpoint, method, status code

### 3. Infrastructure
- **System**: CPU, memory, disk, network
- **Database**: Connections, query performance, replication lag
- **Cache**: Hit rate, memory usage, evictions

### 4. Business Analytics
- **Users**: Signups, logins, active users
- **Transactions**: Volume, success rate, fraud detection
- **Content**: Uploads, views, engagement

### Importing Dashboards
1. Access Grafana: http://localhost:3000
2. Login with admin credentials
3. Go to Dashboards → Import
4. Upload JSON files from `/monitoring/grafana/dashboards/`

## Alerts

### Alert Categories

#### Critical Alerts (Immediate Action)
- API down
- Database unreachable
- High error rate (>5%)
- Security breaches
- Payment failures

#### Warning Alerts (Investigation Needed)
- High response time (>2s)
- Disk space low (<10%)
- Memory usage high (>90%)
- Replication lag (>10s)

#### Info Alerts (Awareness)
- Low traffic
- Scheduled maintenance
- Certificate expiration (30 days)

### Alert Routing

```yaml
Routes:
  critical → Email + Slack + PagerDuty
  security → Email + Slack + SIEM
  warning  → Email + Slack
  info     → Slack only
```

### Testing Alerts

```bash
# Send test alert
curl -XPOST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {
      "alertname": "TestAlert",
      "severity": "warning"
    },
    "annotations": {
      "summary": "This is a test alert"
    }
  }]'
```

## Troubleshooting

### Common Issues

#### 1. Prometheus Not Scraping
```bash
# Check targets
curl http://localhost:9090/api/v1/targets

# Verify connectivity
docker exec agencydark_prometheus wget -O- http://backend:8000/api/v1/monitoring/metrics
```

#### 2. Grafana Can't Connect to Prometheus
```bash
# Test datasource
curl -X POST http://localhost:3000/api/datasources/1/test \
  -H "Authorization: Basic $(echo -n admin:password | base64)"
```

#### 3. No Alerts Firing
```bash
# Check alert rules
curl http://localhost:9090/api/v1/rules

# Verify Alertmanager
curl http://localhost:9093/api/v1/status
```

#### 4. High Memory Usage
```bash
# Check Prometheus storage
du -sh /var/lib/prometheus

# Reduce retention
docker exec agencydark_prometheus promtool tsdb clean \
  --storage.tsdb.path=/prometheus
```

### Debug Commands

```bash
# View logs
docker-compose -f docker-compose.monitoring.yml logs -f prometheus

# Check metrics
curl http://localhost:9090/api/v1/query?query=up

# Test alert routing
amtool --alertmanager.url=http://localhost:9093 check-config

# Validate Prometheus config
docker exec agencydark_prometheus promtool check config /etc/prometheus/prometheus.yml
```

## Best Practices

### 1. Metric Naming
- Use consistent prefixes: `agencydark_`
- Follow Prometheus conventions
- Include units in metric names

### 2. Label Usage
- Keep cardinality low
- Use static labels for grouping
- Avoid user IDs as labels

### 3. Dashboard Design
- One dashboard per concern
- Use variables for filtering
- Include documentation panels

### 4. Alert Design
- Alert on symptoms, not causes
- Include runbook links
- Set appropriate thresholds

### 5. Resource Management
- Monitor monitoring stack itself
- Set resource limits
- Regular cleanup of old data

### 6. Security
- Use HTTPS for external access
- Implement authentication
- Restrict network access
- Encrypt sensitive data

## Maintenance

### Daily Tasks
- Check alert inbox
- Review error dashboards
- Verify backup completion

### Weekly Tasks
- Review metrics growth
- Update dashboards
- Test alert notifications

### Monthly Tasks
- Clean old data
- Update configurations
- Review and tune alerts
- Capacity planning

## Integration

### Application Integration

Add to your application:
```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])
active_users = Gauge('active_users_count', 'Number of active users')

# Use in code
request_count.labels(method='GET', endpoint='/api/users', status=200).inc()
request_duration.labels(method='GET', endpoint='/api/users').observe(0.025)
active_users.set(150)
```

### Log Integration

Configure application logging:
```python
import logging
from pythonjsonlogger import jsonlogger

# Configure JSON logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# Log with structure
logger.info("user_action", extra={"user_id": "123", "action": "login", "ip": "10.0.0.1"})
```

### Trace Integration

Add OpenTelemetry:
```python
from opentelemetry import trace
from opentelemetry.exporter.jaeger import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure tracing
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Use in code
with tracer.start_as_current_span("process_request"):
    # Your code here
    pass
```

## Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Alertmanager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [AgencyDark Runbooks](https://docs.agencydark.com/runbooks)

---
*Last Updated: November 2023*
*Version: 1.0*