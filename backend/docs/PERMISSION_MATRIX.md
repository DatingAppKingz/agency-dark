# Permission Matrix Documentation

## Overview

This document provides a comprehensive matrix of all permissions in the Agency Dark platform, organized by user role and feature type. It serves as the authoritative reference for access control decisions.

## User Roles

| Role | Level | Description | Base Permissions |
|------|-------|-------------|------------------|
| **ADMIN** | 5 | System administrators | Full system access |
| **MANAGER** | 4 | Agency managers | Agency-wide data access |
| **CHATTER** | 3 | Content creators | Own content + limited analytics |
| **MODEL** | 2 | Performers | Own profile + basic features |
| **FAN** | 1 | Subscribers | View content only |
| **USER** | 0 | Basic users | Minimal access |

## Feature Permissions Matrix

### Reports Feature

| Permission | ADMIN | MANAGER | CHATTER | MODEL | FAN | USER |
|------------|-------|---------|---------|--------|-----|------|
| **View Reports** |
| - Own Reports | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| - Team Reports | ✅ | ✅ | ✅* | ❌ | ❌ | ❌ |
| - Agency Reports | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| - Global Reports | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Financial Data** |
| - View Revenue | ✅ | ✅ | ✅** | ✅** | ❌ | ❌ |
| - View Costs | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| - View Profit Margins | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **PII Access** |
| - View PII Data | ✅ | ✅*** | ❌ | ❌ | ❌ | ❌ |
| - Export PII Data | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ |

*Team leaders only  
**Own revenue only  
***With audit logging  
⚠️ Requires approval  

### Exports Feature

| Permission | ADMIN | MANAGER | CHATTER | MODEL | FAN | USER |
|------------|-------|---------|---------|--------|-----|------|
| **Export Formats** |
| - CSV | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| - Excel | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| - PDF | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| - JSON | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Export Limits** |
| - Max Rows | Unlimited | 100,000 | 10,000 | 1,000 | N/A | N/A |
| - Rate Limit/Hour | 100 | 50 | 10 | 5 | 0 | 0 |
| - Daily Quota (rows) | Unlimited | 1M | 100K | 10K | 0 | 0 |
| **Data Sensitivity** |
| - Public Data | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| - Internal Data | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| - Confidential | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| - Restricted | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Analytics Feature

| Permission | ADMIN | MANAGER | CHATTER | MODEL | FAN | USER |
|------------|-------|---------|---------|--------|-----|------|
| **Analytics Scope** |
| - Own Analytics | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| - Team Analytics | ✅ | ✅ | ✅* | ❌ | ❌ | ❌ |
| - Agency Analytics | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| - Global Analytics | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Metric Types** |
| - Basic Metrics | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| - Advanced Metrics | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| - Financial Metrics | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ |
| - Predictive Analytics | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Time Ranges** |
| - Real-time | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| - Last 30 days | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| - Last 90 days | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| - Historical (>90d) | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ |

*Team leaders only  
⚠️ Requires special permission  

### Messaging Feature

| Permission | ADMIN | MANAGER | CHATTER | MODEL | FAN | USER |
|------------|-------|---------|---------|--------|-----|------|
| **Message Types** |
| - Direct Messages | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| - Broadcast Messages | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| - Marketing Campaigns | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ |
| - System Notifications | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Recipient Limits** |
| - Max Recipients/Message | Unlimited | 10,000 | 1,000 | 100 | 1 | 0 |
| - Daily Message Limit | Unlimited | 50,000 | 5,000 | 500 | 50 | 0 |
| **Template Access** |
| - View Templates | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| - Create Templates | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| - Approve Templates | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| - Use Unapproved | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

⚠️ Requires approval  

### API Keys Feature

| Permission | ADMIN | MANAGER | CHATTER | MODEL | FAN | USER |
|------------|-------|---------|---------|--------|-----|------|
| **API Key Management** |
| - Create API Keys | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| - Max Active Keys | Unlimited | 10 | 5 | 3 | 0 | 0 |
| - Key Rotation | ✅ | ✅ | ✅ | ✅ | N/A | N/A |
| **API Scopes** |
| - read:own_data | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| - write:own_data | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| - read:team_data | ✅ | ✅ | ✅* | ❌ | ❌ | ❌ |
| - write:team_data | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| - read:agency_data | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| - write:agency_data | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| - admin:* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

*Team leaders only

### Admin Feature

| Permission | ADMIN | MANAGER | CHATTER | MODEL | FAN | USER |
|------------|-------|---------|---------|--------|-----|------|
| **User Management** |
| - View Users | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ |
| - Create Users | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| - Modify Users | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ |
| - Delete Users | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Role Management** |
| - Assign Roles | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ |
| - Create Custom Roles | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **System Configuration** |
| - View Settings | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| - Modify Settings | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| - View Audit Logs | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ |

⚠️ Limited scope  

## Special Conditions and Restrictions

### Time-Based Access

Certain permissions can be configured with time-based restrictions:

| Feature | Time Restrictions Available |
|---------|---------------------------|
| Reports | Business hours only (9 AM - 6 PM) |
| Exports | Batch exports after hours only |
| Analytics | Real-time during business hours |
| Admin | 24/7 for ADMIN, business hours for others |

### Geographic Restrictions

Access can be limited based on geographic location:

| Feature | Geographic Restrictions |
|---------|------------------------|
| Exports | Block certain countries |
| API Keys | IP whitelist/blacklist |
| Admin | Require VPN for admin features |

### MFA Requirements

Multi-factor authentication requirements by feature and data sensitivity:

