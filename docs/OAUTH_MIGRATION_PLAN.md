# OAuth2.0 Migration Plan for AgencyDark

## Executive Summary
Complete replacement of the current JWT-based authentication system with a comprehensive OAuth2.0 implementation using Authlib, following the OAUTH_IMPLEMENTATION_GUIDE.md specifications.

## Current State Analysis

### Existing Authentication System
- **Location**: `backend/core/security_v2/`
- **Technology**: Custom JWT implementation using python-jose
- **Components**:
  - JWT token generation and validation
  - Refresh token mechanism
  - Role-based access control (RBAC)
  - CurrentUser dependency injection
  - Session management (basic)

### Files to be Replaced/Modified
```
backend/core/security_v2/
├── authentication/
│   ├── jwt_handler.py (REPLACE)
│   └── __init__.py (MODIFY)
├── authorization/
│   ├── decorators.py (MODIFY)
│   └── __init__.py (KEEP)
├── middleware.py (REPLACE)
└── config.py (MODIFY)

backend/core/
├── dependencies.py (REPLACE CurrentUser)
└── middleware/auth.py (REPLACE)

backend/api/v1/endpoints/
└── auth.py (COMPLETELY REWRITE)
```

## Migration Phases

### Phase 1: Foundation (Week 1)
**Goal**: Set up OAuth2.0 infrastructure without breaking existing auth

#### Day 1-2: Dependencies & Database
```bash
# Install new dependencies
pip install authlib[crypto]
pip install geoip2
pip install aiosmtplib
```

**Database Migration**:
```sql
-- Create OAuth tables
CREATE TABLE oauth_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID REFERENCES agencies(id) NOT NULL,
    client_id VARCHAR(48) UNIQUE NOT NULL,
    client_secret VARCHAR(120),
    client_name VARCHAR(100),
    redirect_uris TEXT[],
    grant_types TEXT[] DEFAULT ARRAY['authorization_code'],
    response_types TEXT[] DEFAULT ARRAY['code'],
    scope TEXT DEFAULT '',
    allowed_agencies UUID[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE TABLE oauth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID REFERENCES agencies(id) NOT NULL,
    user_id UUID REFERENCES users(id),
    client_id VARCHAR(48) REFERENCES oauth_clients(client_id),
    token_type VARCHAR(40),
    access_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    scope TEXT DEFAULT '',
    expires_at TIMESTAMP,
    extra_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE oauth_authorization_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID REFERENCES agencies(id) NOT NULL,
    user_id UUID REFERENCES users(id),
    client_id VARCHAR(48) REFERENCES oauth_clients(client_id),
    code VARCHAR(120) UNIQUE NOT NULL,
    redirect_uri TEXT,
    scope TEXT DEFAULT '',
    code_challenge VARCHAR(128),
    code_challenge_method VARCHAR(10),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Add OAuth fields to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS age_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_id VARCHAR(255);
```

#### Day 3-4: Core OAuth Implementation

**New Files Structure**:
```
backend/oauth/
├── __init__.py
├── models.py          # OAuth database models
├── provider.py        # OAuth2 server implementation
├── consumer.py        # External OAuth clients
├── grants.py          # Custom grant types
└── validators.py      # Token validators

backend/services/
└── session_manager.py # Redis session management

backend/middleware/
└── adult_security.py  # Adult content compliance
```

**Implementation Order**:
1. Create OAuth models (`backend/oauth/models.py`)
2. Implement OAuth provider (`backend/oauth/provider.py`)
3. Set up Redis session manager (`backend/services/session_manager.py`)
4. Create OAuth consumer for external APIs (`backend/oauth/consumer.py`)

#### Day 5: Parallel Authentication
- Keep existing JWT auth working
- Add OAuth endpoints at `/api/oauth/*`
- Create compatibility layer for CurrentUser

### Phase 2: OAuth Provider Implementation (Week 2)
**Goal**: Fully functional OAuth2.0 server with multi-tenant support

#### Day 6-7: Authorization Server
```python
# backend/oauth/provider.py
from authlib.integrations.fastapi_oauth2 import AuthorizationServer
from authlib.oauth2.rfc6749 import grants
from authlib.oauth2.rfc7636 import CodeChallenge

class MultiTenantAuthorizationServer:
    def __init__(self, app, db_session):
        self.server = AuthorizationServer(app)
        self.setup_grants()
    
    def setup_grants(self):
        # Authorization Code with PKCE (mandatory)
        self.server.register_grant(
            MultiTenantAuthorizationCodeGrant,
            [CodeChallenge(required=True)]
        )
        # Refresh Token Grant
        self.server.register_grant(RefreshTokenGrant)
        # Client Credentials for M2M
        self.server.register_grant(ClientCredentialsGrant)
```

#### Day 8-9: OAuth Endpoints
```python
# backend/api/v1/oauth.py
@router.get("/authorize")  # User authorization
@router.post("/token")      # Token exchange
@router.post("/introspect") # Token validation
@router.post("/revoke")     # Token revocation
@router.get("/.well-known/openid-configuration")  # Discovery
```

#### Day 10: Multi-Tenant Support
- Agency isolation in all OAuth operations
- Subdomain-based tenant resolution
- Cross-agency authorization rules

### Phase 3: External OAuth Integration (Week 3)
**Goal**: Connect to Instagram, OnlyFans (when available)

#### Day 11-12: OAuth Consumer
```python
# backend/oauth/consumer.py
class ExternalOAuthManager:
    def configure_instagram(self, agency):
        """Per-agency Instagram OAuth"""
        
    def configure_onlyfans(self, agency):
        """Per-agency OnlyFans OAuth"""
```

#### Day 13-14: Secure Token Storage
- Encrypt external tokens before storage
- Implement token refresh automation
- Handle webhook callbacks

