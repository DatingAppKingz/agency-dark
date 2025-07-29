# Agency Backend - Production Documentation

## Overview

This documentation provides comprehensive guidance for deploying, operating, and maintaining the Agency Backend system in production environments.

## Table of Contents

1. [Architecture Overview](./architecture.md)
2. [Deployment Guide](./deployment-guide.md)
3. [Operational Runbooks](./runbooks/)
4. [Monitoring & Alerts](./monitoring.md)
5. [Security Guidelines](./security.md)
6. [Performance Tuning](./performance.md)
7. [Disaster Recovery](./disaster-recovery.md)
8. [API Documentation](./api-docs.md)
9. [Troubleshooting Guide](./troubleshooting.md)
10. [SLA & Support](./sla.md)

## Quick Start

### Prerequisites

- Kubernetes 1.27+
- PostgreSQL 16+
- Redis 7+
- Docker 24+
- Helm 3.12+

### Deployment

```bash
# Clone repository
git clone https://github.com/agency/backend.git
cd backend

# Deploy with Helm
helm install agency-backend ./helm/agency-backend \
  --namespace production \
  --values ./helm/agency-backend/values-production.yaml

# Verify deployment
kubectl get pods -n production
kubectl get ingress -n production
```

### Health Checks

```bash
# Check application health
curl https://api.agency.com/health

# Check detailed metrics
curl https://api.agency.com/metrics
```

## System Requirements

### Minimum Production Requirements

- **CPU**: 4 cores
- **Memory**: 8GB RAM
- **Storage**: 100GB SSD
- **Network**: 100 Mbps

### Recommended Production Setup

- **CPU**: 8+ cores
- **Memory**: 16GB+ RAM
- **Storage**: 500GB+ SSD with backup
- **Network**: 1 Gbps
- **High Availability**: 3+ nodes

## Architecture

The Agency Backend follows a microservices architecture with the following components:

- **API Gateway**: FastAPI-based REST API
- **Database**: PostgreSQL with read replicas
- **Cache**: Redis with clustering
- **Message Queue**: Celery with Redis backend
- **Search**: Elasticsearch (optional)
- **Monitoring**: Prometheus + Grafana

## Security

- All communication encrypted with TLS 1.3
- API authentication via JWT tokens
- Database encryption at rest
- Secrets managed via HashiCorp Vault or AWS Secrets Manager
- Regular security scanning and updates

## Monitoring

Key metrics to monitor:

- API response times (p50, p95, p99)
- Error rates
- Database query performance
- Cache hit rates
- Resource utilization (CPU, memory, disk)
- Business metrics (users, campaigns, tasks)

## Support

- **Critical Issues**: Page on-call engineer
- **High Priority**: Create urgent ticket
- **Normal Priority**: Create standard ticket
- **Questions**: Check documentation or ask in Slack

## License

Copyright (c) 2025 Agency. All rights reserved.