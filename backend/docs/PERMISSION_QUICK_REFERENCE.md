# Permission System Quick Reference

## Quick Start

### Check a Permission

```python
from core.security.feature_permissions.service import feature_permission_service

# Basic permission check
allowed, reason = await feature_permission_service.check_feature_permission(
    db=db_session,
    user=current_user,
    feature_type=FeatureType.REPORTS,
    action="view_report"
)

if not allowed:
    raise PermissionDeniedError(reason)
```

### Check with Context

```python
# Permission check with context
context = {
    "report_type": "financial",
    "contains_pii": True,
    "date_range": "2024-Q1"
}

allowed, reason = await feature_permission_service.check_feature_permission(
    db=db_session,
    user=current_user,
    feature_type=FeatureType.REPORTS,
    action="view_report",
    request_context=context
)
```

## Common Permission Patterns

### 1. Protect an Endpoint

```python
from fastapi import Depends
from core.security.dependencies import require_permission

@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    user: User = Depends(get_current_user),
    _: None = Depends(require_permission(FeatureType.REPORTS, "view_report"))
):
    # User has permission, proceed with logic
    return fetch_report(report_id)
```

### 2. Check Multiple Permissions

```python
# Check if user has ANY of these permissions
permissions_to_check = [
    (FeatureType.REPORTS, "view_report"),
    (FeatureType.ANALYTICS, "view_analytics")
]

for feature_type, action in permissions_to_check:
    allowed, _ = await feature_permission_service.check_feature_permission(
        db=db_session,
        user=current_user,
        feature_type=feature_type,
        action=action
    )
    if allowed:
        break
else:
    raise PermissionDeniedError("No valid permissions")
```

### 3. Export with Quota Check

```python
from core.security.feature_permissions.export_permissions import export_permission_service

# Check export permission with quota
allowed, reason, permission = await export_permission_service.check_export_permission(
    db=db_session,
    user=current_user,
    export_format=ExportFormat.CSV,
    estimated_rows=10000
)

if not allowed:
    if "quota" in reason.lower():
        return {"error": "Export quota exceeded", "retry_after": "1 hour"}
    else:
        return {"error": reason}

# Proceed with export
```

### 4. Analytics Scope Check

```python
from core.security.feature_permissions.analytics_permissions import analytics_permission_service

# Check analytics access with scope
allowed, reason, permission = await analytics_permission_service.check_analytics_access(
    db=db_session,
    user=current_user,
    analytics_type="revenue_report",
    scope=AnalyticsScope.TEAM,
    metrics=["revenue", "profit_margin"]
)

if not allowed:
    # Check if it's just a scope issue
    if "scope" in reason:
        # Try with a lower scope
        allowed, reason, permission = await analytics_permission_service.check_analytics_access(
            db=db_session,
            user=current_user,
            analytics_type="revenue_report",
            scope=AnalyticsScope.OWN,
            metrics=["revenue"]
        )
```

### 5. Time-Restricted Access

```python
# Create permission with time restrictions
permission = FeaturePermission(
    name="Business Hours Only",
    feature_type=FeatureType.REPORTS,
    user_id=user.id,
    access_start_time="09:00",
    access_end_time="17:00",
    access_timezone="America/New_York",
    access_days_of_week=[1, 2, 3, 4, 5]  # Mon-Fri
)

# The service automatically checks time restrictions
allowed, reason = await feature_permission_service.check_feature_permission(
    db=db_session,
    user=current_user,
    feature_type=FeatureType.REPORTS,
    action="view_report"
)
# May return: (False, "Access denied outside allowed hours")
```

## Rate Limiting

### Basic Rate Limit Check

```python
from core.rate_limit.service import rate_limiter

allowed, info = await rate_limiter.check_rate_limit(
    db=db_session,
    identifier=str(user.id),
    identifier_type=RateLimitType.USER,
    endpoint=request.url.path,
    user=user,
    ip_address=request.client.host
)

if not allowed:
    raise RateLimitExceededError(
        f"Rate limit exceeded. Retry after {info.get('retry_after', 60)} seconds"
    )
```

