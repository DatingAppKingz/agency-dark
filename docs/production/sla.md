# Service Level Agreement (SLA)

## Overview

This document defines the Service Level Agreement for the Agency Backend API service.

## Service Availability

### Production Environment

- **Target Uptime**: 99.9% (excluding scheduled maintenance)
- **Measurement Period**: Monthly
- **Scheduled Maintenance**: 2 hours per month, announced 72 hours in advance

### Availability Calculation

```
Availability % = (Total Minutes - Downtime Minutes) / Total Minutes × 100
```

Exclusions:
- Scheduled maintenance windows
- Force majeure events
- Customer-caused outages
- Third-party service failures

## Performance Targets

### API Response Times

| Endpoint Type | P50 | P95 | P99 |
|--------------|-----|-----|-----|
| Health Check | 10ms | 50ms | 100ms |
| GET Requests | 50ms | 200ms | 500ms |
| POST/PUT/PATCH | 100ms | 500ms | 1000ms |
| Complex Queries | 200ms | 1000ms | 2000ms |

### Throughput

- **Sustained Load**: 10,000 requests/minute
- **Peak Load**: 20,000 requests/minute
- **Concurrent Users**: 5,000

### Error Rates

- **5xx Errors**: < 0.1%
- **4xx Errors**: < 5% (excluding client errors)
- **Timeout Rate**: < 0.01%

## Data Guarantees

### Durability

- **Database**: 99.999999999% (11 9's) with multi-region replication
- **File Storage**: 99.999999999% (11 9's) with S3
- **Backup Retention**: 30 days

### Recovery Objectives

- **RTO (Recovery Time Objective)**: 4 hours
- **RPO (Recovery Point Objective)**: 1 hour

### Backup Schedule

- **Full Backup**: Daily at 02:00 UTC
- **Incremental**: Every hour
- **Transaction Logs**: Continuous (5-minute intervals)

## Security Commitments

### Compliance

- **Data Encryption**: AES-256 at rest, TLS 1.3 in transit
- **Access Control**: RBAC with MFA
- **Audit Logging**: 90-day retention
- **Vulnerability Scanning**: Weekly
- **Penetration Testing**: Quarterly

### Incident Response

- **Detection**: < 5 minutes
- **Acknowledgment**: < 15 minutes
- **Resolution**: Based on severity (see incident runbook)

## Support Levels

### Standard Support (Business Hours)

- **Hours**: Monday-Friday, 9 AM - 6 PM EST
- **Response Time**:
  - Critical: 1 hour
  - High: 4 hours
  - Medium: 1 business day
  - Low: 2 business days

### Premium Support (24/7)

- **Hours**: 24/7/365
- **Response Time**:
  - Critical: 15 minutes
  - High: 1 hour
  - Medium: 4 hours
  - Low: 1 business day

## Service Credits

### Availability Credits

| Monthly Uptime % | Service Credit |
|------------------|----------------|
| 99.0% - 99.9% | 0% |
| 95.0% - 99.0% | 10% |
| 90.0% - 95.0% | 25% |
| < 90.0% | 50% |

### Performance Credits

| Performance Violation | Service Credit |
|----------------------|----------------|
| P95 > 2x target for > 5% of requests | 5% |
| P99 > 3x target for > 1% of requests | 10% |
| Error rate > 2x target for > 1 hour | 10% |

### Credit Request Process

1. Submit request within 30 days of incident
2. Include:
   - Incident dates and times
   - Affected services
   - Impact description
   - Supporting data
3. Credits applied to next invoice

## Monitoring & Reporting

### Real-time Monitoring

- **Status Page**: https://status.agency.com
- **Metrics Dashboard**: https://metrics.agency.com
- **API Health**: https://api.agency.com/health

### Monthly Reports

Delivered by the 5th business day of each month:

- Uptime percentage
- Performance metrics (P50, P95, P99)
- Incident summary
- Capacity utilization
- Security scan results

### Quarterly Business Reviews

- Service performance analysis
- Capacity planning
- Feature roadmap updates
- Security posture review
- Cost optimization opportunities

## Maintenance Windows

### Scheduled Maintenance

- **Frequency**: Monthly
- **Duration**: Up to 2 hours
- **Time**: Sunday 2:00 AM - 4:00 AM UTC
- **Notification**: 72 hours in advance via:
  - Email to technical contacts
  - Status page update
  - In-app notification

### Emergency Maintenance

- **Notification**: As soon as possible
- **Duration**: Minimized
- **Approval**: Requires VP approval
- **Follow-up**: Post-mortem within 48 hours

## Responsibilities

### Our Responsibilities

- Maintain service availability
- Monitor performance
- Provide security updates
- Backup data
- Respond to incidents
- Provide support

### Customer Responsibilities

- Implement proper error handling
- Follow API rate limits
- Maintain secure credentials
- Update client libraries
- Report issues promptly
- Provide accurate contact information

## Definitions

- **Downtime**: Service returning 5xx errors or timeout for > 5 minutes
- **Scheduled Maintenance**: Pre-announced service work
- **Business Day**: Monday-Friday, excluding holidays
- **Month**: Calendar month
- **Incident**: Unplanned service degradation

## Exclusions

This SLA does not apply to:

- Beta features
- Free tier usage
- Development/staging environments
- Customer-caused issues
- Force majeure events
- Deprecated APIs (after notice period)

## Changes to SLA

- **Notice Period**: 30 days for material changes
- **Communication**: Email and status page
- **Acceptance**: Continued use constitutes acceptance

## Contact Information

- **Support Portal**: https://support.agency.com
- **Email**: support@agency.com
- **Emergency**: +1-555-911-2345
- **Status Page**: https://status.agency.com

---

*Last Updated: January 2025*
*Version: 1.0*