| Data Sensitivity | MFA Required |
|-----------------|--------------|
| Public | No |
| Internal | No |
| Confidential | Yes (for non-ADMIN) |
| Restricted | Yes (always) |

### Approval Workflows

Certain high-risk operations require approval:

| Operation | Approver Required | Approval Timeout |
|-----------|------------------|------------------|
| PII Export | ADMIN or MANAGER | 24 hours |
| Bulk User Modification | ADMIN | 48 hours |
| Financial Report Export | MANAGER or higher | 24 hours |
| Marketing Campaign >1000 recipients | MANAGER | 12 hours |

## Rate Limiting by Role

Default rate limits applied by user role:

| Role | Requests/Minute | Burst Size | Cost Units/Hour |
|------|----------------|------------|-----------------|
| ADMIN | 1000 | 200 | Unlimited |
| MANAGER | 500 | 100 | 10,000 |
| CHATTER | 200 | 50 | 5,000 |
| MODEL | 100 | 20 | 2,000 |
| FAN | 60 | 10 | 1,000 |
| USER | 30 | 5 | 500 |

## Audit Requirements

All permission checks are logged with the following information:

| Field | Description | Retention |
|-------|-------------|-----------|
| User ID | User making the request | 7 years |
| Action | Permission checked | 7 years |
| Result | Allowed/Denied | 7 years |
| Reason | If denied, why | 7 years |
| Context | Request metadata | 3 years |
| IP Address | Source IP | 1 year |
| Timestamp | When checked | 7 years |

## Permission Inheritance

Permissions follow this inheritance model:

1. **User-specific permissions** (highest priority)
2. **Role-based permissions**
3. **Agency default permissions**
4. **System default permissions** (lowest priority)

When multiple permissions apply, the system uses:
- **Most permissive** for allowed actions
- **Most restrictive** for denied actions
- **Explicit deny** always overrides allow

## API Scopes Reference

Detailed API scopes and their permissions:

| Scope | Description | Allowed Operations |
|-------|-------------|-------------------|
| `read:own_data` | Read user's own data | GET /api/v1/me/* |
| `write:own_data` | Modify user's own data | PUT/POST /api/v1/me/* |
| `read:reports` | Read reports | GET /api/v1/reports/* |
| `write:reports` | Create/modify reports | POST/PUT /api/v1/reports/* |
| `read:analytics` | Read analytics | GET /api/v1/analytics/* |
| `export:data` | Export data | POST /api/v1/export/* |
| `send:messages` | Send messages | POST /api/v1/messages/* |
| `admin:users` | Manage users | ALL /api/v1/admin/users/* |
| `admin:system` | System administration | ALL /api/v1/admin/* |

## Compliance Considerations

### GDPR Compliance

- Users with PII access must have legitimate purpose
- All PII access is logged
- Right to erasure must be enforced
- Data minimization principle applied to exports

### SOX Compliance

- Financial data access requires approval workflow
- All financial reports are audit logged
- Separation of duties enforced
- Change management for permission modifications

### HIPAA Compliance (if applicable)

- PHI access restricted to authorized personnel
- Minimum necessary standard applied
- Access logs retained for 6 years
- Encryption required for PHI exports

## Permission Configuration Examples

### Example 1: Marketing Team Member

```json
{
  "role": "CHATTER",
  "custom_permissions": {
    "messaging": {
      "allowed_message_types": ["marketing", "broadcast"],
      "max_recipients": 5000,
      "template_access": "approved_only",
      "daily_limit": 10000
    },
    "analytics": {
      "scope": "team",
      "can_view_revenue": true,
      "time_range_limit_days": 90
    },
    "exports": {
      "allowed_formats": ["csv", "excel"],
      "max_rows": 50000,
      "rate_limit_per_hour": 20
    }
  },
  "restrictions": {
    "access_hours": "09:00-18:00",
    "access_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "requires_mfa": true,
    "ip_whitelist": ["office_network"]
  }
}
```

### Example 2: External API Integration

```json
{
  "api_key_permissions": {
    "scopes": [
      "read:reports",
      "read:analytics",
      "export:data"
    ],
    "rate_limit": {
      "requests_per_minute": 100,
      "cost_per_hour": 5000
    },
    "restrictions": {
      "ip_whitelist": ["1.2.3.4", "5.6.7.8"],
      "allowed_endpoints": [
        "/api/v1/reports/daily",
        "/api/v1/analytics/summary",
        "/api/v1/export/users"
      ],
      "data_sensitivity_max": "internal"
    }
  }
}
```

## Security Best Practices

1. **Principle of Least Privilege**: Grant minimum permissions required
2. **Regular Audits**: Review permissions quarterly
3. **Time-bound Access**: Set expiration for temporary permissions
4. **Segregation of Duties**: Separate conflicting responsibilities
5. **Defense in Depth**: Layer multiple permission checks
6. **Fail Secure**: Deny by default when in doubt
7. **Monitoring**: Alert on unusual permission patterns

## Troubleshooting Common Issues

| Issue | Possible Cause | Solution |
|-------|---------------|----------|
| "Permission Denied" | Missing required permission | Check permission matrix |
| "Rate Limit Exceeded" | Too many requests | Wait or request limit increase |
| "MFA Required" | Accessing sensitive data | Enable MFA on account |
| "Geographic Restriction" | Access from blocked location | Use VPN or request exception |
| "Time Restriction" | Outside allowed hours | Access during permitted time |

## Version History

- **v1.0** (2024-01-01): Initial permission matrix
- **v1.1** (2024-01-15): Added messaging permissions
- **v1.2** (2024-02-01): Enhanced rate limiting
- **v1.3** (2024-02-15): Added compliance requirements
- **v1.4** (Current): Integration with audit system