### Cost-Based Rate Limiting

```python
# For expensive operations
request_metadata = {
    "compute_time_ms": 250,
    "database_reads": 10,
    "database_writes": 2,
    "ml_inference_calls": 1
}

allowed, info = await rate_limiter.check_rate_limit(
    db=db_session,
    identifier=str(user.id),
    identifier_type=RateLimitType.USER,
    endpoint="/api/v1/ml/analyze",
    user=user,
    request_metadata=request_metadata
)

# info contains remaining cost budget
print(f"Remaining cost budget: {info.get('remaining_cost', 0)}")
```

## Audit Logging

### Log Security Events

```python
from core.audit.service import audit_service

# Log successful access
await audit_service.log(
    db=db_session,
    action=AuditAction.REPORT_ACCESSED,
    user=current_user,
    resource_id=report_id,
    resource_type="report",
    ip_address=request.client.host,
    user_agent=request.headers.get("user-agent"),
    details={
        "report_type": "financial",
        "rows_returned": 1500,
        "export_format": "pdf"
    }
)

# Log permission denial
await audit_service.log(
    db=db_session,
    action=AuditAction.PERMISSION_DENIED,
    user=current_user,
    details={
        "feature": "exports",
        "reason": "Exceeded daily quota",
        "attempted_rows": 100000
    },
    severity=AuditSeverity.WARNING
)
```

### Log High-Risk Operations

```python
# Log with risk score
await audit_service.log(
    db=db_session,
    action=AuditAction.BULK_DATA_EXPORT,
    user=current_user,
    resource_id=export_id,
    details={
        "total_records": 50000,
        "contains_pii": True,
        "destination": "external_system"
    },
    severity=AuditSeverity.WARNING,
    risk_score=75  # High risk due to PII + volume
)
```

## API Key Management

### Create API Key

```python
from core.security.api_key_manager import api_key_manager

# Create API key with scopes
api_key, raw_key = await api_key_manager.create_api_key(
    db=db_session,
    user_id=user.id,
    name="Analytics API Key",
    scopes=["read:analytics", "read:reports"],
    expires_in_days=90
)

# raw_key is only available now, store it securely
print(f"API Key: {raw_key}")
```

### Validate API Key

```python
# In your dependency
async def get_api_key_user(
    api_key: str = Header(..., alias="X-API-Key")
) -> User:
    key_info = await api_key_manager.validate_api_key(
        db=db_session,
        api_key=api_key,
        required_scope="read:reports"
    )
    
    if not key_info:
        raise HTTPException(401, "Invalid API key")
    
    return key_info.user
```

## Common Decorators

### Permission Required Decorator

```python
from core.security.decorators import permission_required

@router.post("/reports/export")
@permission_required(FeatureType.EXPORTS, "export_data")
async def export_report(
    request: ExportRequest,
    user: User = Depends(get_current_user)
):
    # Permission already checked by decorator
    return create_export(request)
```

### Rate Limited Decorator

```python
from core.security.decorators import rate_limited

@router.get("/api/v1/expensive-operation")
@rate_limited(requests_per_minute=10, cost=5.0)
async def expensive_operation(
    user: User = Depends(get_current_user)
):
    # Rate limiting already applied
    return perform_expensive_operation()
```

### Audit Logged Decorator

```python
from core.security.decorators import audit_logged

@router.delete("/users/{user_id}")
@audit_logged(action=AuditAction.USER_DELETED, severity=AuditSeverity.WARNING)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    # Deletion will be automatically logged
    return delete_user_by_id(user_id)
```

## Testing Permissions

