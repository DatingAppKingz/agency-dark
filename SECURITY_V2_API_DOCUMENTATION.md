# Security_v2 API Documentation

## Overview

The AgencyDark platform now uses the `security_v2` module for all authentication and authorization. This document describes the new API endpoints and security features.

## Authentication Endpoints

### POST /api/v1/auth/login
Login with email and password to receive JWT tokens.

**Request Body:**
```json
{
  "email": "admin@agency.com",
  "password": "admin123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "admin@agency.com",
    "role": "super_admin"
  }
}
```

### GET /api/v1/auth/me
Get current user information (requires authentication).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "id": "uuid",
  "email": "admin@agency.com",
  "role": "super_admin",
  "permissions": ["users.read", "users.write", "analytics.view"]
}
```

### POST /api/v1/auth/refresh
Refresh the access token using a refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### POST /api/v1/auth/logout
Logout and invalidate the current session.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "message": "Successfully logged out"
}
```

## RBAC (Role-Based Access Control)

### Roles

The system implements 7 distinct roles with hierarchical permissions:

1. **SUPER_ADMIN** - Complete system access
   - All permissions
   - System configuration
   - User management across all agencies

2. **AGENCY_OWNER** - Full agency control
   - Manage agency settings
   - Manage all agency users
   - View all agency data
   - Financial operations

3. **AGENCY_ADMIN** - Agency administration
   - Manage agency users (except owner)
   - Manage models and clients
   - View reports
   - Cannot access financial data

4. **AGENCY_USER** - Standard agency operations
   - Manage assigned models
   - View agency data
   - Create reports
   - Limited user management

5. **MODEL** - Model-specific access
   - View own profile
   - Update availability
   - View own bookings
   - Communicate with agency

6. **CLIENT** - Client access
   - View available models
   - Make bookings
   - View own booking history
   - Communication features

7. **VIEWER** - Read-only access
   - View public information
   - No modification permissions
   - Limited data access

### Permissions

Each role has specific permissions that control access to features:

```python
# Permission examples
PERMISSIONS = {
    "users.read": "View user information",
    "users.write": "Create/update users",
    "users.delete": "Delete users",
    "analytics.view": "View analytics dashboard",
    "analytics.export": "Export analytics data",
    "financial.view": "View financial data",
    "financial.manage": "Manage financial operations",
    "models.read": "View model profiles",
    "models.write": "Update model information",
    "bookings.create": "Create new bookings",
    "bookings.manage": "Manage all bookings",
    "reports.generate": "Generate reports",
    "settings.manage": "Manage system settings"
}
```

## Security Features

### Password Security
- **Hashing**: BCrypt with 12 rounds
- **Validation**: Minimum 8 characters, complexity requirements
- **Storage**: Only hashed passwords stored in database

### JWT Tokens
- **Algorithm**: HS256
- **Access Token**: 30 minutes expiry
- **Refresh Token**: 7 days expiry
- **Claims**: user_id, email, role, permissions

### Session Management
- Redis-backed session storage
- Automatic session cleanup
- Support for multiple sessions per user
- Session invalidation on logout

### Rate Limiting
- Configurable per-endpoint limits
- Role-based rate limits
- IP-based tracking
- Automatic cooldown periods

## Example Usage

### Login Flow
```javascript
// 1. Login
const response = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'admin@agency.com',
    password: 'admin123'
  })
});

const { access_token, refresh_token } = await response.json();

// 2. Use access token for authenticated requests
const userResponse = await fetch('http://localhost:8000/api/v1/auth/me', {
  headers: {
    'Authorization': `Bearer ${access_token}`
  }
});

const user = await userResponse.json();
```

### Frontend Integration
```typescript
// Using the authServiceV2
import { authService } from '@/services/auth';

// Login
const result = await authService.login({
  email: 'admin@agency.com',
  password: 'admin123'
});

// Check authentication
const user = await authService.checkAuth();

// Logout
await authService.logout();
```

## Configuration

### Environment Variables
```bash
# JWT Configuration
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Security Features
ENABLE_RBAC=true
ENABLE_RATE_LIMITING=true
ENABLE_SESSION_MANAGEMENT=true

# Password Policy
PASSWORD_MIN_LENGTH=8
PASSWORD_REQUIRE_UPPERCASE=true
PASSWORD_REQUIRE_LOWERCASE=true
PASSWORD_REQUIRE_NUMBERS=true
PASSWORD_REQUIRE_SPECIAL=true
PASSWORD_HASH_ROUNDS=12

# Database
DATABASE_URL=postgresql://user:pass@localhost/dbname

# Redis
REDIS_URL=redis://localhost:6379
```

### Feature Flags
```python
# Enable/disable features in SecurityConfig
ENABLE_RBAC = True
ENABLE_API_KEYS = True
ENABLE_RATE_LIMITING = True
ENABLE_AUDIT_LOGGING = True
ENABLE_SESSION_MANAGEMENT = True
```

## Migration from Old Security

If migrating from the old security system:

1. All passwords have been hashed with bcrypt
2. JWT tokens replace the old token system
3. RBAC replaces simple role checking
4. Sessions are now managed in Redis

## Testing

### Test Accounts
```
admin@agency.com / admin123 (super_admin)
```

Additional test accounts can be created through the API or database seeds.

### Health Check
```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "security": "security_v2",
  "features": {
    "rbac": true,
    "jwt": true,
    "session_management": true
  }
}
```

## Troubleshooting

### Common Issues

1. **Login fails with "Invalid credentials"**
   - Ensure password is hashed in database
   - Check email exists in users table
   - Verify bcrypt is installed

2. **Token rejected on protected endpoints**
   - Check token hasn't expired (30 min for access token)
   - Ensure Authorization header format is correct
   - Verify JWT_SECRET_KEY matches between services

3. **RBAC permissions not working**
   - Check user's role in database
   - Verify ENABLE_RBAC=true in config
   - Review permission mappings for the role

## Support

For issues or questions about the security_v2 implementation:
- Review the implementation documents in the project
- Check the test suite at `backend/test_security_v2_complete.py`
- Consult the source code in `backend/core/security_v2/`