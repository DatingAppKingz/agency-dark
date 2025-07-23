# AgencyDark Security Documentation

## Overview

AgencyDark implements multiple layers of security to protect user data and ensure safe operations. This document outlines the security measures implemented in the system.

## Table of Contents

1. [Authentication & Authorization](#authentication--authorization)
2. [Data Protection](#data-protection)
3. [API Security](#api-security)
4. [Input Validation](#input-validation)
5. [Audit Logging](#audit-logging)
6. [Security Headers](#security-headers)
7. [Best Practices](#best-practices)

## Authentication & Authorization

### JWT Token System
- **Access Tokens**: Short-lived (30 minutes) for API access
- **Refresh Tokens**: Long-lived (7 days) for token renewal
- **Token Storage**: Tokens should be stored securely on the client side
- **Token Rotation**: Refresh tokens are rotated on each use

### Role-Based Access Control (RBAC)
The system implements 6 distinct roles with hierarchical permissions:

1. **SUPER_ADMIN**: Full system access
2. **AGENCY_OWNER**: Full agency management
3. **AGENCY_ADMIN**: Agency operations management
4. **MODEL**: Model account management
5. **CHATTER**: Fan communication access
6. **VIEWER**: Read-only access

### Password Security
- Minimum 8 characters
- Must contain uppercase, lowercase, and numbers
- Passwords are hashed using bcrypt with salt rounds
- Password reset tokens expire after 24 hours

## Data Protection

### Encryption at Rest
Sensitive data is encrypted using AES-256-GCM:
- API credentials
- Banking information
- Personal identification data
- Cryptocurrency wallet addresses

### Encryption in Transit
- All API communications use HTTPS/TLS 1.3
- WebSocket connections use WSS
- Certificate pinning for mobile applications (future)

### Data Masking
Sensitive information is masked in logs and UI:
- Email: `jo**@example.com`
- Phone: `+1 ****1234`
- API Keys: `agdk_abc...xyz`

## API Security

### Rate Limiting
Default limits per endpoint:
- Authentication: 5 requests/minute
- API calls: 100 requests/minute
- Webhooks: 1000 requests/hour

### API Key Management
- Keys are hashed using SHA-512
- Automatic rotation every 365 days
- IP whitelisting support
- Scope-based permissions

### Security Middleware
1. **SQL Injection Protection**: Pattern matching and parameterized queries
2. **XSS Prevention**: Input sanitization and CSP headers
3. **CSRF Protection**: Token validation for state-changing operations

## Input Validation

### Field Validation
- Email: RFC-compliant validation
- Phone: E.164 format
- URLs: Protocol and format verification
- File uploads: Type and size restrictions

### Content Sanitization
- HTML content cleaned using bleach
- Allowed tags: `p`, `br`, `strong`, `em`, `a`
- Script tags and event handlers removed

## Audit Logging

### Logged Events
- Authentication attempts (success/failure)
- Permission denials
- Data access and modifications
- Financial transactions
- API key usage
- Configuration changes

### Log Retention
- Security events: 2 years
- Access logs: 1 year
- Debug logs: 30 days

### Log Security
- Logs are encrypted at rest
- PII is masked in logs
- Separate storage from application data

## Security Headers

### HTTP Security Headers
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
```

### Content Security Policy (CSP)
```
default-src 'self';
script-src 'self' 'unsafe-inline' 'unsafe-eval';
style-src 'self' 'unsafe-inline';
img-src 'self' data: https:;
connect-src 'self' wss: https://api.inflow.com https://onlyfansapi.com;
frame-ancestors 'none';
```

## Best Practices

### Development
1. Never commit secrets to version control
2. Use environment variables for configuration
3. Rotate credentials regularly
4. Follow the principle of least privilege

### Deployment
1. Use separate environments (dev, staging, prod)
2. Enable firewall rules
3. Regular security updates
4. Monitor for suspicious activity

### Incident Response
1. **Detection**: Automated alerts for security events
2. **Containment**: Automatic account lockout after failed attempts
3. **Investigation**: Comprehensive audit logs
4. **Recovery**: Backup and restore procedures

### Security Testing
- Unit tests for authentication and authorization
- Integration tests for API security
- Penetration testing quarterly
- Dependency vulnerability scanning

## Compliance

### GDPR Compliance
- Right to erasure (data deletion)
- Data portability
- Consent management
- Privacy by design

### Data Retention
- User data: As long as account is active
- Financial records: 7 years
- Logs: According to type (see Audit Logging)

## Security Contacts

For security concerns or vulnerability reports:
- Email: security@agencydark.com
- PGP Key: [Public key fingerprint]

## Version History

- v1.0.0 - Initial security implementation
- Last updated: 2024-01-01