### Unit Test Example

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_report_permission():
    mock_db = AsyncMock()
    user = User(id=uuid.uuid4(), role=UserRole.MANAGER)
    
    permission = FeaturePermission(
        feature_type=FeatureType.REPORTS,
        user_id=user.id,
        allowed_actions=["view_report"],
        can_access_financial_data=True
    )
    
    with patch.object(
        feature_permission_service,
        '_get_user_feature_permissions',
        return_value=[permission]
    ):
        allowed, reason = await feature_permission_service.check_feature_permission(
            db=mock_db,
            user=user,
            feature_type=FeatureType.REPORTS,
            action="view_report"
        )
        
        assert allowed is True
        assert reason is None
```

### Integration Test Example

```python
@pytest.mark.asyncio
async def test_export_with_rate_limit(client, test_user):
    # Make requests up to rate limit
    for i in range(5):
        response = await client.post(
            "/api/v1/export",
            headers={"Authorization": f"Bearer {test_user.token}"},
            json={"format": "csv", "type": "users"}
        )
        assert response.status_code == 200
    
    # Next request should be rate limited
    response = await client.post(
        "/api/v1/export",
        headers={"Authorization": f"Bearer {test_user.token}"},
        json={"format": "csv", "type": "users"}
    )
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()
```

## Troubleshooting

### Debug Permission Denials

```python
# Enable debug logging
import logging
logging.getLogger("core.security").setLevel(logging.DEBUG)

# Get detailed permission info
from core.security.feature_permissions.service import feature_permission_service

# This will log detailed information about the permission check
allowed, reason = await feature_permission_service.check_feature_permission(
    db=db_session,
    user=current_user,
    feature_type=FeatureType.REPORTS,
    action="view_report",
    debug=True  # Enable debug mode
)

# Check the logs for:
# - Which permissions were found
# - How they were evaluated
# - Why access was denied
```

### Common Issues

1. **"No permissions configured"**
   - User has no permissions for this feature
   - Check if permissions were created properly

2. **"Access denied outside allowed hours"**
   - Permission has time restrictions
   - Check timezone settings

3. **"Rate limit exceeded"**
   - Too many requests in time window
   - Check rate limit configuration

4. **"MFA required"**
   - Permission requires multi-factor auth
   - Ensure user has MFA enabled

5. **"Invalid API key"**
   - Key might be expired or revoked
   - Check key status in database

## Performance Tips

1. **Cache Permission Results**
   ```python
   # Permissions are automatically cached for 5 minutes
   # To bypass cache (not recommended):
   allowed, reason = await feature_permission_service.check_feature_permission(
       db=db_session,
       user=current_user,
       feature_type=FeatureType.REPORTS,
       action="view_report",
       bypass_cache=True
   )
   ```

2. **Batch Permission Checks**
   ```python
   # Instead of multiple individual checks
   permissions_to_check = [
       (FeatureType.REPORTS, ["view_report", "export_report"]),
       (FeatureType.ANALYTICS, ["view_analytics"])
   ]
   
   results = await feature_permission_service.batch_check_permissions(
       db=db_session,
       user=current_user,
       permission_checks=permissions_to_check
   )
   ```

3. **Warm Cache for Active Users**
   ```python
   # Pre-load permissions for active users
   await feature_permission_service.warm_permission_cache(
       db=db_session,
       user=active_user,
       feature_types=[FeatureType.REPORTS, FeatureType.ANALYTICS]
   )
   ```

## Security Best Practices

1. **Always Check Permissions**
   - Never assume a user has permission
   - Check at the API layer, not just UI

2. **Use Principle of Least Privilege**
   - Grant minimum required permissions
   - Use time-based restrictions when possible

3. **Log Everything**
   - All permission checks are logged
   - All denials trigger audit events

4. **Fail Secure**
   - Default to deny when uncertain
   - Handle errors gracefully

5. **Regular Reviews**
   - Audit permissions quarterly
   - Remove unused permissions
   - Check for privilege creep