
# Authentication Guide

## Overview

The Agency API uses JWT (JSON Web Tokens) for authentication. This guide covers all authentication methods and best practices.

## Authentication Methods

### 1. Email/Password Authentication

The standard authentication flow:

```python
import requests

# Login
response = requests.post(
    "https://api.agency.com/api/v1/auth/login",
    json={"email": "user@example.com", "password": "secure-password"}
)
token = response.json()["access_token"]

# Use token in requests
headers = {"Authorization": f"Bearer {token}"}
user = requests.get(
    "https://api.agency.com/api/v1/users/me",
    headers=headers
).json()
```

### 2. API Key Authentication

For server-to-server communication:

```python
headers = {"X-API-Key": "your-api-key"}
response = requests.get(
    "https://api.agency.com/api/v1/analytics",
    headers=headers
)
```

### 3. OAuth 2.0

We support OAuth 2.0 for third-party integrations:

#### Authorization Code Flow

1. Redirect user to authorization URL:
```
https://api.agency.com/oauth/authorize?
  response_type=code&
  client_id=YOUR_CLIENT_ID&
  redirect_uri=YOUR_REDIRECT_URI&
  scope=read write&
  state=RANDOM_STATE
```

2. Exchange code for token:
```python
response = requests.post(
    "https://api.agency.com/oauth/token",
    data={
        "grant_type": "authorization_code",
        "code": "AUTH_CODE",
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "redirect_uri": "YOUR_REDIRECT_URI"
    }
)
```

### 4. Service Accounts

For automated systems and CI/CD:

```python
# Create service account token
response = requests.post(
    "https://api.agency.com/api/v1/auth/service-account",
    json={
        "service_account_id": "sa_123",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----..."
    }
)
```

## Token Management

### Token Expiration

- Access tokens expire after 1 hour
- Refresh tokens expire after 30 days
- Service account tokens expire after 90 days

### Refreshing Tokens

```python
response = requests.post(
    "https://api.agency.com/api/v1/auth/refresh",
    json={"refresh_token": "your-refresh-token"}
)
new_token = response.json()["access_token"]
```

### Token Revocation

```python
requests.post(
    "https://api.agency.com/api/v1/auth/revoke",
    json={"token": "token-to-revoke"},
    headers={"Authorization": f"Bearer {admin_token}"}
)
```

## Security Best Practices

### 1. Token Storage

- **Never** store tokens in source code
- Use environment variables or secure vaults
- Implement token encryption at rest

### 2. Token Transmission

- Always use HTTPS
- Include tokens in Authorization header, not URL
- Implement request signing for sensitive operations

### 3. Token Rotation

- Rotate API keys regularly
- Implement automatic token refresh
- Monitor token usage for anomalies

### 4. Scope Management

Request minimal scopes:

```python
# Good - specific scopes
scopes = ["users:read", "content:write"]

# Bad - overly broad
scopes = ["admin"]
```

## Multi-Factor Authentication (MFA)

### Enabling MFA

```python
# Enable TOTP
response = requests.post(
    "https://api.agency.com/api/v1/auth/mfa/enable",
    json={"type": "totp"},
    headers=headers
)
qr_code = response.json()["qr_code"]
```

### Authentication with MFA

```python
# Login with MFA
response = requests.post(
    "https://api.agency.com/api/v1/auth/login",
    json={
        "email": "user@example.com",
        "password": "password",
        "mfa_code": "123456"
    }
)
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check token expiration
   - Verify token format
   - Ensure correct Authorization header

2. **403 Forbidden**
   - Check token scopes
   - Verify resource permissions
   - Check rate limits

3. **Invalid Token**
   - Token may be corrupted
   - Check for extra whitespace
   - Verify token hasn't been revoked

### Debug Headers

Include debug headers for detailed error info:

```python
headers = {
    "Authorization": f"Bearer {token}",
    "X-Debug-Mode": "true"
}
```

## Code Examples

### Python SDK
```python
from agency_sdk import Client

client = Client(api_key="your-api-key")
user = client.users.get_current()
```

### Node.js SDK
```javascript
const { AgencyClient } = require('@agency/sdk');

const client = new AgencyClient({
  apiKey: 'your-api-key'
});

const user = await client.users.getCurrent();
```

### Go SDK
```go
import "github.com/agency/agency-go"

client := agency.NewClient("your-api-key")
user, err := client.Users.GetCurrent()
```

## Additional Resources

- [OAuth 2.0 Specification](https://oauth.net/2/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [API Security Checklist](https://github.com/shieldfy/API-Security-Checklist)
