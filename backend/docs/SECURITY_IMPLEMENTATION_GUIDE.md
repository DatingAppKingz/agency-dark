# Security Implementation Guide

## Overview

This guide provides step-by-step instructions for implementing and maintaining the security features of the Agency Dark platform. It covers configuration, deployment, monitoring, and troubleshooting.

## Table of Contents

1. [Initial Setup](#initial-setup)
2. [Configuration](#configuration)
3. [Permission System Setup](#permission-system-setup)
4. [Rate Limiting Configuration](#rate-limiting-configuration)
5. [Audit System Setup](#audit-system-setup)
6. [API Security](#api-security)
7. [Database Security](#database-security)
8. [Monitoring Setup](#monitoring-setup)
9. [Testing Security](#testing-security)
10. [Maintenance](#maintenance)

## Initial Setup

### Prerequisites

```bash
# Required software
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Docker & Docker Compose
- OpenSSL 1.1.1+
```

### Environment Setup

1. **Create Security Environment File**

```bash
# Create .env.security file
cat > .env.security << EOF
# Security Configuration
JWT_SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=RS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Encryption Keys
ENCRYPTION_KEY=$(openssl rand -hex 32)
API_KEY_SALT=$(openssl rand -hex 16)

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT_LIMIT=100
RATE_LIMIT_WINDOW_SECONDS=60

# Audit Configuration
AUDIT_LOG_LEVEL=INFO
AUDIT_RETENTION_DAYS=2555  # 7 years for SOX

# Security Headers
SECURITY_HEADERS_ENABLED=true
CORS_ALLOWED_ORIGINS=https://app.agencydark.com
HSTS_MAX_AGE=31536000

# MFA Configuration
MFA_ENABLED=true
MFA_ISSUER=AgencyDark
TOTP_WINDOW=1

# Geographic Restrictions
GEO_BLOCKING_ENABLED=true
BLOCKED_COUNTRIES=KP,IR,SY
EOF
```

2. **Generate RSA Keys for JWT**

```bash
# Generate private key
openssl genpkey -algorithm RSA -out jwt_private.pem -pkeyopt rsa_keygen_bits:2048

# Generate public key
openssl rsa -pubout -in jwt_private.pem -out jwt_public.pem

# Set permissions
chmod 600 jwt_private.pem
chmod 644 jwt_public.pem
```

3. **Initialize Database**

```bash
# Run migrations
alembic upgrade head

# Create initial security tables
python scripts/init_security.py
```

## Configuration

### Security Configuration File

Create `config/security.yaml`:

```yaml
security:
  # Authentication settings
  authentication:
    jwt:
      algorithm: RS256
      access_token_expire: 900  # 15 minutes
      refresh_token_expire: 604800  # 7 days
      issuer: "agencydark.com"
      audience: "agencydark-api"
    
    password:
      min_length: 12
      require_uppercase: true
      require_lowercase: true
      require_numbers: true
      require_special: true
      history_count: 5
      max_age_days: 90
    
    mfa:
      enabled: true
      required_for_roles: ["ADMIN", "MANAGER"]
      methods: ["totp", "sms", "email"]
      backup_codes_count: 10
  
  # Authorization settings
  authorization:
    cache_ttl: 300
    evaluation_strategy: "first_match"
    default_deny: true
    
  # Rate limiting
  rate_limiting:
    algorithms:
      default: "token_bucket"
      api: "sliding_window"
      exports: "fixed_window"
    
    limits:
      global:
        requests_per_minute: 10000
        burst_size: 500
      
      per_user:
        requests_per_minute: 1000
        burst_size: 100
      
      per_ip:
        requests_per_minute: 300
        burst_size: 50
    
    cost_factors:
      compute_time_ms: 0.01
      database_reads: 0.5
      database_writes: 1.0
      cache_misses: 0.2
      external_api_calls: 2.0
      ml_inference: 5.0
  
  # Audit settings
  audit:
    enabled: true
    batch_size: 100
    flush_interval: 5
    
    storage:
      primary: "postgresql"
      backup: "s3"
      archive: "glacier"
    
    retention:
      hot_days: 90
      warm_days: 365
      cold_years: 7
    
    compliance:
      gdpr_enabled: true
      sox_enabled: true
      hipaa_enabled: false
  
  # Security headers
  headers:
    strict_transport_security: "max-age=31536000; includeSubDomains"
    content_security_policy: "default-src 'self'; script-src 'self' 'unsafe-inline';"
    x_frame_options: "DENY"
    x_content_type_options: "nosniff"
    x_xss_protection: "1; mode=block"
    referrer_policy: "strict-origin-when-cross-origin"
    permissions_policy: "geolocation=(), microphone=(), camera=()"
```

### Application Configuration

Update `main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from core.security.middleware import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    AuditLoggingMiddleware,
    AuthenticationMiddleware
)
from core.security.cache_strategies import init_cache_system

app = FastAPI(title="Agency Dark API", docs_url=None, redoc_url=None)

# Security middleware stack (order matters!)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.agencydark.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["app.agencydark.com", "*.agencydark.com"]
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(AuditLoggingMiddleware)

@app.on_event("startup")
async def startup_event():
    # Initialize security systems
    await init_cache_system()
    await init_rate_limiters()
    await init_audit_system()
```

## Permission System Setup

### 1. Create Default Roles

```python
# scripts/create_default_roles.py
import asyncio
from core.database import get_db
from models.role import Role, UserRole

async def create_default_roles():
    async with get_db() as db:
        roles = [
            {
                "name": "admin",
                "level": UserRole.ADMIN,
                "description": "Full system access"
            },
            {
                "name": "manager", 
                "level": UserRole.MANAGER,
                "description": "Agency management access"
            },
            {
                "name": "chatter",
                "level": UserRole.CHATTER,
                "description": "Content creator access"
            },
            {
                "name": "model",
                "level": UserRole.MODEL,
                "description": "Model/performer access"
            },
            {
                "name": "fan",
                "level": UserRole.FAN,
                "description": "Subscriber access"
            },
            {
                "name": "user",
                "level": UserRole.USER,
                "description": "Basic user access"
            }
        ]
        
        for role_data in roles:
            role = Role(**role_data)
            db.add(role)
        
        await db.commit()
        print("Default roles created successfully")

if __name__ == "__main__":
    asyncio.run(create_default_roles())
```

### 2. Create Default Permissions

```python
# scripts/create_default_permissions.py
import asyncio
from core.database import get_db
from models.feature_permission import FeaturePermission, FeatureType
from models.role import UserRole

PERMISSION_TEMPLATES = {
    UserRole.ADMIN: {
        FeatureType.REPORTS: {
            "allowed_actions": ["*"],
            "can_access_financial_data": True,
            "can_access_pii_data": True,
            "report_types": ["*"]
        },
        FeatureType.EXPORTS: {
            "allowed_actions": ["*"],
            "allowed_export_formats": ["*"],
            "max_export_rows": None,  # Unlimited
            "can_export_pii_data": True
        },
        FeatureType.ANALYTICS: {
            "allowed_actions": ["*"],
            "analytics_scope": "GLOBAL",
            "can_view_revenue_data": True,
            "can_view_cost_data": True
        }
    },
    UserRole.MANAGER: {
        FeatureType.REPORTS: {
            "allowed_actions": ["view_report", "export_report"],
            "can_access_financial_data": True,
            "can_access_pii_data": False,
            "report_types": ["performance", "analytics", "summary"]
        },
        # ... more permissions
    }
}

async def create_default_permissions():
    async with get_db() as db:
        for role, features in PERMISSION_TEMPLATES.items():
            for feature_type, config in features.items():
                permission = FeaturePermission(
                    name=f"{role.name} - {feature_type.value}",
                    feature_type=feature_type,
                    role_id=role.id,
                    **config
                )
                db.add(permission)
        
        await db.commit()
        print("Default permissions created successfully")
```

### 3. Test Permission System

```python
# scripts/test_permissions.py
from core.security.feature_permissions.service import feature_permission_service

async def test_permission_check():
    # Create test user
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        role=UserRole.MANAGER
    )
    
    # Test permission check
    allowed, reason = await feature_permission_service.check_feature_permission(
        db=db,
        user=user,
        feature_type=FeatureType.REPORTS,
        action="view_report"
    )
    
    print(f"Permission check: allowed={allowed}, reason={reason}")
```

## Rate Limiting Configuration

### 1. Configure Rate Limits

```python
# scripts/configure_rate_limits.py
from models.rate_limit import RateLimitConfig, RateLimitType, RateLimitAlgorithm

rate_limit_configs = [
    # Global rate limit
    {
        "name": "Global API Limit",
        "limit_type": RateLimitType.GLOBAL,
        "requests_per_minute": 10000,
        "algorithm": RateLimitAlgorithm.TOKEN_BUCKET,
        "burst_size": 1000,
        "priority": 1
    },
    # Per-user limits
    {
        "name": "User API Limit",
        "limit_type": RateLimitType.USER,
        "requests_per_minute": 1000,
        "algorithm": RateLimitAlgorithm.SLIDING_WINDOW,
        "priority": 10
    },
    # Endpoint-specific limits
    {
        "name": "Export Endpoint Limit",
        "limit_type": RateLimitType.ENDPOINT,
        "endpoint_pattern": "/api/v1/export/*",
        "requests_per_minute": 10,
        "algorithm": RateLimitAlgorithm.FIXED_WINDOW,
        "priority": 20
    },
    # Cost-based limit
    {
        "name": "ML Endpoint Cost Limit",
        "limit_type": RateLimitType.ENDPOINT,
        "endpoint_pattern": "/api/v1/ml/*",
        "cost_per_minute": 1000.0,
        "algorithm": RateLimitAlgorithm.TOKEN_BUCKET,
        "priority": 15
    }
]

async def create_rate_limits():
    async with get_db() as db:
        for config in rate_limit_configs:
            rate_limit = RateLimitConfig(**config)
            db.add(rate_limit)
        await db.commit()
```

### 2. Configure Endpoint Costs

```python
# config/endpoint_costs.py
ENDPOINT_COSTS = {
    "/api/v1/reports/generate": {
        "base_cost": 5.0,
        "compute_time_factor": 0.01,
        "database_read_cost": 1.0,
        "result_size_factor": 0.001  # Per KB
    },
    "/api/v1/export/users": {
        "base_cost": 10.0,
        "database_read_cost": 2.0,
        "result_size_factor": 0.01  # Per MB
    },
    "/api/v1/ml/predict": {
        "base_cost": 20.0,
        "ml_inference_cost": 50.0,
        "compute_time_factor": 0.1
    }
}
```

### 3. Test Rate Limiting

```bash
# Test rate limiting with curl
for i in {1..20}; do
    curl -X GET "https://api.agencydark.com/api/v1/reports" \
         -H "Authorization: Bearer $TOKEN" \
         -w "Status: %{http_code}, Time: %{time_total}s\n"
    sleep 0.1
done
```

## Audit System Setup

### 1. Initialize Audit Tables

```sql
-- Additional audit indexes for performance
CREATE INDEX idx_audit_log_user_action_time 
ON audit_logs(user_id, action, timestamp);

CREATE INDEX idx_audit_log_resource 
ON audit_logs(resource_type, resource_id);

CREATE INDEX idx_audit_log_risk 
ON audit_logs(risk_score) 
WHERE risk_score > 50;

-- Partitioning for large audit tables
CREATE TABLE audit_logs_2024_q1 PARTITION OF audit_logs
FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
```

### 2. Configure Audit Streaming

```python
# config/audit_streaming.py
from core.audit.streaming import AuditStreamer

audit_streamer = AuditStreamer(
    kafka_brokers=["kafka1:9092", "kafka2:9092"],
    topic="audit-logs",
    batch_size=100,
    compression="gzip"
)

# Configure SIEM integration
siem_config = {
    "splunk": {
        "endpoint": "https://splunk.company.com:8088",
        "token": os.environ["SPLUNK_HEC_TOKEN"],
        "index": "security"
    },
    "elasticsearch": {
        "hosts": ["https://es1:9200", "https://es2:9200"],
        "index": "audit-logs-%Y.%m.%d",
        "api_key": os.environ["ES_API_KEY"]
    }
}
```

### 3. Set Up Compliance Reports

```python
# scripts/generate_compliance_reports.py
from core.audit.compliance import ComplianceReporter

async def generate_monthly_reports():
    reporter = ComplianceReporter()
    
    # GDPR report
    gdpr_report = await reporter.generate_gdpr_report(
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31)
    )
    
    # SOX report
    sox_report = await reporter.generate_sox_report(
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31)
    )
    
    # Save reports
    await reporter.save_report(gdpr_report, "reports/gdpr_2024_01.pdf")
    await reporter.save_report(sox_report, "reports/sox_2024_01.pdf")
```

## API Security

### 1. API Key Generation

```python
# scripts/generate_api_keys.py
from core.security.api_key_manager import api_key_manager

async def create_api_key_for_service():
    api_key, raw_key = await api_key_manager.create_api_key(
        db=db,
        name="Analytics Service API Key",
        scopes=["read:analytics", "read:reports"],
        expires_in_days=365,
        ip_whitelist=["10.0.0.0/8"],
        rate_limit_per_minute=1000
    )
    
    print(f"API Key created: {raw_key}")
    print(f"Key ID: {api_key.id}")
    print("Store this key securely - it cannot be retrieved again!")
```

### 2. Configure API Gateway

```nginx
# nginx/api_security.conf
server {
    listen 443 ssl http2;
    server_name api.agencydark.com;
    
    # SSL configuration
    ssl_certificate /etc/nginx/ssl/api.crt;
    ssl_certificate_key /etc/nginx/ssl/api.key;
    ssl_protocols TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self'" always;
    
    # Rate limiting zones
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;
    limit_req_zone $http_x_api_key zone=key_limit:10m rate=1000r/s;
    
    location /api/ {
        # Apply rate limits
        limit_req zone=api_limit burst=20 nodelay;
        limit_req zone=key_limit burst=100 nodelay;
        
        # Request size limits
        client_max_body_size 10M;
        client_body_buffer_size 128k;
        
        # Proxy to backend
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Security headers for API
        proxy_hide_header X-Powered-By;
        proxy_hide_header Server;
    }
}
```

## Database Security

### 1. Configure Database Encryption

```sql
-- Enable encryption at rest
ALTER DATABASE agencydark SET encryption_key_id = 'aws/rds';

-- Create encrypted tablespace
CREATE TABLESPACE encrypted_space
LOCATION '/var/lib/postgresql/encrypted'
WITH (encryption_key_id = 'vault/postgresql/key1');

-- Move sensitive tables
ALTER TABLE users SET TABLESPACE encrypted_space;
ALTER TABLE api_keys SET TABLESPACE encrypted_space;
ALTER TABLE audit_logs SET TABLESPACE encrypted_space;
```

### 2. Set Up Row-Level Security

```sql
-- Enable RLS on sensitive tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_permissions ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY agency_isolation ON users
    FOR ALL
    TO application_role
    USING (agency_id = current_setting('app.current_agency_id')::uuid);

CREATE POLICY permission_isolation ON feature_permissions
    FOR SELECT
    TO application_role
    USING (
        user_id = current_setting('app.current_user_id')::uuid
        OR role_id IN (
            SELECT role_id FROM user_roles 
            WHERE user_id = current_setting('app.current_user_id')::uuid
        )
    );
```

### 3. Database Activity Monitoring

```python
# config/database_monitoring.py
DATABASE_AUDIT_CONFIG = {
    "log_connections": True,
    "log_disconnections": True,
    "log_statement": "all",
    "log_min_duration_statement": 100,  # Log queries over 100ms
    
    "pgaudit.log": "ALL",
    "pgaudit.log_catalog": False,
    "pgaudit.log_parameter": True,
    "pgaudit.log_relation": True,
    "pgaudit.log_statement_once": True
}
```

## Monitoring Setup

### 1. Security Metrics

```python
# monitoring/security_metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Authentication metrics
auth_attempts = Counter('auth_attempts_total', 'Total authentication attempts', ['result'])
auth_duration = Histogram('auth_duration_seconds', 'Authentication duration')
active_sessions = Gauge('active_sessions', 'Number of active sessions')

# Authorization metrics
permission_checks = Counter('permission_checks_total', 'Total permission checks', ['result'])
permission_cache_hits = Counter('permission_cache_hits_total', 'Permission cache hits')

# Security events
security_events = Counter('security_events_total', 'Security events', ['type', 'severity'])
blocked_requests = Counter('blocked_requests_total', 'Blocked requests', ['reason'])
```

### 2. Alerting Rules

```yaml
# prometheus/security_alerts.yml
groups:
  - name: security
    rules:
      - alert: HighFailedLoginRate
        expr: rate(auth_attempts_total{result="failed"}[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High failed login rate detected"
          description: "Failed login rate is {{ $value }} per second"
      
      - alert: SuspiciousAPIActivity
        expr: rate(security_events_total{type="suspicious_activity"}[10m]) > 5
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Suspicious API activity detected"
          description: "{{ $value }} suspicious events in last 10 minutes"
      
      - alert: RateLimitBypass
        expr: rate(blocked_requests_total{reason="rate_limit"}[5m]) > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Possible rate limit bypass attempt"
```

### 3. Security Dashboard

```python
# monitoring/security_dashboard.py
GRAFANA_DASHBOARD = {
    "title": "Security Monitoring",
    "panels": [
        {
            "title": "Authentication Overview",
            "targets": [
                "rate(auth_attempts_total[5m])",
                "auth_duration_seconds",
                "active_sessions"
            ]
        },
        {
            "title": "Permission System",
            "targets": [
                "rate(permission_checks_total[5m])",
                "permission_cache_hits / permission_checks_total"
            ]
        },
        {
            "title": "Security Events",
            "targets": [
                "rate(security_events_total[5m]) by (type)",
                "topk(10, security_events_total)"
            ]
        },
        {
            "title": "Rate Limiting",
            "targets": [
                "rate(blocked_requests_total{reason='rate_limit'}[5m])",
                "rate_limit_remaining by (endpoint)"
            ]
        }
    ]
}
```

## Testing Security

### 1. Security Test Suite

```python
# tests/security/test_security_suite.py
import pytest
from tests.security.fixtures import security_test_client

class TestSecuritySuite:
    @pytest.mark.security
    async def test_authentication_flow(self, security_test_client):
        # Test login
        response = await security_test_client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "SecurePassword123!"
        })
        assert response.status_code == 200
        
        # Test token refresh
        refresh_token = response.json()["refresh_token"]
        response = await security_test_client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert response.status_code == 200
    
    @pytest.mark.security
    async def test_sql_injection_prevention(self, security_test_client):
        # Test various SQL injection attempts
        payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --"
        ]
        
        for payload in payloads:
            response = await security_test_client.get(
                f"/api/v1/users?search={payload}"
            )
            # Should return 400 or sanitized results, never 500
            assert response.status_code in [200, 400]
```

### 2. Penetration Testing

```bash
# Run automated security tests
python -m pytest tests/security/penetration/ -v

# Run OWASP ZAP scan
docker run -t owasp/zap2docker-stable zap-baseline.py \
    -t https://api.agencydark.com \
    -r security_report.html

# Run SQLMap for SQL injection testing
sqlmap -u "https://api.agencydark.com/api/v1/users?id=1" \
    --batch --random-agent --level=5 --risk=3
```

### 3. Load Testing with Security

```python
# tests/security/load_test_security.py
from locust import HttpUser, task, between

class SecurityLoadTest(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Authenticate once
        response = self.client.post("/auth/login", json={
            "email": "loadtest@example.com",
            "password": "LoadTest123!"
        })
        self.token = response.json()["access_token"]
    
    @task(3)
    def test_authenticated_request(self):
        self.client.get("/api/v1/reports", 
            headers={"Authorization": f"Bearer {self.token}"})
    
    @task(1)
    def test_rate_limiting(self):
        # Intentionally trigger rate limits
        for _ in range(20):
            self.client.get("/api/v1/expensive-operation",
                headers={"Authorization": f"Bearer {self.token}"})
```

## Maintenance

### 1. Security Updates

```bash
# Check for security updates
pip list --outdated | grep -E "(security|crypto|jwt|auth)"

# Update security dependencies
pip install --upgrade \
    cryptography \
    pyjwt \
    python-jose \
    passlib \
    python-multipart

# Scan for vulnerabilities
safety check
bandit -r app/
```

### 2. Certificate Rotation

```python
# scripts/rotate_certificates.py
import subprocess
from datetime import datetime, timedelta

def check_certificate_expiry():
    """Check SSL certificate expiry dates."""
    certs = [
        "/etc/ssl/api.crt",
        "/etc/ssl/app.crt"
    ]
    
    for cert_path in certs:
        result = subprocess.run([
            "openssl", "x509", "-enddate", "-noout", "-in", cert_path
        ], capture_output=True, text=True)
        
        expiry_str = result.stdout.strip().split("=")[1]
        expiry_date = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
        
        days_until_expiry = (expiry_date - datetime.now()).days
        
        if days_until_expiry < 30:
            print(f"WARNING: {cert_path} expires in {days_until_expiry} days")
            # Trigger renewal process
```

### 3. Security Audit Checklist

```markdown
## Monthly Security Audit Checklist

### Access Control
- [ ] Review user permissions
- [ ] Check for inactive accounts
- [ ] Verify MFA enrollment
- [ ] Audit API key usage

### System Security
- [ ] Review security patches
- [ ] Check firewall rules
- [ ] Verify backup integrity
- [ ] Test restore procedures

### Compliance
- [ ] Generate compliance reports
- [ ] Review audit logs
- [ ] Check data retention
- [ ] Verify encryption status

### Monitoring
- [ ] Review security alerts
- [ ] Check anomaly detection
- [ ] Analyze attack patterns
- [ ] Update threat intelligence
```

## Troubleshooting

### Common Security Issues

1. **"Permission Denied" Errors**
   ```python
   # Check user permissions
   from core.security.debug import debug_permissions
   
   await debug_permissions(user_id, feature_type, action)
   ```

2. **Rate Limit Issues**
   ```bash
   # Check rate limit status
   redis-cli GET "rate_limit:user:123:*"
   
   # Reset rate limits
   redis-cli --scan --pattern "rate_limit:*" | xargs redis-cli DEL
   ```

3. **Authentication Failures**
   ```python
   # Enable debug logging
   import logging
   logging.getLogger("core.security.auth").setLevel(logging.DEBUG)
   ```

4. **Audit Log Issues**
   ```sql
   -- Check audit log size
   SELECT 
       schemaname,
       tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables
   WHERE tablename LIKE 'audit_logs%'
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
   ```

## Security Contacts

- **Security Team**: security@agencydark.com
- **On-Call**: +1-555-SEC-URITY
- **Bug Bounty**: https://agencydark.com/security/bounty

## Additional Resources

- [OWASP Security Guidelines](https://owasp.org)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CIS Security Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [Security Training Materials](internal-link)