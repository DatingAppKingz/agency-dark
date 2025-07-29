# Incident Response Runbook

## Purpose

This runbook provides step-by-step procedures for responding to production incidents in the Agency Backend system.

## Incident Severity Levels

### SEV1 - Critical
- **Definition**: Complete service outage or data loss
- **Response Time**: 15 minutes
- **Examples**: API down, database corruption, security breach

### SEV2 - High
- **Definition**: Major functionality impaired
- **Response Time**: 30 minutes
- **Examples**: Authentication broken, significant performance degradation

### SEV3 - Medium
- **Definition**: Minor functionality impaired
- **Response Time**: 2 hours
- **Examples**: Non-critical features broken, minor performance issues

### SEV4 - Low
- **Definition**: Cosmetic issues
- **Response Time**: Next business day
- **Examples**: UI glitches, documentation errors

## Incident Response Process

### 1. Detection & Triage

```bash
# Check system status
kubectl get pods -n production
kubectl top nodes
kubectl top pods -n production

# Check application logs
kubectl logs -n production -l app=agency-backend --tail=100

# Check metrics
curl https://api.agency.com/health
curl https://api.agency.com/metrics
```

### 2. Initial Response

1. **Acknowledge incident** in PagerDuty/monitoring system
2. **Create incident channel** in Slack: `#incident-YYYY-MM-DD-description`
3. **Assign roles**:
   - Incident Commander (IC)
   - Technical Lead
   - Communications Lead
   - Scribe

### 3. Investigation

#### API Issues

```bash
# Check API pod status
kubectl describe pod -n production -l app=agency-backend

# View recent logs
kubectl logs -n production -l app=agency-backend --since=1h

# Check for recent deployments
kubectl rollout history deployment/agency-backend -n production

# Test API endpoints
curl -v https://api.agency.com/api/v1/health
curl -v https://api.agency.com/api/v1/status
```

#### Database Issues

```bash
# Check database connectivity
kubectl exec -n production deployment/agency-backend -- \
  psql $DATABASE_URL -c "SELECT 1"

# Check connection pool
kubectl exec -n production deployment/agency-backend -- \
  psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity"

# Check for locks
kubectl exec -n production deployment/agency-backend -- \
  psql $DATABASE_URL -c "SELECT * FROM pg_locks WHERE NOT granted"

# Check replication lag
kubectl exec -n production deployment/agency-backend -- \
  psql $DATABASE_URL -c "SELECT * FROM pg_stat_replication"
```

#### Performance Issues

```bash
# Check CPU and memory usage
kubectl top pods -n production
kubectl describe nodes

# Check database slow queries
kubectl exec -n production deployment/agency-backend -- \
  psql $DATABASE_URL -c "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10"

# Check Redis performance
kubectl exec -n production deployment/agency-redis -- redis-cli INFO stats
kubectl exec -n production deployment/agency-redis -- redis-cli SLOWLOG get 10
```

### 4. Mitigation

#### Quick Fixes

```bash
# Restart pods (last resort)
kubectl rollout restart deployment/agency-backend -n production

# Scale up pods
kubectl scale deployment/agency-backend -n production --replicas=10

# Clear cache
kubectl exec -n production deployment/agency-redis -- redis-cli FLUSHALL

# Enable maintenance mode
kubectl set env deployment/agency-backend -n production MAINTENANCE_MODE=true
```

#### Rollback Deployment

```bash
# View deployment history
kubectl rollout history deployment/agency-backend -n production

# Rollback to previous version
kubectl rollout undo deployment/agency-backend -n production

# Rollback to specific revision
kubectl rollout undo deployment/agency-backend -n production --to-revision=42

# Monitor rollback
kubectl rollout status deployment/agency-backend -n production
```

#### Emergency Database Procedures

