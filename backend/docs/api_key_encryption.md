# API Key Encryption Service Documentation

## Overview

The API Key Encryption Service provides secure storage and management of API keys with enterprise-grade encryption, rotation capabilities, and comprehensive audit logging. This service ensures that API credentials are never stored in plain text and provides mechanisms for key lifecycle management.

## Architecture

### Components

1. **EncryptionService** - Core encryption/decryption functionality using Fernet symmetric encryption
2. **APIKeyEncryption** - Specialized service for API key management with rotation support
3. **APIKeyService** - Business logic for API key operations
4. **Middleware** - Authentication middleware for API requests

### Security Features

- **Encryption at Rest**: All API keys are encrypted using AES-256 encryption
- **Key Rotation**: Support for rotating API keys with configurable grace periods
- **IP Whitelisting**: Restrict API key usage to specific IP addresses
- **Scope-based Permissions**: Fine-grained access control with predefined scopes
- **Audit Logging**: Comprehensive logging of all API key operations
- **Automatic Expiration**: Keys can be set to expire after a specified period

## API Key Lifecycle

### 1. Creation

```python
# Create a new API key
result = await APIKeyService.create_api_key(
    db=session,
    user_id=user_id,
    agency_id=agency_id,
    name="Production API Key",
    description="Key for production data access",
    scopes=["read:analytics", "read:financial"],
    expires_in_days=90,
    ip_whitelist=["192.168.1.0/24"],
    metadata={"environment": "production"}
)

# Returns:
{
    "id": "uuid",
    "name": "Production API Key",
    "key_prefix": "ak_1234abcd...",
    "api_key": "ak_1234abcd5678efgh",  # Only shown once
    "api_secret": "sk_abcdef123456789",  # Only shown once
    "scopes": ["read:analytics", "read:financial"],
    "expires_at": "2024-12-31T23:59:59Z",
    "created_at": "2024-01-01T00:00:00Z"
}
```

### 2. Rotation

```python
# Rotate an existing API key
rotated = await APIKeyService.rotate_api_key(
    db=session,
    key_id=key_id,
    user_id=user_id,
    agency_id=agency_id,
    reason="Quarterly security rotation",
    grace_period_hours=24  # Old key remains valid for 24 hours
)
```

### 3. Revocation

```python
# Revoke an API key immediately
await APIKeyService.revoke_api_key(
    db=session,
    key_id=key_id,
    user_id=user_id,
    agency_id=agency_id,
    reason="Security incident"
)
```

### 4. Validation

```python
# Validate API credentials
api_key_record = await APIKeyService.validate_api_key(
    db=session,
    api_key=api_key,
    api_secret=api_secret,
    required_scopes=["read:analytics"],
    ip_address=client_ip
)
```

## Available Scopes

| Scope | Description |
|-------|-------------|
| `read:analytics` | Read access to analytics data |
| `write:analytics` | Write access to analytics data |
| `read:financial` | Read access to financial data |
| `write:financial` | Write access to financial data |
| `read:models` | Read access to model profiles |
| `write:models` | Write access to model profiles |
| `read:fans` | Read access to fan data |
| `write:fans` | Write access to fan data |
| `admin` | Full administrative access |

## API Endpoints

### Create API Key
```http
POST /api/v1/api-keys
Authorization: Bearer {jwt_token}

{
    "name": "My API Key",
    "description": "Key for external integration",
    "scopes": ["read:analytics", "read:financial"],
    "expires_in_days": 90,
    "ip_whitelist": ["192.168.1.1"],
    "metadata": {"purpose": "reporting"}
}
```

### List API Keys
```http
GET /api/v1/api-keys?include_revoked=false
Authorization: Bearer {jwt_token}
```

### Get API Key Details
```http
GET /api/v1/api-keys/{key_id}
Authorization: Bearer {jwt_token}
```

### Rotate API Key
```http
POST /api/v1/api-keys/{key_id}/rotate
Authorization: Bearer {jwt_token}

{
    "reason": "Scheduled rotation",
    "grace_period_hours": 24
}
```

### Revoke API Key
```http
POST /api/v1/api-keys/{key_id}/revoke
Authorization: Bearer {jwt_token}

{
    "reason": "No longer needed"
}
```

### Get Audit Logs
```http
GET /api/v1/api-keys/{key_id}/audit-logs?limit=100
Authorization: Bearer {jwt_token}
```

### Validate API Key
```http
POST /api/v1/api-keys/validate

{
    "api_key": "ak_...",
    "api_secret": "sk_...",
    "required_scopes": ["read:analytics"]
}
```

