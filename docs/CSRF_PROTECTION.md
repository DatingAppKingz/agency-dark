# CSRF Protection Implementation

## Overview

Cross-Site Request Forgery (CSRF) protection has been implemented using the double-submit cookie pattern combined with custom headers for maximum security.

## How It Works

### 1. Token Generation
- When a user first visits the site or logs in, a CSRF token is generated
- The token includes:
  - Random secure string
  - Timestamp for expiration
  - HMAC signature for integrity

### 2. Token Storage
- CSRF token is stored in a cookie named `__Secure-CSRF-Token`
- Cookie settings:
  - `httpOnly: false` (must be readable by JavaScript)
  - `secure: true` (in production)
  - `sameSite: strict/lax` (based on environment)

### 3. Token Validation
- For all state-changing requests (POST, PUT, DELETE, PATCH):
  - Token must be present in the `X-CSRF-Token` header
  - Token in header must match token in cookie
  - Token signature must be valid
  - Token must not be expired (24-hour expiry)

## Backend Implementation

### Middleware
```python
# Automatically added to all routes
from core.middleware.csrf import CSRFMiddleware
app.add_middleware(CSRFMiddleware)
```

### Excluded Paths
The following paths are excluded from CSRF protection:
- `/api/v1/auth/login` - Initial login
- `/api/v1/auth/register` - Registration
- `/api/v1/external/*` - External API endpoints (use API keys)
- `/api/v1/webhooks/*` - Webhook endpoints
- Documentation endpoints

### Manual Endpoint Protection
```python
from fastapi import Depends
from core.auth.csrf import verify_csrf_token

@router.post("/sensitive-action", dependencies=[Depends(verify_csrf_token)])
async def sensitive_action():
    # This endpoint requires valid CSRF token
    pass
```

## Frontend Implementation

### Automatic Token Handling
The API client automatically includes CSRF tokens for all state-changing requests:

```typescript
// In services/api/client.ts
apiClient.interceptors.request.use(async (config) => {
  const needsCSRF = ['post', 'put', 'patch', 'delete'].includes(config.method);
  if (needsCSRF) {
    const csrfToken = await getCSRFToken();
    config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});
```

### Manual Token Management
```typescript
import { getCSRFToken, clearCSRFToken } from '@/utils/csrf';

// Get current CSRF token
const token = await getCSRFToken();

// Clear token on logout
clearCSRFToken();
```

## API Endpoints

### Get CSRF Token
```
GET /api/v1/auth/csrf-token
```
Returns a new CSRF token and sets the cookie.

### Login Response
The login endpoint now includes the CSRF token in the response:
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "csrf_token": "..."
}
```

## Testing

### Test Script
Run the CSRF protection test:
```bash
cd backend
python3 test_csrf_protection.py
```

### Manual Testing
1. Get a CSRF token:
   ```bash
   curl -X GET http://localhost:8000/api/v1/auth/csrf-token
   ```

2. Use the token in requests:
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/logout \
     -H "X-CSRF-Token: <your-token>" \
     -H "Cookie: __Secure-CSRF-Token=<your-token>"
   ```

## Security Features

1. **Token Integrity**: HMAC signature prevents tampering
2. **Token Expiry**: 24-hour expiration prevents old token reuse
3. **Double Submit**: Token must be in both cookie and header
4. **Secure Cookie**: Uses secure flag in production
5. **SameSite Protection**: Additional protection against CSRF

## Common Issues

### CSRF Token Not Found
- Ensure you're including credentials in requests: `withCredentials: true`
- Check that the CSRF cookie is being set
- Verify the token hasn't expired

### CSRF Token Mismatch
- Ensure the token in the header matches the cookie
- Check for multiple tabs/windows with different tokens
- Verify no middleware is modifying headers

### Token Expired
- Tokens expire after 24 hours
- Get a new token via `/api/v1/auth/csrf-token`
- Login automatically provides a fresh token

## Best Practices

1. **Always include CSRF tokens** for state-changing operations
2. **Don't disable CSRF protection** unless absolutely necessary
3. **Refresh tokens periodically** for long-running sessions
4. **Clear tokens on logout** to prevent reuse
5. **Use HTTPS in production** for secure cookie transmission