```bash
# Kill long-running queries
kubectl exec -n production deployment/agency-backend -- \
  psql $DATABASE_URL -c "
    SELECT pg_terminate_backend(pid) 
    FROM pg_stat_activity 
    WHERE state = 'active' 
    AND query_start < now() - interval '5 minutes'
    AND query NOT LIKE '%pg_stat_activity%'
  "

# Vacuum and analyze
kubectl exec -n production deployment/agency-backend -- \
  psql $DATABASE_URL -c "VACUUM ANALYZE"

# Reset connections
kubectl exec -n production deployment/agency-backend -- \
  psql $DATABASE_URL -c "
    SELECT pg_terminate_backend(pid) 
    FROM pg_stat_activity 
    WHERE datname = 'agency_production' 
    AND pid <> pg_backend_pid()
  "
```

### 5. Communication

#### Internal Updates (Every 30 minutes)

```
**Incident Update - [TIME]**
- **Status**: Investigating / Mitigating / Resolved
- **Impact**: [Affected services and users]
- **Current Actions**: [What we're doing]
- **Next Update**: [Time]
```

#### External Updates (Status Page)

```
**[Service Name] - [Severity] Incident**

We are currently experiencing [issue description]. 
Our team is actively working on resolution.

**Impact**: [User-facing impact]
**Started**: [Time]
**Next Update**: [Time]
```

### 6. Resolution

1. **Verify fix**:
   ```bash
   # Run smoke tests
   ./scripts/smoke-tests.sh https://api.agency.com
   
   # Check metrics
   curl https://api.agency.com/health
   ```

2. **Monitor stability** for 30 minutes

3. **Update status page** to "Resolved"

4. **Close incident**:
   - Mark incident as resolved in monitoring system
   - Archive Slack channel
   - Schedule post-mortem

## Common Issues & Solutions

### High Memory Usage

```bash
# Identify memory consumers
kubectl top pods -n production --sort-by=memory

# Get memory profile
kubectl exec -n production deployment/agency-backend -- \
  curl -X POST http://localhost:8000/admin/memory/optimize

# Increase memory limits
kubectl set resources deployment/agency-backend -n production \
  --limits=memory=2Gi --requests=memory=1Gi
```

### Database Connection Exhaustion

```bash
# Check connection count
kubectl exec -n production deployment/agency-backend -- \
  psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity"

# Increase connection pool
kubectl set env deployment/agency-backend -n production \
  DB_POOL_SIZE=50 DB_POOL_MAX_OVERFLOW=10

# Kill idle connections
kubectl exec -n production deployment/agency-backend -- \
  psql $DATABASE_URL -c "
    SELECT pg_terminate_backend(pid) 
    FROM pg_stat_activity 
    WHERE state = 'idle' 
    AND state_change < now() - interval '10 minutes'
  "
```

### Redis Memory Full

```bash
# Check memory usage
kubectl exec -n production deployment/agency-redis -- \
  redis-cli INFO memory

# Set eviction policy
kubectl exec -n production deployment/agency-redis -- \
  redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Clear old keys
kubectl exec -n production deployment/agency-redis -- \
  redis-cli --scan --pattern "cache:*" | xargs redis-cli DEL
```

## Post-Incident

### Post-Mortem Template

1. **Incident Summary**
   - Duration
   - Impact
   - Root cause

2. **Timeline**
   - Detection
   - Response
   - Mitigation
   - Resolution

3. **What Went Well**

4. **What Went Wrong**

5. **Action Items**
   - Owner
   - Due date
   - Priority

### Follow-up Actions

- Update runbooks
- Improve monitoring
- Add automated remediation
- Update documentation
- Share learnings

## Emergency Contacts

- **On-Call Engineer**: PagerDuty
- **Engineering Manager**: [Phone]
- **VP Engineering**: [Phone]
- **Security Team**: security@agency.com
- **AWS Support**: [Case URL]

## Tools & Resources

- **Monitoring**: https://grafana.agency.com
- **Logs**: https://logs.agency.com
- **Status Page**: https://status.agency.com
- **Runbooks**: https://wiki.agency.com/runbooks
- **Architecture Diagrams**: https://wiki.agency.com/architecture