## Using API Keys

### Authentication Methods

#### 1. Authorization Header
```http
GET /api/v1/analytics/revenue
Authorization: Bearer ak_1234abcd:sk_abcdef123456
```

#### 2. Custom Headers
```http
GET /api/v1/analytics/revenue
X-API-Key: ak_1234abcd
X-API-Secret: sk_abcdef123456
```

#### 3. Query Parameters (for webhooks)
```http
GET /api/v1/webhook/callback?api_key=ak_1234abcd&api_secret=sk_abcdef123456
```

### Using in Code

```python
# Python example
import requests

headers = {
    "Authorization": f"Bearer {api_key}:{api_secret}"
}

response = requests.get(
    "https://api.agencydark.com/v1/analytics/revenue",
    headers=headers
)
```

```javascript
// JavaScript example
const response = await fetch('https://api.agencydark.com/v1/analytics/revenue', {
    headers: {
        'Authorization': `Bearer ${apiKey}:${apiSecret}`
    }
});
```

## Middleware Usage

### Protecting Endpoints with API Keys

```python
from core.middleware.api_key_auth import require_api_key

@router.get("/protected-data")
async def get_protected_data(
    api_key_info: dict = Depends(require_api_key(["read:analytics"]))
):
    # api_key_info contains:
    # - api_key_id
    # - agency_id
    # - user_id
    # - scopes
    return {"agency_id": api_key_info["agency_id"]}
```

### Allowing Either API Key or JWT

```python
from core.middleware.api_key_auth import require_api_key_or_jwt

@router.get("/data")
async def get_data(
    auth_info: dict = Depends(require_api_key_or_jwt(["read:data"]))
):
    if auth_info["auth_type"] == "api_key":
        # Handle API key authentication
        agency_id = auth_info["agency_id"]
    else:
        # Handle JWT authentication
        user_role = auth_info["user_role"]
```

## Security Best Practices

### 1. Key Storage
- Never store API keys in source code
- Use environment variables or secure key management services
- Rotate keys regularly (recommended: every 90 days)

### 2. Transmission
- Always use HTTPS when transmitting API keys
- Never log or display full API keys
- Use the key prefix for identification in logs

### 3. Access Control
- Apply principle of least privilege with scopes
- Use IP whitelisting for production keys
- Set expiration dates on all keys

### 4. Monitoring
- Review audit logs regularly
- Monitor for unusual usage patterns
- Set up alerts for failed authentication attempts

### 5. Rotation Strategy
- Implement regular rotation schedule
- Use grace periods to allow smooth transitions
- Update all systems before old key expires

## Configuration

### Environment Variables

```env
# Master encryption key (generate with Fernet.generate_key())
ENCRYPTION_KEY=your-base64-encoded-key-here
```

### Settings

```python
# Maximum API key lifetime
MAX_API_KEY_LIFETIME_DAYS = 365

# Default expiration
DEFAULT_API_KEY_EXPIRATION_DAYS = 90

# Grace period for rotations
DEFAULT_ROTATION_GRACE_PERIOD_HOURS = 24

# Rate limiting for API key usage
API_KEY_RATE_LIMIT = 1000  # requests per hour
```

## Troubleshooting

### Common Issues

1. **"Invalid API credentials"**
   - Verify the API key and secret are correct
   - Check if the key has expired
   - Ensure the key hasn't been revoked

2. **"Missing required scopes"**
   - Verify the API key has the necessary scopes
   - Check if using admin scope for full access

3. **"IP not whitelisted"**
   - Check if your IP is in the whitelist
   - Verify the IP address format

4. **"API key expired"**
   - Create a new API key
   - Implement rotation before expiration

### Debug Mode

Enable debug logging for API key operations:

```python
import logging
logging.getLogger("core.application.api_key_service").setLevel(logging.DEBUG)
```

## Migration Guide

### From Plain Text to Encrypted Keys

1. Generate encryption key:
```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())  # Save as ENCRYPTION_KEY
```

2. Run migration:
```bash
alembic upgrade head
```

3. Migrate existing keys:
```python
# Script to encrypt existing plain text keys
for key in plain_text_keys:
    encrypted = api_key_encryption.encrypt_api_key(
        api_key=key.api_key,
        api_secret=key.api_secret
    )
    # Update database with encrypted data
```

## Performance Considerations

- API key validation is cached for 5 minutes
- Use batch operations for multiple key validations
- Consider read replicas for high-volume validation
- Monitor cache hit rates for optimization