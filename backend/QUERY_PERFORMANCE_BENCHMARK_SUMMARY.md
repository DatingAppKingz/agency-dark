# Query Performance Benchmark Summary

## Overview

This document summarizes the query performance improvements implemented in the AgencyDark database through migrations 004 and 022.

## Performance Optimizations Implemented

### 1. Migration 004 - Database Optimization

#### Core Domain Indexes
- **Users Table**
  - `idx_users_agency_role`: Composite index on (agency_id, role) for multi-tenant queries
  - `idx_users_active_verified`: Index on (is_active, is_verified) for filtering active users
  - `idx_users_last_login`: Index on last_login for recent activity queries
  - `idx_active_users`: Partial index for active & verified users only

- **Model Profiles Table**
  - `idx_model_profiles_agency_active`: Composite index on (agency_id, is_active)
  - `idx_model_profiles_last_sync`: Index on last_sync_at for sync scheduling
  - `idx_model_profiles_earnings`: Index on total_earnings for top earner queries
  - `idx_active_model_profiles`: Partial index for active models only

- **Fans Table**
  - `idx_fans_active_subscribers`: Composite index on (model_id, is_subscriber, is_paying)
  - `idx_fans_last_active`: Index on (model_id, last_active_at) for engagement tracking
  - `idx_fans_total_spent`: Index on (model_id, total_spent) for high-value fan queries
  - `idx_paying_fans`: Partial index for paying fans only

- **Other Tables**
  - `idx_sessions_expires_active`: Index on (expires_at, is_active) for session cleanup
  - `idx_notifications_user_read`: Index on (user_id, read, created_at) for unread queries
  - `idx_audit_logs_resource`: Index on (resource_type, resource_id, created_at)

#### Query Optimization Settings
- Increased statistics target for high-cardinality columns
- Table statistics auto-update with ANALYZE

### 2. Migration 022 - Multi-Tenant Indexes

Additional indexes for better multi-tenant performance:
- `idx_users_agency_active`: Partial index for active users by agency
- `idx_notifications_agency_unread`: Partial index for unread notifications by agency
- `idx_audit_logs_agency_date`: Index on (agency_id, created_at) for time-based queries

## Expected Performance Improvements

### 1. Multi-Tenant Queries
**Before**: Full table scans filtered by agency_id
**After**: Direct index lookups
**Expected Improvement**: 10-100x faster for agency-scoped queries

### 2. User Queries
- Active users by agency: Uses `idx_users_agency_active`
- Users by role: Uses `idx_users_agency_role`
- Recent logins: Uses `idx_users_last_login`

### 3. Model Performance Queries
- Active models: Uses `idx_model_profiles_agency_active`
- Top earners: Uses `idx_model_profiles_earnings`
- Models needing sync: Uses `idx_model_profiles_last_sync`

### 4. Fan Analytics
- Paying fans: Uses `idx_fans_active_subscribers` and partial index
- High-value fans: Uses `idx_fans_total_spent`
- Recently active fans: Uses `idx_fans_last_active`

### 5. Notification Queries
- Unread notifications: Uses `idx_notifications_user_read`
- Agency unread count: Uses `idx_notifications_agency_unread`

## Query Examples and Expected Performance

### 1. Get Active Users by Agency and Role
```sql
SELECT id, username, email, role
FROM users
WHERE agency_id = $1 AND role = 'chatter' AND is_active = true
ORDER BY created_at DESC
LIMIT 20;
```
**Indexes Used**: `idx_users_agency_role`, `idx_active_users`
**Expected Time**: <5ms for 1000 users

### 2. Top Earning Models
```sql
SELECT id, onlyfans_username, total_earnings
FROM model_profiles
WHERE agency_id = $1 AND is_active = true
ORDER BY total_earnings DESC
LIMIT 10;
```
**Indexes Used**: `idx_model_profiles_agency_active`, `idx_model_profiles_earnings`
**Expected Time**: <10ms for 500 models

### 3. High-Value Paying Fans
```sql
SELECT id, username, total_spent
FROM fans
WHERE model_id = $1 AND is_paying = true AND total_spent > 100
ORDER BY total_spent DESC;
```
**Indexes Used**: `idx_fans_total_spent`, `idx_paying_fans`
**Expected Time**: <20ms for 10,000 fans per model

### 4. Recent Audit Logs
```sql
SELECT id, action, resource_type, created_at
FROM audit_logs
WHERE agency_id = $1 AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 50;
```
**Indexes Used**: `idx_audit_logs_agency_date`
**Expected Time**: <10ms for 100,000 audit logs

## Best Practices for Query Performance

1. **Always include agency_id in WHERE clauses** for multi-tenant queries
2. **Use partial indexes** when querying subsets (e.g., active users only)
3. **Order by indexed columns** when possible
4. **Limit result sets** to avoid unnecessary data transfer
5. **Use EXPLAIN ANALYZE** to verify index usage

## Monitoring Performance

To verify index usage:
```sql
EXPLAIN (ANALYZE, BUFFERS) 
SELECT ... FROM ... WHERE ...;
```

To check index statistics:
```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

## Conclusion

The implemented indexes provide comprehensive coverage for:
- Multi-tenant data isolation
- Common query patterns
- Performance-critical operations
- Analytics and reporting

With proper index usage, query performance should improve by 10-100x for most operations, especially as data volume grows.