### Phase 4: Security & Compliance (Week 4)
**Goal**: Adult content compliance and security hardening

#### Day 15-16: Adult Content Middleware
```python
# backend/middleware/adult_security.py
class AdultContentSecurityMiddleware:
    - Geo-blocking (restricted countries)
    - Age verification integration
    - Security headers
    - Rate limiting per tenant
```

#### Day 17-18: Age Verification
- Integrate with Yoti/VerifyMyAge
- Store verification status
- Enforce on content endpoints

### Phase 5: Migration & Testing (Week 5)
**Goal**: Migrate existing users and test thoroughly

#### Day 19-20: User Migration Script
```python
# backend/scripts/migrate_to_oauth.py
async def migrate_users():
    """
    1. Create OAuth client for each agency
    2. Convert existing sessions to OAuth tokens
    3. Preserve user permissions and roles
    """
```

#### Day 21-22: Testing
- Unit tests for OAuth flows
- Integration tests for multi-tenancy
- Security penetration testing
- Load testing with multiple agencies

### Phase 6: Cutover & Cleanup (Week 6)
**Goal**: Switch to OAuth and remove old code

#### Day 23: Gradual Rollout
```python
# Feature flag approach
if settings.USE_OAUTH:
    return oauth_authenticate()
else:
    return jwt_authenticate()
```

#### Day 24-25: Complete Migration
1. Update all endpoints to use OAuth
2. Remove old JWT code
3. Clean up database

#### Day 26: Monitoring
- Set up OAuth metrics
- Monitor token usage
- Track authentication failures

## Implementation Checklist

### Week 1: Foundation
- [ ] Install Authlib and dependencies
- [ ] Create OAuth database tables
- [ ] Implement OAuth models
- [ ] Set up Redis session manager
- [ ] Create parallel auth structure

### Week 2: OAuth Provider
- [ ] Implement authorization server
- [ ] Add all OAuth endpoints
- [ ] Implement PKCE support
- [ ] Add multi-tenant isolation
- [ ] Create consent screens

### Week 3: External OAuth
- [ ] Instagram OAuth integration
- [ ] Token encryption/decryption
- [ ] Webhook handlers
- [ ] Token refresh automation
- [ ] External API testing

### Week 4: Security
- [ ] Geo-blocking middleware
- [ ] Age verification integration
- [ ] Security headers
- [ ] Rate limiting
- [ ] Audit logging

### Week 5: Migration
- [ ] User migration script
- [ ] Session conversion
- [ ] Testing suite
- [ ] Performance testing
- [ ] Security audit

### Week 6: Deployment
- [ ] Feature flag testing
- [ ] Gradual rollout
- [ ] Remove old code
- [ ] Documentation update
- [ ] Monitoring setup

## Risk Mitigation

### High-Risk Areas
1. **User Session Disruption**
   - Solution: Parallel authentication during migration
   - Fallback: Keep JWT auth as backup

2. **Multi-Tenant Data Leakage**
   - Solution: Strict agency_id validation
   - Testing: Automated tenant isolation tests

3. **External API Integration**
   - Solution: Robust error handling
   - Fallback: Queue failed operations

4. **Performance Impact**
   - Solution: Redis caching, connection pooling
   - Monitoring: Real-time performance metrics

## Success Metrics

### Technical Metrics
- [ ] 100% of users migrated to OAuth
- [ ] < 50ms token validation time
- [ ] Zero authentication-related downtime
- [ ] 100% test coverage for OAuth flows

### Business Metrics
- [ ] No increase in user complaints
- [ ] Improved security audit score
- [ ] Successful external API integrations
- [ ] Compliance with adult content regulations

## Rollback Plan

### Immediate Rollback (< 1 hour)
```python
# Environment variable switch
AUTHENTICATION_MODE=jwt  # Switch back to JWT
```

### Database Rollback
```sql
-- Keep OAuth tables but disable
UPDATE users SET oauth_provider = NULL;
-- Re-enable JWT sessions
```

## Post-Migration Tasks

### Documentation
- [ ] Update API documentation
- [ ] Create OAuth client guide
- [ ] Update security policies
- [ ] Training for support team

### Optimization
- [ ] Token cleanup job
- [ ] Performance tuning
- [ ] Cache optimization
- [ ] Database indexing

## Dependencies

### Technical Dependencies
- PostgreSQL 13+
- Redis 6+
- Python 3.11+
- Authlib 1.2+

### External Services
- Age verification provider (Yoti/VerifyMyAge)
- GeoIP database (MaxMind)
- Email service (for notifications)

## Team Responsibilities

### Backend Team
- OAuth implementation
- Database migrations
- API modifications

### DevOps Team
- Infrastructure setup
- Redis deployment
- Monitoring setup

### Security Team
- Security audit
- Penetration testing
- Compliance verification

### QA Team
- Test plan execution
- Integration testing
- Performance testing

## Timeline Summary

| Week | Phase | Deliverables |
|------|-------|-------------|
| 1 | Foundation | OAuth infrastructure, parallel auth |
| 2 | Provider | Working OAuth2.0 server |
| 3 | Consumer | External API integrations |
| 4 | Security | Compliance and hardening |
| 5 | Migration | User migration, testing |
| 6 | Deployment | Production rollout |

## Conclusion

This migration plan provides a structured approach to replacing the current JWT authentication with a comprehensive OAuth2.0 implementation. The parallel authentication approach ensures zero downtime, while the phased migration reduces risk. The new system will provide:

1. **Industry-standard OAuth2.0** compliance
2. **Multi-tenant isolation** for agencies
3. **External API integration** capabilities
4. **Adult content compliance** features
5. **Enhanced security** with PKCE and token introspection

Total estimated time: 6 weeks with a 2-developer team.